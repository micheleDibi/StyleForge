"""
Router FastAPI per la dashboard del distributore (sola lettura).

Espone:
  GET /api/distributor/resellers   elenco dei propri rivenditori con i crediti attuali

Accesso riservato agli utenti con entity_type='distributore' (gate
get_current_distributor). Un distributore vede solo i rivenditori a lui
assegnati (User.distributor_id == distributore.id).

Nota: dopo la rimozione di PagoPA non sono più disponibili gli aggregati di spesa
(totale speso / numero acquisti) né lo storico ordini, che derivavano dagli
ordini di pagamento.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_distributor
from database import get_db
from db_models import User
from models import DistributorResellerItem, DistributorResellerListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/distributor", tags=["Distributor"])


@router.get("/resellers", response_model=DistributorResellerListResponse)
def list_my_resellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_distributor),
):
    """Rivenditori assegnati al distributore corrente, con i crediti attuali."""
    resellers = (
        db.query(User)
        .filter(User.distributor_id == current_user.id)
        .order_by(User.username.asc())
        .all()
    )

    items = [
        DistributorResellerItem(
            id=str(r.id),
            username=r.username,
            full_name=r.full_name,
            email=r.email,
            credits=r.credits,
        )
        for r in resellers
    ]

    return DistributorResellerListResponse(resellers=items, total=len(items))
