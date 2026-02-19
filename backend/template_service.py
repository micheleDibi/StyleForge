"""
Servizio gestione template di esportazione per tesi/relazioni.
Gestisce CRUD template, parametri help e applicazione a PDF/DOCX.
"""

import copy
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from db_models import SystemSetting

logger = logging.getLogger(__name__)


# ============================================================================
# TEMPLATE DEFAULT
# ============================================================================

DEFAULT_PDF_SETTINGS = {
    "page_size": "A4",
    "margin_top": 50,
    "margin_bottom": 50,
    "margin_left": 50,
    "margin_right": 50,
    "font_body": "helv",
    "font_body_size": 11,
    "font_title_size": 24,
    "font_chapter_size": 18,
    "font_section_size": 14,
    "line_height_multiplier": 1.5,
    "include_toc": True,
    "include_page_numbers": True,
    "page_number_position": "bottom_center",
    "include_header": False,
    "header_text": "",
    "include_footer": False,
    "footer_text": "",
    "title_alignment": "center",
    "body_alignment": "left",
    "chapter_spacing_before": 20,
    "section_spacing_before": 15,
    "paragraph_spacing": 0,
}

DEFAULT_DOCX_SETTINGS = {
    "font_name": "Times New Roman",
    "font_size": 12,
    "title_alignment": "center",
    "line_spacing": 1.5,
    "paragraph_spacing_after": 6,
    "include_toc": True,
    "include_page_numbers": True,
    "toc_indent": 0.5,
    "heading1_size": 16,
    "heading2_size": 14,
}

DEFAULT_EXPORT_TEMPLATES = {
    "templates": [
        {
            "id": "default",
            "name": "Template Standard",
            "is_default": True,
            "pdf": copy.deepcopy(DEFAULT_PDF_SETTINGS),
            "docx": copy.deepcopy(DEFAULT_DOCX_SETTINGS),
        }
    ]
}


# ============================================================================
# HELP / TOOLTIP PER OGNI PARAMETRO
# ============================================================================

TEMPLATE_PARAM_HELP = {
    "pdf": {
        "page_size": {
            "label": "Formato pagina",
            "description": "Dimensione fisica della pagina del documento PDF.",
            "type": "select",
            "options": ["A4", "Letter", "A5"],
            "default": "A4",
            "example": "A4 = 210x297mm (standard europeo e accademico). Letter = 216x279mm (standard USA). A5 = 148x210mm (formato piccolo)."
        },
        "margin_top": {
            "label": "Margine superiore",
            "description": "Spazio vuoto tra il bordo superiore della pagina e l'inizio del contenuto.",
            "type": "number",
            "min": 20, "max": 150, "default": 50, "unit": "pt",
            "example": "50pt = circa 1.76cm. Per tesi accademiche si consiglia 60-72pt (2-2.5cm). Margini piu' ampi danno un aspetto piu' pulito."
        },
        "margin_bottom": {
            "label": "Margine inferiore",
            "description": "Spazio vuoto tra la fine del contenuto e il bordo inferiore della pagina.",
            "type": "number",
            "min": 20, "max": 150, "default": 50, "unit": "pt",
            "example": "50pt = circa 1.76cm. Aumentare se si usano numeri di pagina o pie' di pagina."
        },
        "margin_left": {
            "label": "Margine sinistro",
            "description": "Spazio vuoto sul lato sinistro della pagina.",
            "type": "number",
            "min": 20, "max": 150, "default": 50, "unit": "pt",
            "example": "Per documenti rilegati, usare 72-85pt (2.5-3cm) per lasciare spazio alla rilegatura."
        },
        "margin_right": {
            "label": "Margine destro",
            "description": "Spazio vuoto sul lato destro della pagina.",
            "type": "number",
            "min": 20, "max": 150, "default": 50, "unit": "pt",
            "example": "50pt = circa 1.76cm. Di solito uguale o leggermente piu' piccolo del margine sinistro."
        },
        "font_body": {
            "label": "Font corpo testo",
            "description": "Il carattere tipografico usato per il testo principale del documento.",
            "type": "select",
            "options": ["helv", "tiro", "cour"],
            "default": "helv",
            "example": "helv = Helvetica (sans-serif, moderno e pulito). tiro = Times (serif, classico accademico). cour = Courier (monospazio, stile macchina da scrivere)."
        },
        "font_body_size": {
            "label": "Dimensione font corpo",
            "description": "La grandezza del testo principale in punti tipografici.",
            "type": "number",
            "min": 8, "max": 16, "default": 11, "unit": "pt",
            "example": "11pt e' lo standard per documenti professionali. 12pt per tesi accademiche. 10pt per documenti compatti."
        },
        "font_title_size": {
            "label": "Dimensione font titolo",
            "description": "La grandezza del titolo principale della tesi sulla prima pagina.",
            "type": "number",
            "min": 14, "max": 36, "default": 24, "unit": "pt",
            "example": "24pt per un titolo ben visibile. 20pt per un look piu' sobrio. 28pt per massimo impatto."
        },
        "font_chapter_size": {
            "label": "Dimensione font capitoli",
            "description": "La grandezza dei titoli dei capitoli (es. 'Capitolo 1: Introduzione').",
            "type": "number",
            "min": 12, "max": 28, "default": 18, "unit": "pt",
            "example": "18pt crea una buona gerarchia visiva. Deve essere piu' grande delle sezioni ma piu' piccolo del titolo."
        },
        "font_section_size": {
            "label": "Dimensione font sezioni",
            "description": "La grandezza dei titoli delle sezioni all'interno dei capitoli.",
            "type": "number",
            "min": 10, "max": 22, "default": 14, "unit": "pt",
            "example": "14pt distingue chiaramente le sezioni dal corpo testo (11pt). Per documenti accademici, 13-14pt e' ideale."
        },
        "line_height_multiplier": {
            "label": "Interlinea",
            "description": "Moltiplicatore dello spazio tra le righe di testo. 1.0 = singola, 1.5 = una e mezza, 2.0 = doppia.",
            "type": "number",
            "min": 1.0, "max": 3.0, "default": 1.5, "step": 0.1,
            "example": "1.5 e' lo standard per documenti leggibili. 2.0 (doppia interlinea) e' richiesto da molte universita'. 1.15 per documenti compatti."
        },
        "include_toc": {
            "label": "Includere indice",
            "description": "Se attivo, inserisce automaticamente un indice (sommario) all'inizio del documento con tutti i capitoli e le sezioni.",
            "type": "boolean",
            "default": True,
            "example": "L'indice viene generato automaticamente dalla struttura dei capitoli e delle sezioni della tesi."
        },
        "include_page_numbers": {
            "label": "Numeri di pagina",
            "description": "Se attivo, aggiunge il numero di pagina su ogni pagina del documento.",
            "type": "boolean",
            "default": True,
            "example": "I numeri di pagina facilitano la navigazione del documento e sono richiesti nella maggior parte dei contesti accademici."
        },
        "page_number_position": {
            "label": "Posizione numeri pagina",
            "description": "Dove posizionare il numero di pagina sulla pagina.",
            "type": "select",
            "options": ["bottom_center", "bottom_right", "top_center", "top_right"],
            "default": "bottom_center",
            "example": "bottom_center = centrato in basso (standard). bottom_right = in basso a destra. top_right = in alto a destra (stile articolo)."
        },
        "include_header": {
            "label": "Intestazione pagina",
            "description": "Se attivo, aggiunge un testo fisso nell'intestazione (parte superiore) di ogni pagina.",
            "type": "boolean",
            "default": False,
            "example": "L'intestazione puo' contenere il titolo della tesi abbreviato o il nome dell'autore."
        },
        "header_text": {
            "label": "Testo intestazione",
            "description": "Il testo che appare nell'intestazione di ogni pagina. Visibile solo se 'Intestazione pagina' e' attivo.",
            "type": "text",
            "default": "",
            "example": "Esempio: 'Tesi di Laurea - Nome Autore' oppure 'Capitolo corrente'."
        },
        "include_footer": {
            "label": "Pie' di pagina",
            "description": "Se attivo, aggiunge un testo fisso nel pie' di pagina (parte inferiore) di ogni pagina.",
            "type": "boolean",
            "default": False,
            "example": "Il pie' di pagina puo' contenere informazioni come l'universita', il dipartimento o la data."
        },
        "footer_text": {
            "label": "Testo pie' di pagina",
            "description": "Il testo che appare nel pie' di pagina di ogni pagina. Visibile solo se 'Pie' di pagina' e' attivo.",
            "type": "text",
            "default": "",
            "example": "Esempio: 'Universita' degli Studi di Roma - A.A. 2024/2025'."
        },
        "title_alignment": {
            "label": "Allineamento titolo",
            "description": "Come viene allineato il titolo principale sulla pagina.",
            "type": "select",
            "options": ["left", "center", "right"],
            "default": "center",
            "example": "center = centrato (standard accademico). left = allineato a sinistra (stile moderno). right = allineato a destra (raro)."
        },
        "body_alignment": {
            "label": "Allineamento testo",
            "description": "Come viene allineato il testo del corpo del documento.",
            "type": "select",
            "options": ["left", "center", "right", "justify"],
            "default": "left",
            "example": "left = allineato a sinistra (piu' leggibile). justify = giustificato (aspetto professionale, standard nelle tesi). center = centrato (solo per testi brevi)."
        },
        "chapter_spacing_before": {
            "label": "Spazio prima capitolo",
            "description": "Spazio verticale aggiunto prima dell'inizio di ogni nuovo capitolo.",
            "type": "number",
            "min": 0, "max": 60, "default": 20, "unit": "pt",
            "example": "20pt aggiunge una breve pausa visiva. 40pt crea una separazione piu' marcata tra capitoli."
        },
        "section_spacing_before": {
            "label": "Spazio prima sezione",
            "description": "Spazio verticale aggiunto prima dell'inizio di ogni nuova sezione.",
            "type": "number",
            "min": 0, "max": 40, "default": 15, "unit": "pt",
            "example": "15pt e' sufficiente per distinguere le sezioni. Deve essere minore dello spazio prima capitolo."
        },
        "paragraph_spacing": {
            "label": "Spazio tra paragrafi",
            "description": "Spazio extra aggiunto tra un paragrafo e il successivo.",
            "type": "number",
            "min": 0, "max": 20, "default": 0, "unit": "pt",
            "example": "0 = nessuno spazio extra (paragrafi separati solo dall'interlinea). 6pt = leggera separazione tra paragrafi."
        },
    },
    "docx": {
        "font_name": {
            "label": "Nome font",
            "description": "Il carattere tipografico usato nel documento Word.",
            "type": "select",
            "options": ["Times New Roman", "Arial", "Calibri", "Georgia", "Garamond", "Cambria"],
            "default": "Times New Roman",
            "example": "Times New Roman = serif classico, standard accademico. Arial = sans-serif, moderno. Calibri = default Word, leggibile. Garamond = serif elegante."
        },
        "font_size": {
            "label": "Dimensione font",
            "description": "La grandezza del testo principale nel documento Word.",
            "type": "number",
            "min": 8, "max": 16, "default": 12, "unit": "pt",
            "example": "12pt e' lo standard accademico per Times New Roman. 11pt per Arial o Calibri."
        },
        "title_alignment": {
            "label": "Allineamento titolo",
            "description": "Come viene allineato il titolo principale nel documento Word.",
            "type": "select",
            "options": ["left", "center", "right"],
            "default": "center",
            "example": "center = centrato (standard per tesi). left = allineato a sinistra."
        },
        "line_spacing": {
            "label": "Interlinea",
            "description": "Spazio tra le righe di testo nel documento Word.",
            "type": "number",
            "min": 1.0, "max": 3.0, "default": 1.5, "step": 0.1,
            "example": "1.5 = una e mezza (standard). 2.0 = doppia (richiesta da molte universita'). 1.15 = compatta."
        },
        "paragraph_spacing_after": {
            "label": "Spazio dopo paragrafo",
            "description": "Spazio aggiunto dopo ogni paragrafo nel documento Word.",
            "type": "number",
            "min": 0, "max": 24, "default": 6, "unit": "pt",
            "example": "6pt = leggera separazione (standard). 12pt = separazione marcata tra paragrafi."
        },
        "include_toc": {
            "label": "Includere indice",
            "description": "Se attivo, inserisce un indice automatico all'inizio del documento Word.",
            "type": "boolean",
            "default": True,
            "example": "L'indice nel DOCX usa gli stili Heading di Word ed e' aggiornabile automaticamente."
        },
        "include_page_numbers": {
            "label": "Numeri di pagina",
            "description": "Se attivo, aggiunge numeri di pagina nel documento Word.",
            "type": "boolean",
            "default": True,
            "example": "I numeri di pagina vengono inseriti nel pie' di pagina del documento Word."
        },
        "toc_indent": {
            "label": "Indentazione indice",
            "description": "Rientro delle voci dell'indice rispetto al margine sinistro.",
            "type": "number",
            "min": 0.0, "max": 2.0, "default": 0.5, "step": 0.1, "unit": "inches",
            "example": "0.5 inches = circa 1.27cm. Le sezioni vengono indentate rispetto ai capitoli."
        },
        "heading1_size": {
            "label": "Dimensione titolo capitoli",
            "description": "La grandezza dei titoli dei capitoli (Heading 1) nel documento Word.",
            "type": "number",
            "min": 12, "max": 28, "default": 16, "unit": "pt",
            "example": "16pt crea una buona gerarchia. Deve essere piu' grande del corpo testo."
        },
        "heading2_size": {
            "label": "Dimensione titolo sezioni",
            "description": "La grandezza dei titoli delle sezioni (Heading 2) nel documento Word.",
            "type": "number",
            "min": 10, "max": 24, "default": 14, "unit": "pt",
            "example": "14pt distingue le sezioni dal corpo testo. Deve essere piu' piccolo di Heading 1."
        },
    }
}


# ============================================================================
# FUNZIONI CRUD
# ============================================================================

def get_export_templates(db: Optional[Session] = None) -> dict:
    """Recupera i template di esportazione dal DB o ritorna i default."""
    if db is None:
        return copy.deepcopy(DEFAULT_EXPORT_TEMPLATES)

    try:
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == 'export_templates'
        ).first()

        if setting and setting.value:
            return setting.value
    except Exception as e:
        logger.warning(f"Errore lettura template da DB, uso default: {e}")

    return copy.deepcopy(DEFAULT_EXPORT_TEMPLATES)


def save_export_templates(templates_data: dict, admin_user_id, db: Session) -> dict:
    """Salva i template di esportazione nel database."""
    templates = templates_data.get("templates", [])
    if not templates:
        raise HTTPException(status_code=400, detail="Deve esserci almeno un template")

    # Verifica che ci sia esattamente un template default
    defaults = [t for t in templates if t.get("is_default")]
    if len(defaults) == 0:
        templates[0]["is_default"] = True
    elif len(defaults) > 1:
        for t in templates:
            t["is_default"] = False
        templates[0]["is_default"] = True

    setting = db.query(SystemSetting).filter(
        SystemSetting.key == 'export_templates'
    ).first()

    if setting:
        setting.value = templates_data
        setting.updated_at = datetime.utcnow()
        setting.updated_by = admin_user_id
    else:
        setting = SystemSetting(
            key='export_templates',
            value=templates_data,
            updated_at=datetime.utcnow(),
            updated_by=admin_user_id
        )
        db.add(setting)

    db.commit()
    return get_export_templates(db)


def delete_template(template_id: str, admin_user_id, db: Session) -> dict:
    """Elimina un template (non quello default)."""
    if template_id == "default":
        raise HTTPException(status_code=400, detail="Non puoi eliminare il template Standard")

    data = get_export_templates(db)
    templates = data.get("templates", [])
    original_len = len(templates)

    templates = [t for t in templates if t.get("id") != template_id]

    if len(templates) == original_len:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' non trovato")

    if not templates:
        raise HTTPException(status_code=400, detail="Deve esserci almeno un template")

    # Se abbiamo eliminato il template default, imposta il primo come default
    if not any(t.get("is_default") for t in templates):
        templates[0]["is_default"] = True

    data["templates"] = templates
    return save_export_templates(data, admin_user_id, db)


def get_template_by_id(template_id: Optional[str], db: Optional[Session] = None) -> dict:
    """Trova un template specifico per ID, o il default."""
    data = get_export_templates(db)
    templates = data.get("templates", [])

    if template_id:
        for t in templates:
            if t.get("id") == template_id:
                return t

    # Ritorna il default
    for t in templates:
        if t.get("is_default"):
            return t

    # Fallback al primo template o ai default hardcoded
    if templates:
        return templates[0]

    return DEFAULT_EXPORT_TEMPLATES["templates"][0]


def generate_template_id() -> str:
    """Genera un ID univoco per un nuovo template."""
    return f"tpl-{uuid.uuid4().hex[:8]}"


# ============================================================================
# PAGE SIZES
# ============================================================================

PAGE_SIZES = {
    "A4": (595, 842),
    "Letter": (612, 792),
    "A5": (420, 595),
}


def get_page_dimensions(page_size: str) -> tuple:
    """Ritorna (width, height) per il formato pagina."""
    return PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])
