"""
Image processing engine per StyleForge.
Gestisce enhancement base, analisi AI, upscaling e correzione colore.
"""

import io
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY
# ============================================================================

def get_image_info(image_path: str) -> Dict[str, Any]:
    """Restituisce metadati base dell'immagine."""
    with Image.open(image_path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "size_bytes": Path(image_path).stat().st_size
        }


def image_to_base64(image_path: str, max_dimension: int = 1568) -> Tuple[str, str]:
    """
    Converte immagine in base64 per Claude Vision API.
    Ridimensiona se necessario per rispettare i limiti API.

    Returns:
        Tuple (base64_data, media_type)
    """
    with Image.open(image_path) as img:
        if max(img.width, img.height) > max_dimension:
            ratio = max_dimension / max(img.width, img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        if img.mode == "RGBA":
            fmt = "PNG"
        else:
            fmt = "JPEG"
            if img.mode != "RGB":
                img = img.convert("RGB")

        img.save(buffer, format=fmt, quality=95)
        buffer.seek(0)
        return base64.standard_b64encode(buffer.read()).decode("utf-8"), fmt.lower()


def _get_save_kwargs(output_path: str, img: Image.Image) -> dict:
    """Parametri di salvataggio ottimali in base all'estensione."""
    ext = Path(output_path).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        save_img = img
        if img.mode == "RGBA":
            save_img = img.convert("RGB")
        return {"format": "JPEG", "quality": 95, "optimize": True}
    elif ext == ".png":
        return {"format": "PNG", "optimize": True}
    elif ext == ".webp":
        return {"format": "WebP", "quality": 95}
    else:
        return {"format": "PNG"}


def _prepare_for_save(img: Image.Image, output_path: str) -> Image.Image:
    """Converte il modo colore se necessario per il formato di output."""
    ext = Path(output_path).suffix.lower()
    if ext in (".jpg", ".jpeg") and img.mode == "RGBA":
        return img.convert("RGB")
    return img


# ============================================================================
# BASIC ENHANCEMENTS (Pillow)
# ============================================================================

def apply_basic_enhancement(
    image_path: str,
    output_path: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Enhancement base: sharpen, denoise, contrasto, luminosita', saturazione.

    Params:
        sharpen: float (0.0 = nessun cambiamento, 1.0 = default, 2.0 = forte)
        denoise: bool o int (True = default, int = forza filtro)
        contrast: float (1.0 = nessun cambiamento, >1 = piu' contrasto)
        brightness: float (1.0 = nessun cambiamento, >1 = piu' luminoso)
        saturation: float (1.0 = nessun cambiamento, >1 = piu' saturo)
    """
    with Image.open(image_path) as img:
        original_mode = img.mode
        alpha = None
        if img.mode == "RGBA":
            alpha = img.split()[-1]
            img = img.convert("RGB")

        # Denoise (MedianFilter)
        denoise = params.get("denoise", False)
        if denoise:
            strength = denoise if isinstance(denoise, int) and denoise > 1 else 3
            if strength % 2 == 0:
                strength += 1
            img = img.filter(ImageFilter.MedianFilter(size=strength))

        # Contrasto
        contrast = params.get("contrast", 1.0)
        if isinstance(contrast, (int, float)) and contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)

        # Luminosita'
        brightness = params.get("brightness", 1.0)
        if isinstance(brightness, (int, float)) and brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(brightness)

        # Saturazione
        saturation = params.get("saturation", 1.0)
        if isinstance(saturation, (int, float)) and saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(saturation)

        # Sharpen
        sharpen = params.get("sharpen", 0.0)
        if isinstance(sharpen, (int, float)) and sharpen > 0:
            img = ImageEnhance.Sharpness(img).enhance(1.0 + sharpen)

        # Ripristina canale alpha
        if alpha is not None:
            img = img.convert("RGBA")
            r, g, b, _ = img.split()
            img = Image.merge("RGBA", (r, g, b, alpha))

        img = _prepare_for_save(img, output_path)
        save_kwargs = _get_save_kwargs(output_path, img)
        img.save(output_path, **save_kwargs)

    return get_image_info(output_path)


# ============================================================================
# UPSCALING (LANCZOS + sharpening pipeline)
# ============================================================================

def apply_upscale(
    image_path: str,
    output_path: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Upscale immagine con LANCZOS resampling + post-sharpening.

    Params:
        scale_factor: float (1.5, 2.0, 3.0, 4.0)
        sharpen_after: bool (True = applica sharpening dopo upscale)
    """
    from config import IMAGE_MAX_DIMENSION

    scale_factor = params.get("scale_factor", 2.0)
    sharpen_after = params.get("sharpen_after", True)

    with Image.open(image_path) as img:
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)

        # Limita alla dimensione massima
        if max(new_width, new_height) > IMAGE_MAX_DIMENSION:
            ratio = IMAGE_MAX_DIMENSION / max(new_width, new_height)
            new_width = int(new_width * ratio)
            new_height = int(new_height * ratio)

        img_upscaled = img.resize((new_width, new_height), Image.LANCZOS)

        # Post-sharpening per ridurre sfocatura da upscaling
        if sharpen_after:
            if img_upscaled.mode == "RGBA":
                alpha = img_upscaled.split()[-1]
                rgb = img_upscaled.convert("RGB")
                rgb = ImageEnhance.Sharpness(rgb).enhance(1.3)
                rgb = rgb.filter(
                    ImageFilter.UnsharpMask(radius=2, percent=100, threshold=2)
                )
                rgb = rgb.convert("RGBA")
                r, g, b, _ = rgb.split()
                img_upscaled = Image.merge("RGBA", (r, g, b, alpha))
            else:
                img_upscaled = ImageEnhance.Sharpness(img_upscaled).enhance(1.3)
                img_upscaled = img_upscaled.filter(
                    ImageFilter.UnsharpMask(radius=2, percent=100, threshold=2)
                )

        img_upscaled = _prepare_for_save(img_upscaled, output_path)
        save_kwargs = _get_save_kwargs(output_path, img_upscaled)
        img_upscaled.save(output_path, **save_kwargs)

    return get_image_info(output_path)


# ============================================================================
# COLOR CORRECTION (OpenCV)
# ============================================================================

def apply_color_correction(
    image_path: str,
    output_path: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Correzione colore: white balance, gamma, histogram equalization, CLAHE.

    Params:
        auto_white_balance: bool
        gamma: float (1.0 = nessun cambiamento, <1 = piu' luminoso, >1 = piu' scuro)
        histogram_equalization: bool
        clahe: bool (Contrast Limited Adaptive Histogram Equalization)
    """
    import cv2

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Impossibile leggere l'immagine: {image_path}")

    has_alpha = img.shape[2] == 4 if len(img.shape) == 3 and img.shape[2] == 4 else False
    alpha_channel = None
    if has_alpha:
        alpha_channel = img[:, :, 3]
        img = img[:, :, :3]

    # Auto White Balance (algoritmo Gray World)
    if params.get("auto_white_balance", False):
        result = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float64)
        avg_a = np.average(result[:, :, 1])
        avg_b = np.average(result[:, :, 2])
        result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * (result[:, :, 0] / 255.0) * 1.1)
        result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * (result[:, :, 0] / 255.0) * 1.1)
        result = np.clip(result, 0, 255).astype(np.uint8)
        img = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)

    # Gamma correction
    gamma = params.get("gamma", 1.0)
    if isinstance(gamma, (int, float)) and gamma != 1.0:
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255
            for i in np.arange(0, 256)
        ]).astype("uint8")
        img = cv2.LUT(img, table)

    # Histogram equalization (canale Y in YCrCb)
    if params.get("histogram_equalization", False):
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        img = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    # CLAHE (migliore dell'equalizzazione semplice)
    if params.get("clahe", False):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # Ripristina canale alpha
    if has_alpha and alpha_channel is not None:
        img = np.dstack([img, alpha_channel])

    cv2.imwrite(output_path, img)
    return get_image_info(output_path)


# ============================================================================
# AI-POWERED ANALYSIS (Claude Vision)
# ============================================================================

def analyze_image_with_claude(image_path: str) -> Dict[str, Any]:
    """
    Usa Claude Vision API per analizzare la qualita' dell'immagine
    e suggerire i parametri di enhancement ottimali.

    Returns:
        Dict con overall_quality, issues_detected, suggestions, auto_params
    """
    import anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_VISION_MODEL

    b64_data, media_type = image_to_base64(image_path)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    analysis_prompt = """Analizza questa immagine per problemi di qualita' e suggerisci miglioramenti.
Restituisci un oggetto JSON con esattamente questa struttura:
{
    "overall_quality": "poor|fair|good|excellent",
    "issues_detected": ["lista dei problemi di qualita' trovati"],
    "suggestions": [
        {"type": "sharpen|denoise|contrast|brightness|saturation|white_balance|upscale",
         "reason": "perche' questo miglioramento e' necessario",
         "priority": "high|medium|low"}
    ],
    "auto_params": {
        "sharpen": 0.0,
        "denoise": false,
        "contrast": 1.0,
        "brightness": 1.0,
        "saturation": 1.0,
        "auto_white_balance": false,
        "gamma": 1.0,
        "clahe": false
    }
}

Regole per auto_params:
- sharpen: 0.0-2.0 (0 = nessuno, 1.0 = moderato, 2.0 = forte)
- denoise: true solo se l'immagine ha rumore visibile
- contrast: 0.8-1.5 (1.0 = invariato)
- brightness: 0.8-1.3 (1.0 = invariata)
- saturation: 0.8-1.5 (1.0 = invariata)
- auto_white_balance: true solo se i colori sono sbilanciati
- gamma: 0.7-1.5 (1.0 = invariato)
- clahe: true solo se c'e' poco contrasto locale

Output SOLO il JSON, senza altro testo."""

    message = client.messages.create(
        model=CLAUDE_VISION_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": f"image/{media_type}",
                        "data": b64_data
                    }
                },
                {
                    "type": "text",
                    "text": analysis_prompt
                }
            ]
        }]
    )

    response_text = message.content[0].text.strip()

    # Rimuovi code blocks markdown se presenti
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Rimuovi prima e ultima riga (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Errore parsing risposta Claude Vision: {e}")
        # Fallback: parametri conservativi
        return {
            "overall_quality": "fair",
            "issues_detected": ["Impossibile analizzare automaticamente"],
            "suggestions": [
                {"type": "sharpen", "reason": "Miglioramento generico", "priority": "medium"}
            ],
            "auto_params": {
                "sharpen": 0.5,
                "denoise": False,
                "contrast": 1.1,
                "brightness": 1.0,
                "saturation": 1.05,
                "auto_white_balance": False,
                "gamma": 1.0,
                "clahe": False
            }
        }


def apply_ai_enhancement(
    image_path: str,
    output_path: str,
    params: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Enhancement AI-powered: analizza con Claude Vision, poi applica i parametri suggeriti.

    Returns:
        Tuple (image_info, ai_analysis)
    """
    # Step 1: Analizza con Claude Vision
    ai_analysis = analyze_image_with_claude(image_path)

    # Step 2: Applica i parametri auto-generati
    auto_params = ai_analysis.get("auto_params", {})

    # Enhancement base dai suggerimenti AI
    basic_params = {
        "sharpen": auto_params.get("sharpen", 0),
        "denoise": auto_params.get("denoise", False),
        "contrast": auto_params.get("contrast", 1.0),
        "brightness": auto_params.get("brightness", 1.0),
        "saturation": auto_params.get("saturation", 1.0),
    }
    image_info = apply_basic_enhancement(image_path, output_path, basic_params)

    # Correzione colore se suggerita dall'AI
    needs_color = (
        auto_params.get("auto_white_balance", False) or
        auto_params.get("gamma", 1.0) != 1.0 or
        auto_params.get("clahe", False)
    )

    if needs_color:
        color_params = {
            "auto_white_balance": auto_params.get("auto_white_balance", False),
            "gamma": auto_params.get("gamma", 1.0),
            "clahe": auto_params.get("clahe", False),
        }
        image_info = apply_color_correction(output_path, output_path, color_params)

    return image_info, ai_analysis
