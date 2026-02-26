"""
Router FastAPI per gli endpoint di image enhancement.
"""

import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from models import (
    ImageEnhanceResponse,
    JobStatus, JobType
)
from db_models import User, ImageEnhancement
from database import get_db, SessionLocal
from auth import get_current_active_user, require_permission
from credits import estimate_credits, deduct_credits
from job_manager import job_manager
from image_processor import (
    get_image_info, apply_basic_enhancement, apply_upscale,
    apply_color_correction, apply_ai_enhancement, analyze_image_with_claude
)
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image", tags=["Image Enhancement"])


# ============================================================================
# UPLOAD + ENHANCE
# ============================================================================

@router.post("/enhance", response_model=ImageEnhanceResponse)
async def enhance_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    enhancement_type: str = Form("basic"),
    params: str = Form("{}"),
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Carica un'immagine e avvia il job di enhancement."""

    # Valida estensione
    ext = Path(file.filename).suffix.lower()
    if ext not in config.IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato. Formati accettati: {', '.join(config.IMAGE_ALLOWED_EXTENSIONS)}"
        )

    # Valida dimensione
    content = await file.read()
    if len(content) > config.IMAGE_MAX_UPLOAD_SIZE:
        max_mb = config.IMAGE_MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File troppo grande. Massimo: {max_mb}MB")

    # Valida tipo enhancement
    valid_types = ("basic", "ai_analysis", "upscale", "color_correction")
    if enhancement_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo enhancement non valido. Valori: {', '.join(valid_types)}"
        )

    # Parse parametri
    try:
        enhancement_params = json.loads(params)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Parametri JSON non validi")

    # Mappa tipo enhancement a operazione crediti
    credit_op_map = {
        "basic": "image_enhance_basic",
        "ai_analysis": "image_enhance_ai",
        "upscale": "image_enhance_upscale",
        "color_correction": "image_enhance_color",
    }
    credit_op = credit_op_map[enhancement_type]

    # Stima e deduzione crediti
    credit_estimate = estimate_credits(credit_op, enhancement_params, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type=credit_op,
        description=f"Image Enhancement ({enhancement_type}): {file.filename}",
        db=db
    )

    # Salva file caricato
    user_id = str(current_user.id)
    file_id = uuid.uuid4().hex[:12]
    upload_filename = f"{file_id}_{file.filename}"
    upload_path = config.IMAGE_UPLOADS_DIR / upload_filename

    with open(upload_path, "wb") as f:
        f.write(content)

    # Info immagine
    img_info = get_image_info(str(upload_path))

    # Crea record enhancement
    enhancement_id = str(uuid.uuid4())
    db_enhancement = ImageEnhancement(
        id=enhancement_id,
        job_id="pending",
        user_id=current_user.id,
        original_filename=file.filename,
        original_path=str(upload_path),
        original_width=img_info["width"],
        original_height=img_info["height"],
        original_size_bytes=img_info["size_bytes"],
        enhancement_type=enhancement_type,
        enhancement_params=enhancement_params,
    )
    db.add(db_enhancement)
    db.flush()

    # Crea job
    job_name = f"Image Enhancement ({enhancement_type}): {file.filename}"
    job_id = job_manager.create_job(
        session_id=None,
        user_id=user_id,
        job_type='image_enhancement',
        task_func=_image_enhancement_task,
        name=job_name,
        enhancement_id=enhancement_id,
        image_path=str(upload_path),
        output_dir=str(config.IMAGE_RESULTS_DIR),
        enhancement_type=enhancement_type,
        enhancement_params=enhancement_params,
        original_filename=file.filename,
    )

    # Aggiorna record con job_id
    db_enhancement.job_id = job_id
    db.commit()

    # Esegui in background
    background_tasks.add_task(job_manager.execute_job, job_id)

    return ImageEnhanceResponse(
        job_id=job_id,
        enhancement_id=enhancement_id,
        status='pending',
        message=f"Enhancement avviato. Monitora con GET /jobs/{job_id}",
        created_at=datetime.utcnow()
    )


# ============================================================================
# ANALYZE ONLY (senza enhancement)
# ============================================================================

@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Analizza immagine con Claude Vision senza applicare enhancement."""
    ext = Path(file.filename).suffix.lower()
    if ext not in config.IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato non supportato.")

    content = await file.read()
    if len(content) > config.IMAGE_MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File troppo grande.")

    # Deduzione crediti per analisi AI
    credit_estimate = estimate_credits('image_enhance_ai', {}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate['credits_needed'],
        operation_type='image_enhance_ai',
        description=f"Image AI Analysis: {file.filename}",
        db=db
    )

    # Salva temporaneamente e analizza
    temp_path = config.IMAGE_UPLOADS_DIR / f"analyze_{uuid.uuid4().hex[:8]}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        analysis = analyze_image_with_claude(str(temp_path))
        return {"analysis": analysis, "filename": file.filename}
    finally:
        temp_path.unlink(missing_ok=True)


# ============================================================================
# DOWNLOAD IMMAGINE MIGLIORATA
# ============================================================================

@router.get("/download/{job_id}")
async def download_enhanced_image(
    job_id: str,
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Scarica l'immagine migliorata."""
    enhancement = db.query(ImageEnhancement).filter(
        ImageEnhancement.job_id == job_id,
        ImageEnhancement.user_id == current_user.id
    ).first()

    if not enhancement:
        raise HTTPException(status_code=404, detail="Enhancement non trovato")

    if not enhancement.enhanced_path or not Path(enhancement.enhanced_path).exists():
        raise HTTPException(status_code=404, detail="Immagine migliorata non ancora disponibile")

    return FileResponse(
        enhancement.enhanced_path,
        filename=f"enhanced_{enhancement.original_filename}",
        media_type="application/octet-stream"
    )


# ============================================================================
# DOWNLOAD IMMAGINE ORIGINALE
# ============================================================================

@router.get("/download-original/{job_id}")
async def download_original_image(
    job_id: str,
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Scarica l'immagine originale per confronto prima/dopo."""
    enhancement = db.query(ImageEnhancement).filter(
        ImageEnhancement.job_id == job_id,
        ImageEnhancement.user_id == current_user.id
    ).first()

    if not enhancement:
        raise HTTPException(status_code=404, detail="Enhancement non trovato")

    if not Path(enhancement.original_path).exists():
        raise HTTPException(status_code=404, detail="Immagine originale non trovata")

    return FileResponse(
        enhancement.original_path,
        filename=enhancement.original_filename,
        media_type="application/octet-stream"
    )


# ============================================================================
# RISULTATO ENHANCEMENT
# ============================================================================

@router.get("/result/{job_id}")
async def get_enhancement_result(
    job_id: str,
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Dettagli del risultato enhancement."""
    enhancement = db.query(ImageEnhancement).filter(
        ImageEnhancement.job_id == job_id,
        ImageEnhancement.user_id == current_user.id
    ).first()

    if not enhancement:
        raise HTTPException(status_code=404, detail="Enhancement non trovato")

    return enhancement.to_dict()


# ============================================================================
# STORICO ENHANCEMENT UTENTE
# ============================================================================

@router.get("/history")
async def get_enhancement_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(require_permission('image_enhance')),
    db: DBSession = Depends(get_db)
):
    """Storico enhancement dell'utente."""
    enhancements = db.query(ImageEnhancement).filter(
        ImageEnhancement.user_id == current_user.id
    ).order_by(
        ImageEnhancement.created_at.desc()
    ).offset(offset).limit(limit).all()

    total = db.query(ImageEnhancement).filter(
        ImageEnhancement.user_id == current_user.id
    ).count()

    return {
        "enhancements": [e.to_dict() for e in enhancements],
        "total": total
    }


# ============================================================================
# TASK FUNCTION (eseguita dal job_manager in background)
# ============================================================================

def _image_enhancement_task(
    enhancement_id: str,
    image_path: str,
    output_dir: str,
    enhancement_type: str,
    enhancement_params: dict,
    original_filename: str,
    **kwargs
) -> str:
    """
    Funzione background per image enhancement.
    Chiamata da job_manager.execute_job().
    """
    db = SessionLocal()
    try:
        # Genera percorso output
        ext = Path(original_filename).suffix.lower()
        output_filename = f"enhanced_{uuid.uuid4().hex[:8]}_{original_filename}"
        output_path = str(Path(output_dir) / output_filename)

        ai_analysis = None

        if enhancement_type == "basic":
            result_info = apply_basic_enhancement(image_path, output_path, enhancement_params)

        elif enhancement_type == "ai_analysis":
            result_info, ai_analysis = apply_ai_enhancement(image_path, output_path, enhancement_params)

        elif enhancement_type == "upscale":
            result_info = apply_upscale(image_path, output_path, enhancement_params)

        elif enhancement_type == "color_correction":
            result_info = apply_color_correction(image_path, output_path, enhancement_params)

        else:
            raise ValueError(f"Tipo enhancement sconosciuto: {enhancement_type}")

        # Aggiorna record nel database
        enhancement = db.query(ImageEnhancement).filter(
            ImageEnhancement.id == enhancement_id
        ).first()

        if enhancement:
            enhancement.enhanced_path = output_path
            enhancement.enhanced_width = result_info.get("width")
            enhancement.enhanced_height = result_info.get("height")
            enhancement.enhanced_size_bytes = result_info.get("size_bytes")
            enhancement.completed_at = datetime.utcnow()
            if ai_analysis:
                enhancement.ai_analysis_result = ai_analysis
            db.commit()

        return json.dumps({
            "enhancement_id": enhancement_id,
            "enhanced_path": output_path,
            "ai_analysis": ai_analysis
        })

    finally:
        db.close()
