"""
Webhook entranti da SolutionPA per il push esito pagamento.

Espone:
  POST /api/pagopa/esito       (REST registerPayment, JSON, Basic Auth dedicata)

Idempotenza: chiamate ripetute con lo stesso IUV sono no-op (re-delivery PagoPA
fino a 7 giorni). Race-safe: il blocco "find order + update + add_credits"
e' wrappato in transazione DB con SELECT ... FOR UPDATE sull'ordine.

Autenticazione: Basic Auth con credenziali dedicate (PAGOPA_NOTIFY_AUTH_USER /
PAGOPA_NOTIFY_AUTH_PASS) — separate dalle credenziali outbound. NON e' la JWT
auth utente.

Riferimento: Specifiche EnteEsito V_2.1, sez. 4 (registerPayment REST).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import config
from credits import add_credits
from database import get_db
from db_models import PagoPAEvent, PaymentOrder, User


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pagopa", tags=["PagoPA Webhooks"])

_basic = HTTPBasic(auto_error=False)


# ============================================================================
# AUTENTICAZIONE BASIC AUTH DEDICATA
# ============================================================================

def _check_basic_auth(credentials: Optional[HTTPBasicCredentials]):
    """
    Verifica le credenziali Basic Auth fornite da SolutionPA per i webhook.
    Confronto in tempo costante per evitare timing attacks.
    """
    expected_user = config.PAGOPA_NOTIFY_AUTH_USER
    expected_pass = config.PAGOPA_NOTIFY_AUTH_PASS

    if not expected_user or not expected_pass:
        # Webhook protection non configurata: rifiutiamo qualunque chiamata.
        logger.error("[PagoPA webhook] credenziali Basic Auth non configurate")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook auth non configurata",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, expected_user)
    pass_ok = secrets.compare_digest(credentials.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


# ============================================================================
# SCHEMA REQUEST/RESPONSE (registerPayment)
# ============================================================================

class _Receipt(BaseModel):
    amountPaid: Optional[int] = Field(None, description="Importo pagato in centesimi di euro")
    bankTxRefNum: Optional[str] = None
    bankExecDate: Optional[str] = None


class RegisterPaymentRequest(BaseModel):
    """Body REST inviato da SolutionPA al webhook /esito."""
    domainId: str = Field(..., description="Codice fiscale Ente Creditore (DOMINIO)")
    creditorTxId: str = Field(..., description="IUV (Identificativo Univoco Versamento)")
    contextId: Optional[str] = Field(None, description="CCP / sessione PagoPA")
    payStatus: str = Field(..., description="EXECUTED | NOT_EXECUTED | ACCEPTED")
    pspId: Optional[str] = None
    receipt: Optional[_Receipt] = None
    receiptXML: Optional[str] = None  # RT in Base64


class RegisterPaymentResponse(BaseModel):
    """Risposta che SolutionPA si aspetta. result=OK conferma presa in carico."""
    result: str = "OK"
    errorReason: Optional[str] = None
    errorReasonAgID: Optional[str] = None
    errorMessage: Optional[str] = None


# ============================================================================
# Helpers
# ============================================================================

def _record_event(
    db: Session,
    *,
    order_id=None,
    iuv: Optional[str] = None,
    event_type: str,
    source: str,
    payload: Dict[str, Any],
    error: Optional[str] = None,
    processed: bool = True,
) -> PagoPAEvent:
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
    return ev


def _ko_response(reason: str, agid: str, message: str = "") -> RegisterPaymentResponse:
    return RegisterPaymentResponse(
        result="KO",
        errorReason=reason,
        errorReasonAgID=agid,
        errorMessage=message,
    )


# ============================================================================
# ENDPOINT REST: registerPayment
# ============================================================================

@router.post(
    "/esito",
    response_model=RegisterPaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Push esito pagamento (registerPayment) inviato da SolutionPA",
)
def receive_payment_outcome(
    payload: RegisterPaymentRequest,
    request: Request,
    credentials: HTTPBasicCredentials = Depends(_basic),
    db: Session = Depends(get_db),
):
    """
    Riceve l'esito di un pagamento PagoPA e accredita i crediti se EXECUTED.

    Idempotenza: se l'ordine e' gia' PAID, log + 200 OK senza ri-accreditare.
    Verifica dominio: rifiuta se domainId != PAGOPA_DOMINIO configurato.
    """
    _check_basic_auth(credentials)

    raw_payload = payload.model_dump()
    logger.info(
        "[PagoPA webhook] registerPayment iuv=%s status=%s domain=%s",
        payload.creditorTxId,
        payload.payStatus,
        payload.domainId,
    )

    # 1. Validazione dominio
    if payload.domainId and config.PAGOPA_DOMINIO and payload.domainId != config.PAGOPA_DOMINIO:
        _record_event(
            db,
            iuv=payload.creditorTxId,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
            error=f"domainId {payload.domainId} non corrisponde a {config.PAGOPA_DOMINIO}",
            processed=False,
        )
        db.commit()
        return _ko_response(
            "DOMAIN_ID_NOT_VALID",
            "PAA_ID_DOMINIO_ERRATO",
            f"domainId {payload.domainId} non riconosciuto",
        )

    # 2. Trova l'ordine (with FOR UPDATE per evitare race con re-delivery)
    order_q = db.query(PaymentOrder).filter(PaymentOrder.iuv == payload.creditorTxId)
    order = order_q.with_for_update().first() if db.bind.dialect.name == "postgresql" else order_q.first()

    if not order:
        # Evento orfano: non blocchiamo SolutionPA con KO permanente; logghiamo e
        # rispondiamo PAY_TX_NOT_FOUND. SolutionPA NON deve riprovare in caso di
        # IUV sconosciuto (pagamento mai esistito lato Ente).
        _record_event(
            db,
            iuv=payload.creditorTxId,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
            error="IUV non trovato",
            processed=False,
        )
        db.commit()
        return _ko_response(
            "PAY_TX_NOT_FOUND",
            "PAA_PAGAMENTO_SCONOSCIUTO",
            f"IUV {payload.creditorTxId} non trovato",
        )

    # 3. Idempotenza: gia' PAID -> log e OK
    if order.status == "PAID":
        _record_event(
            db,
            order_id=order.id,
            iuv=order.iuv,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
            error="re-delivery (ordine gia' PAID)",
        )
        db.commit()
        return RegisterPaymentResponse(result="OK")

    if order.status in ("REFUNDED", "CANCELED", "EXPIRED"):
        # Stati terminali non-OK: logghiamo ma non riapriamo l'ordine
        _record_event(
            db,
            order_id=order.id,
            iuv=order.iuv,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
            error=f"ordine in stato terminale {order.status}",
            processed=False,
        )
        db.commit()
        return _ko_response(
            "PAY_TX_NOT_PAYABLE1",
            "PAA_PAGAMENTO_ANNULLATO",
            f"Ordine in stato {order.status}",
        )

    # 4. Aggiorna stato in base a payStatus
    pay_status = (payload.payStatus or "").upper()
    now = datetime.utcnow()

    order.notify_received_at = now
    order.notify_payload = raw_payload
    order.context_id = payload.contextId or order.context_id

    if pay_status == "EXECUTED":
        # Successo -> accredito crediti
        amount_paid = payload.receipt.amountPaid if (payload.receipt and payload.receipt.amountPaid is not None) else order.amount_cents
        order.amount_paid_cents = amount_paid
        order.paid_at = now
        order.status = "PAID"

        # Trova l'utente
        user = db.query(User).filter(User.id == order.user_id).first()
        if not user:
            _record_event(
                db,
                order_id=order.id,
                iuv=order.iuv,
                event_type="ESITO_PUSH",
                source="rest",
                payload=raw_payload,
                error="user non trovato per l'ordine",
                processed=False,
            )
            db.commit()
            return _ko_response("INTERNAL_ERROR", "PAA_SYSTEM_ERROR", "Utente non trovato")

        # Accredita crediti (riusa add_credits, transaction_type='pagopa_purchase')
        try:
            tx = add_credits(
                user=user,
                amount=order.credits,
                description=f"Acquisto PagoPA — IUV {order.iuv} — {order.causale}",
                db=db,
                transaction_type="pagopa_purchase",
            )
            order.credits_granted_at = now
            order.credits_transaction_id = tx.id
        except Exception as e:
            logger.exception("[PagoPA webhook] errore accredito crediti per IUV %s", order.iuv)
            _record_event(
                db,
                order_id=order.id,
                iuv=order.iuv,
                event_type="ESITO_PUSH",
                source="rest",
                payload=raw_payload,
                error=f"add_credits failed: {e}",
                processed=False,
            )
            db.commit()
            # Restituisco KO temporaneo: SolutionPA riprovera'
            return _ko_response("INTERNAL_ERROR", "PAA_SYSTEM_ERROR", "Errore accredito interno")

        _record_event(
            db,
            order_id=order.id,
            iuv=order.iuv,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
        )
        db.commit()
        logger.info(
            "[PagoPA webhook] +%d crediti utente %s (IUV %s)",
            order.credits, user.username, order.iuv,
        )
        return RegisterPaymentResponse(result="OK")

    if pay_status == "NOT_EXECUTED":
        order.status = "FAILED"
        _record_event(
            db,
            order_id=order.id,
            iuv=order.iuv,
            event_type="ESITO_PUSH",
            source="rest",
            payload=raw_payload,
        )
        db.commit()
        return RegisterPaymentResponse(result="OK")

    # ACCEPTED o stati intermedi: registriamo l'evento, mantieniamo AWAITING_PAYMENT
    _record_event(
        db,
        order_id=order.id,
        iuv=order.iuv,
        event_type="ESITO_PUSH",
        source="rest",
        payload=raw_payload,
    )
    db.commit()
    return RegisterPaymentResponse(result="OK")
