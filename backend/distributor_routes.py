"""
Router FastAPI per la dashboard del distributore (sola lettura).

Espone:
  GET /api/distributor/resellers                  elenco dei propri rivenditori con
                                                  crediti, totale speso e n. acquisti
  GET /api/distributor/resellers/{id}/payments    storico ordini di un rivenditore

Accesso riservato agli utenti con entity_type='distributore' (gate
get_current_distributor). Un distributore vede solo i rivenditori a lui
assegnati (User.distributor_id == distributore.id).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_distributor
from database import get_db
from db_models import PaymentOrder, User
from models import (
    DistributorResellerItem,
    DistributorResellerListResponse,
    PaymentOrderListResponse,
    PaymentOrderResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/distributor", tags=["Distributor"])


@router.get("/resellers", response_model=DistributorResellerListResponse)
def list_my_resellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_distributor),
):
    """Rivenditori assegnati al distributore corrente, con aggregati di spesa."""
    resellers = (
        db.query(User)
        .filter(User.distributor_id == current_user.id)
        .order_by(User.username.asc())
        .all()
    )

    items = []
    for r in resellers:
        total_cents, count = (
            db.query(
                func.coalesce(func.sum(PaymentOrder.amount_cents), 0),
                func.count(PaymentOrder.id),
            )
            .filter(PaymentOrder.user_id == r.id, PaymentOrder.status == "PAID")
            .one()
        )
        items.append(
            DistributorResellerItem(
                id=str(r.id),
                username=r.username,
                full_name=r.full_name,
                email=r.email,
                credits=r.credits,
                total_spent_eur=round((total_cents or 0) / 100.0, 2),
                purchase_count=count or 0,
            )
        )

    return DistributorResellerListResponse(resellers=items, total=len(items))


@router.get("/resellers/{reseller_id}/payments", response_model=PaymentOrderListResponse)
def reseller_payments(
    reseller_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_distributor),
):
    """Storico ordini di un rivenditore (solo se assegnato al distributore corrente)."""
    try:
        rid = UUID(reseller_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Rivenditore non trovato")

    reseller = db.query(User).filter(User.id == rid).first()
    # Il controllo di ownership È il confine di sicurezza: 404 se non è un mio rivenditore.
    if not reseller or reseller.distributor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rivenditore non trovato")

    q = db.query(PaymentOrder).filter(PaymentOrder.user_id == reseller.id)
    total = q.count()
    rows = q.order_by(PaymentOrder.created_at.desc()).limit(limit).offset(offset).all()
    return PaymentOrderListResponse(
        orders=[PaymentOrderResponse(**r.to_dict()) for r in rows],
        total=total,
    )
