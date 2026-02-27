"""
Router FastAPI per la creazione di contenuti Instagram (Carosello / Post / Copertina).
Analizza articoli EduNews24 e genera testi ottimizzati per i social media.
"""

import base64
import json
import re
import logging
from io import BytesIO
from datetime import datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from typing import List, Optional
from anthropic import Anthropic
from sqlalchemy.orm import Session

from auth import require_permission, get_current_admin_user, get_current_active_user
from db_models import User, SystemSetting
from database import get_db
from credits import estimate_credits, deduct_credits
from image_utils import (
    enhance_image_bytes, get_media_type_for_url, get_output_format_for_media_type
)
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/carousel", tags=["Carousel Creator"])

# Anthropic client
_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# ============================================================================
# PROMPT DI DEFAULT (migliorati)
# ============================================================================

DEFAULT_PROMPTS = {
    "carousel": """Sei un content creator esperto di social media per il settore educazione e informazione.
Il tuo compito e' convertire un articolo di EduNews24 in un carosello Instagram testuale da 6 slide.

═══ REGOLE GENERALI ═══
- Nessun emoji, tono sobrio e autorevole
- Non usare trattini o elenchi puntati
- Periodi discorsivi e fluidi
- Evidenzia le parole chiave in **bold** (usa doppio asterisco)
- Tono: accattivante e istituzionale
- VERIFICA LA VERIDICITA' dell'articolo confrontandolo con le tue conoscenze
- Adatta il linguaggio alla categoria dell'articolo (indicata sotto)

═══ STRUTTURA OUTPUT ═══
Rispondi ESCLUSIVAMENTE con un JSON valido, senza testo aggiuntivo, senza code block markdown.

{
  "slides": [
    {
      "numero": 1,
      "titolo": "TITOLO SLIDE 1 (max 5 parole, d'impatto)",
      "contenuto": "Riassunto accattivante dell'articolo che sintetizza cosa trovera' il lettore. Massimo 2 righe, diretto e informativo. Non inserire sottotitolo in questa slide."
    },
    {
      "numero": 2,
      "titolo": "TITOLO SLIDE 2 (max 4 parole)",
      "contenuto": "Introduzione tematica corposa. Spiega perche' l'argomento trattato e' importante oggi. Inserisci una contestualizzazione attuale con approfondimenti."
    },
    {
      "numero": 3,
      "titolo": "TITOLO SLIDE 3 (max 4 parole)",
      "contenuto": "Sviluppa 2-3 concetti fondamentali dell'articolo in modo discorsivo e approfondito. Non fare elenchi puntati. Evita di svelare tutti i dettagli dell'articolo."
    },
    {
      "numero": 4,
      "titolo": "TITOLO SLIDE 4 (max 4 parole)",
      "contenuto": "Approfondimenti utili, strategie vincenti, risorse consigliate o errori comuni. Non svelare tutto, stimola la curiosita' e l'interesse ad approfondire."
    },
    {
      "numero": 5,
      "titolo": "TITOLO SLIDE 5 (max 4 parole)",
      "contenuto": "Prospettiva strategica che rafforza autorevolezza e valore informativo. Non ripetere quanto gia' detto nelle slide precedenti."
    },
    {
      "numero": 6,
      "titolo": "CHIUSURA",
      "contenuto": "Riflessione breve sull'utilita' dell'argomento (max 2 frasi). Poi CTA: invito a leggere l'articolo completo su EduNews24.it"
    }
  ],
  "categoria": "categoria dell'articolo",
  "verifica": "breve nota sulla verifica di veridicita'"
}

═══ ARTICOLO DA ANALIZZARE ═══
Categoria: {categoria}
Titolo: {titolo}

{contenuto}""",

    "post": """Sei un copywriter esperto di social media per il settore educazione e informazione.
Il tuo compito e' generare titolo e sottotitolo per una grafica singola Instagram/Facebook che accompagna un articolo di EduNews24.

═══ REGOLE ═══
- Il TITOLO deve corrispondere esattamente al titolo dell'articolo, in maiuscolo. Massimo 120 caratteri spazi inclusi e massimo 20 parole.
- Il SOTTOTITOLO deve essere una sintesi incisiva che anticipa i punti salienti senza spoilerare l'intero contenuto. Massimo 165 caratteri spazi inclusi e massimo 25 parole.
- Tono giornalistico ma coinvolgente, pensato per giovani e studenti interessati a cultura, educazione, scienza e attualita'.
- Nessun emoji.

═══ STRUTTURA OUTPUT ═══
Rispondi ESCLUSIVAMENTE con un JSON valido, senza testo aggiuntivo, senza code block markdown.

{
  "titolo": "TITOLO IN MAIUSCOLO DELL'ARTICOLO",
  "sottotitolo": "Sottotitolo incisivo e informativo",
  "titolo_chars": numero_caratteri_titolo,
  "sottotitolo_chars": numero_caratteri_sottotitolo
}

═══ ARTICOLO DA ANALIZZARE ═══
Categoria: {categoria}
Titolo: {titolo}

{contenuto}""",

    "copertina": """Sei un social media manager esperto nella creazione di copertine video per Instagram.
Il tuo compito e' riscrivere il titolo di un articolo di EduNews24 in forma di copertina video Instagram: accattivante, breve, perfetta per i social.

═══ REGOLE ═══
- Massimo 160 caratteri
- Deve essere d'impatto e catturare l'attenzione immediatamente
- Usa un hook iniziale forte (domanda retorica, dato sorprendente, affermazione provocatoria)
- Tono diretto, immediato, social-native
- Nessun emoji
- Non deve essere una copia del titolo originale, ma una rielaborazione creativa

═══ STRUTTURA OUTPUT ═══
Rispondi ESCLUSIVAMENTE con un JSON valido, senza testo aggiuntivo, senza code block markdown.

{
  "testo": "Testo della copertina video rielaborato",
  "chars": numero_caratteri
}

═══ ARTICOLO DA ANALIZZARE ═══
Categoria: {categoria}
Titolo: {titolo}

{contenuto}"""
}

SYSTEM_PROMPT = """Sei un esperto di content creation per social media, specializzato nel settore educazione, formazione e informazione italiana.
Rispondi SEMPRE e SOLO in formato JSON valido. Nessun testo aggiuntivo, nessun markdown code block, nessuna spiegazione fuori dal JSON.
Lingua: italiano."""


# ============================================================================
# MODELLI PYDANTIC
# ============================================================================

class ProcessUrlRequest(BaseModel):
    url: str = Field(..., description="URL dell'articolo EduNews24")
    section_type: str = Field(..., pattern="^(carousel|post|copertina)$")

class UpdatePromptRequest(BaseModel):
    section_type: str = Field(..., pattern="^(carousel|post|copertina)$")
    prompt: str = Field(..., min_length=50)

class ExportPdfRequest(BaseModel):
    results: List[dict] = Field(..., description="Array di risultati da esportare")
    section_type: str = Field(..., pattern="^(carousel|post|copertina)$")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_prompts(db: Session) -> dict:
    """Recupera i prompt dal DB o ritorna i default."""
    try:
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == 'carousel_prompts'
        ).first()
        if setting and setting.value:
            merged = DEFAULT_PROMPTS.copy()
            merged.update(setting.value)
            return merged
    except Exception as e:
        logger.warning(f"Errore lettura prompt da DB: {e}")
    return DEFAULT_PROMPTS.copy()


def _extract_category_from_url(url: str) -> str:
    """Estrai la categoria dal path dell'URL EduNews24."""
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip('/').split('/') if p]
        if parts:
            return parts[0]
    except Exception:
        pass
    return "generale"


async def _fetch_article(url: str) -> dict:
    """
    Scarica e parsa un articolo da EduNews24.
    Ritorna dict con titolo, contenuto, og_image, categoria.
    """
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; StyleForge/1.0)"
        })
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Titolo
    og_title = soup.find('meta', property='og:title')
    title = og_title['content'] if og_title and og_title.get('content') else ''
    if not title:
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else ''

    # Immagine
    og_image = soup.find('meta', property='og:image')
    image_url = og_image['content'] if og_image and og_image.get('content') else ''

    # Contenuto articolo
    content = ''
    # Prova selettori comuni WordPress/EduNews24
    for selector in ['.entry-content', '.post-content', 'article .content', 'article']:
        article_el = soup.select_one(selector)
        if article_el:
            # Rimuovi script, style, nav
            for tag in article_el.find_all(['script', 'style', 'nav', 'aside', 'footer']):
                tag.decompose()
            content = article_el.get_text(separator='\n', strip=True)
            break

    if not content:
        # Fallback: prendi tutto il body
        body = soup.find('body')
        if body:
            for tag in body.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            content = body.get_text(separator='\n', strip=True)

    # Limita contenuto a ~8000 caratteri per non eccedere context window
    if len(content) > 8000:
        content = content[:8000] + "\n[...contenuto troncato...]"

    categoria = _extract_category_from_url(url)

    return {
        "titolo": title,
        "contenuto": content,
        "og_image": image_url,
        "categoria": categoria,
    }


async def _fetch_image(image_url: str) -> Optional[bytes]:
    """Scarica un'immagine da URL e ritorna i bytes."""
    if not image_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(image_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StyleForge/1.0)"
            })
            response.raise_for_status()
            if len(response.content) > 10 * 1024 * 1024:  # Max 10MB
                logger.warning(f"Immagine troppo grande: {len(response.content)} bytes")
                return None
            return response.content
    except Exception as e:
        logger.warning(f"Errore download immagine {image_url}: {e}")
        return None


def _parse_ai_response(text: str) -> dict:
    """Parsa la risposta JSON di Claude."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Prova a estrarre JSON dal testo
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Prova con array (per carousel slides)
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return {"slides": json.loads(match.group())}
        except json.JSONDecodeError:
            pass

    logger.warning(f"Impossibile parsare risposta AI: {text[:300]}")
    return {"error": "Impossibile interpretare la risposta AI", "raw": text}


def _generate_pdf(results: list, section_type: str) -> bytes:
    """Genera un PDF dai risultati."""
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    y = 50
    margin = 50
    max_width = 595 - 2 * margin
    line_height = 14
    font_size = 10
    title_font_size = 14

    def add_text(text, size=font_size, bold=False, color=(0, 0, 0)):
        nonlocal y, page
        fontname = "helv"
        lines = text.split('\n')
        for line in lines:
            # Word wrap
            words = line.split(' ')
            current_line = ''
            for word in words:
                test_line = f"{current_line} {word}".strip() if current_line else word
                text_length = fitz.get_text_length(test_line, fontname=fontname, fontsize=size)
                if text_length > max_width and current_line:
                    if y > 792 - margin:
                        page = doc.new_page(width=595, height=842)
                        y = 50
                    page.insert_text((margin, y), current_line, fontname=fontname, fontsize=size, color=color)
                    y += line_height + (2 if size > font_size else 0)
                    current_line = word
                else:
                    current_line = test_line
            if current_line:
                if y > 792 - margin:
                    page = doc.new_page(width=595, height=842)
                    y = 50
                page.insert_text((margin, y), current_line, fontname=fontname, fontsize=size, color=color)
                y += line_height + (2 if size > font_size else 0)

    def add_separator():
        nonlocal y, page
        if y > 792 - margin:
            page = doc.new_page(width=595, height=842)
            y = 50
        y += 5
        page.draw_line((margin, y), (595 - margin, y), color=(0.8, 0.8, 0.8), width=0.5)
        y += 10

    # Header
    section_labels = {"carousel": "Carosello Instagram", "post": "Post Singolo", "copertina": "Copertina Video"}
    add_text(f"StyleForge - {section_labels.get(section_type, section_type)}", size=18, bold=True, color=(0.96, 0.45, 0.09))
    y += 5
    add_text(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", size=8, color=(0.5, 0.5, 0.5))
    y += 10
    add_separator()

    for i, result in enumerate(results):
        article_title = result.get('article_title', f'Articolo {i+1}')
        category = result.get('article_category', '')

        add_text(f"{'─' * 60}", size=8, color=(0.7, 0.7, 0.7))
        y += 3
        add_text(f"ARTICOLO: {article_title}", size=title_font_size, bold=True)
        if category:
            add_text(f"Categoria: {category}", size=9, color=(0.4, 0.4, 0.4))
        y += 5

        content = result.get('content', {})

        if section_type == 'carousel' and isinstance(content.get('slides'), list):
            for slide in content['slides']:
                num = slide.get('numero', '?')
                titolo = slide.get('titolo', '')
                testo = slide.get('contenuto', '')
                add_text(f"SLIDE {num}: {titolo}", size=11, bold=True, color=(0.2, 0.2, 0.6))
                # Rimuovi markdown bold per PDF
                testo_clean = testo.replace('**', '')
                add_text(testo_clean, size=font_size)
                y += 5

        elif section_type == 'post':
            titolo = content.get('titolo', '')
            sottotitolo = content.get('sottotitolo', '')
            add_text(f"TITOLO: {titolo}", size=12, bold=True)
            y += 3
            add_text(f"SOTTOTITOLO: {sottotitolo}", size=11)
            tc = content.get('titolo_chars', len(titolo))
            sc = content.get('sottotitolo_chars', len(sottotitolo))
            add_text(f"Caratteri titolo: {tc} | Caratteri sottotitolo: {sc}", size=8, color=(0.5, 0.5, 0.5))

        elif section_type == 'copertina':
            testo = content.get('testo', '')
            add_text(f"COPERTINA: {testo}", size=12, bold=True)
            chars = content.get('chars', len(testo))
            add_text(f"Caratteri: {chars}", size=8, color=(0.5, 0.5, 0.5))

        y += 10
        add_separator()

    # Salva PDF in bytes
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/process")
async def process_url(
    request: ProcessUrlRequest,
    current_user: User = Depends(require_permission('carousel_creator')),
    db: Session = Depends(get_db),
):
    """Processa un URL di articolo e genera il contenuto Instagram."""

    # Stima e deduzione crediti
    include_image = True
    estimation = estimate_credits('carousel_creator', {'include_image': include_image}, db)
    credits_needed = estimation['credits_needed']
    deduct_credits(
        user=current_user,
        amount=credits_needed,
        operation_type='carousel_creator',
        description=f"Contenuto Instagram ({request.section_type}): {request.url[:80]}",
        db=db
    )

    # 1. Fetch articolo
    try:
        article = await _fetch_article(request.url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Impossibile raggiungere l'articolo: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"Errore fetch articolo: {e}")
        raise HTTPException(status_code=400, detail=f"Errore nel recupero dell'articolo: {str(e)}")

    if not article['contenuto']:
        raise HTTPException(status_code=400, detail="Impossibile estrarre il contenuto dell'articolo")

    # 2. Carica prompt appropriato
    prompts = _get_prompts(db)
    prompt_template = prompts.get(request.section_type, DEFAULT_PROMPTS[request.section_type])

    # Sostituisci placeholders
    prompt = prompt_template.format(
        categoria=article['categoria'],
        titolo=article['titolo'],
        contenuto=article['contenuto']
    )

    # 3. Genera contenuto con Claude
    try:
        response = _client.messages.create(
            model=config.CAROUSEL_CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw_text = response.content[0].text
        content = _parse_ai_response(raw_text)
    except Exception as e:
        logger.error(f"Errore generazione contenuto: {e}")
        raise HTTPException(status_code=500, detail="Errore nella generazione del contenuto AI")

    # 4. Gestione immagine
    image_original_b64 = None
    image_enhanced_b64 = None
    image_analysis = None
    image_format = "jpeg"

    if article['og_image']:
        image_bytes = await _fetch_image(article['og_image'])
        if image_bytes:
            image_original_b64 = base64.b64encode(image_bytes).decode('utf-8')

            # Enhancement con AI
            try:
                media_type = get_media_type_for_url(article['og_image'])
                output_format = get_output_format_for_media_type(media_type)
                enhanced_bytes, analysis, _ = enhance_image_bytes(image_bytes, media_type, output_format)
                image_enhanced_b64 = base64.b64encode(enhanced_bytes).decode('utf-8')
                image_analysis = analysis
                image_format = output_format.lower()
            except Exception as e:
                logger.warning(f"Errore enhancement immagine: {e}")

    return JSONResponse({
        "content": content,
        "article_title": article['titolo'],
        "article_category": article['categoria'],
        "image_original_b64": image_original_b64,
        "image_enhanced_b64": image_enhanced_b64,
        "image_analysis": image_analysis,
        "image_format": image_format,
        "url": request.url,
    })


@router.get("/prompts")
async def get_prompts(
    current_user: User = Depends(require_permission('carousel_creator')),
    db: Session = Depends(get_db),
):
    """Ottieni i prompt correnti per le tre sezioni."""
    prompts = _get_prompts(db)
    return JSONResponse({
        "carousel": prompts.get("carousel", DEFAULT_PROMPTS["carousel"]),
        "post": prompts.get("post", DEFAULT_PROMPTS["post"]),
        "copertina": prompts.get("copertina", DEFAULT_PROMPTS["copertina"]),
    })


@router.put("/prompts")
async def update_prompt(
    request: UpdatePromptRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Aggiorna il prompt di una sezione (solo admin)."""
    setting = db.query(SystemSetting).filter(
        SystemSetting.key == 'carousel_prompts'
    ).first()

    if setting:
        current_value = setting.value or {}
        current_value[request.section_type] = request.prompt
        setting.value = current_value
        setting.updated_at = datetime.utcnow()
        setting.updated_by = current_user.id
    else:
        setting = SystemSetting(
            key='carousel_prompts',
            value={request.section_type: request.prompt},
            updated_at=datetime.utcnow(),
            updated_by=current_user.id
        )
        db.add(setting)

    db.commit()

    return JSONResponse({
        "message": f"Prompt '{request.section_type}' aggiornato con successo",
        "section_type": request.section_type,
    })


@router.post("/export-pdf")
async def export_pdf(
    request: ExportPdfRequest,
    current_user: User = Depends(require_permission('carousel_creator')),
):
    """Esporta i risultati in formato PDF."""
    if not request.results:
        raise HTTPException(status_code=400, detail="Nessun risultato da esportare")

    try:
        pdf_bytes = _generate_pdf(request.results, request.section_type)
    except Exception as e:
        logger.error(f"Errore generazione PDF: {e}")
        raise HTTPException(status_code=500, detail="Errore nella generazione del PDF")

    section_labels = {"carousel": "carosello", "post": "post", "copertina": "copertina"}
    filename = f"styleforge_{section_labels.get(request.section_type, 'contenuti')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
