"""
Generatore del report PDF "Detector AI" StyleForge-branded.

Sostituisce il PDF originale ricevuto da Compilatio con un report dal layout
proprietario, includendo gli stessi dati (percentuali, fonti, punti di interesse)
in un'estetica e con marchio StyleForge.

Sezioni del report:
  1. Header + Riassunto (sezione 1/3)  - sempre presente
  2. Fonti di somiglianza (sezione 2/3) - se POI con riferimento a fonti esterne
  3. Punti di interesse (sezione 3/3)   - se document_text salvato (nuove scansioni)

Il modulo e' del tutto indipendente dalle API di Compilatio: lavora solo sui
dati gia' persistiti nella tabella compilatio_scans.
"""

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


# ============================================================================
# COSTANTI VISIVE — palette StyleForge (arancio) + colori semantici Compilatio
# ============================================================================

# Brand StyleForge
BRAND_ORANGE = (0.96, 0.50, 0.13)
BRAND_ORANGE_DARK = (0.85, 0.36, 0.04)
BRAND_TEXT = (0.10, 0.10, 0.12)
BRAND_MUTED = (0.45, 0.45, 0.50)
BRAND_BG_SOFT = (0.97, 0.97, 0.98)
BRAND_BORDER = (0.88, 0.88, 0.92)

# Colori per i tipi di passaggio (mutuati dal report Compilatio)
COLOR_AI_BG = (0.88, 0.96, 1.00)         # azzurro chiaro
COLOR_AI_LINE = (0.10, 0.55, 0.85)       # blu
COLOR_SIM_BG = (1.00, 0.88, 0.88)        # rosa chiaro
COLOR_SIM_LINE = (0.85, 0.20, 0.20)      # rosso
COLOR_QUOT_BG = (0.93, 0.93, 0.93)       # grigio chiaro
COLOR_QUOT_LINE = (0.50, 0.50, 0.50)     # grigio

# Layout pagina A4 (in points)
PAGE_W = 595
PAGE_H = 842
MARGIN = 50
CONTENT_W = PAGE_W - 2 * MARGIN

FONT_REG = "helv"
FONT_BOLD = "hebo"


# ============================================================================
# NORMALIZZAZIONE TESTO
# ============================================================================
#
# Helvetica (Base 14 PDF) supporta solo Latin-1. Caratteri Unicode comuni nel
# testo italiano (apostrofo tipografico, virgolette curve, em-dash, NBSP, ecc.)
# vengono sostituiti con i loro equivalenti ASCII *prima* del rendering perche'
# altrimenti `fitz.get_text_length` (usato per calcolare le posizioni X) e
# `fitz.insert_text` (che li sostituisce con un fallback) divergono e i
# segmenti seguenti finiscono accavallati.
#
# Tutte le sostituzioni sono 1:1 in codepoint per non shiftare le posizioni
# delle POI (Compilatio le restituisce in offset di codepoint del testo
# originale).
_NORMALIZATION_PAIRS = [
    # Apostrofi tipografici / virgolette singole
    (0x2018, "'"), (0x2019, "'"), (0x201A, "'"), (0x201B, "'"),
    (0x2032, "'"),  # prime
    # Virgolette doppie tipografiche
    (0x201C, '"'), (0x201D, '"'), (0x201E, '"'), (0x201F, '"'),
    (0x2033, '"'),  # double prime
    (0x00AB, '"'), (0x00BB, '"'),  # caporali
    # Trattini lunghi
    (0x2013, "-"), (0x2014, "-"), (0x2015, "-"), (0x2212, "-"),
    # Ellissi (1 codepoint -> 1 codepoint)
    (0x2026, "."),
    # Spazi unicode -> spazio normale
    (0x00A0, " "), (0x2002, " "), (0x2003, " "), (0x2004, " "),
    (0x2005, " "), (0x2006, " "), (0x2009, " "), (0x202F, " "),
    (0x205F, " "), (0x3000, " "),
    # Zero-width / formatting -> spazio (preserva la lunghezza)
    (0x200B, " "), (0x200C, " "), (0x200D, " "), (0xFEFF, " "),
]

_TEXT_NORMALIZATION_TABLE = str.maketrans({chr(cp): repl for cp, repl in _NORMALIZATION_PAIRS})


def _normalize_text(text: Optional[str]) -> Optional[str]:
    """Sostituisce i caratteri Unicode non supportati da Helvetica con
    equivalenti ASCII, mantenendo la stessa lunghezza in codepoint."""
    if text is None:
        return None
    return text.translate(_TEXT_NORMALIZATION_TABLE)


# ============================================================================
# DATACLASS DI APPOGGIO
# ============================================================================

@dataclass
class Position:
    start: int
    end: int
    type: str  # 'ai' | 'similarity' | 'quotation'


@dataclass
class SourceItem:
    label: str
    url: Optional[str]
    percent: float
    matches: int


# ============================================================================
# PARSER POI DIFENSIVO
# ============================================================================

def _classify_poi_type(raw: Any) -> str:
    """Mappa una stringa di tipo ad un tipo canonico ('ai' | 'similarity' | 'quotation')."""
    if not raw:
        return "similarity"
    s = str(raw).lower()
    if "ai" in s or "artificial" in s or "ia" == s or "ai_generated" in s or "machine" in s:
        return "ai"
    if "quot" in s or "cit" in s:
        return "quotation"
    if (
        "sim" in s
        or "exact" in s
        or "match" in s
        or "plag" in s
        or "paraphr" in s
        or "same_meaning" in s
        or "translat" in s
    ):
        return "similarity"
    return "similarity"


# Priorita' di evidenziazione quando un POI ha piu' tipi (Compilatio puo' assegnare
# piu' classificazioni alla stessa porzione di testo).
_POI_TYPE_PRIORITY = {"ai": 3, "similarity": 2, "quotation": 1}


def _resolve_poi_type(poi: dict) -> str:
    """
    Determina il tipo canonico di un POI Compilatio.
    Compilatio espone i tipi nel campo `types` (lista). Manteniamo
    fallback a `type/category/kind` per altre sorgenti.
    """
    raw = poi.get("types")
    if raw is None:
        raw = poi.get("type") or poi.get("category") or poi.get("kind")

    candidates: List[str] = []
    if isinstance(raw, list):
        candidates = [str(x) for x in raw if x]
    elif raw:
        candidates = [str(raw)]

    if not candidates:
        return "similarity"

    classified = [_classify_poi_type(c) for c in candidates]
    # Sceglie il tipo con priorita' piu' alta (AI > similarity > quotation).
    return max(classified, key=lambda t: _POI_TYPE_PRIORITY.get(t, 0))


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_position(poi: dict) -> Tuple[Optional[int], Optional[int]]:
    """Cerca i riferimenti di start/end fra i nomi piu' comuni."""
    start = _coerce_int(
        poi.get("start")
        or poi.get("start_char")
        or poi.get("offset")
        or poi.get("from")
    )
    end = _coerce_int(
        poi.get("end")
        or poi.get("end_char")
        or poi.get("to")
    )

    # Eventuale oggetto 'position' o 'span'
    if start is None or end is None:
        for key in ("position", "span", "range", "location"):
            obj = poi.get(key)
            if isinstance(obj, dict):
                start = start if start is not None else _coerce_int(obj.get("start") or obj.get("from"))
                end = end if end is not None else _coerce_int(obj.get("end") or obj.get("to"))

    # Se solo start + length
    if start is not None and end is None:
        length = _coerce_int(poi.get("length") or poi.get("len"))
        if length is not None:
            end = start + length

    return start, end


def _extract_source_info(poi: dict) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """Estrae (titolo, url, percentuale) dalla POI se presenti."""
    src = poi.get("source") or poi.get("matched_source") or poi.get("document") or {}

    if isinstance(src, str):
        return None, src, None

    if not isinstance(src, dict):
        src = {}

    title = (
        src.get("title")
        or src.get("name")
        or src.get("description")
        or poi.get("source_title")
        or poi.get("title")
    )
    url = (
        src.get("url")
        or src.get("link")
        or src.get("href")
        or poi.get("source_url")
        or poi.get("url")
        or poi.get("link")
    )
    percent = _coerce_float(
        poi.get("similarity_percent")
        or poi.get("similarity")
        or poi.get("score")
        or src.get("similarity_percent")
        or src.get("score")
    )

    return title, url, percent


def parse_pois(pois: List[dict]) -> Tuple[List[Position], List[SourceItem]]:
    """
    Estrae posizioni (per evidenziazione inline) e fonti uniche dalla lista POI.
    Robusto a schemi diversi: prova vari nomi di campo conosciuti.
    """
    positions: List[Position] = []
    sources_map: Dict[str, SourceItem] = {}

    if not pois:
        return positions, []

    for poi in pois:
        if not isinstance(poi, dict):
            continue

        ptype = _resolve_poi_type(poi)
        start, end = _extract_position(poi)
        if start is not None and end is not None and end > start:
            positions.append(Position(start=start, end=end, type=ptype))

        if ptype == "similarity":
            title, url, percent = _extract_source_info(poi)
            if not (title or url):
                continue
            key = (url or title or "").strip()
            if not key:
                continue
            if key in sources_map:
                sources_map[key].matches += 1
                if percent and percent > sources_map[key].percent:
                    sources_map[key].percent = percent
            else:
                sources_map[key] = SourceItem(
                    label=(title or url or key)[:300],
                    url=url,
                    percent=percent or 0.0,
                    matches=1,
                )

    # Ordina posizioni per start, poi per end
    positions.sort(key=lambda p: (p.start, p.end))
    sources = sorted(sources_map.values(), key=lambda s: -s.percent)
    return positions, sources


# ============================================================================
# HELPER DI DISEGNO
# ============================================================================

def _draw_brand_mark(page: fitz.Page, x: float, y: float, size: float = 32):
    """Disegna il marchio StyleForge come quadrato arrotondato arancione con 'S'."""
    rect = fitz.Rect(x, y, x + size, y + size)
    shape = page.new_shape()
    # Quadrato arrotondato (approssimato disegnando un rettangolo + finte rounded corners)
    shape.draw_rect(rect)
    shape.finish(fill=BRAND_ORANGE, color=BRAND_ORANGE_DARK, width=0.8)
    shape.commit()
    # Lettera S al centro
    page.insert_text(
        fitz.Point(x + size * 0.30, y + size * 0.72),
        "S",
        fontname=FONT_BOLD,
        fontsize=size * 0.62,
        color=(1, 1, 1),
    )


def _draw_donut(page: fitz.Page, cx: float, cy: float, radius: float, percent: float, label: str = ""):
    """
    Disegna un anello con porzione colorata pari a `percent`.
    `percent` 0..100. Colore graduato in base al valore.
    """
    pct = max(0.0, min(100.0, float(percent or 0)))
    # Colore in base alla soglia
    if pct >= 50:
        ring_color = (0.85, 0.20, 0.20)  # rosso
    elif pct >= 25:
        ring_color = (0.93, 0.55, 0.13)  # arancio
    else:
        ring_color = (0.20, 0.65, 0.30)  # verde
    bg_ring = (0.88, 0.88, 0.90)

    # Anello di sfondo (cerchio pieno grigio + cerchio bianco interno)
    shape = page.new_shape()
    shape.draw_circle(fitz.Point(cx, cy), radius)
    shape.finish(fill=bg_ring, color=bg_ring, width=0)
    shape.commit()

    # Settore colorato (approssimazione: tanti piccoli triangoli)
    if pct > 0:
        steps = max(4, int(pct))  # piu' fluido per pct alti
        angle_total = (pct / 100.0) * 2 * math.pi
        # Partiamo da -90 deg (top) e procediamo in senso orario
        start = -math.pi / 2
        shape = page.new_shape()
        # Costruisci poligono: centro + N punti sul cerchio
        p_prev = fitz.Point(cx, cy - radius)
        for i in range(1, steps + 1):
            theta = start + angle_total * (i / steps)
            p_curr = fitz.Point(cx + radius * math.cos(theta), cy + radius * math.sin(theta))
            shape.draw_polyline([fitz.Point(cx, cy), p_prev, p_curr, fitz.Point(cx, cy)])
            p_prev = p_curr
        shape.finish(fill=ring_color, color=ring_color, width=0)
        shape.commit()

    # Buco bianco al centro per fare l'effetto donut
    inner_r = radius * 0.62
    shape = page.new_shape()
    shape.draw_circle(fitz.Point(cx, cy), inner_r)
    shape.finish(fill=(1, 1, 1), color=(1, 1, 1), width=0)
    shape.commit()

    # Testo della percentuale al centro
    label_pct = f"{pct:.0f}%"
    text_w = fitz.get_text_length(label_pct, fontname=FONT_BOLD, fontsize=18)
    page.insert_text(
        fitz.Point(cx - text_w / 2, cy + 4),
        label_pct,
        fontname=FONT_BOLD,
        fontsize=18,
        color=ring_color,
    )
    if label:
        text_w = fitz.get_text_length(label, fontname=FONT_REG, fontsize=8)
        page.insert_text(
            fitz.Point(cx - text_w / 2, cy + 18),
            label,
            fontname=FONT_REG,
            fontsize=8,
            color=BRAND_MUTED,
        )


def _draw_section_header(page: fitz.Page, y: float, title: str, subtitle: str) -> float:
    """Banda orizzontale con titolo sezione."""
    rect = fitz.Rect(MARGIN, y, MARGIN + CONTENT_W, y + 26)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(fill=BRAND_BG_SOFT, color=BRAND_BORDER, width=0.5)
    shape.commit()
    page.insert_text(
        fitz.Point(MARGIN + 12, y + 18),
        title,
        fontname=FONT_BOLD,
        fontsize=12,
        color=BRAND_TEXT,
    )
    if subtitle:
        title_w = fitz.get_text_length(title, fontname=FONT_BOLD, fontsize=12)
        page.insert_text(
            fitz.Point(MARGIN + 12 + title_w + 8, y + 18),
            subtitle,
            fontname=FONT_REG,
            fontsize=10,
            color=BRAND_MUTED,
        )
    return y + 26 + 14


def _draw_label_value(page: fitz.Page, x: float, y: float, label: str, value: str,
                      max_value_w: float = 260):
    """Riga 'Label : value' usata nella tabella metadati."""
    page.insert_text(
        fitz.Point(x, y),
        f"{label} :",
        fontname=FONT_BOLD,
        fontsize=8.5,
        color=BRAND_TEXT,
    )
    label_w = fitz.get_text_length(f"{label} :", fontname=FONT_BOLD, fontsize=8.5)
    # Tronca value se troppo lungo
    val = value or "-"
    while fitz.get_text_length(val, fontname=FONT_REG, fontsize=8.5) > max_value_w and len(val) > 4:
        val = val[:-2]
    if val != (value or "-"):
        val = val[:-1] + "…"
    page.insert_text(
        fitz.Point(x + label_w + 4, y),
        val,
        fontname=FONT_REG,
        fontsize=8.5,
        color=BRAND_TEXT,
    )


def _draw_score_row(page: fitz.Page, y: float, icon_color: Tuple[float, float, float],
                    title: str, description: str, percent: float) -> float:
    """Riga con titolo, descrizione e percentuale (stile Compilatio)."""
    # Pallino colorato
    shape = page.new_shape()
    shape.draw_circle(fitz.Point(MARGIN + 8, y + 6), 6)
    shape.finish(fill=icon_color, color=icon_color, width=0)
    shape.commit()

    # Titolo
    page.insert_text(
        fitz.Point(MARGIN + 22, y + 9),
        title,
        fontname=FONT_BOLD,
        fontsize=11,
        color=BRAND_TEXT,
    )

    # Percentuale a destra
    pct_label = f"{float(percent or 0):.1f}%" if percent and percent < 1 == False else (
        f"<1%" if percent and percent < 1 else f"{int(percent or 0)}%"
    )
    if percent is None:
        pct_label = "0%"
    elif percent > 0 and percent < 1:
        pct_label = "<1%"
    else:
        pct_label = f"{percent:.0f}%"
    pct_w = fitz.get_text_length(pct_label, fontname=FONT_BOLD, fontsize=12)
    page.insert_text(
        fitz.Point(MARGIN + CONTENT_W - pct_w, y + 9),
        pct_label,
        fontname=FONT_BOLD,
        fontsize=12,
        color=icon_color,
    )

    # Descrizione (riga sotto)
    if description:
        # Word wrap manuale se serve
        desc_lines = _wrap_text(description, FONT_REG, 9, CONTENT_W - 30)
        line_y = y + 22
        for line in desc_lines[:2]:
            page.insert_text(
                fitz.Point(MARGIN + 22, line_y),
                line,
                fontname=FONT_REG,
                fontsize=9,
                color=BRAND_MUTED,
            )
            line_y += 11
        return line_y + 4
    return y + 26


def _wrap_text(text: str, fontname: str, fontsize: float, max_w: float) -> List[str]:
    """Word wrap che ritorna linee che entrano in `max_w` punti."""
    if not text:
        return []
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for w in words:
            test = f"{current} {w}".strip() if current else w
            if fitz.get_text_length(test, fontname=fontname, fontsize=fontsize) <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
    return lines


def _draw_position_bar(page: fitz.Page, y: float, positions: List[Position],
                       doc_length: int) -> float:
    """
    Disegna una barra orizzontale con tacche colorate per ogni POI.
    Dimensione tacche scalata per la lunghezza del documento.
    """
    bar_x0 = MARGIN
    bar_x1 = MARGIN + CONTENT_W
    bar_y = y + 8

    # Linea di base
    shape = page.new_shape()
    shape.draw_line(fitz.Point(bar_x0, bar_y), fitz.Point(bar_x1, bar_y))
    shape.finish(color=BRAND_BORDER, width=0.6)
    shape.commit()

    if not positions or doc_length <= 0:
        return y + 24

    bar_w = bar_x1 - bar_x0
    for p in positions:
        ratio_s = max(0.0, min(1.0, p.start / max(1, doc_length)))
        ratio_e = max(0.0, min(1.0, p.end / max(1, doc_length)))
        x_s = bar_x0 + ratio_s * bar_w
        x_e = bar_x0 + ratio_e * bar_w
        if x_e - x_s < 1.5:
            x_e = x_s + 1.5  # spessore minimo

        if p.type == "ai":
            color = COLOR_AI_LINE
        elif p.type == "similarity":
            color = COLOR_SIM_LINE
        else:
            color = COLOR_QUOT_LINE

        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(x_s, bar_y - 6, x_e, bar_y + 6))
        shape.finish(fill=color, color=color, width=0)
        shape.commit()

    return y + 24


# ============================================================================
# RENDER PAGINA 1: HEADER + RIASSUNTO
# ============================================================================

def _render_page_summary(doc: fitz.Document, scan_data: Dict[str, Any]) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    # ---- Header brand ----
    _draw_brand_mark(page, MARGIN, MARGIN, size=34)
    page.insert_text(
        fitz.Point(MARGIN + 46, MARGIN + 12),
        "Rapporto di analisi",
        fontname=FONT_BOLD,
        fontsize=12,
        color=BRAND_TEXT,
    )
    page.insert_text(
        fitz.Point(MARGIN + 46, MARGIN + 26),
        "Detector AI · StyleForge",
        fontname=FONT_REG,
        fontsize=10,
        color=BRAND_MUTED,
    )

    # ---- Donut globale (allineato a destra; label a sinistra del donut) ----
    global_pct = float(scan_data.get("global_score_percent") or 0)
    donut_radius = 28
    donut_cx = PAGE_W - MARGIN - donut_radius
    donut_cy = MARGIN + donut_radius + 4
    _draw_donut(page, cx=donut_cx, cy=donut_cy, radius=donut_radius,
                percent=global_pct, label="")
    label_text = "Passaggi sospetti"
    label_w = fitz.get_text_length(label_text, fontname=FONT_BOLD, fontsize=10)
    page.insert_text(
        fitz.Point(donut_cx - donut_radius - 12 - label_w, donut_cy + 4),
        label_text,
        fontname=FONT_BOLD,
        fontsize=10,
        color=BRAND_TEXT,
    )

    # ---- Titolo documento ----
    y = MARGIN + 70
    title_str = scan_data.get("display_title") or scan_data.get("document_filename") or "Documento"
    page.insert_text(
        fitz.Point(MARGIN, y),
        title_str[:80],
        fontname=FONT_BOLD,
        fontsize=11,
        color=BRAND_TEXT,
    )
    page.insert_text(
        fitz.Point(MARGIN, y + 14),
        f"ID : {scan_data.get('scan_id', '-')}",
        fontname=FONT_REG,
        fontsize=8.5,
        color=BRAND_MUTED,
    )

    # ---- Box metadati (due colonne) ----
    y_box = y + 30
    box_h = 64
    rect = fitz.Rect(MARGIN, y_box, MARGIN + CONTENT_W, y_box + box_h)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(fill=BRAND_BG_SOFT, color=BRAND_BORDER, width=0.5)
    shape.commit()

    col_w = CONTENT_W / 2
    left_x = MARGIN + 12
    right_x = MARGIN + col_w + 12
    line_y = y_box + 14
    line_h = 13

    n_words = int(scan_data.get("word_count") or 0)
    n_chars = int(scan_data.get("char_count") or 0)
    if not n_chars and scan_data.get("document_text"):
        n_chars = len(scan_data["document_text"])

    # Sinistra
    _draw_label_value(page, left_x, line_y, "Nome del file", title_str, max_value_w=col_w - 80)
    _draw_label_value(page, left_x, line_y + line_h, "Numero di parole", f"{n_words:,}".replace(",", "."))
    _draw_label_value(page, left_x, line_y + 2 * line_h, "Numero di caratteri", f"{n_chars:,}".replace(",", "."))

    # Destra (Depositante volutamente omesso: il report e' anonimo lato utente)
    src_label_map = {
        "manual": "Caricamento manuale",
        "thesis": "Wizard tesi",
        "generate": "Generazione",
        "humanize": "Umanizzazione",
    }
    _draw_label_value(page, right_x, line_y, "Tipo di caricamento",
                      src_label_map.get(scan_data.get("source_type") or "manual", "Manuale"))
    completed = scan_data.get("completed_at")
    if isinstance(completed, datetime):
        completed_str = completed.strftime("%d/%m/%Y %H:%M")
    elif isinstance(completed, str):
        completed_str = completed[:16].replace("T", " ")
    else:
        completed_str = "-"
    _draw_label_value(page, right_x, line_y + line_h, "Data fine analisi", completed_str)

    # ---- Sezione 1/3 Riassunto ----
    y = y_box + box_h + 24
    y = _draw_section_header(page, y, "Riassunto", "(sezione 1/3)")

    positions: List[Position] = scan_data.get("positions") or []
    doc_length = int(scan_data.get("char_count") or 0) or len(scan_data.get("document_text") or "") or 1

    # Posizione testi sospetti
    page.insert_text(
        fitz.Point(MARGIN, y),
        "Posizione dei testi sospetti nel documento :",
        fontname=FONT_REG,
        fontsize=10,
        color=BRAND_TEXT,
    )
    y = _draw_position_bar(page, y + 6, positions, doc_length)
    y += 8

    # Incluso nel punteggio
    page.insert_text(
        fitz.Point(MARGIN, y),
        "Incluso nel punteggio dei testi sospetti :",
        fontname=FONT_BOLD,
        fontsize=10,
        color=BRAND_TEXT,
    )
    y += 18
    sim = float(scan_data.get("similarity_percent") or 0)
    ai = float(scan_data.get("ai_generated_percent") or 0)
    y = _draw_score_row(
        page, y,
        icon_color=COLOR_SIM_LINE,
        title="Similitudini",
        description="Passaggi che presentano analogie con fonti presenti in diverse collezioni.",
        percent=sim,
    )
    y = _draw_score_row(
        page, y,
        icon_color=COLOR_AI_LINE,
        title="Rilevamento dell'intelligenza artificiale",
        description=(
            "Testi stilisticamente vicini a un testo generato da un'intelligenza artificiale. "
            "Questo tasso e' un indicatore e non una prova."
        ),
        percent=ai,
    )

    # Non incluso nel punteggio
    y += 8
    page.insert_text(
        fitz.Point(MARGIN, y),
        "Non incluso nella percentuale di testi sospetti :",
        fontname=FONT_BOLD,
        fontsize=10,
        color=BRAND_TEXT,
    )
    y += 18
    quot = float(scan_data.get("quotation_percent") or 0)
    y = _draw_score_row(
        page, y,
        icon_color=COLOR_QUOT_LINE,
        title="Testi tra virgolette",
        description="Passaggi tra virgolette, spesso rivelatori di una citazione.",
        percent=quot,
    )

    # ---- Footer pagina ----
    _draw_footer(page, page_num=1)


# ============================================================================
# RENDER PAGINA 2: FONTI DI SOMIGLIANZA
# ============================================================================

def _render_page_sources(doc: fitz.Document, scan_data: Dict[str, Any]) -> None:
    sources: List[SourceItem] = scan_data.get("sources") or []
    if not sources:
        return  # Nessuna fonte parseable, salto la pagina

    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MARGIN
    y = _draw_section_header(page, y, "Fonti di somiglianza", "(sezione 2/3)")

    # Pannello "Similitudini"
    sim = float(scan_data.get("similarity_percent") or 0)
    y = _draw_score_row(
        page, y,
        icon_color=COLOR_SIM_LINE,
        title="Similitudini",
        description="Passaggi che presentano analogie con fonti presenti in diverse collezioni.",
        percent=sim,
    )
    y += 12

    # Header tabella
    page.insert_text(
        fitz.Point(MARGIN, y),
        "Fonte con similitudini accidentali",
        fontname=FONT_BOLD,
        fontsize=11,
        color=BRAND_TEXT,
    )
    y += 18

    col_n_w = 30
    col_pct_w = 70
    col_desc_w = CONTENT_W - col_n_w - col_pct_w - 10

    # Riga header
    shape = page.new_shape()
    shape.draw_line(fitz.Point(MARGIN, y), fitz.Point(MARGIN + CONTENT_W, y))
    shape.finish(color=BRAND_BORDER, width=0.5)
    shape.commit()
    page.insert_text(fitz.Point(MARGIN + 4, y - 4), "N°", fontname=FONT_BOLD, fontsize=8.5, color=BRAND_MUTED)
    page.insert_text(fitz.Point(MARGIN + col_n_w + 8, y - 4), "Descrizione", fontname=FONT_BOLD, fontsize=8.5, color=BRAND_MUTED)
    page.insert_text(fitz.Point(MARGIN + col_n_w + 8 + col_desc_w, y - 4), "Similitudine", fontname=FONT_BOLD, fontsize=8.5, color=BRAND_MUTED)
    y += 8

    # Righe
    for idx, src in enumerate(sources, start=1):
        if y > PAGE_H - MARGIN - 40:
            _draw_footer(page, page_num=2)
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y = MARGIN

        page.insert_text(
            fitz.Point(MARGIN + 4, y + 12),
            str(idx),
            fontname=FONT_BOLD,
            fontsize=10,
            color=COLOR_SIM_LINE,
        )

        # Title + URL
        title = (src.label or "")[:120]
        page.insert_text(
            fitz.Point(MARGIN + col_n_w + 8, y + 8),
            title,
            fontname=FONT_BOLD,
            fontsize=9.5,
            color=BRAND_TEXT,
        )
        if src.url:
            url_short = src.url
            while fitz.get_text_length(url_short, fontname=FONT_REG, fontsize=8) > col_desc_w - 20 and len(url_short) > 30:
                url_short = url_short[:-2]
            if url_short != src.url:
                url_short = url_short + "…"
            page.insert_text(
                fitz.Point(MARGIN + col_n_w + 8, y + 22),
                url_short,
                fontname=FONT_REG,
                fontsize=8,
                color=BRAND_MUTED,
            )

        # Percent
        pct_lab = "<1%" if src.percent and src.percent < 1 else f"{src.percent:.0f}%"
        if not src.percent:
            pct_lab = "<1%"
        pct_x = MARGIN + col_n_w + 8 + col_desc_w
        page.insert_text(
            fitz.Point(pct_x, y + 14),
            pct_lab,
            fontname=FONT_BOLD,
            fontsize=11,
            color=COLOR_SIM_LINE,
        )

        # Riga separatrice
        shape = page.new_shape()
        shape.draw_line(fitz.Point(MARGIN, y + 30), fitz.Point(MARGIN + CONTENT_W, y + 30))
        shape.finish(color=BRAND_BORDER, width=0.3)
        shape.commit()

        y += 34

    _draw_footer(page, page_num=2)


# ============================================================================
# RENDER PAGINA 3+: PUNTI DI INTERESSE (testo evidenziato)
# ============================================================================

def _build_segments(text: str, positions: List[Position]) -> List[Tuple[str, str]]:
    """
    Spezza il testo in segmenti (testo, type) basandosi su `positions`.
    type in: 'normal' | 'ai' | 'similarity' | 'quotation'.
    Le posizioni che si sovrappongono prendono il colore della prima.
    """
    if not positions:
        return [(text, "normal")]

    # Risolvi sovrapposizioni: per ogni char teniamo il primo type incontrato
    L = len(text)
    type_arr = [None] * L
    for p in positions:
        s = max(0, min(L, p.start))
        e = max(0, min(L, p.end))
        if e <= s:
            continue
        for i in range(s, e):
            if type_arr[i] is None:
                type_arr[i] = p.type

    segments: List[Tuple[str, str]] = []
    if L == 0:
        return segments
    cur_type = type_arr[0]
    cur_start = 0
    for i in range(1, L):
        if type_arr[i] != cur_type:
            seg_text = text[cur_start:i]
            segments.append((seg_text, cur_type or "normal"))
            cur_start = i
            cur_type = type_arr[i]
    segments.append((text[cur_start:], cur_type or "normal"))
    return segments


def _layout_lines(text: str, fontname: str, fontsize: float, max_w: float) -> List[Tuple[str, int]]:
    """
    Spezza `text` in righe che entrano in `max_w`. Mantiene i \\n come line break
    forzati. Ritorna una lista di tuple (line_str, char_offset_nel_testo_originale).
    Il char_offset serve per sapere quale tratto della riga e' evidenziato.
    """
    lines: List[Tuple[str, int]] = []
    n = len(text)
    i = 0
    while i < n:
        # Trova il prossimo newline
        nl = text.find("\n", i)
        para_end = nl if nl >= 0 else n
        para = text[i:para_end]
        para_offset = i

        # Word-wrap del paragrafo
        if not para:
            lines.append(("", para_offset))
        else:
            j = 0
            cur_start = 0  # offset nel paragrafo
            cur_len_chars = 0
            last_break = -1  # ultima posizione dove possiamo wrappare (dopo uno spazio)
            while j <= len(para):
                # Misura il sub-testo da cur_start a j
                if j == len(para):
                    # Ultima riga del paragrafo
                    seg = para[cur_start:j]
                    if seg or cur_start == 0:
                        lines.append((seg, para_offset + cur_start))
                    break
                ch = para[j]
                seg_so_far = para[cur_start:j + 1]
                w = fitz.get_text_length(seg_so_far, fontname=fontname, fontsize=fontsize)
                if w > max_w:
                    # Devo wrappare. Usa l'ultimo punto di break valido se c'e'.
                    if last_break > cur_start:
                        seg = para[cur_start:last_break]
                        lines.append((seg.rstrip(), para_offset + cur_start))
                        # Salta gli spazi dopo il break
                        cur_start = last_break
                        while cur_start < len(para) and para[cur_start] == " ":
                            cur_start += 1
                        j = cur_start
                        last_break = -1
                        continue
                    else:
                        # Parola troppo lunga, taglia hard a j (almeno un char per evitare loop)
                        seg = para[cur_start:max(j, cur_start + 1)]
                        lines.append((seg, para_offset + cur_start))
                        cur_start = max(j, cur_start + 1)
                        j = cur_start
                        last_break = -1
                        continue
                if ch == " ":
                    last_break = j + 1
                j += 1

        i = para_end
        if nl >= 0:
            # Salta il \n
            i += 1
            # Se la prossima e' empty (paragrafo vuoto) inseriamo riga vuota
            # (gestita gia' al prossimo giro se text[i] == '\n')


    return lines


def _render_page_pois(doc: fitz.Document, scan_data: Dict[str, Any]) -> None:
    text = scan_data.get("document_text")
    positions: List[Position] = scan_data.get("positions") or []

    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MARGIN
    y = _draw_section_header(page, y, "Punti di interesse", "(sezione 3/3)")

    if not text:
        page.insert_text(
            fitz.Point(MARGIN, y),
            "Documento originale non disponibile per questa scansione.",
            fontname=FONT_BOLD,
            fontsize=11,
            color=BRAND_TEXT,
        )
        y += 18
        info_lines = _wrap_text(
            "La scansione e' stata effettuata prima dell'attivazione della funzione "
            "di archiviazione del testo originale per il report. Sono comunque "
            "disponibili tutti i dati statistici nelle sezioni precedenti.",
            FONT_REG, 9.5, CONTENT_W,
        )
        for line in info_lines:
            page.insert_text(fitz.Point(MARGIN, y), line, fontname=FONT_REG, fontsize=9.5, color=BRAND_MUTED)
            y += 14
        _draw_footer(page, page_num=3)
        return

    # Legenda colori
    _draw_legend(page, y)
    y += 22

    # Costruisci array di tipo per ogni char (None = normal)
    n = len(text)
    type_arr: List[Optional[str]] = [None] * n
    for p in positions:
        s = max(0, min(n, p.start))
        e = max(0, min(n, p.end))
        if e <= s:
            continue
        for i in range(s, e):
            if type_arr[i] is None:
                type_arr[i] = p.type

    # Spezza il testo in righe (offset incluso)
    fontsize = 9.5
    line_height = fontsize * 1.55
    lines = _layout_lines(text, FONT_REG, fontsize, CONTENT_W)

    page_num = 3
    y_cursor = y

    for line_text, line_offset in lines:
        # Wrap pagina
        if y_cursor > PAGE_H - MARGIN - 8:
            _draw_footer(page, page_num=page_num)
            page_num += 1
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y_cursor = MARGIN + 12

        if not line_text:
            y_cursor += line_height
            continue

        # 1) Disegna prima i bg rect per i range evidenziati su questa riga
        # Trova i run consecutivi dello stesso type all'interno della riga
        L = len(line_text)
        i = 0
        while i < L:
            t = type_arr[line_offset + i] if (line_offset + i) < n else None
            if t in ("ai", "similarity", "quotation"):
                # Trova fine del run
                j = i + 1
                while j < L and (line_offset + j) < n and type_arr[line_offset + j] == t:
                    j += 1
                # Calcola x_start, x_end usando get_text_length
                prefix_w = fitz.get_text_length(line_text[:i], fontname=FONT_REG, fontsize=fontsize)
                run_w = fitz.get_text_length(line_text[i:j], fontname=FONT_REG, fontsize=fontsize)
                x_s = MARGIN + prefix_w
                x_e = MARGIN + prefix_w + run_w

                # Background
                bg = COLOR_AI_BG if t == "ai" else (COLOR_SIM_BG if t == "similarity" else COLOR_QUOT_BG)
                shape = page.new_shape()
                shape.draw_rect(fitz.Rect(x_s - 1, y_cursor - fontsize + 1, x_e + 1, y_cursor + 3))
                shape.finish(fill=bg, color=bg, width=0)
                shape.commit()

                # Sottolineatura per ai/similarity
                if t in ("ai", "similarity"):
                    line_color = COLOR_AI_LINE if t == "ai" else COLOR_SIM_LINE
                    shape = page.new_shape()
                    shape.draw_line(fitz.Point(x_s, y_cursor + 1.5), fitz.Point(x_e, y_cursor + 1.5))
                    shape.finish(color=line_color, width=0.7)
                    shape.commit()

                i = j
            else:
                i += 1

        # 2) Renderizza la riga run-by-run (un solo insert_text per run, con
        #    posizione X calcolata dal prefix). Ogni run ha al massimo un colore;
        #    niente double-render, niente overlay -> nessuna sovrapposizione.
        i = 0
        while i < L:
            t_raw = type_arr[line_offset + i] if (line_offset + i) < n else None
            t = t_raw if t_raw in ("ai", "similarity", "quotation") else "normal"
            j = i + 1
            while j < L:
                t_next_raw = type_arr[line_offset + j] if (line_offset + j) < n else None
                t_next = t_next_raw if t_next_raw in ("ai", "similarity", "quotation") else "normal"
                if t_next != t:
                    break
                j += 1

            if t == "ai":
                color = COLOR_AI_LINE
            elif t == "similarity":
                color = COLOR_SIM_LINE
            else:
                color = BRAND_TEXT

            prefix_w = fitz.get_text_length(line_text[:i], fontname=FONT_REG, fontsize=fontsize) if i > 0 else 0
            page.insert_text(
                fitz.Point(MARGIN + prefix_w, y_cursor),
                line_text[i:j],
                fontname=FONT_REG,
                fontsize=fontsize,
                color=color,
            )
            i = j

        y_cursor += line_height

    _draw_footer(page, page_num=page_num)


def _draw_legend(page: fitz.Page, y: float):
    items = [
        ("Rilevamento AI", COLOR_AI_BG, COLOR_AI_LINE),
        ("Similitudine", COLOR_SIM_BG, COLOR_SIM_LINE),
        ("Tra virgolette", COLOR_QUOT_BG, COLOR_QUOT_LINE),
    ]
    x = MARGIN
    for label, bg, line in items:
        # Pillola colorata
        rect = fitz.Rect(x, y - 8, x + 12, y + 4)
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(fill=bg, color=line, width=0.6)
        shape.commit()
        page.insert_text(fitz.Point(x + 16, y + 2), label, fontname=FONT_REG, fontsize=8.5, color=BRAND_TEXT)
        x += 100


def _draw_footer(page: fitz.Page, page_num: int):
    txt = f"StyleForge · Detector AI · pagina {page_num}"
    page.insert_text(
        fitz.Point(MARGIN, PAGE_H - 30),
        txt,
        fontname=FONT_REG,
        fontsize=8,
        color=BRAND_MUTED,
    )


# ============================================================================
# ENTRY POINT
# ============================================================================

def generate_styleforge_report(scan_data: Dict[str, Any], output_path: str) -> str:
    """
    Genera il PDF StyleForge-branded e lo scrive in output_path.

    `scan_data` deve contenere (chiavi accettate):
      - scan_id, document_filename, display_title (opzionale)
      - word_count, char_count
      - global_score_percent, similarity_percent, ai_generated_percent,
        quotation_percent, exact_percent (...altre se serve)
      - source_type (manual|thesis|generate|humanize)
      - completed_at (datetime o ISO string)
      - user_full_name / user_email
      - document_text (str)  -> abilita la sezione 3
      - scan_details (dict con `pois` list)  -> abilita evidenziazioni e fonti

    Ritorna `output_path`.
    """
    # Pre-processa pois
    pois = []
    sd = scan_data.get("scan_details")
    if isinstance(sd, dict):
        pois = sd.get("pois") or []
    positions, sources = parse_pois(pois)

    # Normalizza il testo originale prima di inserirlo nel PDF.
    # Helvetica (Base 14) non supporta vari simboli Unicode (apostrofi tipografici,
    # virgolette curve, em-dash, ecc.). La normalizzazione e' length-preserving
    # cosi' le `positions` restano coerenti.
    enriched = dict(scan_data)
    if enriched.get("document_text"):
        enriched["document_text"] = _normalize_text(enriched["document_text"])

    # Conteggio caratteri se non gia' fornito
    if not enriched.get("char_count"):
        if enriched.get("document_text"):
            enriched["char_count"] = len(enriched["document_text"])

    enriched["positions"] = positions
    enriched["sources"] = sources

    doc = fitz.open()
    try:
        _render_page_summary(doc, enriched)
        _render_page_sources(doc, enriched)
        _render_page_pois(doc, enriched)
        doc.save(output_path)
    finally:
        doc.close()

    logger.info(f"[StyleForge Report] PDF generato: {output_path}")
    return output_path
