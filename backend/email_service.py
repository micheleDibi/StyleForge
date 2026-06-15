"""
Servizio email + token monouso per StyleForge.

- Token monouso su DB (tabella email_tokens): si salva solo lo SHA-256 del token
  grezzo; il raw viene inserito nel link inviato via email.
- Invio email con smtplib (stdlib). OVH: STARTTLS su porta 587 (465 non utilizzabile).
  Se SMTP non è configurato (SMTP_HOST vuoto) il link viene loggato invece di
  inviare l'email (utile in sviluppo). L'invio non solleva mai eccezioni: va
  usato in BackgroundTasks con soli argomenti stringa (nessuna Session).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from sqlalchemy.orm import Session

import config
from db_models import EmailToken, User

logger = logging.getLogger(__name__)

# TTL per scopo del token
PURPOSE_TTL = {
    "verify": timedelta(hours=24),
    "set_password": timedelta(hours=72),
    "reset": timedelta(hours=1),
}

# Path frontend per ogni scopo (per costruire il link)
PURPOSE_PATH = {
    "verify": "/verify-email",
    "set_password": "/set-password",
    "reset": "/reset-password",
}


# ============================================================================
# Token monouso
# ============================================================================

def _utcnow() -> datetime:
    """Adesso in UTC, timezone-AWARE (la colonna expires_at è TIMESTAMPTZ)."""
    return datetime.now(timezone.utc)


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalizza a UTC aware: i TIMESTAMPTZ tornano aware, ma se per qualche
    motivo arrivasse un naive lo trattiamo come UTC. Evita il
    'can't compare offset-naive and offset-aware datetimes'."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_email_token(db: Session, user_id, purpose: str) -> str:
    """Crea un token monouso, ne salva l'hash e ritorna il token grezzo (per il link)."""
    ttl = PURPOSE_TTL.get(purpose, timedelta(hours=24))
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        purpose=purpose,
        expires_at=_utcnow() + ttl,
    ))
    db.commit()
    return raw


def consume_email_token(db: Session, raw: str, purpose: str) -> Optional[User]:
    """Valida e consuma (monouso) un token. Ritorna l'utente o None se non valido."""
    if not raw:
        return None
    tok = (
        db.query(EmailToken)
        .filter(EmailToken.token_hash == _hash_token(raw), EmailToken.purpose == purpose)
        .first()
    )
    if not tok or tok.used_at is not None or _as_aware_utc(tok.expires_at) < _utcnow():
        return None
    tok.used_at = _utcnow()
    user = db.query(User).filter(User.id == tok.user_id).first()
    db.commit()
    return user


def build_link(purpose: str, raw_token: str) -> str:
    """Costruisce il link assoluto al frontend per lo scopo dato."""
    path = PURPOSE_PATH.get(purpose, "/")
    base = config.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}{path}?token={raw_token}"


# ============================================================================
# Invio email (smtplib, STARTTLS/SSL configurabile)
# ============================================================================

def _send_email(to_addr: str, subject: str, text_body: str, html_body: str) -> None:
    """Invia un'email. Non solleva mai: logga eventuali errori. Se SMTP non è
    configurato, logga il contenuto (così i link sono testabili in sviluppo)."""
    if not config.SMTP_HOST:
        logger.warning("[EMAIL] SMTP non configurato — email NON inviata a %s.\nOggetto: %s\n%s",
                       to_addr, subject, text_body)
        return

    msg = EmailMessage()
    msg["From"] = formataddr((config.MAIL_FROM_NAME, config.MAIL_FROM))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        if config.SMTP_USE_SSL:
            # Porta 465 (SSL implicito) — non usato su OVH, ma supportato.
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            # STARTTLS su porta 587 (default, OVH).
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
        logger.info("[EMAIL] inviata a %s (%s)", to_addr, subject)
    except Exception:
        logger.exception("[EMAIL] invio fallito a %s", to_addr)


def _layout(title: str, intro: str, button_label: str, link: str, footer: str) -> tuple[str, str]:
    """Costruisce (text, html) per un'email con un pulsante-link."""
    text = (
        f"{title}\n\n{intro}\n\n{button_label}: {link}\n\n{footer}\n\n— StyleForge"
    )
    html = f"""\
<!DOCTYPE html>
<html lang="it"><body style="margin:0;background:#f8fafc;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
  <div style="max-width:520px;margin:0 auto;padding:32px 24px;">
    <h1 style="font-size:20px;margin:0 0 16px;">{title}</h1>
    <p style="font-size:15px;line-height:1.6;color:#334155;margin:0 0 24px;">{intro}</p>
    <p style="margin:0 0 28px;">
      <a href="{link}" style="display:inline-block;background:#f97316;color:#fff;text-decoration:none;
         font-weight:600;padding:12px 24px;border-radius:10px;font-size:15px;">{button_label}</a>
    </p>
    <p style="font-size:13px;color:#64748b;line-height:1.6;margin:0 0 8px;">
      Se il pulsante non funziona, copia e incolla questo link nel browser:<br>
      <a href="{link}" style="color:#f97316;word-break:break-all;">{link}</a>
    </p>
    <p style="font-size:13px;color:#94a3b8;line-height:1.6;margin:24px 0 0;border-top:1px solid #e2e8f0;padding-top:16px;">{footer}</p>
    <p style="font-size:12px;color:#cbd5e1;margin:16px 0 0;">— StyleForge</p>
  </div>
</body></html>"""
    return text, html


def send_verification_email(to_addr: str, full_name: str, link: str) -> None:
    """Email di conferma registrazione (self-registration)."""
    name = full_name or "ciao"
    text, html = _layout(
        title="Conferma la tua email",
        intro=f"{name}, grazie per esserti registrato su StyleForge. "
              "Conferma il tuo indirizzo email per attivare l'accesso al tuo account.",
        button_label="Conferma email",
        link=link,
        footer="Il link è valido per 24 ore. Se non hai richiesto tu la registrazione, ignora questa email.",
    )
    _send_email(to_addr, "Conferma la tua email — StyleForge", text, html)


def send_invite_email(to_addr: str, full_name: str, link: str) -> None:
    """Email di invito (utente creato da admin): imposta la password."""
    name = full_name or "ciao"
    text, html = _layout(
        title="Imposta la tua password",
        intro=f"{name}, è stato creato un account StyleForge per te. "
              "Imposta la tua password per attivare l'account e accedere.",
        button_label="Imposta password",
        link=link,
        footer="Il link è valido per 72 ore. Se non ti aspettavi questa email, ignorala.",
    )
    _send_email(to_addr, "Sei stato invitato su StyleForge — Imposta la password", text, html)


def send_reset_email(to_addr: str, full_name: str, link: str) -> None:
    """Email di reset password (password dimenticata)."""
    name = full_name or "ciao"
    text, html = _layout(
        title="Reimposta la tua password",
        intro=f"{name}, abbiamo ricevuto una richiesta di reimpostazione della password "
              "per il tuo account StyleForge. Clicca qui sotto per sceglierne una nuova.",
        button_label="Reimposta password",
        link=link,
        footer="Il link è valido per 1 ora. Se non hai richiesto tu il reset, ignora questa email: la password non verrà cambiata.",
    )
    _send_email(to_addr, "Reimposta la tua password — StyleForge", text, html)
