"""
Modulo di elaborazione immagini per StyleForge.
Applica miglioramenti guidati da AI usando Pillow.
"""

import logging
from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


def _apply_auto_levels(img: Image.Image) -> Image.Image:
    """Ribilanciamento automatico dei livelli tonali (histogram stretching)."""
    if img.mode == "RGBA":
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = ImageOps.autocontrast(rgb, cutoff=1)
        r2, g2, b2 = rgb.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    return ImageOps.autocontrast(img, cutoff=1)


def _apply_highlights_shadows(img: Image.Image, highlights: float, shadows: float) -> Image.Image:
    """
    Recupero alte luci e schiarimento ombre.
    highlights: -50 a +50 (negativo = recupera alte luci)
    shadows: -50 a +50 (positivo = schiarisci ombre)
    """
    if highlights == 0 and shadows == 0:
        return img

    has_alpha = img.mode == "RGBA"
    if has_alpha:
        r, g, b, a = img.split()
        work = Image.merge("RGB", (r, g, b))
    else:
        work = img.copy()

    # Crea lookup table
    lut = list(range(256))

    if highlights != 0:
        factor = highlights / 100.0
        for i in range(256):
            if i > 180:
                strength = (i - 180) / 75.0
                lut[i] = max(0, min(255, int(i + factor * strength * 50)))

    if shadows != 0:
        shadow_lut = list(range(256))
        factor = shadows / 100.0
        for i in range(256):
            if i < 80:
                strength = (80 - i) / 80.0
                shadow_lut[i] = max(0, min(255, int(i + factor * strength * 50)))
        lut = [shadow_lut[v] for v in lut]

    work = work.point(lut * 3)

    if has_alpha:
        r2, g2, b2 = work.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    return work


def _apply_warmth(img: Image.Image, warmth: float) -> Image.Image:
    """
    Regolazione bilanciamento del bianco (caldo/freddo).
    warmth: -30 a +30. Positivo = piu caldo (boost rosso, riduci blu).
    """
    if warmth == 0:
        return img

    has_alpha = img.mode == "RGBA"
    if has_alpha:
        r, g, b, a = img.split()
    else:
        r, g, b = img.split()

    factor = warmth / 30.0
    r_adjust = int(factor * 12)
    b_adjust = int(-factor * 12)

    r = r.point(lambda x: max(0, min(255, x + r_adjust)))
    b = b.point(lambda x: max(0, min(255, x + b_adjust)))

    if has_alpha:
        return Image.merge("RGBA", (r, g, b, a))
    return Image.merge("RGB", (r, g, b))


def _apply_vibrance(img: Image.Image, vibrance: float) -> Image.Image:
    """
    Vibrance: potenzia selettivamente i colori meno saturi.
    vibrance: 0.5-2.0, 1.0 = nessun cambio.
    """
    if vibrance == 1.0:
        return img

    has_alpha = img.mode == "RGBA"
    if has_alpha:
        rgb_img = img.convert("RGB")
    else:
        rgb_img = img.copy()

    hsv = rgb_img.convert("HSV")
    h, s, v = hsv.split()

    # Vibrance: boost proporzionale alla desaturazione
    def vibrance_map(sat_val):
        # Pixel meno saturi ricevono boost maggiore
        desaturation = 1.0 - (sat_val / 255.0)
        effective_factor = 1.0 + (vibrance - 1.0) * (0.3 + 0.7 * desaturation)
        return max(0, min(255, int(sat_val * effective_factor)))

    s = s.point(vibrance_map)
    result = Image.merge("HSV", (h, s, v)).convert("RGB")

    if has_alpha:
        r, g, b = result.split()
        _, _, _, a = img.split()
        return Image.merge("RGBA", (r, g, b, a))
    return result


def _apply_noise_reduction(img: Image.Image, level: str) -> Image.Image:
    """Riduzione rumore con filtri Pillow."""
    if level == "none":
        return img
    elif level == "light":
        return img.filter(ImageFilter.SMOOTH)
    elif level == "medium":
        return img.filter(ImageFilter.SMOOTH_MORE)
    elif level == "heavy":
        smoothed = img.filter(ImageFilter.GaussianBlur(radius=1))
        return ImageEnhance.Sharpness(smoothed).enhance(1.2)
    return img


def apply_enhancements(image_bytes: bytes, params: dict, output_format: str = "JPEG") -> bytes:
    """
    Applica i miglioramenti raccomandati da Claude all'immagine.

    Args:
        image_bytes: Bytes dell'immagine originale
        params: Dizionario parametri da Claude
        output_format: Formato output (JPEG, PNG, WEBP)

    Returns:
        Bytes dell'immagine migliorata
    """
    img = Image.open(BytesIO(image_bytes))

    # Correggi orientamento EXIF
    img = ImageOps.exif_transpose(img)

    # Converti in RGB se necessario (es. palette mode)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    logger.info(f"Elaborazione immagine {img.size[0]}x{img.size[1]}, mode={img.mode}")

    # 1. Auto levels
    if params.get("auto_levels", False):
        img = _apply_auto_levels(img)
        logger.debug("Applicato auto levels")

    # 2. Highlights / Shadows
    highlights = params.get("highlights", 0)
    shadows = params.get("shadows", 0)
    if highlights != 0 or shadows != 0:
        img = _apply_highlights_shadows(img, highlights, shadows)
        logger.debug(f"Applicato highlights={highlights}, shadows={shadows}")

    # 3. Brightness
    brightness = params.get("brightness", 1.0)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
        logger.debug(f"Applicato brightness={brightness}")

    # 4. Contrast
    contrast = params.get("contrast", 1.0)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
        logger.debug(f"Applicato contrast={contrast}")

    # 5. Warmth
    warmth = params.get("warmth", 0)
    if warmth != 0:
        img = _apply_warmth(img, warmth)
        logger.debug(f"Applicato warmth={warmth}")

    # 6. Color saturation
    color_saturation = params.get("color_saturation", 1.0)
    if color_saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(color_saturation)
        logger.debug(f"Applicato color_saturation={color_saturation}")

    # 7. Vibrance
    vibrance = params.get("vibrance", 1.0)
    if vibrance != 1.0:
        img = _apply_vibrance(img, vibrance)
        logger.debug(f"Applicato vibrance={vibrance}")

    # 8. Noise reduction
    noise_reduction = params.get("noise_reduction", "none")
    if noise_reduction != "none":
        img = _apply_noise_reduction(img, noise_reduction)
        logger.debug(f"Applicato noise_reduction={noise_reduction}")

    # 9. Sharpness (sempre per ultimo, dopo noise reduction)
    sharpness = params.get("sharpness", 1.0)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
        logger.debug(f"Applicato sharpness={sharpness}")

    # Salva nel formato richiesto
    buffer = BytesIO()
    save_kwargs = {}

    if output_format.upper() == "JPEG":
        # JPEG non supporta alpha
        if img.mode == "RGBA":
            img = img.convert("RGB")
        save_kwargs["quality"] = 95
        save_kwargs["optimize"] = True
    elif output_format.upper() == "PNG":
        save_kwargs["optimize"] = True
    elif output_format.upper() == "WEBP":
        save_kwargs["quality"] = 95
        save_kwargs["method"] = 4

    img.save(buffer, format=output_format.upper(), **save_kwargs)
    buffer.seek(0)

    logger.info(f"Immagine migliorata: {len(buffer.getvalue())} bytes")
    return buffer.getvalue()
