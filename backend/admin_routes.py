"""
Router per gli endpoint di amministrazione.
Solo accessibile da utenti con ruolo admin.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database import get_db
from auth import get_current_admin_user, get_effective_permissions
from db_models import (
    User, Role, RolePermission, UserPermission, CreditTransaction, SystemSetting, APIKey,
    CreditPackage, CreditRequest
)
from credits import (
    add_credits, get_user_transactions, PERMISSION_CODES,
    get_credit_costs, save_credit_costs, reset_credit_costs,
    is_credit_costs_default, DEFAULT_CREDIT_COSTS
)
from models import (
    AdminUserResponse, AdminUserListResponse,
    AdminUpdateUserRequest, AdminChangeRoleRequest,
    AdminSetPermissionsRequest, AdminAdjustCreditsRequest,
    RoleResponse, RoleListResponse, AdminUpdateRolePermissionsRequest,
    AdminStatsResponse, CreditTransactionResponse, CreditTransactionListResponse,
    AdminCreateUserRequest, CreditCostsResponse, CreditCostsUpdateRequest,
    ExportTemplateListResponse, ExportTemplateUpdateRequest,
    CreditPackageResponse, CreditPackageListResponse, AdminCreditPackageRequest,
    CreditRequestItem, CreditRequestListResponse, ResolveRequestRequest,
)
import config
from template_service import (
    get_export_templates, save_export_templates, delete_template,
    TEMPLATE_PARAM_HELP, generate_template_id
)

router = APIRouter(prefix="/admin", tags=["Administration"])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_admin_user_response(user: User, db: Session) -> AdminUserResponse:
    """Costruisce la risposta utente dettagliata per admin."""
    permissions = get_effective_permissions(user, db)

    # Ottieni override utente
    user_overrides = {}
    overrides = db.query(UserPermission).filter(UserPermission.user_id == user.id).all()
    for override in overrides:
        user_overrides[override.permission_code] = override.granted

    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        credits=user.credits,
        permissions=permissions,
        user_overrides=user_overrides,
        email_verified=bool(getattr(user, 'email_verified', False)),
        entity_type=getattr(user, 'entity_type', None) or 'privato',
        parent_id=str(user.parent_id) if getattr(user, 'parent_id', None) else None,
        distributor_id=str(user.distributor_id) if getattr(user, 'distributor_id', None) else None,
        codice_fiscale=getattr(user, 'codice_fiscale', None),
        partita_iva=getattr(user, 'partita_iva', None),
        ragione_sociale=getattr(user, 'ragione_sociale', None),
        indirizzo_fatturazione=getattr(user, 'indirizzo_fatturazione', None),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login
    )


def _set_user_parent(user: User, parent_value, db: Session) -> None:
    """
    Imposta/azzera il genitore (parent_id) di `user` con validazione di coerenza
    entity_type + protezione anti-ciclo. `parent_value`: '' azzera, UUID stringa imposta.
    Mantiene allineato il legacy distributor_id (per i rivenditori) finché esiste.
    """
    pv = (parent_value or "").strip()
    if pv == "":
        user.parent_id = None
        user.distributor_id = None
        return
    child_et = (user.entity_type or 'privato').strip().lower()
    if child_et == 'distributore':
        raise HTTPException(status_code=400, detail="Un distributore non può avere un genitore.")
    try:
        parent = db.query(User).filter(User.id == UUID(pv)).first()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="parent_id non valido")
    if not parent:
        raise HTTPException(status_code=404, detail="Genitore non trovato")
    parent_et = (parent.entity_type or 'privato').strip().lower()
    if child_et == 'rivenditore' and parent_et != 'distributore':
        raise HTTPException(status_code=400, detail="Il genitore di un rivenditore deve essere un distributore.")
    if child_et == 'privato' and parent_et not in ('rivenditore', 'distributore'):
        raise HTTPException(status_code=400, detail="Il genitore di un privato deve essere un rivenditore o un distributore.")
    from hierarchy import assert_no_cycle
    assert_no_cycle(user, parent, db)
    user.parent_id = parent.id
    user.distributor_id = parent.id if child_et == 'rivenditore' else None


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    entity_type: Optional[str] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista tutti gli utenti con filtri opzionali."""
    query = db.query(User).options(joinedload(User.role))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term))
        )

    if role_id is not None:
        query = query.filter(User.role_id == role_id)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if entity_type is not None:
        query = query.filter(User.entity_type == entity_type)

    users = query.order_by(User.created_at.desc()).all()

    return AdminUserListResponse(
        users=[build_admin_user_response(u, db) for u in users],
        total=len(users)
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Dettaglio singolo utente."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    return build_admin_user_response(user, db)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: str,
    request: AdminUpdateUserRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiorna dati utente (is_active, full_name, entity_type, distributor_id)."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if request.is_active is not None:
        user.is_active = request.is_active
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.entity_type is not None:
        et = request.entity_type.strip().lower()
        if et not in ('distributore', 'rivenditore', 'privato'):
            raise HTTPException(
                status_code=400,
                detail="entity_type deve essere 'distributore', 'rivenditore' o 'privato'",
            )
        user.entity_type = et
        # I distributori sono la radice dell'albero: nessun genitore.
        if et == 'distributore':
            user.parent_id = None
            user.distributor_id = None
    # Assegnazione/azzeramento del genitore nell'albero. Si accetta `parent_id`
    # (canonico) oppure il legacy `distributor_id` come alias.
    parent_value = request.parent_id if request.parent_id is not None else request.distributor_id
    if parent_value is not None:
        _set_user_parent(user, parent_value, db)
    if request.codice_fiscale is not None:
        user.codice_fiscale = (request.codice_fiscale or "").upper().strip() or None
    if request.partita_iva is not None:
        user.partita_iva = (request.partita_iva or "").strip() or None
    if request.ragione_sociale is not None:
        user.ragione_sociale = (request.ragione_sociale or "").strip() or None
    if request.indirizzo_fatturazione is not None:
        user.indirizzo_fatturazione = (request.indirizzo_fatturazione or "").strip() or None

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return build_admin_user_response(user, db)


@router.put("/users/{user_id}/role", response_model=AdminUserResponse)
async def change_user_role(
    user_id: str,
    request: AdminChangeRoleRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Cambia il ruolo di un utente."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    # Verifica che il ruolo esista
    role = db.query(Role).filter(Role.id == request.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")

    user.role_id = role.id
    # Aggiorna anche is_admin in base al ruolo
    user.is_admin = (role.name == 'admin')
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return build_admin_user_response(user, db)


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Ottieni permessi effettivi e override di un utente."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    effective = get_effective_permissions(user, db)

    # Permessi del ruolo
    role_perms = []
    if user.role_id:
        role_permissions = db.query(RolePermission).filter(
            RolePermission.role_id == user.role_id
        ).all()
        role_perms = [rp.permission_code for rp in role_permissions]

    # Override utente
    overrides = {}
    user_overrides = db.query(UserPermission).filter(UserPermission.user_id == user.id).all()
    for override in user_overrides:
        overrides[override.permission_code] = override.granted

    return {
        "user_id": str(user.id),
        "role_name": user.role.name if user.role else None,
        "role_permissions": role_perms,
        "user_overrides": overrides,
        "effective_permissions": effective,
        "all_permission_codes": PERMISSION_CODES
    }


@router.put("/users/{user_id}/permissions", response_model=AdminUserResponse)
async def set_user_permissions(
    user_id: str,
    request: AdminSetPermissionsRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Imposta override permessi per un utente.
    - True: forza abilitazione
    - False: forza disabilitazione
    - None/null: rimuovi override (eredita dal ruolo)
    """
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    for perm_code, granted in request.permissions.items():
        if perm_code not in PERMISSION_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Codice permesso non valido: {perm_code}. Validi: {PERMISSION_CODES}"
            )

        # Cerca override esistente
        existing = db.query(UserPermission).filter(
            UserPermission.user_id == user.id,
            UserPermission.permission_code == perm_code
        ).first()

        if granted is None:
            # Rimuovi override
            if existing:
                db.delete(existing)
        else:
            if existing:
                existing.granted = granted
            else:
                new_override = UserPermission(
                    user_id=user.id,
                    permission_code=perm_code,
                    granted=granted
                )
                db.add(new_override)

    db.commit()
    db.refresh(user)

    return build_admin_user_response(user, db)


# ============================================================================
# CREDITS MANAGEMENT
# ============================================================================

@router.post("/users/{user_id}/credits", response_model=AdminUserResponse)
async def adjust_user_credits(
    user_id: str,
    request: AdminAdjustCreditsRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiungi o rimuovi crediti a un utente."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    add_credits(
        user=user,
        amount=request.amount,
        description=request.description,
        db=db,
        transaction_type='admin_adjustment',
        admin_user=admin_user
    )

    db.refresh(user)
    return build_admin_user_response(user, db)


@router.get("/users/{user_id}/transactions", response_model=CreditTransactionListResponse)
async def get_user_credit_transactions(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Storico transazioni crediti di un utente."""
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    transactions = get_user_transactions(user.id, db, limit=limit, offset=offset)
    total = db.query(func.count(CreditTransaction.id)).filter(
        CreditTransaction.user_id == user.id
    ).scalar()

    return CreditTransactionListResponse(
        transactions=transactions,
        total=total or 0
    )


# ============================================================================
# ROLES MANAGEMENT
# ============================================================================

@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista tutti i ruoli con i loro permessi."""
    roles = db.query(Role).options(joinedload(Role.permissions)).all()

    return RoleListResponse(
        roles=[
            RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_default=role.is_default,
                permissions=[rp.permission_code for rp in role.permissions],
                created_at=role.created_at,
                updated_at=role.updated_at
            )
            for role in roles
        ]
    )


@router.put("/roles/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: int,
    request: AdminUpdateRolePermissionsRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiorna i permessi di un ruolo."""
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")

    # Valida i codici permesso
    for perm in request.permissions:
        if perm not in PERMISSION_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Codice permesso non valido: {perm}. Validi: {PERMISSION_CODES}"
            )

    # Rimuovi tutti i permessi attuali del ruolo
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()

    # Inserisci i nuovi permessi
    for perm_code in request.permissions:
        new_perm = RolePermission(
            role_id=role.id,
            permission_code=perm_code
        )
        db.add(new_perm)

    role.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(role)

    # Ricarica permessi
    updated_permissions = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_default=role.is_default,
        permissions=[rp.permission_code for rp in updated_permissions],
        created_at=role.created_at,
        updated_at=role.updated_at
    )


# ============================================================================
# STATISTICS
# ============================================================================

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Statistiche generali per la dashboard admin."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0

    # Crediti distribuiti (somma delle transazioni positive di tipo admin_adjustment)
    total_distributed = db.query(func.coalesce(func.sum(CreditTransaction.amount), 0)).filter(
        CreditTransaction.amount > 0
    ).scalar() or 0

    # Crediti consumati (somma abs delle transazioni negative)
    total_consumed = db.query(func.coalesce(func.sum(func.abs(CreditTransaction.amount)), 0)).filter(
        CreditTransaction.amount < 0
    ).scalar() or 0

    # Operazioni oggi
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    operations_today = db.query(func.count(CreditTransaction.id)).filter(
        CreditTransaction.transaction_type == 'consumption',
        CreditTransaction.created_at >= today
    ).scalar() or 0

    # Operazioni questa settimana
    week_ago = datetime.utcnow() - timedelta(days=7)
    operations_week = db.query(func.count(CreditTransaction.id)).filter(
        CreditTransaction.transaction_type == 'consumption',
        CreditTransaction.created_at >= week_ago
    ).scalar() or 0

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_credits_distributed=total_distributed,
        total_credits_consumed=total_consumed,
        operations_today=operations_today,
        operations_this_week=operations_week
    )


# ============================================================================
# USER CREATION
# ============================================================================

@router.post("/users", response_model=AdminUserResponse)
async def create_user(
    request: AdminCreateUserRequest,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Crea un nuovo utente dal pannello admin.
    L'utente NON ha password: riceve un'email di invito per impostarla (e verificare l'email)."""
    # Verifica email duplicata
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail=f"Email '{request.email}' gia' in uso"
        )

    # Verifica username duplicato
    existing_username = db.query(User).filter(User.username == request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=400,
            detail=f"Username '{request.username}' gia' in uso"
        )

    # Determina il ruolo
    if request.role_id:
        role = db.query(Role).filter(Role.id == request.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Ruolo non trovato")
        role_id = role.id
        is_admin = (role.name == 'admin')
    else:
        # Ruolo default
        default_role = db.query(Role).filter(Role.is_default == True).first()
        role_id = default_role.id if default_role else None
        is_admin = False

    # Crea utente SENZA password ed email NON verificata: l'invito imposterà
    # la password e verificherà/attiverà l'account.
    entity_type = (request.entity_type or 'privato').strip().lower()
    if entity_type not in ('distributore', 'rivenditore', 'privato'):
        raise HTTPException(status_code=400, detail="entity_type non valido")

    new_user = User(
        email=request.email,
        username=request.username,
        hashed_password=None,
        full_name=request.full_name,
        role_id=role_id,
        is_admin=is_admin,
        credits=request.credits,
        is_active=request.is_active,
        email_verified=False,
        entity_type=entity_type,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Genitore opzionale nell'albero (l'admin può creare chiunque sotto chiunque).
    if request.parent_id:
        _set_user_parent(new_user, request.parent_id, db)
        db.commit()
        db.refresh(new_user)

    # Se crediti > 0, registra transazione
    if request.credits > 0:
        from credits import add_credits as _add_credits
        _add_credits(
            user=new_user,
            amount=0,  # gia' assegnati in fase di creazione, registra solo la transazione
            description=f"Crediti iniziali alla creazione utente ({request.credits})",
            db=db,
            transaction_type='admin_adjustment',
            admin_user=admin_user
        )

    # Invia l'email di invito (imposta password + verifica) in background.
    from email_service import create_email_token, build_link, send_invite_email
    raw = create_email_token(db, new_user.id, 'set_password')
    link = build_link('set_password', raw)
    background_tasks.add_task(send_invite_email, new_user.email, new_user.full_name or new_user.username, link)

    return build_admin_user_response(new_user, db)


@router.post("/users/{user_id}/resend-invite")
async def resend_invite(
    user_id: str,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Reinvia l'email di invito/verifica a un utente non ancora verificato."""
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="L'utente ha già verificato l'email")

    from email_service import create_email_token, build_link, send_invite_email, send_verification_email
    if not user.hashed_password:
        # Utente invitato che non ha ancora impostato la password.
        raw = create_email_token(db, user.id, 'set_password')
        background_tasks.add_task(send_invite_email, user.email, user.full_name or user.username, build_link('set_password', raw))
    else:
        # Utente registrato che non ha ancora confermato l'email.
        raw = create_email_token(db, user.id, 'verify')
        background_tasks.add_task(send_verification_email, user.email, user.full_name or user.username, build_link('verify', raw))
    return {"message": "Email reinviata"}


# ============================================================================
# SYSTEM SETTINGS - CREDIT COSTS
# ============================================================================

@router.get("/settings/credit-costs", response_model=CreditCostsResponse)
async def get_credit_costs_settings(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Recupera i costi dei crediti correnti (personalizzati o default)."""
    costs = get_credit_costs(db)
    is_default = is_credit_costs_default(db)

    return CreditCostsResponse(
        costs=costs,
        is_default=is_default
    )


@router.put("/settings/credit-costs", response_model=CreditCostsResponse)
async def update_credit_costs_settings(
    request: CreditCostsUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiorna i costi dei crediti (personalizzazione admin)."""
    updated_costs = save_credit_costs(
        costs=request.costs,
        admin_user_id=admin_user.id,
        db=db
    )

    return CreditCostsResponse(
        costs=updated_costs,
        is_default=False
    )


@router.delete("/settings/credit-costs", response_model=CreditCostsResponse)
async def reset_credit_costs_settings(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Ripristina i costi dei crediti ai valori default."""
    default_costs = reset_credit_costs(
        admin_user_id=admin_user.id,
        db=db
    )

    return CreditCostsResponse(
        costs=default_costs,
        is_default=True
    )


@router.get("/settings/eur-per-credit")
async def get_eur_per_credit(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Recupera il tasso di conversione EUR per credito."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == 'eur_per_credit').first()
    value = float(setting.value) if setting and setting.value else 0.10
    return {"eur_per_credit": value}


@router.put("/settings/eur-per-credit")
async def update_eur_per_credit(
    request: dict,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiorna il tasso di conversione EUR per credito."""
    from datetime import datetime
    value = request.get("eur_per_credit")
    if value is None or not isinstance(value, (int, float)) or value < 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Valore deve essere un numero >= 0")

    setting = db.query(SystemSetting).filter(SystemSetting.key == 'eur_per_credit').first()
    if setting:
        setting.value = str(value)
        setting.updated_at = datetime.utcnow()
        setting.updated_by = admin_user.id
    else:
        setting = SystemSetting(
            key='eur_per_credit',
            value=str(value),
            updated_at=datetime.utcnow(),
            updated_by=admin_user.id
        )
        db.add(setting)
    db.commit()
    return {"eur_per_credit": value}


# ============================================================================
# TEMPLATE ESPORTAZIONE
# ============================================================================

@router.get("/templates", response_model=ExportTemplateListResponse)
async def get_templates(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Restituisce tutti i template di esportazione + parametri help."""
    data = get_export_templates(db)
    return ExportTemplateListResponse(
        templates=data.get("templates", []),
        help=TEMPLATE_PARAM_HELP
    )


@router.put("/templates")
async def update_templates(
    request: ExportTemplateUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Salva/aggiorna la lista completa dei template."""
    templates_dicts = [t.model_dump() for t in request.templates]
    data = {"templates": templates_dicts}
    result = save_export_templates(data, admin_user.id, db)
    return ExportTemplateListResponse(
        templates=result.get("templates", []),
        help=TEMPLATE_PARAM_HELP
    )


@router.delete("/templates/{template_id}")
async def remove_template(
    template_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Elimina un template (non quello default/standard)."""
    result = delete_template(template_id, admin_user.id, db)
    return ExportTemplateListResponse(
        templates=result.get("templates", []),
        help=TEMPLATE_PARAM_HELP
    )


@router.get("/templates/help")
async def get_template_help(
    admin_user: User = Depends(get_current_admin_user),
):
    """Restituisce le descrizioni di tutti i parametri dei template per i tooltip."""
    return TEMPLATE_PARAM_HELP


@router.post("/templates/background-upload")
async def upload_template_background(
    file: UploadFile = File(...),
    admin_user: User = Depends(get_current_admin_user),
):
    """Carica un'immagine di sfondo per i template PDF."""
    import config
    import uuid as _uuid

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo file non supportato: {file.content_type}. Usa JPG, PNG o WebP."
        )

    # Max 5MB
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 5MB).")

    bg_dir = config.UPLOAD_DIR / "template_backgrounds"
    bg_dir.mkdir(exist_ok=True, parents=True)

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    filename = f"bg_{_uuid.uuid4().hex[:12]}.{ext}"
    file_path = bg_dir / filename

    with open(file_path, "wb") as f:
        f.write(contents)

    return {"filename": filename, "url": f"/admin/templates/backgrounds/{filename}"}


@router.get("/templates/backgrounds/{filename}")
async def serve_template_background(filename: str):
    """Serve un'immagine di sfondo per i template."""
    import config

    # Sanitize filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome file non valido")

    file_path = config.UPLOAD_DIR / "template_backgrounds" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Immagine non trovata")

    return FileResponse(file_path)


@router.delete("/templates/backgrounds/{filename}")
async def delete_template_background(
    filename: str,
    admin_user: User = Depends(get_current_admin_user),
):
    """Elimina un'immagine di sfondo."""
    import config

    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome file non valido")

    file_path = config.UPLOAD_DIR / "template_backgrounds" / filename
    if file_path.exists():
        file_path.unlink()

    return {"ok": True}


# ============================================================================
# API KEYS
# ============================================================================

@router.post("/api-keys")
async def create_api_key(
    request: dict,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Crea una nuova API key per un utente."""
    from api_key_auth import generate_api_key

    user_id = request.get('user_id')
    name = request.get('name', 'API Key')
    expires_in_days = request.get('expires_in_days')
    rate_limit = request.get('rate_limit_per_minute', 30)

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id richiesto")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    full_key, key_hash, key_prefix = generate_api_key()

    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))

    db_key = APIKey(
        user_id=user.id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
        expires_at=expires_at,
        rate_limit_per_minute=min(max(int(rate_limit), 1), 300),
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    return {
        "id": str(db_key.id),
        "name": db_key.name,
        "key": full_key,
        "key_prefix": db_key.key_prefix,
        "user_id": str(db_key.user_id),
        "expires_at": db_key.expires_at.isoformat() if db_key.expires_at else None,
        "rate_limit_per_minute": db_key.rate_limit_per_minute,
        "created_at": db_key.created_at.isoformat(),
        "message": "Salva questa chiave in modo sicuro. Non verra' mostrata di nuovo."
    }


@router.get("/api-keys")
async def list_api_keys(
    user_id: Optional[str] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Lista tutte le API keys, con filtro opzionale per utente."""
    query = db.query(APIKey).join(User)

    if user_id:
        query = query.filter(APIKey.user_id == user_id)

    keys = query.order_by(APIKey.created_at.desc()).all()

    return {
        "keys": [
            {
                "id": str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "user_id": str(k.user_id),
                "user_email": k.user.email if k.user else None,
                "is_active": k.is_active,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "rate_limit_per_minute": k.rate_limit_per_minute,
                "created_at": k.created_at.isoformat(),
            }
            for k in keys
        ],
        "total": len(keys)
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Revoca (disattiva) una API key."""
    db_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not db_key:
        raise HTTPException(status_code=404, detail="API key non trovata")

    db_key.is_active = False
    db.commit()

    return {"message": f"API key '{db_key.name}' revocata", "id": str(db_key.id)}


# ---- Pacchetti crediti -------------------------------------------------------

@router.get("/credit-packages", response_model=CreditPackageListResponse)
async def admin_list_packages(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    rows = db.query(CreditPackage).order_by(CreditPackage.sort_order.asc(), CreditPackage.id.asc()).all()
    return CreditPackageListResponse(packages=[CreditPackageResponse(**r.to_dict()) for r in rows])


@router.post("/credit-packages", response_model=CreditPackageResponse)
async def admin_create_package(
    request: AdminCreditPackageRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    et = (request.entity_type or 'privato').strip().lower()
    if et not in ('distributore', 'rivenditore', 'privato'):
        raise HTTPException(status_code=400, detail="entity_type deve essere 'distributore', 'rivenditore' o 'privato'")
    pkg = CreditPackage(
        name=request.name,
        credits=request.credits,
        price_cents=request.price_cents,
        is_active=request.is_active,
        sort_order=request.sort_order,
        description=request.description,
        entity_type=et,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return CreditPackageResponse(**pkg.to_dict())


@router.put("/credit-packages/{package_id}", response_model=CreditPackageResponse)
async def admin_update_package(
    package_id: int,
    request: AdminCreditPackageRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    pkg = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Pacchetto non trovato")

    et = (request.entity_type or 'privato').strip().lower()
    if et not in ('distributore', 'rivenditore', 'privato'):
        raise HTTPException(status_code=400, detail="entity_type deve essere 'distributore', 'rivenditore' o 'privato'")

    pkg.name = request.name
    pkg.credits = request.credits
    pkg.price_cents = request.price_cents
    pkg.is_active = request.is_active
    pkg.sort_order = request.sort_order
    pkg.description = request.description
    pkg.entity_type = et
    pkg.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pkg)
    return CreditPackageResponse(**pkg.to_dict())


@router.delete("/credit-packages/{package_id}")
async def admin_delete_package(
    package_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    pkg = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Pacchetto non trovato")

    db.delete(pkg)
    db.commit()
    return {"message": "Pacchetto eliminato", "id": package_id}


# ============================================================================
# RICHIESTE CREDITI — inbox admin (richieste dei distributori)
# ============================================================================

def _admin_req_item(cr: CreditRequest, db: Session) -> CreditRequestItem:
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


@router.get("/credit-requests", response_model=CreditRequestListResponse)
async def admin_list_credit_requests(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Richieste crediti pending indirizzate al pool admin (dei distributori)."""
    rows = (
        db.query(CreditRequest)
        .filter(CreditRequest.approver_is_admin == True, CreditRequest.status == 'pending')  # noqa: E712
        .order_by(CreditRequest.created_at.asc())
        .all()
    )
    return CreditRequestListResponse(requests=[_admin_req_item(r, db) for r in rows], total=len(rows))


@router.get("/credit-requests/history", response_model=CreditRequestListResponse)
async def admin_credit_requests_history(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Storico delle richieste admin gestite (approvate/rifiutate/annullate)."""
    rows = (
        db.query(CreditRequest)
        .filter(CreditRequest.approver_is_admin == True, CreditRequest.status != 'pending')  # noqa: E712
        .order_by(CreditRequest.resolved_at.desc(), CreditRequest.created_at.desc())
        .all()
    )
    return CreditRequestListResponse(requests=[_admin_req_item(r, db) for r in rows], total=len(rows))


@router.post("/credit-requests/{request_id}/approve", response_model=CreditRequestItem)
async def admin_approve_credit_request(
    request_id: str,
    body: ResolveRequestRequest = ResolveRequestRequest(),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Approva una richiesta admin: accredita i crediti (admin = crediti infiniti)."""
    try:
        cr = db.query(CreditRequest).filter(
            CreditRequest.id == UUID(request_id),
            CreditRequest.status == 'pending',
        ).with_for_update().one_or_none()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID richiesta non valido")
    if not cr or not cr.approver_is_admin:
        raise HTTPException(status_code=409, detail="Richiesta non trovata o già gestita")

    requester = db.query(User).filter(User.id == cr.requester_id).first()
    if not requester:
        raise HTTPException(status_code=404, detail="Richiedente non trovato")

    cr.status = 'approved'
    cr.resolver_id = admin_user.id
    cr.resolved_at = datetime.utcnow()
    cr.note = body.note
    add_credits(
        user=requester,
        amount=cr.package_credits,
        description=f"Approvazione richiesta crediti ({cr.package_name})",
        db=db,
        transaction_type='admin_adjustment',
        admin_user=admin_user,
    )
    db.refresh(cr)
    return _admin_req_item(cr, db)


@router.post("/credit-requests/{request_id}/reject", response_model=CreditRequestItem)
async def admin_reject_credit_request(
    request_id: str,
    body: ResolveRequestRequest = ResolveRequestRequest(),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    try:
        cr = db.query(CreditRequest).filter(
            CreditRequest.id == UUID(request_id),
            CreditRequest.status == 'pending',
        ).with_for_update().one_or_none()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID richiesta non valido")
    if not cr or not cr.approver_is_admin:
        raise HTTPException(status_code=409, detail="Richiesta non trovata o già gestita")
    cr.status = 'rejected'
    cr.resolver_id = admin_user.id
    cr.resolved_at = datetime.utcnow()
    cr.note = body.note
    db.commit()
    db.refresh(cr)
    return _admin_req_item(cr, db)

