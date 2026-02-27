"""
Router FastAPI per il miglioramento immagini con AI.
Analisi tramite Claude Opus 4.6 (vision) + elaborazione con Pillow.
"""

import base64
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth import require_permission
from db_models import User
from database import get_db
from credits import estimate_credits, deduct_credits
from image_utils import (
    MEDIA_TYPE_MAP, FORMAT_MAP,
    analyze_image_with_claude, validate_enhancement_params
)
from image_processor import apply_enhancements
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image", tags=["Image Enhancement"])


@router.post("/enhance")
async def enhance_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission('enhance_image')),
    db: Session = Depends(get_db),
):
    """
    Migliora la qualita di un'immagine usando analisi AI + elaborazione algoritmica.
    """
    # Validazione estensione
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome file mancante")

    ext = Path(file.filename).suffix.lower()
    if ext not in config.IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato: {ext}. Formati accettati: {', '.join(config.IMAGE_ALLOWED_EXTENSIONS)}"
        )

    # Leggi file in memoria
    image_bytes = await file.read()
    original_size = len(image_bytes)

    # Validazione dimensione
    if original_size > config.IMAGE_MAX_UPLOAD_SIZE:
        max_mb = config.IMAGE_MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Immagine troppo grande ({original_size / (1024*1024):.1f}MB). Massimo: {max_mb:.0f}MB"
        )

    if original_size == 0:
        raise HTTPException(status_code=400, detail="File vuoto")

    # Stima e deduzione crediti
    estimation = estimate_credits('enhance_image', {}, db)
    credits_needed = estimation['credits_needed']
    deduct_credits(
        user=current_user,
        amount=credits_needed,
        operation_type='enhance_image',
        description=f"Miglioramento immagine: {file.filename}",
        db=db
    )

    # Analisi e enhancement tramite modulo condiviso
    media_type = MEDIA_TYPE_MAP.get(ext, "image/jpeg")
    params = analyze_image_with_claude(image_bytes, media_type)
    analysis = params.pop("analysis", "")

    # Applica miglioramenti
    output_format = FORMAT_MAP.get(ext, "JPEG")
    try:
        enhanced_bytes = apply_enhancements(image_bytes, params, output_format)
    except Exception as e:
        logger.error(f"Errore elaborazione immagine: {e}")
        raise HTTPException(status_code=500, detail="Errore durante l'elaborazione dell'immagine")

    # Encode risultato in base64
    enhanced_base64 = base64.b64encode(enhanced_bytes).decode('utf-8')

    return JSONResponse({
        "analysis": analysis,
        "params": params,
        "image_base64": enhanced_base64,
        "format": output_format.lower(),
        "original_size": original_size,
        "enhanced_size": len(enhanced_bytes),
    })
