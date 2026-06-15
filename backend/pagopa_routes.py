"""
Router FastAPI per il flusso di acquisto crediti via PagoPA / SolutionPA.

Espone endpoint utente:
  GET  /api/payments/packages       lista pacchetti acquistabili
  POST /api/payments/initiate       crea PaymentOrder, ritorna checkout_url
  GET  /api/payments/{order_id}     dettaglio ordine (per polling post-checkout)
  GET  /api/payments/history        storico ordini dell'utente

Il push esito (notifica da SolutionPA) e' in pagopa_webhooks.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import config
import pagopa_client as pgc
from auth import get_current_active_user
from database import get_db
from db_models import CreditPackage, PagoPAEvent, PaymentOrder, User
from models import (
    CreditPackageListResponse,
    CreditPackageResponse,
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentOrderListResponse,
    PaymentOrderResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


# ============================================================================
# Helpers
# ============================================================================

def _admin_blocked() -> HTTPException:
    """Gli admin non comprano crediti (illimitati)."""
    return HTTPException(
        status_code=400,
        detail="Gli admin StyleForge hanno crediti illimitati e non possono effettuare acquisti.",
    )


def _is_admin(user: User) -> bool:
    return bool(user.is_admin or (user.role and user.role.name == "admin"))


def _record_event(
    db: Session,
    *,
    order_id=None,
    iuv: Optional[str] = None,
    event_type: str,
    source: str = "system",
    payload: dict,
    error: Optional[str] = None,
    processed: bool = True,
) -> None:
    """Salva un evento PagoPA (audit log) senza fare commit (lo fa il caller)."""
    ev = PagoPAEvent(
        order_id=order_id,
        iuv=iuv,
        event_type=event_type,
        source=source,
        payload=payload,
        processed=processed,
        error=error,
    )
    db.add(ev)


# ============================================================================
# Endpoint
# ============================================================================

@router.get("/packages", response_model=CreditPackageListResponse)
def list_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Restituisce i pacchetti crediti attivi del sottotipo dell'utente, ordinati
    per sort_order. Richiede login (vetrina pacchetti, non pubblica).
    """
    q = db.query(CreditPackage).filter(CreditPackage.is_active == True)  # noqa: E712
    # Ogni utente vede solo i pacchetti del proprio sottotipo (l'admin vede tutto,
    # ma non acquista comunque).
    if not _is_admin(current_user):
        subtype = (getattr(current_user, 'entity_type', None) or 'privato').strip().lower()
        q = q.filter(CreditPackage.entity_type == subtype)

    rows = q.order_by(CreditPackage.sort_order.asc(), CreditPackage.id.asc()).all()
    return CreditPackageListResponse(packages=[CreditPackageResponse(**r.to_dict()) for r in rows])


@router.post("/initiate", response_model=InitiatePaymentResponse)
def initiate_payment(
    request: InitiatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Avvia un pagamento PagoPA per il pacchetto richiesto.

    Flusso:
      1. Validazione (admin escluso, pacchetto attivo, CF formato corretto)
      2. Crea PaymentOrder con status=PENDING (snapshot pacchetto + dati pagatore)
      3. Chiama pdpCaricaPagamentoInAttesa -> ottiene IUV
      4. Chiama pdpAttivaRPT -> ottiene checkout URL + CCP
      5. Aggiorna PaymentOrder: status=AWAITING_PAYMENT, iuv, context_id, checkout_url
      6. Se save_to_profile=true, salva i dati anagrafici sull'utente
      7. Ritorna { order_id, checkout_url, ... }
    """
    if _is_admin(current_user):
        raise _admin_blocked()

    pkg = db.query(CreditPackage).filter(CreditPackage.id == request.package_id).first()
    if not pkg or not pkg.is_active:
        raise HTTPException(status_code=404, detail="Pacchetto non disponibile")

    # Difesa: un utente può acquistare solo i pacchetti del proprio sottotipo.
    subtype = (getattr(current_user, 'entity_type', None) or 'privato').strip().lower()
    if (pkg.entity_type or 'privato') != subtype:
        raise HTTPException(status_code=403, detail="Pacchetto non disponibile per il tuo profilo")

    cf = pgc.normalize_codice_fiscale(request.codice_fiscale)
    if not (pgc.is_valid_codice_fiscale(cf) or pgc.is_valid_partita_iva(cf)):
        raise HTTPException(
            status_code=400,
            detail="Codice fiscale non valido (atteso 16 alfanumerici, oppure 11 cifre per P.IVA)",
        )

    # Snapshot dati pagatore (CF normalizzato)
    payer_anagrafica = (
        request.ragione_sociale
        or current_user.full_name
        or current_user.username
    )
    payer_email = request.payer_email or current_user.email
    expires_at = datetime.utcnow() + timedelta(days=config.PAGOPA_POSITION_TTL_DAYS)
    causale = f"StyleForge crediti — {pkg.name} ({pkg.credits} crediti)"

    order = PaymentOrder(
        user_id=current_user.id,
        package_id=pkg.id,
        credits=pkg.credits,
        amount_cents=pkg.price_cents,
        causale=causale,
        payer_codice_fiscale=cf,
        payer_partita_iva=request.partita_iva,
        payer_ragione_sociale=request.ragione_sociale,
        payer_email=payer_email,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(order)
    db.flush()  # ottiene order.id senza commit
    order_id = str(order.id)

    # Chiama SolutionPA (carica + attiva). Se fallisce, marchiamo l'ordine FAILED e propaghiamo 502.
    try:
        iuv = pgc.carica_pagamento_in_attesa(
            payer_codice_fiscale=cf,
            payer_anagrafica=payer_anagrafica,
            importo_totale_cents=pkg.price_cents,
            causale=causale,
            id_tenant=order_id[:35],
            payer_email=payer_email,
            payer_partita_iva=request.partita_iva,
            payer_ragione_sociale=request.ragione_sociale,
        )
        order.iuv = iuv
        _record_event(
            db,
            order_id=order.id,
            iuv=iuv,
            event_type="POSITION_LOADED",
            source="soap",
            payload={"order_id": order_id, "iuv": iuv},
        )

        return_url = f"{config.PAGOPA_RETURN_URL_BASE.rstrip('/')}?orderId={order_id}"
        checkout_url, ccp = pgc.attiva_rpt(iuv=iuv, return_url=return_url)

        order.checkout_url = checkout_url
        order.context_id = ccp[:35] if ccp else None
        order.status = "AWAITING_PAYMENT"
        _record_event(
            db,
            order_id=order.id,
            iuv=iuv,
            event_type="RPT_ACTIVATED",
            source="soap",
            payload={"order_id": order_id, "iuv": iuv, "ccp": ccp, "checkout_url": checkout_url},
        )

    except pgc.PagoPAValidationError as e:
        order.status = "FAILED"
        _record_event(db, order_id=order.id, event_type="POSITION_LOADED", source="soap",
                      payload={"order_id": order_id}, error=str(e), processed=False)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except pgc.PagoPARemoteError as e:
        order.status = "FAILED"
        _record_event(db, order_id=order.id, event_type="POSITION_LOADED", source="soap",
                      payload={"order_id": order_id, "code": e.code}, error=str(e), processed=False)
        db.commit()
        logger.error("[PagoPA] errore remoto initiate_payment: %s", e)
        raise HTTPException(status_code=502, detail=f"Errore SolutionPA: {e.code}")
    except pgc.PagoPAError as e:
        order.status = "FAILED"
        _record_event(db, order_id=order.id, event_type="POSITION_LOADED", source="soap",
                      payload={"order_id": order_id}, error=str(e), processed=False)
        db.commit()
        logger.exception("[PagoPA] errore client initiate_payment")
        raise HTTPException(status_code=502, detail="Errore comunicazione con SolutionPA")

    # Salva i dati anagrafici sul profilo utente se richiesto
    if request.save_to_profile:
        current_user.codice_fiscale = cf if pgc.is_valid_codice_fiscale(cf) else current_user.codice_fiscale
        if request.partita_iva:
            current_user.partita_iva = request.partita_iva
        if request.ragione_sociale:
            current_user.ragione_sociale = request.ragione_sociale

    db.commit()
    db.refresh(order)

    return InitiatePaymentResponse(
        order_id=order_id,
        iuv=order.iuv,
        checkout_url=order.checkout_url,
        amount_cents=order.amount_cents,
        credits=order.credits,
        expires_at=order.expires_at,
    )


@router.get("/history", response_model=PaymentOrderListResponse)
def get_payment_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Storico ordini dell'utente corrente."""
    q = db.query(PaymentOrder).filter(PaymentOrder.user_id == current_user.id)
    total = q.count()
    rows = q.order_by(PaymentOrder.created_at.desc()).limit(limit).offset(offset).all()
    return PaymentOrderListResponse(
        orders=[PaymentOrderResponse(**r.to_dict()) for r in rows],
        total=total,
    )


@router.get("/{order_id}", response_model=PaymentOrderResponse)
def get_payment(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Dettaglio di un ordine (per polling dalla pagina /payments/return).
    Solo l'owner puo' leggerlo (gli admin usano /admin/payments).
    """
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id).first()
    if not order or str(order.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return PaymentOrderResponse(**order.to_dict())
