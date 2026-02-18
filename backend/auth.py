"""
Sistema di autenticazione JWT per StyleForge.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session, joinedload

from database import get_db
from db_models import User, RefreshToken, Role, RolePermission, UserPermission
from dotenv import load_dotenv

load_dotenv()

# Configurazione JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserCreate(BaseModel):
    """Schema per la registrazione utente."""
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema per il login."""
    username: str  # Può essere username o email
    password: str


class UserResponse(BaseModel):
    """Schema per la risposta utente."""
    id: str
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    role: Optional[str] = None
    credits: int = 0
    permissions: list = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema per aggiornamento profilo utente."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    """Schema per cambio password."""
    current_password: str
    new_password: str


class Token(BaseModel):
    """Schema per il token JWT."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Dati estratti dal token."""
    user_id: Optional[str] = None
    username: Optional[str] = None


# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Genera l'hash di una password."""
    return pwd_context.hash(password)


# ============================================================================
# TOKEN UTILITIES
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un access token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un refresh token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """Decodifica un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, username=username)
    except JWTError:
        return None


# ============================================================================
# USER OPERATIONS
# ============================================================================

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Trova un utente per email."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Trova un utente per username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Trova un utente per ID."""
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Autentica un utente tramite username/email e password."""
    # Prova prima con username
    user = get_user_by_username(db, username)
    if not user:
        # Prova con email
        user = get_user_by_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, user_data: UserCreate) -> User:
    """Crea un nuovo utente con il ruolo default ('user')."""
    hashed_password = get_password_hash(user_data.password)

    # Trova il ruolo default
    default_role = db.query(Role).filter(Role.is_default == True).first()

    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role_id=default_role.id if default_role else None,
        credits=0
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================================================
# PERMISSIONS SYSTEM
# ============================================================================

def get_effective_permissions(user: User, db: Session) -> list:
    """
    Calcola i permessi effettivi di un utente combinando ruolo + override.

    Logica:
    1. Se admin -> tutti i permessi
    2. Parti dai permessi del ruolo
    3. Applica override utente (granted=True aggiunge, granted=False rimuove)

    Returns:
        Lista di permission_code effettivi (es. ['train', 'thesis', 'generate'])
    """
    from credits import PERMISSION_CODES

    # Admin ha tutti i permessi
    if user.is_admin or (user.role and user.role.name == 'admin'):
        return PERMISSION_CODES.copy()

    # Permessi del ruolo
    role_perms = set()
    if user.role_id:
        role_permissions = db.query(RolePermission).filter(
            RolePermission.role_id == user.role_id
        ).all()
        role_perms = {rp.permission_code for rp in role_permissions}

    # Override utente
    user_overrides = db.query(UserPermission).filter(
        UserPermission.user_id == user.id
    ).all()

    effective_perms = set(role_perms)
    for override in user_overrides:
        if override.granted:
            effective_perms.add(override.permission_code)
        else:
            effective_perms.discard(override.permission_code)

    return sorted(list(effective_perms))


def build_user_response(user: User, db: Session) -> UserResponse:
    """
    Costruisce la risposta utente completa con ruolo, crediti e permessi.
    """
    permissions = get_effective_permissions(user, db)
    role_name = user.role.name if user.role else None

    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        role=role_name,
        credits=user.credits if not (user.is_admin or (user.role and user.role.name == 'admin')) else -1,  # -1 = infiniti
        permissions=permissions,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login
    )


def require_permission(permission_code: str):
    """
    FastAPI dependency factory che verifica che l'utente abbia un permesso specifico.

    Uso:
        @router.post("/generate")
        async def generate(user: User = Depends(require_permission('generate'))):
            ...
    """
    async def dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Admin ha sempre accesso
        if current_user.is_admin or (current_user.role and current_user.role.name == 'admin'):
            return current_user

        # Controlla override utente (priorita' massima)
        user_override = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.permission_code == permission_code
        ).first()

        if user_override is not None:
            if user_override.granted:
                return current_user
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Non hai il permesso per questa funzionalita'"
                )

        # Nessun override -> controlla permessi del ruolo
        if current_user.role_id:
            role_perm = db.query(RolePermission).filter(
                RolePermission.role_id == current_user.role_id,
                RolePermission.permission_code == permission_code
            ).first()

            if role_perm:
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Non hai il permesso per questa funzionalita'"
        )

    return dependency


def update_user(db: Session, user: User, user_data: UserUpdate) -> User:
    """Aggiorna i dati di un utente."""
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.email is not None:
        user.email = user_data.email
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, new_password: str) -> User:
    """Cambia la password di un utente."""
    user.hashed_password = get_password_hash(new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: User) -> None:
    """Aggiorna il timestamp dell'ultimo login."""
    user.last_login = datetime.utcnow()
    db.commit()


# ============================================================================
# REFRESH TOKEN OPERATIONS
# ============================================================================

def save_refresh_token(db: Session, user_id: UUID, token: str, expires_at: datetime) -> RefreshToken:
    """Salva un refresh token nel database."""
    db_token = RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """Trova un refresh token."""
    return db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.revoked == False
    ).first()


def revoke_refresh_token(db: Session, token: str) -> bool:
    """Revoca un refresh token."""
    db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if db_token:
        db_token.revoked = True
        db.commit()
        return True
    return False


def revoke_all_user_tokens(db: Session, user_id: UUID) -> int:
    """Revoca tutti i refresh token di un utente."""
    result = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()
    return result


def cleanup_expired_tokens(db: Session) -> int:
    """Rimuove i token scaduti o revocati."""
    result = db.query(RefreshToken).filter(
        (RefreshToken.expires_at < datetime.utcnow()) | (RefreshToken.revoked == True)
    ).delete()
    db.commit()
    return result


# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency per ottenere l'utente corrente dal token JWT.
    Carica anche il ruolo (eager loading).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(token)
    if token_data is None or token_data.user_id is None:
        raise credentials_exception

    try:
        user_id = UUID(token_data.user_id)
    except ValueError:
        raise credentials_exception

    # Eager load del ruolo per evitare query N+1
    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utente disabilitato"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency per ottenere l'utente corrente attivo.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utente disabilitato"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency per ottenere l'utente corrente solo se è admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permessi insufficienti"
        )
    return current_user


# ============================================================================
# OPTIONAL AUTH DEPENDENCY
# ============================================================================

async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency opzionale per ottenere l'utente corrente.
    Ritorna None se il token non è valido o assente.
    """
    if not token:
        return None

    token_data = decode_token(token)
    if token_data is None or token_data.user_id is None:
        return None

    try:
        user_id = UUID(token_data.user_id)
    except ValueError:
        return None

    user = get_user_by_id(db, user_id)
    return user if user and user.is_active else None
