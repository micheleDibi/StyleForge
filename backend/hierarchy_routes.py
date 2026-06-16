"""
Router FastAPI per la gestione dell'albero di distribuzione lato manager
(distributore e rivenditore): creazione di sotto-utenti e assegnazione crediti.

Le richieste crediti e gli inviti di spostamento sono aggiunti nelle fasi successive.
L'autorizzazione sul singolo target è verificata con hierarchy.can_manage.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_manager, get_current_active_user
from db_models import User, Role, CreditPackage, CreditRequest, ParentMoveInvitation
from credits import transfer_credits, is_admin_user
import hierarchy
from models import (
    HierarchyCreateUserRequest, HierarchyUserItem, HierarchyChildrenResponse,
    AssignCreditsRequest, CreditRequestCreate, CreditRequestItem,
    CreditRequestListResponse, ResolveRequestRequest,
    InvitePrivatoRequest, MoveTokenRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hierarchy", tags=["Hierarchy"])


def _to_item(u: User) -> HierarchyUserItem:
    return HierarchyUserItem(
        id=str(u.id),
        username=u.username,
        full_name=u.full_name,
        email=u.email,
        entity_type=(u.entity_type or 'privato'),
        credits=u.credits,
        parent_id=str(u.parent_id) if u.parent_id else None,
        is_active=bool(u.is_active),
        email_verified=bool(getattr(u, 'email_verified', False)),
    )


@router.get("/children", response_model=HierarchyChildrenResponse)
def my_children(
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """Figli diretti del manager corrente, con i crediti attuali."""
    items = [_to_item(c) for c in hierarchy.get_children(current_user, db)]
    return HierarchyChildrenResponse(children=items, total=len(items))


@router.get("/subtree", response_model=HierarchyChildrenResponse)
def my_subtree(
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """Intero sottoalbero del manager corrente."""
    items = [_to_item(d) for d in hierarchy.get_descendants(current_user, db)]
    return HierarchyChildrenResponse(children=items, total=len(items))


@router.post("/users", response_model=HierarchyUserItem)
def create_sub_user(
    request: HierarchyCreateUserRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """
    Crea un sotto-utente (rivenditore/privato secondo i permessi dell'attore),
    associato sotto il manager corrente, e invia l'email di invito (set_password).
    Eventuali crediti iniziali vengono TRASFERITI dal saldo del creatore.
    """
    entity_type = (request.entity_type or '').strip().lower()
    allowed = hierarchy.allowed_child_entity_types(current_user)
    if entity_type not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Non puoi creare un utente di tipo '{entity_type}'. Consentiti: {', '.join(sorted(allowed)) or 'nessuno'}.",
        )

    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail=f"Email '{request.email}' già in uso")
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=400, detail=f"Username '{request.username}' già in uso")

    # Pre-check del saldo per i crediti iniziali (evita di creare l'utente e poi fallire).
    if request.credits > 0 and current_user.credits < request.credits:
        raise HTTPException(
            status_code=402,
            detail=f"Crediti insufficienti per l'assegnazione iniziale ({current_user.credits} < {request.credits}).",
        )

    default_role = db.query(Role).filter(Role.is_default == True).first()  # noqa: E712
    new_user = User(
        email=request.email,
        username=request.username,
        hashed_password=None,
        full_name=request.full_name,
        role_id=default_role.id if default_role else None,
        is_admin=False,
        credits=0,
        is_active=True,
        email_verified=False,
        entity_type=entity_type,
        parent_id=current_user.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if request.credits > 0:
        transfer_credits(
            current_user, new_user, request.credits, db,
            description="Crediti iniziali alla creazione",
        )
        db.refresh(new_user)

    # Invito set_password (riusa il flusso esistente).
    from email_service import create_email_token, build_link, send_invite_email
    raw = create_email_token(db, new_user.id, 'set_password')
    link = build_link('set_password', raw)
    background_tasks.add_task(send_invite_email, new_user.email, new_user.full_name or new_user.username, link)

    return _to_item(new_user)


@router.post("/users/{user_id}/assign-credits", response_model=HierarchyUserItem)
def assign_credits(
    user_id: str,
    request: AssignCreditsRequest,
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """Trasferisce crediti dal manager corrente a un proprio sotto-utente."""
    try:
        target = db.query(User).filter(User.id == UUID(user_id)).first()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID utente non valido")
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if not hierarchy.can_manage(current_user, target, db):
        raise HTTPException(status_code=403, detail="Non puoi gestire questo utente")

    transfer_credits(
        current_user, target, request.amount, db,
        description=request.description or "Assegnazione crediti",
    )
    db.refresh(target)
    return _to_item(target)


# ============================================================================
# Richieste crediti (scelta pacchetto -> referente / admin)
# ============================================================================

def _req_item(cr: CreditRequest, db: Session) -> CreditRequestItem:
    requester = cr.requester or db.query(User).filter(User.id == cr.requester_id).first()
    return CreditRequestItem(
        id=str(cr.id),
        requester_id=str(cr.requester_id),
        requester_username=requester.username if requester else None,
        requester_email=requester.email if requester else None,
        requester_entity_type=(requester.entity_type if requester else None),
        approver_id=str(cr.approver_id) if cr.approver_id else None,
        approver_is_admin=bool(cr.approver_is_admin),
        package_id=cr.package_id,
        package_name=cr.package_name,
        package_credits=cr.package_credits,
        package_price_cents=cr.package_price_cents,
        package_price_eur=round(cr.package_price_cents / 100.0, 2),
        status=cr.status,
        note=cr.note,
        created_at=cr.created_at,
        resolved_at=cr.resolved_at,
    )


@router.post("/requests", response_model=CreditRequestItem)
def create_request(
    request: CreditRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Crea una richiesta di crediti scegliendo un pacchetto del proprio listino.
    Il referente è calcolato dalla posizione nell'albero (genitore o admin).
    """
    if is_admin_user(current_user):
        raise HTTPException(status_code=400, detail="Gli admin hanno crediti illimitati e non inviano richieste.")

    pkg = db.query(CreditPackage).filter(
        CreditPackage.id == request.package_id,
        CreditPackage.is_active == True,  # noqa: E712
    ).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Pacchetto non trovato o non attivo")
    requester_et = (current_user.entity_type or 'privato').strip().lower()
    if (pkg.entity_type or 'privato').strip().lower() != requester_et:
        raise HTTPException(status_code=403, detail="Questo pacchetto non è disponibile per il tuo profilo.")

    # Una sola richiesta pending alla volta.
    existing = db.query(CreditRequest).filter(
        CreditRequest.requester_id == current_user.id,
        CreditRequest.status == 'pending',
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Hai già una richiesta in attesa. Attendi la sua gestione o annullala.")

    approver, approver_is_admin = hierarchy.compute_approver(current_user, db)
    cr = CreditRequest(
        requester_id=current_user.id,
        approver_id=approver.id if approver else None,
        approver_is_admin=approver_is_admin,
        package_id=pkg.id,
        package_name=pkg.name,
        package_credits=pkg.credits,
        package_price_cents=pkg.price_cents,
        status='pending',
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return _req_item(cr, db)


@router.get("/requests/mine", response_model=CreditRequestListResponse)
def my_requests(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CreditRequest)
        .filter(CreditRequest.requester_id == current_user.id)
        .order_by(CreditRequest.created_at.desc())
        .all()
    )
    return CreditRequestListResponse(requests=[_req_item(r, db) for r in rows], total=len(rows))


@router.post("/requests/{request_id}/cancel", response_model=CreditRequestItem)
def cancel_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        cr = db.query(CreditRequest).filter(
            CreditRequest.id == UUID(request_id),
            CreditRequest.status == 'pending',
        ).with_for_update().one_or_none()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID richiesta non valido")
    if not cr:
        raise HTTPException(status_code=409, detail="Richiesta non trovata o già gestita")
    if cr.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Non puoi annullare questa richiesta")
    cr.status = 'canceled'
    cr.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(cr)
    return _req_item(cr, db)


@router.get("/requests/inbox", response_model=CreditRequestListResponse)
def requests_inbox(
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """Richieste pending indirizzate al manager corrente."""
    rows = (
        db.query(CreditRequest)
        .filter(
            CreditRequest.approver_id == current_user.id,
            CreditRequest.status == 'pending',
        )
        .order_by(CreditRequest.created_at.asc())
        .all()
    )
    return CreditRequestListResponse(requests=[_req_item(r, db) for r in rows], total=len(rows))


@router.post("/requests/{request_id}/approve", response_model=CreditRequestItem)
def approve_request(
    request_id: str,
    body: ResolveRequestRequest = ResolveRequestRequest(),
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """
    Approva una richiesta indirizzata al manager: trasferisce i crediti del
    pacchetto dal proprio saldo al richiedente. 402 se il saldo non basta
    (la richiesta resta pending). Lock di riga + guard di stato contro le race.
    """
    try:
        cr = db.query(CreditRequest).filter(
            CreditRequest.id == UUID(request_id),
            CreditRequest.status == 'pending',
        ).with_for_update().one_or_none()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID richiesta non valido")
    if not cr:
        raise HTTPException(status_code=409, detail="Richiesta non trovata o già gestita")
    if cr.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Questa richiesta non è indirizzata a te")

    requester = db.query(User).filter(User.id == cr.requester_id).first()
    if not requester:
        raise HTTPException(status_code=404, detail="Richiedente non trovato")

    # Marca approvata PRIMA del trasferimento: transfer_credits committa entrambe
    # le modifiche atomicamente (il lock sulla richiesta è tenuto fino al commit).
    cr.status = 'approved'
    cr.resolver_id = current_user.id
    cr.resolved_at = datetime.utcnow()
    cr.note = body.note
    try:
        transfer_credits(
            current_user, requester, cr.package_credits, db,
            description=f"Approvazione richiesta crediti ({cr.package_name})",
        )
    except HTTPException:
        db.rollback()
        raise
    db.refresh(cr)
    return _req_item(cr, db)


@router.post("/requests/{request_id}/reject", response_model=CreditRequestItem)
def reject_request(
    request_id: str,
    body: ResolveRequestRequest = ResolveRequestRequest(),
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    try:
        cr = db.query(CreditRequest).filter(
            CreditRequest.id == UUID(request_id),
            CreditRequest.status == 'pending',
        ).with_for_update().one_or_none()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID richiesta non valido")
    if not cr:
        raise HTTPException(status_code=409, detail="Richiesta non trovata o già gestita")
    if cr.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Questa richiesta non è indirizzata a te")
    cr.status = 'rejected'
    cr.resolver_id = current_user.id
    cr.resolved_at = datetime.utcnow()
    cr.note = body.note
    db.commit()
    db.refresh(cr)
    return _req_item(cr, db)


# ============================================================================
# Invito privato (crea-o-sposta) + accetta/rifiuta spostamento (token email)
# ============================================================================

def _unique_username(db: Session, email: str) -> str:
    base = re.sub(r'[^a-z0-9._-]', '', (email.split('@')[0] or 'utente').lower()) or 'utente'
    if len(base) < 3:
        base = (base + 'user')[:20]
    candidate = base[:40]
    i = 1
    while db.query(User).filter(User.username == candidate).first():
        i += 1
        candidate = f"{base[:36]}-{i}"
    return candidate


def _norm_expires(dt) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@router.post("/invite-privato")
def invite_privato(
    request: InvitePrivatoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_manager),
    db: Session = Depends(get_db),
):
    """
    Invita un privato via email (crea-o-sposta):
      - email senza account -> crea un nuovo privato sotto di me + invito set_password;
      - privato esistente di un altro genitore -> invito di spostamento (accetta/rifiuta);
      - già mio -> no-op; account non-privato -> errore.
    """
    email = (request.email or '').strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email obbligatoria")

    existing = db.query(User).filter(func.lower(User.email) == email.lower()).first()

    # --- Nessun account: crea un nuovo privato sotto di me ---
    if not existing:
        username = (request.username or '').strip() or _unique_username(db, email)
        if db.query(User).filter(User.username == username).first():
            username = _unique_username(db, email)
        default_role = db.query(Role).filter(Role.is_default == True).first()  # noqa: E712
        new_user = User(
            email=email,
            username=username,
            hashed_password=None,
            full_name=(request.full_name or None),
            role_id=default_role.id if default_role else None,
            is_admin=False,
            credits=0,
            is_active=True,
            email_verified=False,
            entity_type='privato',
            parent_id=current_user.id,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        from email_service import create_email_token, build_link, send_invite_email
        raw = create_email_token(db, new_user.id, 'set_password')
        link = build_link('set_password', raw)
        background_tasks.add_task(send_invite_email, new_user.email, new_user.full_name or new_user.username, link)
        return {"status": "created", "message": "Nuovo privato creato e invitato via email."}

    # --- Account esistente ---
    if (existing.entity_type or 'privato').strip().lower() != 'privato':
        raise HTTPException(status_code=400, detail="L'utente esiste ma non è un privato e non può essere spostato.")
    if existing.parent_id == current_user.id:
        return {"status": "already", "message": "Questo privato è già associato a te."}

    # Annulla eventuali inviti pendenti precedenti per lo stesso privato.
    db.query(ParentMoveInvitation).filter(
        ParentMoveInvitation.privato_id == existing.id,
        ParentMoveInvitation.status == 'pending',
    ).update({"status": "canceled", "resolved_at": datetime.utcnow()}, synchronize_session=False)

    from email_service import build_link, send_move_invite_email, hash_token
    raw = secrets.token_urlsafe(32)
    inv = ParentMoveInvitation(
        privato_id=existing.id,
        from_parent_id=existing.parent_id,
        to_parent_id=current_user.id,
        token_hash=hash_token(raw),
        status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
    )
    db.add(inv)
    db.commit()
    link = build_link('move_invite', raw)
    background_tasks.add_task(
        send_move_invite_email, existing.email, existing.full_name or existing.username,
        current_user.full_name or current_user.username, link,
    )
    return {"status": "move_invited", "message": "Invito di spostamento inviato al privato."}


@router.post("/move/accept")
def move_accept(body: MoveTokenRequest, db: Session = Depends(get_db)):
    """Il privato accetta lo spostamento (pubblico, via token email)."""
    from email_service import hash_token
    inv = (
        db.query(ParentMoveInvitation)
        .filter(ParentMoveInvitation.token_hash == hash_token(body.token), ParentMoveInvitation.status == 'pending')
        .with_for_update()
        .one_or_none()
    )
    if not inv:
        raise HTTPException(status_code=410, detail="Invito non valido o già gestito")
    if _norm_expires(inv.expires_at) < datetime.now(timezone.utc):
        inv.status = 'expired'
        inv.resolved_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=410, detail="Invito scaduto")

    privato = db.query(User).filter(User.id == inv.privato_id).first()
    to_parent = db.query(User).filter(User.id == inv.to_parent_id).first()
    if not privato or not to_parent:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if (privato.entity_type or 'privato').strip().lower() != 'privato':
        raise HTTPException(status_code=400, detail="L'account non è (più) un privato.")
    if (to_parent.entity_type or '').strip().lower() not in ('rivenditore', 'distributore'):
        raise HTTPException(status_code=400, detail="Il referente non è più valido.")
    hierarchy.assert_no_cycle(privato, to_parent, db)

    privato.parent_id = to_parent.id
    privato.distributor_id = None
    inv.status = 'accepted'
    inv.resolved_at = datetime.utcnow()
    db.commit()
    return {"message": "Spostamento completato: sei stato associato al nuovo referente."}


@router.post("/move/reject")
def move_reject(body: MoveTokenRequest, db: Session = Depends(get_db)):
    """Il privato rifiuta lo spostamento (pubblico, via token email)."""
    from email_service import hash_token
    inv = (
        db.query(ParentMoveInvitation)
        .filter(ParentMoveInvitation.token_hash == hash_token(body.token), ParentMoveInvitation.status == 'pending')
        .with_for_update()
        .one_or_none()
    )
    if not inv:
        raise HTTPException(status_code=410, detail="Invito non valido o già gestito")
    inv.status = 'rejected'
    inv.resolved_at = datetime.utcnow()
    db.commit()
    return {"message": "Invito rifiutato. Nessuna modifica effettuata."}
