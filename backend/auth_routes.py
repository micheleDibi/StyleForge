"""
Router per gli endpoint di autenticazione.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from auth import (
    UserCreate, UserLogin, UserResponse, UserUpdate, PasswordChange, Token,
    create_access_token, create_refresh_token, decode_token,
    get_user_by_email, get_user_by_username, get_user_by_id,
    authenticate_user, create_user, update_user, change_password, update_last_login,
    save_refresh_token, get_refresh_token, revoke_refresh_token, revoke_all_user_tokens,
    get_current_user, get_current_active_user,
    verify_password, build_user_response,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)
from db_models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# REGISTRATION
# ============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Registra un nuovo utente.

    - **email**: Email univoca dell'utente
    - **username**: Username univoco
    - **password**: Password (minimo 8 caratteri consigliati)
    - **full_name**: Nome completo (opzionale)
    """
    # Verifica che email non sia già in uso
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata"
        )

    # Verifica che username non sia già in uso
    if get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username già in uso"
        )

    # Validazione password
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La password deve essere di almeno 6 caratteri"
        )

    # Crea l'utente (con ruolo default 'user' assegnato automaticamente)
    user = create_user(db, user_data)

    return build_user_response(user, db)


# ============================================================================
# LOGIN
# ============================================================================

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Effettua il login e restituisce i token JWT.

    - **username**: Username o email dell'utente
    - **password**: Password dell'utente
    """
    user = authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabilitato"
        )

    # Aggiorna ultimo login
    update_last_login(db, user)

    # Crea i token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Salva il refresh token nel database
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    save_refresh_token(db, user.id, refresh_token, expires_at)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/login/form", response_model=Token)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login con OAuth2 form (per compatibilità con Swagger UI).
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabilitato"
        )

    # Aggiorna ultimo login
    update_last_login(db, user)

    # Crea i token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Salva il refresh token nel database
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    save_refresh_token(db, user.id, refresh_token, expires_at)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


# ============================================================================
# TOKEN REFRESH
# ============================================================================

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """
    Rinnova l'access token usando il refresh token.
    """
    # Verifica che il refresh token sia valido nel database
    db_token = get_refresh_token(db, refresh_token)
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido o revocato"
        )

    # Verifica che non sia scaduto
    if db_token.expires_at < datetime.now(timezone.utc):
        revoke_refresh_token(db, refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token scaduto"
        )

    # Decodifica il token per ottenere i dati utente
    token_data = decode_token(refresh_token)
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido"
        )

    # Verifica che l'utente esista ancora
    user = get_user_by_id(db, UUID(token_data.user_id))
    if not user or not user.is_active:
        revoke_refresh_token(db, refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disabilitato"
        )

    # Revoca il vecchio refresh token
    revoke_refresh_token(db, refresh_token)

    # Crea nuovi token
    new_access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Salva il nuovo refresh token
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    save_refresh_token(db, user.id, new_refresh_token, expires_at)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


# ============================================================================
# LOGOUT
# ============================================================================

@router.post("/logout")
async def logout(
    refresh_token: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Effettua il logout revocando il refresh token.
    """
    if refresh_token:
        revoke_refresh_token(db, refresh_token)

    return {"message": "Logout effettuato con successo"}


@router.post("/logout/all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Effettua il logout da tutti i dispositivi revocando tutti i refresh token.
    """
    count = revoke_all_user_tokens(db, current_user.id)
    return {"message": f"Logout effettuato da {count} sessioni"}


# ============================================================================
# USER PROFILE
# ============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Restituisce il profilo dell'utente corrente con ruolo, crediti e permessi.
    """
    return build_user_response(current_user, db)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Aggiorna il profilo dell'utente corrente.
    """
    # Verifica che la nuova email non sia già in uso
    if user_data.email and user_data.email != current_user.email:
        if get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email già in uso"
            )

    updated_user = update_user(db, current_user, user_data)

    return build_user_response(updated_user, db)


@router.post("/me/change-password")
async def change_user_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cambia la password dell'utente corrente.
    """
    # Verifica la password attuale
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password attuale non corretta"
        )

    # Validazione nuova password
    if len(password_data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nuova password deve essere di almeno 6 caratteri"
        )

    # Cambia la password
    change_password(db, current_user, password_data.new_password)

    # Revoca tutti i refresh token (logout da tutti i dispositivi)
    revoke_all_user_tokens(db, current_user.id)

    return {"message": "Password cambiata con successo. Effettua nuovamente il login."}


# ============================================================================
# ACCOUNT DELETION
# ============================================================================

@router.delete("/me")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Elimina l'account dell'utente corrente.
    Richiede la password per conferma.
    """
    # Verifica la password
    if not verify_password(password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password non corretta"
        )

    # Revoca tutti i token
    revoke_all_user_tokens(db, current_user.id)

    # Elimina l'utente (cascade eliminerà sessioni e job)
    db.delete(current_user)
    db.commit()

    return {"message": "Account eliminato con successo"}
