"""
Servizio di integrazione con Copyleaks AI Content Detection API.
Gestisce autenticazione, rilevamento AI e generazione report PDF.
"""

import os
import io
import uuid
import time
import logging
import httpx
import fitz  # PyMuPDF
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CopyleaksService:
    """Wrapper per le API Copyleaks Writer Detector."""

    AUTH_URL = "https://id.copyleaks.com/v3/account/login/api"
    DETECT_URL = "https://api.copyleaks.com/v2/writer-detector"

    def __init__(self):
        self.email = os.getenv("COPYLEAKS_EMAIL", "")
        self.api_key = os.getenv("COPYLEAKS_API_KEY", "")
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0  # timestamp

    def _ensure_token(self):
        """
        Ottiene o rinnova il token di accesso Copyleaks.
        Il token dura 48h; lo rinnoviamo con 1h di margine.
        """
        now = time.time()
        if self._access_token and now < self._token_expiry:
            return

        if not self.email or not self.api_key:
            raise RuntimeError(
                "Copyleaks non configurato: impostare COPYLEAKS_EMAIL e COPYLEAKS_API_KEY"
            )

        logger.info("Copyleaks: richiesta nuovo access token...")
        try:
            response = httpx.post(
                self.AUTH_URL,
                json={"email": self.email, "key": self.api_key},
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token") or data.get("accessToken")
            if not self._access_token:
                raise RuntimeError(f"Token non trovato nella risposta: {data}")
            # Token valido 48h, rinnoviamo dopo 47h
            self._token_expiry = now + (47 * 3600)
            logger.info("Copyleaks: token ottenuto con successo")
        except httpx.HTTPStatusError as e:
            logger.error(f"Copyleaks auth failed: {e.response.status_code} {e.response.text}")
            raise RuntimeError(f"Autenticazione Copyleaks fallita: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Copyleaks auth error: {e}")
            raise RuntimeError(f"Errore autenticazione Copyleaks: {e}")

    def detect(self, text: str, sandbox: bool = False) -> dict:
        """
        Esegue il rilevamento AI sul testo fornito.

        Args:
            text: Testo da analizzare (255-25000 caratteri)
            sandbox: Se True, usa modalita' test (nessun credito consumato)

        Returns:
            dict con ai_percentage, human_percentage, total_words, segments, model_version, scan_id
        """
        self._ensure_token()

        scan_id = f"sf-{uuid.uuid4().hex[:16]}"

        try:
            response = httpx.post(
                f"{self.DETECT_URL}/{scan_id}/check",
                json={
                    "text": text,
                    "sandbox": sandbox,
                    "explain": False,
                    "sensitivity": 2,
                },
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60.0,
            )

            if response.status_code == 401:
                # Token scaduto, riprova
                self._access_token = None
                self._token_expiry = 0
                self._ensure_token()
                response = httpx.post(
                    f"{self.DETECT_URL}/{scan_id}/check",
                    json={
                        "text": text,
                        "sandbox": sandbox,
                        "explain": False,
                        "sensitivity": 2,
                    },
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=60.0,
                )

            response.raise_for_status()
            data = response.json()

            return self._parse_response(data, text, scan_id)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RuntimeError(
                    "Rate limit Copyleaks raggiunto. Riprovare tra qualche minuto."
                )
            logger.error(f"Copyleaks detect error: {e.response.status_code} {e.response.text}")
            raise RuntimeError(
                f"Errore Copyleaks: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Copyleaks detect error: {e}")
            raise RuntimeError(f"Errore rilevamento AI: {e}")

    def _parse_response(self, data: dict, original_text: str, scan_id: str) -> dict:
        """Normalizza la risposta Copyleaks nel formato interno."""
        summary = data.get("summary", {})
        ai_score = summary.get("ai", 0)
        human_score = summary.get("human", 0)

        scanned_doc = data.get("scannedDocument", {})
        total_words = scanned_doc.get("totalWords", 0)
        model_version = data.get("modelVersion", "")

        # Parsa i segmenti con posizioni carattere
        segments = []
        results = data.get("results", [])

        for result in results:
            classification_code = result.get("classification", 0)
            classification = "ai" if classification_code == 2 else "human"

            matches = result.get("matches", [])
            for match in matches:
                text_info = match.get("text", {})
                chars_info = text_info.get("chars", {})
                starts = chars_info.get("starts", [])
                lengths = chars_info.get("lengths", [])

                for i in range(len(starts)):
                    start = starts[i]
                    length = lengths[i] if i < len(lengths) else 0
                    end = start + length

                    # Estrai il testo del segmento dall'originale
                    segment_text = original_text[start:end] if end <= len(original_text) else original_text[start:]

                    segments.append({
                        "text": segment_text,
                        "classification": classification,
                        "start": start,
                        "length": length,
                    })

        # Ordina i segmenti per posizione
        segments.sort(key=lambda s: s["start"])

        # Se Copyleaks non ha restituito segmenti dettagliati,
        # crea un unico segmento con la classificazione globale
        if not segments and original_text:
            overall_class = "ai" if ai_score > 0.5 else "human"
            segments.append({
                "text": original_text,
                "classification": overall_class,
                "start": 0,
                "length": len(original_text),
            })

        return {
            "ai_percentage": round(ai_score * 100, 1),
            "human_percentage": round(human_score * 100, 1),
            "total_words": total_words,
            "segments": segments,
            "model_version": model_version,
            "scan_id": scan_id,
        }


def generate_detection_report_pdf(
    text: str,
    segments: list,
    ai_percentage: float,
    human_percentage: float,
) -> bytes:
    """
    Genera un report PDF con il testo e le parti AI evidenziate.

    Args:
        text: Testo originale
        segments: Lista di segmenti con classification, start, length
        ai_percentage: Percentuale AI
        human_percentage: Percentuale umano

    Returns:
        bytes del PDF generato
    """
    doc = fitz.open()

    # Colori
    COLOR_AI_BG = fitz.utils.getColor("lightsalmon")
    COLOR_HUMAN_BG = fitz.utils.getColor("palegreen")
    COLOR_BLACK = fitz.utils.getColor("black")
    COLOR_WHITE = fitz.utils.getColor("white")
    COLOR_RED = fitz.utils.getColor("red")
    COLOR_GREEN = fitz.utils.getColor("green")
    COLOR_GRAY = fitz.utils.getColor("gray")
    COLOR_ORANGE = fitz.utils.getColor("orange")

    # Dimensioni pagina A4
    page_width = 595
    page_height = 842
    margin_left = 50
    margin_right = 50
    margin_top = 50
    margin_bottom = 50
    content_width = page_width - margin_left - margin_right

    # =========================================================================
    # PAGINA 1: RIEPILOGO
    # =========================================================================
    page = doc.new_page(width=page_width, height=page_height)

    y = margin_top

    # Titolo
    page.insert_text(
        fitz.Point(margin_left, y + 24),
        "StyleForge",
        fontsize=28,
        fontname="helv",
        color=COLOR_ORANGE,
    )
    y += 35

    page.insert_text(
        fitz.Point(margin_left, y + 18),
        "AI Detection Report",
        fontsize=18,
        fontname="helv",
        color=COLOR_BLACK,
    )
    y += 30

    # Linea separatrice
    page.draw_line(
        fitz.Point(margin_left, y),
        fitz.Point(page_width - margin_right, y),
        color=COLOR_ORANGE,
        width=2,
    )
    y += 25

    # Data e ora
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    page.insert_text(
        fitz.Point(margin_left, y + 12),
        f"Data scansione: {now}",
        fontsize=11,
        fontname="helv",
        color=COLOR_GRAY,
    )
    y += 25

    # Conteggio parole
    word_count = len(text.split())
    char_count = len(text)
    page.insert_text(
        fitz.Point(margin_left, y + 12),
        f"Parole analizzate: {word_count:,}  |  Caratteri: {char_count:,}",
        fontsize=11,
        fontname="helv",
        color=COLOR_GRAY,
    )
    y += 40

    # Barra percentuale AI vs Human
    bar_height = 40
    bar_y = y

    # Sfondo barra
    page.draw_rect(
        fitz.Rect(margin_left, bar_y, page_width - margin_right, bar_y + bar_height),
        color=COLOR_GRAY,
        fill=COLOR_GRAY,
        width=0,
    )

    # Porzione AI (rosso)
    ai_width = content_width * (ai_percentage / 100)
    if ai_width > 0:
        page.draw_rect(
            fitz.Rect(margin_left, bar_y, margin_left + ai_width, bar_y + bar_height),
            color=COLOR_RED,
            fill=COLOR_RED,
            width=0,
        )

    # Porzione Human (verde)
    human_width = content_width * (human_percentage / 100)
    if human_width > 0:
        page.draw_rect(
            fitz.Rect(
                page_width - margin_right - human_width,
                bar_y,
                page_width - margin_right,
                bar_y + bar_height,
            ),
            color=COLOR_GREEN,
            fill=COLOR_GREEN,
            width=0,
        )

    # Label percentuale sulla barra
    if ai_percentage > 10:
        page.insert_text(
            fitz.Point(margin_left + 10, bar_y + 26),
            f"AI: {ai_percentage:.1f}%",
            fontsize=14,
            fontname="helvB",
            color=COLOR_WHITE,
        )
    if human_percentage > 10:
        page.insert_text(
            fitz.Point(page_width - margin_right - human_width + 10, bar_y + 26),
            f"Umano: {human_percentage:.1f}%",
            fontsize=14,
            fontname="helvB",
            color=COLOR_WHITE,
        )

    y = bar_y + bar_height + 30

    # Legenda
    # AI
    page.draw_rect(
        fitz.Rect(margin_left, y, margin_left + 18, y + 18),
        color=COLOR_RED,
        fill=COLOR_AI_BG,
        width=1,
    )
    page.insert_text(
        fitz.Point(margin_left + 25, y + 13),
        "Testo rilevato come AI",
        fontsize=11,
        fontname="helv",
        color=COLOR_BLACK,
    )

    # Human
    page.draw_rect(
        fitz.Rect(margin_left + 250, y, margin_left + 268, y + 18),
        color=COLOR_GREEN,
        fill=COLOR_HUMAN_BG,
        width=1,
    )
    page.insert_text(
        fitz.Point(margin_left + 275, y + 13),
        "Testo rilevato come umano",
        fontsize=11,
        fontname="helv",
        color=COLOR_BLACK,
    )

    y += 50

    # Riepilogo statistiche
    page.insert_text(
        fitz.Point(margin_left, y + 16),
        "Riepilogo Analisi",
        fontsize=16,
        fontname="helvB",
        color=COLOR_BLACK,
    )
    y += 30

    stats = [
        f"Percentuale AI:          {ai_percentage:.1f}%",
        f"Percentuale Umano:       {human_percentage:.1f}%",
        f"Parole totali:           {word_count:,}",
        f"Caratteri totali:        {char_count:,}",
    ]

    # Conta segmenti AI
    ai_segments = [s for s in segments if s.get("classification") == "ai"]
    human_segments = [s for s in segments if s.get("classification") == "human"]
    stats.append(f"Segmenti AI rilevati:    {len(ai_segments)}")
    stats.append(f"Segmenti umani:          {len(human_segments)}")

    for stat in stats:
        page.insert_text(
            fitz.Point(margin_left + 10, y + 12),
            stat,
            fontsize=11,
            fontname="helv",
            color=COLOR_BLACK,
        )
        y += 20

    y += 20
    page.insert_text(
        fitz.Point(margin_left, y + 12),
        "Analisi eseguita con Copyleaks AI Content Detection",
        fontsize=9,
        fontname="helv",
        color=COLOR_GRAY,
    )

    # =========================================================================
    # PAGINE SUCCESSIVE: TESTO CON EVIDENZIAZIONE
    # =========================================================================

    # Prepara una mappa posizione -> classificazione
    char_classifications = ["unknown"] * len(text)
    for seg in segments:
        start = seg.get("start", 0)
        length = seg.get("length", 0)
        classification = seg.get("classification", "unknown")
        for i in range(start, min(start + length, len(text))):
            char_classifications[i] = classification

    # Dividi il testo in blocchi con classificazione uniforme
    blocks = []
    if text:
        current_class = char_classifications[0]
        current_start = 0
        for i in range(1, len(text)):
            if char_classifications[i] != current_class:
                blocks.append({
                    "text": text[current_start:i],
                    "classification": current_class,
                })
                current_class = char_classifications[i]
                current_start = i
        blocks.append({
            "text": text[current_start:],
            "classification": current_class,
        })

    # Rendering del testo evidenziato
    fontsize = 10
    line_height = fontsize * 1.6
    page = doc.new_page(width=page_width, height=page_height)

    # Titolo pagina
    y = margin_top
    page.insert_text(
        fitz.Point(margin_left, y + 14),
        "Testo Analizzato — Evidenziazione AI",
        fontsize=14,
        fontname="helvB",
        color=COLOR_BLACK,
    )
    y += 30

    # Rendering blocco per blocco come textbox
    for block in blocks:
        block_text = block["text"]
        classification = block["classification"]

        if not block_text.strip():
            # Conta le righe vuote
            newlines = block_text.count("\n")
            y += line_height * max(newlines, 1)
            if y > page_height - margin_bottom - 20:
                page = doc.new_page(width=page_width, height=page_height)
                y = margin_top
            continue

        # Scegli colore sfondo
        if classification == "ai":
            bg_color = COLOR_AI_BG
        elif classification == "human":
            bg_color = COLOR_HUMAN_BG
        else:
            bg_color = None

        # Dividi in righe per il wrapping
        words = block_text.replace("\n", " \n ").split(" ")
        lines = []
        current_line = ""

        for word in words:
            if word == "\n":
                lines.append(current_line)
                current_line = ""
                continue
            test_line = f"{current_line} {word}".strip() if current_line else word
            # Stima larghezza: ~6 pixel per carattere a fontsize 10
            if len(test_line) * 5.5 > content_width:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        for line in lines:
            if y + line_height > page_height - margin_bottom:
                page = doc.new_page(width=page_width, height=page_height)
                y = margin_top

            # Disegna sfondo evidenziazione
            if bg_color and line.strip():
                text_width = len(line) * 5.5
                rect = fitz.Rect(
                    margin_left - 2,
                    y - 2,
                    min(margin_left + text_width + 4, page_width - margin_right),
                    y + line_height - 2,
                )
                page.draw_rect(rect, color=None, fill=bg_color, width=0)

            # Inserisci testo
            page.insert_text(
                fitz.Point(margin_left, y + fontsize),
                line,
                fontsize=fontsize,
                fontname="helv",
                color=COLOR_BLACK,
            )
            y += line_height

    # Salva PDF in memoria
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# Istanza singleton
copyleaks_service = CopyleaksService()
