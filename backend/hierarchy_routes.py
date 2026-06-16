"""
Router FastAPI per la gestione dell'albero di distribuzione lato manager
(distributore e rivenditore): creazione di sotto-utenti e assegnazione crediti.

Le richieste crediti e gli inviti di spostamento sono aggiunti nelle fasi successive.
L'autorizzazione sul singolo target è verificata con hierarchy.can_manage.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_manager
from db_models import User, Role
from credits import transfer_credits
import hierarchy
from models import (
    HierarchyCreateUserRequest, HierarchyUserItem, HierarchyChildrenResponse,
    AssignCreditsRequest,
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
