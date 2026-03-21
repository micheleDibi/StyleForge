"""
Video Generation Routes (Admin-only).

Image-to-Video generation using MiniMax API.
"""

import json
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import Response, StreamingResponse
from jose import JWTError, jwt

from auth import get_current_admin_user, SECRET_KEY, ALGORITHM
from db_models import User
from minimax_service import minimax_service
import config

router = APIRouter(prefix="/api/video", tags=["video"])

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
    url: str = Query(..., description="MiniMax video URL"),
    token: str = Query(..., description="JWT token for auth"),
    request: Request = None,
):
    """
    Stream video from MiniMax URL to avoid CORS issues.
    Uses JWT token as query param since <video src> can't send headers.
    Supports HTTP Range requests for Safari compatibility.
    """
    # Verify JWT token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "access":
            raise HTTPException(status_code=401, detail="Token non valido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    # Download video from MiniMax
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            video_data = resp.content
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Errore download video: {e}")

    total_size = len(video_data)
    range_header = request.headers.get("range") if request else None

    if range_header:
        # Parse Range header (e.g. "bytes=0-1023")
        range_spec = range_header.strip().lower()
        if not range_spec.startswith("bytes="):
            raise HTTPException(status_code=416, detail="Invalid range")
        byte_range = range_spec[6:]
        parts = byte_range.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else total_size - 1
        end = min(end, total_size - 1)

        if start > end or start >= total_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        content_length = end - start + 1
        return Response(
            content=video_data[start:end + 1],
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Content-Disposition": "inline",
                "Cache-Control": "public, max-age=3600",
            },
        )

    # Full response (no Range header)
    return Response(
        content=video_data,
        media_type="video/mp4",
        headers={
            "Content-Length": str(total_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=3600",
        },
    )
