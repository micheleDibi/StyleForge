"""
API esterna v1 per accesso programmatico alle funzionalita' di umanizzazione.
Protetta da API key (header X-API-Key).
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from db_models import User
from api_key_auth import get_api_key_user
from session_manager import session_manager
from job_manager import job_manager
from auth import get_effective_permissions
from models import (
    ExternalHumanizeRequest, ExternalAntiAIRequest,
    ExternalJobSubmittedResponse, ExternalJobStatusResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["External API v1"])


def _check_humanize_permission(user: User, db: Session):
    """Verifica che l'utente abbia il permesso 'humanize'."""
    perms = get_effective_permissions(user, db)
    if 'humanize' not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="L'account non ha il permesso 'humanize'"
        )


@router.post("/humanize", response_model=ExternalJobSubmittedResponse)
async def external_humanize(
    request: ExternalHumanizeRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """
    Umanizzazione completa con sessione addestrata.
    Il testo viene riscritto nello stile appreso dall'autore.
    Ritorna un job_id da usare per il polling del risultato.
    """
    _check_humanize_permission(user, db)
    user_id = str(user.id)

    # Valida sessione
    if not session_manager.session_exists(request.session_id, user_id):
        raise HTTPException(status_code=404, detail="Sessione non trovata")

    client = session_manager.get_session(request.session_id, user_id)
    if not client.is_trained:
        raise HTTPException(status_code=400, detail="La sessione non e' ancora addestrata")

    # Importa task function (lazy per evitare import circolare)
    from api import humanize_content_task

    job_id = job_manager.create_job(
        session_id=request.session_id,
        user_id=user_id,
        job_type='humanization',
        task_func=humanize_content_task,
        name=f"API: Humanize ({len(request.text)} chars)",
        testo=request.text
    )
    session_manager.add_job_to_session(request.session_id, job_id)
    background_tasks.add_task(job_manager.execute_job, job_id)

    logger.info(f"API v1 humanize job {job_id} creato per utente {user.email}")

    return ExternalJobSubmittedResponse(
        job_id=job_id,
        status="pending",
        message="Job inviato. Usa GET /api/v1/jobs/{job_id} per ottenere il risultato."
    )


@router.post("/anti-ai-correct", response_model=ExternalJobSubmittedResponse)
async def external_anti_ai_correct(
    request: ExternalAntiAIRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_api_key_user),
    db: Session = Depends(get_db)
):
    """
    Correzione anti-AI (no sessione richiesta).
    Applica micro-modifiche conservative per ridurre la rilevabilita' AI.
    Ritorna un job_id da usare per il polling del risultato.
    """
    _check_humanize_permission(user, db)
    user_id = str(user.id)

    from api import anti_ai_correction_task

    job_id = job_manager.create_job(
        session_id=None,
        user_id=user_id,
        job_type='humanization',
        task_func=anti_ai_correction_task,
        name=f"API: Anti-AI ({len(request.text)} chars)",
        testo=request.text
    )
    background_tasks.add_task(job_manager.execute_job, job_id)

    logger.info(f"API v1 anti-ai-correct job {job_id} creato per utente {user.email}")

    return ExternalJobSubmittedResponse(
        job_id=job_id,
        status="pending",
        message="Job inviato. Usa GET /api/v1/jobs/{job_id} per ottenere il risultato."
    )


@router.get("/jobs/{job_id}", response_model=ExternalJobStatusResponse)
async def external_get_job(
    job_id: str,
    user: User = Depends(get_api_key_user),
):
    """
    Polling stato e risultato di un job.
    Ritorna solo job appartenenti all'utente della API key.
    """
    job_status = job_manager.get_job_status(job_id, user_id=str(user.id))
    if not job_status:
        raise HTTPException(status_code=404, detail="Job non trovato")

    return ExternalJobStatusResponse(
        job_id=job_status['job_id'],
        status=job_status['status'],
        progress=job_status.get('progress', 0),
        result=job_status.get('result'),
        error=job_status.get('error'),
        created_at=job_status['created_at'],
        completed_at=job_status.get('completed_at'),
    )
