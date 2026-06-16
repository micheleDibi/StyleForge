"""
Router FastAPI per il listino dei pacchetti crediti (lato utente).

Espone:
  GET /api/packages   pacchetti acquistabili del sottotipo dell'utente

Il CRUD admin dei pacchetti è in admin_routes.py (/admin/credit-packages).
Nota: dopo la rimozione di PagoPA i pacchetti restano come semplice listino;
l'accredito dei crediti avviene manualmente dall'admin.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_active_user
from database import get_db
from db_models import CreditPackage, User
from models import CreditPackageListResponse, CreditPackageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/packages", tags=["Packages"])


def _is_admin(user: User) -> bool:
    return bool(user.is_admin or (user.role and user.role.name == "admin"))


@router.get("", response_model=CreditPackageListResponse)
def list_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Pacchetti crediti attivi del sottotipo dell'utente, ordinati per sort_order.
    Richiede login (vetrina pacchetti, non pubblica).
    """
    q = db.query(CreditPackage).filter(CreditPackage.is_active == True)  # noqa: E712
    # Ogni utente vede solo i pacchetti del proprio sottotipo (l'admin vede tutto).
    if not _is_admin(current_user):
        subtype = (getattr(current_user, 'entity_type', None) or 'privato').strip().lower()
        q = q.filter(CreditPackage.entity_type == subtype)

    rows = q.order_by(CreditPackage.sort_order.asc(), CreditPackage.id.asc()).all()
    return CreditPackageListResponse(packages=[CreditPackageResponse(**r.to_dict()) for r in rows])
