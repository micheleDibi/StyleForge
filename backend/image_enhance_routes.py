"""
Router FastAPI per il miglioramento immagini con AI.
Analisi tramite Claude Opus 4.6 (vision) + elaborazione con Pillow.
"""

import base64
import json
import re
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from anthropic import Anthropic
from sqlalchemy.orm import Session

from auth import require_permission
from db_models import User
from database import get_db
from credits import estimate_credits, deduct_credits
from image_processor import apply_enhancements
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image", tags=["Image Enhancement"])

# Anthropic client
_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Mapping estensioni -> media type
MEDIA_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# Mapping estensioni -> formato Pillow
FORMAT_MAP = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}

SYSTEM_PROMPT = """Sei un esperto di fotografia e post-produzione digitale con 20 anni di esperienza.
Analizza le immagini con occhio professionale e fornisci parametri di miglioramento precisi in formato JSON.
Valuta ogni aspetto: esposizione, contrasto, nitidezza, saturazione, bilanciamento colore, rumore, alte luci, ombre.
Sii conservativo: non esagerare con le correzioni. L'obiettivo e' migliorare la qualita senza stravolgere l'immagine.
Rispondi SOLO con JSON valido, senza testo aggiuntivo, senza markdown code blocks."""

USER_PROMPT = """Analizza questa immagine e determina i migliori parametri di miglioramento per ottenere la massima qualita.
Valuta attentamente: esposizione, contrasto, nitidezza, saturazione, bilanciamento colore, rumore, e qualsiasi altro aspetto migliorabile.

Rispondi con SOLO questo JSON (nessun testo aggiuntivo, nessun code block):
{
  "brightness": <float, 0.5-2.0, 1.0=nessun cambio>,
  "contrast": <float, 0.5-2.0, 1.0=nessun cambio>,
  "sharpness": <float, 0.5-3.0, 1.0=nessun cambio>,
  "color_saturation": <float, 0.5-2.0, 1.0=nessun cambio>,
  "warmth": <float, -30 a +30, 0=nessun cambio. Positivo=piu caldo, negativo=piu freddo>,
  "highlights": <float, -50 a +50, 0=nessun cambio. Negativo=recupera alte luci bruciate>,
  "shadows": <float, -50 a +50, 0=nessun cambio. Positivo=schiarisci ombre>,
  "noise_reduction": <stringa, "none"|"light"|"medium"|"heavy">,
  "auto_levels": <boolean, true se i livelli tonali necessitano ribilanciamento>,
  "vibrance": <float, 0.5-2.0, 1.0=nessun cambio>,
  "analysis": "<breve descrizione in italiano dei problemi identificati e delle correzioni applicate>"
}"""

# Parametri di fallback se Claude non restituisce JSON valido
DEFAULT_PARAMS = {
    "brightness": 1.05,
    "contrast": 1.1,
    "sharpness": 1.3,
    "color_saturation": 1.05,
    "warmth": 0,
    "highlights": 0,
    "shadows": 10,
    "noise_reduction": "light",
    "auto_levels": True,
    "vibrance": 1.1,
    "analysis": "Applicati miglioramenti standard: leggero aumento di contrasto, nitidezza e saturazione."
}


def _parse_claude_response(text: str) -> dict:
    """Estrai il JSON dalla risposta di Claude, con fallback."""
    # Prova parsing diretto
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Prova a estrarre JSON dal testo (potrebbe essere wrappato in markdown)
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning(f"Impossibile parsare risposta Claude, uso parametri default. Risposta: {text[:200]}")
    return DEFAULT_PARAMS.copy()


def _validate_params(params: dict) -> dict:
    """Valida e normalizza i parametri di enhancement."""
    validated = {}
    validated["brightness"] = max(0.5, min(2.0, float(params.get("brightness", 1.0))))
    validated["contrast"] = max(0.5, min(2.0, float(params.get("contrast", 1.0))))
    validated["sharpness"] = max(0.5, min(3.0, float(params.get("sharpness", 1.0))))
    validated["color_saturation"] = max(0.5, min(2.0, float(params.get("color_saturation", 1.0))))
    validated["warmth"] = max(-30, min(30, float(params.get("warmth", 0))))
    validated["highlights"] = max(-50, min(50, float(params.get("highlights", 0))))
    validated["shadows"] = max(-50, min(50, float(params.get("shadows", 0))))

    noise = params.get("noise_reduction", "none")
    validated["noise_reduction"] = noise if noise in ("none", "light", "medium", "heavy") else "none"

    validated["auto_levels"] = bool(params.get("auto_levels", False))
    validated["vibrance"] = max(0.5, min(2.0, float(params.get("vibrance", 1.0))))
    validated["analysis"] = str(params.get("analysis", ""))

    return validated


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

    # Encode immagine per Claude Vision
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    media_type = MEDIA_TYPE_MAP.get(ext, "image/jpeg")

    # Analisi Claude Vision
    try:
        logger.info(f"Invio immagine a Claude Vision per analisi ({original_size} bytes)")
        response = _client.messages.create(
            model=config.IMAGE_ENHANCE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        }
                    },
                    {
                        "type": "text",
                        "text": USER_PROMPT
                    }
                ]
            }]
        )

        raw_text = response.content[0].text
        logger.info(f"Risposta Claude ricevuta: {len(raw_text)} caratteri")
        params = _parse_claude_response(raw_text)

    except Exception as e:
        logger.error(f"Errore Claude Vision: {e}")
        logger.info("Uso parametri di fallback")
        params = DEFAULT_PARAMS.copy()

    # Valida parametri
    params = _validate_params(params)
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
