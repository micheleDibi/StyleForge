"""
Video Generation Routes (Admin-only).

Image-to-Video generation using MiniMax API.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response

import ssrf_guard
from auth import get_current_admin_user
from db_models import User
from minimax_service import minimax_service
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])

# I file_id di MiniMax sono identificatori opachi: qui basta impedire che una
# stringa arbitraria finisca nella query verso l'API.
_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

ALLOWED_EXTENSIONS = config.VIDEO_ALLOWED_EXTENSIONS
MAX_UPLOAD_SIZE = config.VIDEO_MAX_UPLOAD_SIZE


def _validate_image(file: UploadFile, file_bytes: bytes):
    """Validate uploaded image file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome file mancante")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato. Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Immagine troppo grande. Massimo: {config.VIDEO_MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )


@router.post("/generate")
async def generate_videos(
    file: UploadFile = File(...),
    prompts: str = Form(...),
    model: str = Form("MiniMax-Hailuo-2.3"),
    prompt_optimizer: bool = Form(True),
    duration: Optional[int] = Form(None),
    fast_pretreatment: Optional[bool] = Form(None),
    resolution: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin_user),
):
    """Upload an image and generate one video per prompt."""
    if not config.MINIMAX_API_KEY:
        raise HTTPException(status_code=500, detail="MINIMAX_API_KEY non configurata")

    try:
        prompt_list = json.loads(prompts)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="prompts deve essere un array JSON valido")

    if not isinstance(prompt_list, list) or len(prompt_list) == 0:
        raise HTTPException(status_code=400, detail="Inserisci almeno un prompt")

    if len(prompt_list) > 5:
        raise HTTPException(status_code=400, detail="Massimo 5 prompt per richiesta")

    file_bytes = await file.read()
    _validate_image(file, file_bytes)

    # Encode image as base64
    image_base64 = minimax_service.encode_image(file_bytes, file.filename)

    # Create one task per prompt
    tasks = []
    for prompt in prompt_list:
        prompt_text = str(prompt).strip()
        if not prompt_text:
            continue
        try:
            task_id = await minimax_service.create_video_task(
                image_base64=image_base64,
                prompt=prompt_text,
                model=model,
                prompt_optimizer=prompt_optimizer,
                duration=duration,
                fast_pretreatment=fast_pretreatment,
                resolution=resolution,
            )
            tasks.append({"task_id": task_id, "prompt": prompt_text})
        except Exception as e:
            tasks.append({"task_id": None, "prompt": prompt_text, "error": str(e)})

    return {"tasks": tasks}


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_admin_user),
):
    """Poll the status of a single video generation task."""
    try:
        result = await minimax_service.query_task_status(task_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Errore query MiniMax: {e}")

    return result


@router.get("/status")
async def get_tasks_status(
    task_ids: str = Query(..., description="Comma-separated task IDs"),
    current_user: User = Depends(get_current_admin_user),
):
    """Poll the status of multiple video generation tasks."""
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="Nessun task_id fornito")

    results = []
    for tid in ids:
        try:
            result = await minimax_service.query_task_status(tid)
            results.append(result)
        except Exception as e:
            results.append({"task_id": tid, "status": "Fail", "error": str(e)})

    return {"tasks": results}


@router.get("/proxy")
async def proxy_video(
    file_id: str = Query(..., description="MiniMax file id restituito da /status"),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Scarica il video da MiniMax ed evita al frontend il problema CORS.

    Accetta un `file_id`, MAI un URL: l'URL lo conosce gia' il server e glielo
    faceva rimandare indietro dal browser, che non ci aggiungeva nulla. Il
    risultato era una SSRF full-read (il body veniva restituito verbatim, quindi
    bastava puntare ai metadata cloud), per giunta aperta a qualsiasi utente
    autenticato: questa route faceva un jwt.decode a mano, saltando il lookup
    sul DB, il check is_active e quello di admin che le altre tre hanno.

    Il token non e' piu' un parametro di query (finiva in access log, Referer e
    cronologia): il frontend chiama con Authorization e mostra il video da blob.
    """
    if not _FILE_ID_RE.match(file_id):
        raise HTTPException(status_code=400, detail="file_id non valido")

    if not config.MINIMAX_API_KEY:
        raise HTTPException(status_code=500, detail="MINIMAX_API_KEY non configurata")

    try:
        url = await minimax_service.retrieve_file_url(file_id)
    except Exception as e:
        logger.warning("Risoluzione file_id %s fallita: %s", file_id, e)
        raise HTTPException(status_code=502, detail="Video non disponibile")

    # L'URL viene da MiniMax, non dall'utente: la guard e' difesa in profondita'
    # (se un giorno quella risposta fosse manipolata, non diventa una SSRF).
    try:
        resp = await ssrf_guard.safe_get(
            url,
            max_bytes=config.VIDEO_MAX_PROXY_BYTES,
            deadline_s=config.VIDEO_PROXY_TIMEOUT,
        )
    except ssrf_guard.SsrfBlocked as e:
        logger.error("Destinazione video bloccata dalla guard: %s", e)
        raise HTTPException(status_code=502, detail="Destinazione video non consentita")
    except ssrf_guard.GuardError as e:
        logger.warning("Download video abortito: %s", e)
        raise HTTPException(status_code=502, detail="Errore download video")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Errore download video: {resp.status_code}")

    return Response(
        content=resp.content,
        media_type="video/mp4",
        headers={
            "Content-Length": str(len(resp.content)),
            "Content-Disposition": "inline",
            # Era "public, max-age=3600" su una risposta autenticata: proxy e CDN
            # potevano conservarla e riservirla a chiunque avesse l'URL.
            "Cache-Control": "private, no-store",
        },
    )
