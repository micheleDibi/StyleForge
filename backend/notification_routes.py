"""
Router FastAPI per le notifiche in-app (centro notifiche / campanella).

Endpoint utente:
  GET  /api/notifications              elenco recente + conteggio non letti
  GET  /api/notifications/unread-count solo il conteggio (per il badge, polling)
  POST /api/notifications/{id}/read    segna una notifica come letta
  POST /api/notifications/read-all     segna tutte come lette
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_active_user
from db_models import Notification, User
from models import NotificationItem, NotificationListResponse, UnreadCountResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _unread(db: Session, user_id) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .count()
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return NotificationListResponse(
        notifications=[NotificationItem(**n.to_dict()) for n in rows],
        unread_count=_unread(db, current_user.id),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return UnreadCountResponse(unread_count=_unread(db, current_user.id))


@router.post("/{notif_id}/read")
def mark_read(
    notif_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        n = db.query(Notification).filter(
            Notification.id == UUID(notif_id),
            Notification.user_id == current_user.id,
        ).first()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="ID notifica non valido")
    if not n:
        raise HTTPException(status_code=404, detail="Notifica non trovata")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.commit()
    return {"message": "ok"}


@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True, "read_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    return {"message": "ok"}
