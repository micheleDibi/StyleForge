"""
Utility condivise per l'analisi e il miglioramento immagini con AI.
Usato da image_enhance_routes.py e carousel_routes.py.
"""

import base64
import json
import re
import logging
from pathlib import Path

from anthropic import Anthropic
from image_processor import apply_enhancements
import config

logger = logging.getLogger(__name__)

# Anthropic client (singleton)
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

ANALYSIS_SYSTEM_PROMPT = """Sei un esperto di fotografia e post-produzione digitale con 20 anni di esperienza.
Analizza le immagini con occhio professionale e fornisci parametri di miglioramento precisi in formato JSON.
Valuta ogni aspetto: esposizione, contrasto, nitidezza, saturazione, bilanciamento colore, rumore, alte luci, ombre.
Sii conservativo: non esagerare con le correzioni. L'obiettivo e' migliorare la qualita senza stravolgere l'immagine.
Rispondi SOLO con JSON valido, senza testo aggiuntivo, senza markdown code blocks."""

ANALYSIS_USER_PROMPT = """Analizza questa immagine e determina i migliori parametri di miglioramento per ottenere la massima qualita.
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


def parse_claude_json_response(text: str) -> dict:
    """Estrai il JSON dalla risposta di Claude, con fallback."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning(f"Impossibile parsare risposta Claude, uso parametri default. Risposta: {text[:200]}")
    return DEFAULT_PARAMS.copy()


def validate_enhancement_params(params: dict) -> dict:
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


def analyze_image_with_claude(image_bytes: bytes, media_type: str) -> dict:
    """
    Analizza un'immagine con Claude Vision e restituisce i parametri di enhancement.

    Args:
        image_bytes: Bytes dell'immagine
        media_type: MIME type (es. "image/jpeg")

    Returns:
        dict con parametri validati di enhancement + "analysis" string
    """
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    try:
        logger.info(f"Invio immagine a Claude Vision per analisi ({len(image_bytes)} bytes)")
        response = _client.messages.create(
            model=config.IMAGE_ENHANCE_MODEL,
            max_tokens=1024,
            system=ANALYSIS_SYSTEM_PROMPT,
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
                        "text": ANALYSIS_USER_PROMPT
                    }
                ]
            }]
        )

        raw_text = response.content[0].text
        logger.info(f"Risposta Claude ricevuta: {len(raw_text)} caratteri")
        params = parse_claude_json_response(raw_text)

    except Exception as e:
        logger.error(f"Errore Claude Vision: {e}")
        logger.info("Uso parametri di fallback")
        params = DEFAULT_PARAMS.copy()

    return validate_enhancement_params(params)


def enhance_image_bytes(image_bytes: bytes, media_type: str, output_format: str = "JPEG") -> tuple:
    """
    Pipeline completa: analisi AI + applicazione enhancement.

    Args:
        image_bytes: Bytes dell'immagine originale
        media_type: MIME type dell'immagine
        output_format: Formato output Pillow (JPEG, PNG, WEBP)

    Returns:
        tuple (enhanced_bytes, analysis_text, params_dict)
    """
    params = analyze_image_with_claude(image_bytes, media_type)
    analysis = params.pop("analysis", "")

    enhanced_bytes = apply_enhancements(image_bytes, params, output_format)

    return enhanced_bytes, analysis, params


def get_media_type_for_url(url: str) -> str:
    """Determina il media type dall'URL dell'immagine."""
    url_lower = url.lower().split('?')[0]
    if url_lower.endswith('.png'):
        return "image/png"
    elif url_lower.endswith('.webp'):
        return "image/webp"
    return "image/jpeg"


def get_output_format_for_media_type(media_type: str) -> str:
    """Determina il formato output Pillow dal media type."""
    if media_type == "image/png":
        return "PNG"
    elif media_type == "image/webp":
        return "WEBP"
    return "JPEG"
