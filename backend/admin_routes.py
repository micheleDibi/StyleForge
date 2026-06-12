"""
Router per gli endpoint di amministrazione.
Solo accessibile da utenti con ruolo admin.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database import get_db
from auth import get_current_admin_user, get_effective_permissions, get_password_hash
from db_models import (
    User, Role, RolePermission, UserPermission, CreditTransaction, SystemSetting, APIKey,
    CreditPackage, PaymentOrder, PagoPAEvent
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
    AdminPaymentListItem, AdminPaymentListResponse,
    AdminPaymentDailyPoint, AdminPaymentStatsResponse,
    AdminCancelPaymentResponse, AdminRefundCreditsRequest,
    AdminPagopaConfigResponse, AdminPagopaConfigUpdateRequest,
    AdminEstrccUploadResponse, PaymentOrderResponse,
)
import config
import pagopa_client as pgc
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
        entity_type=getattr(user, 'entity_type', None) or 'private',
        codice_fiscale=getattr(user, 'codice_fiscale', None),
        partita_iva=getattr(user, 'partita_iva', None),
        ragione_sociale=getattr(user, 'ragione_sociale', None),
        indirizzo_fatturazione=getattr(user, 'indirizzo_fatturazione', None),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
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
    """Aggiorna dati utente (is_active, full_name, entity_type)."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if request.is_active is not None:
        user.is_active = request.is_active
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.entity_type is not None:
        et = request.entity_type.strip().lower()
        if et not in ('private', 'training'):
            raise HTTPException(
                status_code=400,
                detail="entity_type deve essere 'private' o 'training'",
            )
        user.entity_type = et
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
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Crea un nuovo utente dal pannello admin."""
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

    # Crea utente
    hashed_password = get_password_hash(request.password)
    new_user = User(
        email=request.email,
        username=request.username,
        hashed_password=hashed_password,
        full_name=request.full_name,
        role_id=role_id,
        is_admin=is_admin,
        credits=request.credits,
        is_active=request.is_active
    )
    db.add(new_user)
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

    return build_admin_user_response(new_user, db)


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


@router.get("/settings/training-discount")
async def get_training_discount(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Recupera lo sconto % sull'acquisto crediti per gli enti di formazione."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == 'training_discount_percent').first()
    value = int(float(setting.value)) if setting and setting.value is not None else 40
    return {"training_discount_percent": max(0, min(100, value))}


@router.put("/settings/training-discount")
async def update_training_discount(
    request: dict,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Aggiorna lo sconto % enti di formazione sull'acquisto crediti (0-100)."""
    from datetime import datetime
    value = request.get("training_discount_percent")
    if value is None or not isinstance(value, (int, float)) or value < 0 or value > 100:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Valore deve essere un intero tra 0 e 100")
    value = int(value)

    setting = db.query(SystemSetting).filter(SystemSetting.key == 'training_discount_percent').first()
    if setting:
        setting.value = str(value)
        setting.updated_at = datetime.utcnow()
        setting.updated_by = admin_user.id
    else:
        setting = SystemSetting(
            key='training_discount_percent',
            value=str(value),
            updated_at=datetime.utcnow(),
            updated_by=admin_user.id
        )
        db.add(setting)
    db.commit()
    return {"training_discount_percent": value}


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


# ============================================================================
# PAGOPA — ORDINI, PACCHETTI, CONFIG, RICONCILIAZIONE
# ============================================================================

# ---- Ordini di pagamento ----------------------------------------------------

@router.get("/payments", response_model=AdminPaymentListResponse)
async def admin_list_payments(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Lista ordini PagoPA con filtri (status, user, range date, search su CF/IUV)."""
    query = db.query(PaymentOrder, User).join(User, PaymentOrder.user_id == User.id)

    if status:
        query = query.filter(PaymentOrder.status == status.upper())
    if user_id:
        try:
            query = query.filter(PaymentOrder.user_id == UUID(user_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="user_id non valido")
    if q:
        like = f"%{q}%"
        query = query.filter(
            (PaymentOrder.iuv.ilike(like))
            | (PaymentOrder.payer_codice_fiscale.ilike(like))
            | (PaymentOrder.payer_ragione_sociale.ilike(like))
        )
    if date_from:
        try:
            d = datetime.fromisoformat(date_from)
            query = query.filter(PaymentOrder.created_at >= d)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from non valida (atteso ISO8601)")
    if date_to:
        try:
            d = datetime.fromisoformat(date_to)
            query = query.filter(PaymentOrder.created_at <= d)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to non valida (atteso ISO8601)")

    total = query.count()
    rows = query.order_by(PaymentOrder.created_at.desc()).limit(limit).offset(offset).all()

    items = []
    for order, user in rows:
        items.append(AdminPaymentListItem(
            id=str(order.id),
            user_id=str(order.user_id),
            user_email=user.email if user else None,
            user_username=user.username if user else None,
            package_id=order.package_id,
            credits=order.credits,
            amount_cents=order.amount_cents,
            amount_eur=round(order.amount_cents / 100.0, 2),
            iuv=order.iuv,
            payer_codice_fiscale=order.payer_codice_fiscale,
            payer_ragione_sociale=order.payer_ragione_sociale,
            status=order.status,
            paid_at=order.paid_at,
            created_at=order.created_at,
            expires_at=order.expires_at,
        ))

    return AdminPaymentListResponse(orders=items, total=total)


@router.get("/payments/stats", response_model=AdminPaymentStatsResponse)
async def admin_payment_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """KPI cruscotto pagamenti: revenue, count, success rate, serie temporale 30gg."""
    # Aggregati totali
    revenue_total = db.query(func.coalesce(func.sum(PaymentOrder.amount_paid_cents), 0)).filter(
        PaymentOrder.status == "PAID"
    ).scalar() or 0
    count_total = db.query(func.count(PaymentOrder.id)).scalar() or 0
    count_paid = db.query(func.count(PaymentOrder.id)).filter(
        PaymentOrder.status == "PAID"
    ).scalar() or 0

    # Aggregati ultimo mese
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    revenue_month = db.query(func.coalesce(func.sum(PaymentOrder.amount_paid_cents), 0)).filter(
        PaymentOrder.status == "PAID", PaymentOrder.paid_at >= one_month_ago
    ).scalar() or 0
    count_month = db.query(func.count(PaymentOrder.id)).filter(
        PaymentOrder.created_at >= one_month_ago
    ).scalar() or 0

    # Count by status
    status_rows = db.query(PaymentOrder.status, func.count(PaymentOrder.id)).group_by(PaymentOrder.status).all()
    count_by_status = {s: int(c) for s, c in status_rows}

    success_rate = (count_paid / count_total) if count_total > 0 else 0.0

    # Serie temporale daily ultimi 30 giorni
    daily_rows = db.query(
        func.date(PaymentOrder.paid_at).label("d"),
        func.coalesce(func.sum(PaymentOrder.amount_paid_cents), 0).label("rev"),
        func.count(PaymentOrder.id).label("cnt"),
    ).filter(
        PaymentOrder.status == "PAID",
        PaymentOrder.paid_at >= one_month_ago,
    ).group_by(func.date(PaymentOrder.paid_at)).order_by(func.date(PaymentOrder.paid_at)).all()

    daily = [
        AdminPaymentDailyPoint(
            date=str(row.d),
            revenue_cents=int(row.rev or 0),
            count=int(row.cnt or 0),
        )
        for row in daily_rows
    ]

    return AdminPaymentStatsResponse(
        revenue_cents_total=int(revenue_total),
        revenue_cents_month=int(revenue_month),
        count_total=int(count_total),
        count_month=int(count_month),
        count_by_status=count_by_status,
        success_rate=round(success_rate, 4),
        daily=daily,
    )


@router.get("/payments/{order_id}", response_model=PaymentOrderResponse)
async def admin_get_payment(
    order_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return PaymentOrderResponse(**order.to_dict())


@router.post("/payments/{order_id}/cancel", response_model=AdminCancelPaymentResponse)
async def admin_cancel_payment(
    order_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Annulla una posizione non ancora pagata su SolutionPA (modalita INV)."""
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if order.status not in ("PENDING", "AWAITING_PAYMENT"):
        raise HTTPException(
            status_code=400,
            detail=f"Ordine in stato {order.status}, non annullabile",
        )
    if not order.iuv:
        # Posizione mai caricata -> solo cancel locale
        order.status = "CANCELED"
        db.commit()
        return AdminCancelPaymentResponse(order_id=order_id, status="CANCELED", message="Annullato (mai caricato)")

    try:
        pgc.annulla_posizione(iuv=order.iuv)
    except pgc.PagoPARemoteError as e:
        raise HTTPException(status_code=502, detail=f"Errore SolutionPA: {e.code}")
    except pgc.PagoPAError as e:
        raise HTTPException(status_code=502, detail=f"Errore comunicazione SolutionPA: {e}")

    order.status = "CANCELED"
    db.add(PagoPAEvent(
        order_id=order.id,
        iuv=order.iuv,
        event_type="POSITION_CANCELED",
        source="manual",
        payload={"admin": admin_user.username},
    ))
    db.commit()
    return AdminCancelPaymentResponse(order_id=order_id, status="CANCELED", message="Posizione annullata")


@router.post("/payments/{order_id}/refund-credits", response_model=PaymentOrderResponse)
async def admin_refund_credits(
    order_id: str,
    request: AdminRefundCreditsRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Rimborso interno: scala i crediti accreditati e marca l'ordine REFUNDED.
    NON storna su PagoPA: lo storno bancario va gestito manualmente.
    """
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    if order.status != "PAID":
        raise HTTPException(status_code=400, detail=f"Ordine in stato {order.status}, non rimborsabile")

    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    add_credits(
        user=user,
        amount=-order.credits,
        description=f"Rimborso ordine PagoPA {order.iuv}: {request.description}",
        db=db,
        transaction_type="refund",
        admin_user=admin_user,
    )
    order.status = "REFUNDED"
    db.add(PagoPAEvent(
        order_id=order.id,
        iuv=order.iuv,
        event_type="ESITO_PUSH",
        source="manual",
        payload={"action": "refund_credits", "admin": admin_user.username, "reason": request.description},
    ))
    db.commit()
    db.refresh(order)
    return PaymentOrderResponse(**order.to_dict())


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
    pkg = CreditPackage(
        name=request.name,
        credits=request.credits,
        price_cents=request.price_cents,
        is_active=request.is_active,
        sort_order=request.sort_order,
        description=request.description,
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

    pkg.name = request.name
    pkg.credits = request.credits
    pkg.price_cents = request.price_cents
    pkg.is_active = request.is_active
    pkg.sort_order = request.sort_order
    pkg.description = request.description
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

    # Soft delete: se ci sono ordini collegati, disattiva invece di eliminare
    has_orders = db.query(PaymentOrder).filter(PaymentOrder.package_id == package_id).limit(1).first()
    if has_orders:
        pkg.is_active = False
        pkg.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Pacchetto disattivato (esistono ordini collegati)", "id": package_id}

    db.delete(pkg)
    db.commit()
    return {"message": "Pacchetto eliminato", "id": package_id}


# ---- Configurazione PagoPA ---------------------------------------------------

def _mask(value: Optional[str]) -> Optional[str]:
    """Maschera una stringa lasciando 2 char iniziali + asterischi + 2 finali."""
    if not value:
        return None
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


@router.get("/pagopa/config", response_model=AdminPagopaConfigResponse)
async def admin_get_pagopa_config(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Configurazione PagoPA con credenziali mascherate."""
    return AdminPagopaConfigResponse(
        test_mode=config.PAGOPA_TEST_MODE,
        wsdl_url=config.PAGOPA_WSDL_URL,
        dominio=config.PAGOPA_DOMINIO or "",
        ub=config.PAGOPA_UB or "",
        cod_tributo=config.PAGOPA_COD_TRIBUTO or "",
        username_masked=_mask(config.PAGOPA_USERNAME),
        password_set=bool(config.PAGOPA_PASSWORD),
        return_url_base=config.PAGOPA_RETURN_URL_BASE,
        notify_username_set=bool(config.PAGOPA_NOTIFY_AUTH_USER),
        notify_password_set=bool(config.PAGOPA_NOTIFY_AUTH_PASS),
    )


@router.put("/pagopa/config", response_model=AdminPagopaConfigResponse)
async def admin_update_pagopa_config(
    request: AdminPagopaConfigUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Aggiorna la configurazione PagoPA. Per ora supporta solo il toggle test_mode;
    le credenziali si configurano via env e si vedono mascherate.
    """
    if request.test_mode is not None:
        # Persistenza in system_settings per re-load runtime; la env resta
        # source-of-truth al boot del server.
        setting = db.query(SystemSetting).filter(SystemSetting.key == "pagopa_config").first()
        config_data = (setting.value if setting else None) or {}
        config_data["test_mode"] = bool(request.test_mode)
        if setting:
            setting.value = config_data
            setting.updated_at = datetime.utcnow()
            setting.updated_by = admin_user.id
        else:
            db.add(SystemSetting(
                key="pagopa_config", value=config_data,
                updated_at=datetime.utcnow(), updated_by=admin_user.id,
            ))
        config.PAGOPA_TEST_MODE = bool(request.test_mode)
        # Reset cache zeep client per re-leggere il WSDL alla prossima call
        pgc.reset_client_cache()
        db.commit()

    return await admin_get_pagopa_config(admin_user=admin_user, db=db)


@router.post("/pagopa/reconcile/upload", response_model=AdminEstrccUploadResponse)
async def admin_upload_estrcc(
    file: UploadFile = File(...),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Upload manuale del file XML estrcc di riconciliazione daily.
    Confronta ogni riga con gli ordini esistenti, segnala discrepanze.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File vuoto")

    try:
        rows = pgc.parse_estrcc(content)
    except pgc.PagoPAError as e:
        raise HTTPException(status_code=400, detail=str(e))

    matched = 0
    unmatched = 0
    discrepancies = 0
    items = []
    for r in rows:
        iuv = r.get("iuv")
        item: dict = {**r, "match": "unmatched"}
        if iuv:
            order = db.query(PaymentOrder).filter(PaymentOrder.iuv == iuv).first()
            if order:
                matched += 1
                item["match"] = "matched"
                item["order_id"] = str(order.id)
                # Verifica importo (tolleranza 1 cent)
                try:
                    importo_pagato = int(round(float(r.get("singolo_importo_pagato") or "0") * 100))
                    expected = order.amount_paid_cents or order.amount_cents
                    if abs(importo_pagato - expected) > 1:
                        discrepancies += 1
                        item["discrepancy"] = {
                            "expected_cents": expected,
                            "reconciled_cents": importo_pagato,
                        }
                except (TypeError, ValueError):
                    pass
                # Aggiorna identificativo flusso e reconciliation_id
                if r.get("identificativo_flusso") and not order.identificativo_flusso:
                    order.identificativo_flusso = r.get("identificativo_flusso")
                if r.get("data_contabile") and not order.reconciliation_id:
                    order.reconciliation_id = f"{r.get('identificativo_flusso')}/{r.get('data_contabile')}"
            else:
                unmatched += 1
        else:
            unmatched += 1

        # Audit log
        db.add(PagoPAEvent(
            order_id=order.id if (iuv and order) else None,
            iuv=iuv,
            event_type="RECONCILIATION_FILE",
            source="manual",
            payload=r,
            processed=True,
        ))
        items.append(item)

    db.commit()
    return AdminEstrccUploadResponse(
        parsed=len(rows),
        matched=matched,
        unmatched=unmatched,
        discrepancies=discrepancies,
        items=items,
    )
