"""
Autenticazione via API Key per accesso programmatico esterno.
"""

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional
from threading import Lock

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session, joinedload

from database import get_db
from db_models import APIKey, User

# Header di autenticazione
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

API_KEY_PREFIX = "sf_k_"


def generate_api_key() -> tuple:
    """
    Genera una nuova API key.
    Returns: (full_key, key_hash, key_prefix)
    """
    random_part = secrets.token_hex(20)  # 40 hex chars
    full_key = f"{API_KEY_PREFIX}{random_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = f"{API_KEY_PREFIX}{random_part[:8]}"
    return full_key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    """Calcola hash SHA-256 di una API key."""
    return hashlib.sha256(key.encode()).hexdigest()


class RateLimiter:
    """Rate limiter sliding window in-memory per API key."""

    def __init__(self):
        self._requests: dict = defaultdict(list)
        self._lock = Lock()

    def check(self, key_hash: str, limit: int, window: int = 60) -> tuple:
        """
        Verifica se la richiesta e' permessa.
        Returns: (allowed: bool, remaining: int)
        """
        now = time.time()
        with self._lock:
            self._requests[key_hash] = [
                t for t in self._requests[key_hash] if t > now - window
            ]
            if len(self._requests[key_hash]) >= limit:
                return False, 0
            self._requests[key_hash].append(now)
            remaining = limit - len(self._requests[key_hash])
            return True, remaining


rate_limiter = RateLimiter()


async def get_api_key_user(
    api_key: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency FastAPI: valida l'header X-API-Key e ritorna l'utente associato.
    Controlla: esistenza, stato attivo, scadenza, rate limit, utente attivo.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-API-Key mancante"
        )

    if not api_key.startswith(API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato API key non valido"
        )

    key_hash = hash_api_key(api_key)
    db_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key non valida"
        )

    if not db_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key revocata"
        )

    if db_key.expires_at and db_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key scaduta"
        )

    # Rate limiting
    allowed, remaining = rate_limiter.check(key_hash, db_key.rate_limit_per_minute)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit superato",
            headers={"Retry-After": "60"}
        )

    # Aggiorna ultimo utilizzo
    db_key.last_used_at = datetime.utcnow()
    db.commit()

    # Carica utente
    user = db.query(User).options(joinedload(User.role)).filter(
        User.id == db_key.user_id
    ).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account utente disabilitato"
        )

    return user
