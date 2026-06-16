"""
Helper per le notifiche in-app.

`notify()` crea una notifica per un singolo utente; `notify_admins()` per tutti
gli admin. Non sollevano mai: una notifica fallita non deve rompere l'operazione
principale (vanno chiamate DOPO il commit dell'operazione, su sessione pulita).
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from db_models import Notification, User

logger = logging.getLogger(__name__)


def notify(db: Session, user_id, type: str, title: str,
           message: Optional[str] = None, link: Optional[str] = None) -> None:
    """Crea una notifica per un utente e committa. Non solleva mai."""
    try:
        db.add(Notification(user_id=user_id, type=type, title=title, message=message, link=link))
        db.commit()
    except Exception:
        logger.exception("notify fallita per user %s (%s)", user_id, type)
        try:
            db.rollback()
        except Exception:
            pass


def notify_admins(db: Session, type: str, title: str,
                  message: Optional[str] = None, link: Optional[str] = None) -> None:
    """Crea una notifica per tutti gli admin. Non solleva mai."""
    try:
        admins = db.query(User).filter(User.is_admin == True).all()  # noqa: E712
        for a in admins:
            db.add(Notification(user_id=a.id, type=type, title=title, message=message, link=link))
        db.commit()
    except Exception:
        logger.exception("notify_admins fallita (%s)", type)
        try:
            db.rollback()
        except Exception:
            pass
