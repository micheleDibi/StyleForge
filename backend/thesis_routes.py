"""
Router FastAPI per la gestione delle tesi/relazioni.

Questo modulo contiene tutti gli endpoint relativi alla funzionalità
di generazione tesi, inclusi lookup, CRUD, allegati e fasi di generazione.
"""

import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import text

from models import (
    ThesisCreateRequest, ThesisResponse, ThesisListResponse,
    ThesisAttachmentResponse, ThesisAttachmentsListResponse,
    GenerateChaptersResponse, ConfirmChaptersRequest,
    GenerateSectionsResponse, ConfirmSectionsRequest,
    StartContentGenerationResponse, GenerationStatusResponse,
    ChapterGenerationStatus, LookupDataResponse,
    WritingStyleResponse, ContentDepthResponse,
    AudienceKnowledgeLevelResponse, AudienceSizeResponse,
    IndustryResponse, TargetAudienceResponse,
    ThesisStatus, ChapterInfo
)
from db_models import (
    User, Thesis, ThesisAttachment, ThesisGenerationJob,
    WritingStyle, ContentDepthLevel, AudienceKnowledgeLevel,
    AudienceSize, Industry, TargetAudience, Session
)
from database import SessionLocal, get_db
from auth import get_current_active_user
from attachment_processor import (
    process_attachment, save_uploaded_file, delete_attachment_file,
    build_attachments_context, cleanup_thesis_attachments
)
from ai_client import get_ai_client, humanize_text_with_claude
from session_manager import session_manager
import config

# Router
router = APIRouter(prefix="/api/thesis", tags=["Thesis Generation"])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_thesis_by_id(db: DBSession, thesis_id: str, user_id: str) -> Thesis:
    """Recupera una tesi verificando l'ownership."""
    thesis = db.query(Thesis).filter(
        Thesis.id == thesis_id,
        Thesis.user_id == user_id
    ).first()

    if not thesis:
        raise HTTPException(status_code=404, detail="Tesi non trovata")

    return thesis


def build_thesis_data_dict(thesis: Thesis, db: DBSession) -> dict:
    """Costruisce il dizionario con tutti i dati della tesi per i prompt."""
    data = {
        "title": thesis.title,
        "description": thesis.description,
        "key_topics": thesis.key_topics or [],
        "num_chapters": thesis.num_chapters,
        "sections_per_chapter": thesis.sections_per_chapter,
        "words_per_section": thesis.words_per_section,
    }

    # Carica i dati di lookup
    if thesis.writing_style_id:
        style = db.query(WritingStyle).get(thesis.writing_style_id)
        if style:
            data["writing_style_name"] = style.name
            data["writing_style_hint"] = style.prompt_hint or ""

    if thesis.content_depth_id:
        depth = db.query(ContentDepthLevel).get(thesis.content_depth_id)
        if depth:
            data["content_depth_name"] = depth.name

    if thesis.knowledge_level_id:
        level = db.query(AudienceKnowledgeLevel).get(thesis.knowledge_level_id)
        if level:
            data["knowledge_level_name"] = level.name
            data["knowledge_level_hint"] = level.prompt_hint or ""

    if thesis.audience_size_id:
        size = db.query(AudienceSize).get(thesis.audience_size_id)
        if size:
            data["audience_size_name"] = size.name

    if thesis.industry_id:
        industry = db.query(Industry).get(thesis.industry_id)
        if industry:
            data["industry_name"] = industry.name

    if thesis.target_audience_id:
        target = db.query(TargetAudience).get(thesis.target_audience_id)
        if target:
            data["target_audience_name"] = target.name
            data["target_audience_hint"] = target.prompt_hint or ""

    return data


# ============================================================================
# LOOKUP ENDPOINTS
# ============================================================================

@router.get("/lookup", response_model=LookupDataResponse)
async def get_all_lookup_data(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce tutti i dati di lookup in una singola chiamata."""
    writing_styles = db.query(WritingStyle).filter(
        WritingStyle.is_active == True
    ).order_by(WritingStyle.sort_order).all()

    content_depths = db.query(ContentDepthLevel).filter(
        ContentDepthLevel.is_active == True
    ).order_by(ContentDepthLevel.sort_order).all()

    knowledge_levels = db.query(AudienceKnowledgeLevel).filter(
        AudienceKnowledgeLevel.is_active == True
    ).order_by(AudienceKnowledgeLevel.sort_order).all()

    audience_sizes = db.query(AudienceSize).filter(
        AudienceSize.is_active == True
    ).order_by(AudienceSize.sort_order).all()

    industries = db.query(Industry).filter(
        Industry.is_active == True
    ).order_by(Industry.sort_order).all()

    target_audiences = db.query(TargetAudience).filter(
        TargetAudience.is_active == True
    ).order_by(TargetAudience.sort_order).all()

    return LookupDataResponse(
        writing_styles=[WritingStyleResponse(**s.to_dict()) for s in writing_styles],
        content_depths=[ContentDepthResponse(**d.to_dict()) for d in content_depths],
        knowledge_levels=[AudienceKnowledgeLevelResponse(**l.to_dict()) for l in knowledge_levels],
        audience_sizes=[AudienceSizeResponse(**s.to_dict()) for s in audience_sizes],
        industries=[IndustryResponse(**i.to_dict()) for i in industries],
        target_audiences=[TargetAudienceResponse(**t.to_dict()) for t in target_audiences]
    )


@router.get("/lookup/writing-styles")
async def get_writing_styles(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce gli stili di scrittura disponibili."""
    styles = db.query(WritingStyle).filter(
        WritingStyle.is_active == True
    ).order_by(WritingStyle.sort_order).all()
    return {"styles": [s.to_dict() for s in styles]}


@router.get("/lookup/content-depths")
async def get_content_depths(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce i livelli di profondità contenuto."""
    levels = db.query(ContentDepthLevel).filter(
        ContentDepthLevel.is_active == True
    ).order_by(ContentDepthLevel.sort_order).all()
    return {"levels": [l.to_dict() for l in levels]}


@router.get("/lookup/knowledge-levels")
async def get_knowledge_levels(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce i livelli di conoscenza del pubblico."""
    levels = db.query(AudienceKnowledgeLevel).filter(
        AudienceKnowledgeLevel.is_active == True
    ).order_by(AudienceKnowledgeLevel.sort_order).all()
    return {"levels": [l.to_dict() for l in levels]}


@router.get("/lookup/audience-sizes")
async def get_audience_sizes(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce le dimensioni del pubblico."""
    sizes = db.query(AudienceSize).filter(
        AudienceSize.is_active == True
    ).order_by(AudienceSize.sort_order).all()
    return {"sizes": [s.to_dict() for s in sizes]}


@router.get("/lookup/industries")
async def get_industries(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce i settori/industrie."""
    industries = db.query(Industry).filter(
        Industry.is_active == True
    ).order_by(Industry.sort_order).all()
    return {"industries": [i.to_dict() for i in industries]}


@router.get("/lookup/target-audiences")
async def get_target_audiences(
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Restituisce i destinatari target."""
    audiences = db.query(TargetAudience).filter(
        TargetAudience.is_active == True
    ).order_by(TargetAudience.sort_order).all()
    return {"audiences": [a.to_dict() for a in audiences]}


# ============================================================================
# THESIS CRUD ENDPOINTS
# ============================================================================

@router.post("", response_model=ThesisResponse)
async def create_thesis(
    request: ThesisCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Crea una nuova tesi/relazione.

    Richiede tutti i parametri di configurazione.
    """
    # Verifica sessione se specificata
    session_uuid = None
    if request.session_id:
        session = db.query(Session).filter(
            Session.session_id == request.session_id,
            Session.user_id == current_user.id
        ).first()
        if session:
            session_uuid = session.id

    # Crea la tesi
    thesis = Thesis(
        user_id=current_user.id,
        session_id=session_uuid,
        title=request.title,
        description=request.description,
        key_topics=request.key_topics,
        writing_style_id=request.writing_style_id,
        content_depth_id=request.content_depth_id,
        num_chapters=request.num_chapters,
        sections_per_chapter=request.sections_per_chapter,
        words_per_section=request.words_per_section,
        knowledge_level_id=request.knowledge_level_id,
        audience_size_id=request.audience_size_id,
        industry_id=request.industry_id,
        target_audience_id=request.target_audience_id,
        ai_provider=request.ai_provider.value if request.ai_provider else "openai",
        status='draft'
    )

    db.add(thesis)
    db.commit()
    db.refresh(thesis)

    return ThesisResponse(**thesis.to_dict())


@router.get("", response_model=ThesisListResponse)
async def list_theses(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Elenca tutte le tesi dell'utente."""
    query = db.query(Thesis).filter(Thesis.user_id == current_user.id)

    if status:
        query = query.filter(Thesis.status == status)

    theses = query.order_by(Thesis.created_at.desc()).all()

    return ThesisListResponse(
        theses=[ThesisResponse(**t.to_dict()) for t in theses],
        total=len(theses)
    )


@router.get("/{thesis_id}", response_model=ThesisResponse)
async def get_thesis(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Ottiene i dettagli di una tesi."""
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))
    return ThesisResponse(**thesis.to_dict())


@router.delete("/{thesis_id}")
async def delete_thesis(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Elimina una tesi e tutti i suoi dati."""
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    # Elimina allegati dal filesystem
    cleanup_thesis_attachments(thesis_id)

    # Elimina dal database (cascade eliminerà allegati e job)
    db.delete(thesis)
    db.commit()

    return {"message": "Tesi eliminata con successo"}


# ============================================================================
# ATTACHMENTS ENDPOINTS
# ============================================================================

@router.post("/{thesis_id}/attachments", response_model=ThesisAttachmentsListResponse)
async def upload_attachments(
    thesis_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Carica allegati per una tesi.

    Supporta PDF, DOCX, TXT. Estrae automaticamente il testo.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    # Verifica limite allegati
    existing_count = db.query(ThesisAttachment).filter(
        ThesisAttachment.thesis_id == thesis.id
    ).count()

    if existing_count + len(files) > config.THESIS_MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Superato il limite di {config.THESIS_MAX_ATTACHMENTS} allegati"
        )

    uploaded = []

    for file in files:
        # Leggi contenuto
        content = await file.read()

        # Salva file
        file_path = save_uploaded_file(content, file.filename, thesis_id)

        try:
            # Processa e estrai testo
            attachment_data = process_attachment(file_path, file.filename)

            # Salva nel database
            attachment = ThesisAttachment(
                thesis_id=thesis.id,
                filename=attachment_data["filename"],
                original_filename=attachment_data["original_filename"],
                file_path=attachment_data["file_path"],
                file_size=attachment_data["file_size"],
                mime_type=attachment_data["mime_type"],
                extracted_text=attachment_data["extracted_text"]
            )

            db.add(attachment)
            db.commit()
            db.refresh(attachment)

            uploaded.append(ThesisAttachmentResponse(**attachment.to_dict()))

        except Exception as e:
            # Se fallisce, elimina il file
            delete_attachment_file(str(file_path))
            raise HTTPException(status_code=400, detail=str(e))

    return ThesisAttachmentsListResponse(
        attachments=uploaded,
        total=len(uploaded)
    )


@router.get("/{thesis_id}/attachments", response_model=ThesisAttachmentsListResponse)
async def list_attachments(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Elenca gli allegati di una tesi."""
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    attachments = db.query(ThesisAttachment).filter(
        ThesisAttachment.thesis_id == thesis.id
    ).order_by(ThesisAttachment.created_at).all()

    return ThesisAttachmentsListResponse(
        attachments=[ThesisAttachmentResponse(**a.to_dict()) for a in attachments],
        total=len(attachments)
    )


@router.delete("/{thesis_id}/attachments/{attachment_id}")
async def delete_attachment(
    thesis_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """Elimina un allegato."""
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    attachment = db.query(ThesisAttachment).filter(
        ThesisAttachment.id == attachment_id,
        ThesisAttachment.thesis_id == thesis.id
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Allegato non trovato")

    # Elimina file
    delete_attachment_file(attachment.file_path)

    # Elimina dal database
    db.delete(attachment)
    db.commit()

    return {"message": "Allegato eliminato con successo"}


# ============================================================================
# GENERATION ENDPOINTS
# ============================================================================

def generate_chapters_task(thesis_id: str, user_id: str):
    """Task background per generare i capitoli."""
    db = SessionLocal()
    try:
        thesis = db.query(Thesis).get(thesis_id)
        if not thesis:
            return

        # Costruisci i dati per il prompt
        thesis_data = build_thesis_data_dict(thesis, db)

        # Costruisci contesto allegati
        attachments = db.query(ThesisAttachment).filter(
            ThesisAttachment.thesis_id == thesis.id
        ).all()
        attachments_context = build_attachments_context(
            [a.to_dict() | {"extracted_text": a.extracted_text} for a in attachments]
        )

        # Genera capitoli con il provider AI selezionato
        provider = thesis.ai_provider or "openai"
        client = get_ai_client(provider)
        logger.info(f"Generazione capitoli con provider: {provider}")
        result = client.generate_chapters(thesis_data, attachments_context)

        # Salva risultato
        thesis.chapters_structure = result
        thesis.status = 'chapters_pending'
        thesis.current_phase = 1

        # Aggiorna job
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis.id,
            ThesisGenerationJob.phase == 'chapters'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'completed'
            job.result = json.dumps(result)
            job.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        # Aggiorna job con errore
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis_id,
            ThesisGenerationJob.phase == 'chapters'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'failed'
            job.error = str(e)
            db.commit()

        # Aggiorna stato tesi
        thesis = db.query(Thesis).get(thesis_id)
        if thesis:
            thesis.status = 'failed'
            db.commit()

    finally:
        db.close()


@router.post("/{thesis_id}/generate-chapters")
async def generate_chapters(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    FASE 1: Genera i titoli dei capitoli.

    Utilizza OpenAI per generare l'indice basato sui parametri.
    L'utente potrà modificare i titoli prima di confermare.
    Generazione sincrona per risposta immediata.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    if thesis.status not in ['draft', 'failed']:
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile generare capitoli: stato attuale '{thesis.status}'"
        )

    try:
        # Costruisci i dati per il prompt
        thesis_data = build_thesis_data_dict(thesis, db)

        # Costruisci contesto allegati
        attachments = db.query(ThesisAttachment).filter(
            ThesisAttachment.thesis_id == thesis.id
        ).all()
        attachments_context = build_attachments_context(
            [a.to_dict() | {"extracted_text": a.extracted_text} for a in attachments]
        )

        # Genera capitoli con il provider AI selezionato (sincrono)
        provider = thesis.ai_provider or "openai"
        client = get_ai_client(provider)
        logger.info(f"Generazione capitoli (sincrono) con provider: {provider}")
        result = client.generate_chapters(thesis_data, attachments_context)

        # Salva risultato
        thesis.chapters_structure = result
        thesis.status = 'chapters_pending'
        thesis.current_phase = 1
        db.commit()

        # Restituisci i capitoli generati
        chapters = result.get("chapters", [])
        return {
            "thesis_id": str(thesis.id),
            "status": "chapters_pending",
            "chapters": chapters,
            "message": "Capitoli generati con successo. Puoi modificarli prima di confermare."
        }

    except Exception as e:
        thesis.status = 'failed'
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione dei capitoli: {str(e)}"
        )


@router.put("/{thesis_id}/chapters")
async def confirm_chapters(
    thesis_id: str,
    request: ConfirmChaptersRequest,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Conferma i titoli dei capitoli (eventualmente modificati dall'utente).
    """
    logger.info(f"Conferma capitoli per tesi {thesis_id}")
    logger.info(f"Capitoli ricevuti: {len(request.chapters)}")

    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    logger.info(f"Stato attuale tesi: {thesis.status}")

    # Permetti conferma se lo stato è chapters_pending o se già chapters_confirmed (retry)
    if thesis.status not in ['chapters_pending', 'chapters_confirmed']:
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile confermare capitoli: stato attuale '{thesis.status}'"
        )

    try:
        # Aggiorna struttura con i capitoli confermati
        chapters_data = []
        for c in request.chapters:
            chapter_dict = c.model_dump()
            # Assicurati che brief_description sia presente
            if not chapter_dict.get('brief_description') and chapter_dict.get('description'):
                chapter_dict['brief_description'] = chapter_dict['description']
            chapters_data.append(chapter_dict)

        thesis.chapters_structure = {"chapters": chapters_data}
        thesis.status = 'chapters_confirmed'
        thesis.num_chapters = len(request.chapters)

        db.commit()
        logger.info(f"Capitoli confermati con successo per tesi {thesis_id}")

        return {"message": "Capitoli confermati con successo", "status": "chapters_confirmed"}

    except Exception as e:
        logger.error(f"Errore conferma capitoli: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel salvataggio dei capitoli: {str(e)}"
        )


def generate_sections_task(thesis_id: str, user_id: str):
    """Task background per generare le sezioni."""
    db = SessionLocal()
    try:
        thesis = db.query(Thesis).get(thesis_id)
        if not thesis:
            return

        # Costruisci dati
        thesis_data = build_thesis_data_dict(thesis, db)
        chapters = thesis.chapters_structure.get("chapters", [])

        # Costruisci contesto allegati
        attachments = db.query(ThesisAttachment).filter(
            ThesisAttachment.thesis_id == thesis.id
        ).all()
        attachments_context = build_attachments_context(
            [a.to_dict() | {"extracted_text": a.extracted_text} for a in attachments]
        )

        # Genera sezioni con il provider AI selezionato
        provider = thesis.ai_provider or "openai"
        client = get_ai_client(provider)
        logger.info(f"Generazione sezioni con provider: {provider}")
        result = client.generate_sections(thesis_data, chapters, attachments_context)

        # Salva risultato
        thesis.chapters_structure = result
        thesis.status = 'sections_pending'
        thesis.current_phase = 2

        # Aggiorna job
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis.id,
            ThesisGenerationJob.phase == 'sections'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'completed'
            job.result = json.dumps(result)
            job.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis_id,
            ThesisGenerationJob.phase == 'sections'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'failed'
            job.error = str(e)
            db.commit()

        thesis = db.query(Thesis).get(thesis_id)
        if thesis:
            thesis.status = 'failed'
            db.commit()

    finally:
        db.close()


@router.post("/{thesis_id}/generate-sections")
async def generate_sections(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    FASE 2: Genera i titoli delle sezioni per ogni capitolo.

    Richiede che i capitoli siano stati confermati.
    Generazione sincrona per risposta immediata.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    if thesis.status != 'chapters_confirmed':
        raise HTTPException(
            status_code=400,
            detail=f"Devi prima confermare i capitoli. Stato attuale: '{thesis.status}'"
        )

    try:
        # Costruisci dati
        thesis_data = build_thesis_data_dict(thesis, db)
        chapters = thesis.chapters_structure.get("chapters", [])

        # Costruisci contesto allegati
        attachments = db.query(ThesisAttachment).filter(
            ThesisAttachment.thesis_id == thesis.id
        ).all()
        attachments_context = build_attachments_context(
            [a.to_dict() | {"extracted_text": a.extracted_text} for a in attachments]
        )

        # Genera sezioni con il provider AI selezionato (sincrono)
        provider = thesis.ai_provider or "openai"
        client = get_ai_client(provider)
        logger.info(f"Generazione sezioni (sincrono) con provider: {provider}")
        result = client.generate_sections(thesis_data, chapters, attachments_context)

        # Salva risultato
        thesis.chapters_structure = result
        thesis.status = 'sections_pending'
        thesis.current_phase = 2
        db.commit()

        # Restituisci le sezioni generate
        chapters_with_sections = result.get("chapters", [])
        return {
            "thesis_id": str(thesis.id),
            "status": "sections_pending",
            "chapters": chapters_with_sections,
            "message": "Sezioni generate con successo. Puoi modificarle prima di confermare."
        }

    except Exception as e:
        thesis.status = 'failed'
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione delle sezioni: {str(e)}"
        )


@router.put("/{thesis_id}/sections")
async def confirm_sections(
    thesis_id: str,
    request: ConfirmSectionsRequest,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Conferma i titoli delle sezioni (eventualmente modificati).
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    if thesis.status != 'sections_pending':
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile confermare sezioni: stato attuale '{thesis.status}'"
        )

    # Aggiorna struttura
    thesis.chapters_structure = {
        "chapters": [c.model_dump() for c in request.chapters]
    }
    thesis.status = 'sections_confirmed'

    db.commit()

    return {"message": "Sezioni confermate con successo", "status": "sections_confirmed"}


def _humanize_content(content: str, trained_session_client, section_name: str = "Sezione") -> str:
    """Helper per umanizzare il contenuto con fallback."""
    try:
        if trained_session_client:
            logger.info(f"Umanizzazione con sessione addestrata per: {section_name}")
            return trained_session_client.umanizzazione(content)
        else:
            logger.info(f"Umanizzazione con Claude per: {section_name}")
            return humanize_text_with_claude(content)
    except Exception as e:
        logger.warning(f"Errore umanizzazione Claude: {e}, uso fallback algoritmico")
        try:
            from anti_ai_processor import humanize_text_post_processing
            return humanize_text_post_processing(content)
        except Exception:
            return content


def _ensure_word_count(client, content: str, target_words: int, context_info: str, max_tokens: int) -> str:
    """
    Verifica che il contenuto raggiunga il target di parole.
    Se è sotto il 70%, chiede al modello di continuare ed espandere.
    Effettua al massimo 2 tentativi di continuazione.
    """
    for attempt in range(2):
        current_words = len(content.split())
        if current_words >= target_words * 0.70:
            return content

        missing_words = target_words - current_words
        logger.info(
            f"Contenuto troppo corto ({current_words}/{target_words} parole) "
            f"per {context_info}. Tentativo di espansione {attempt + 1}/2..."
        )

        continuation_prompt = f"""Il testo seguente dovrebbe avere ALMENO {target_words} parole, ma ne ha solo circa {current_words}.

⚠️ DEVI aggiungere almeno {missing_words} parole NUOVE per raggiungere il target.

REGOLE:
- Continua il discorso da dove si è interrotto
- NON ripetere concetti già scritti — approfondisci con nuovi dettagli, esempi, analisi
- NON scrivere "in conclusione" o "per riassumere" — stai CONTINUANDO, non chiudendo
- Mantieni lo stesso stile e tono del testo esistente
- Se il testo contiene citazioni [x], mantienile e puoi aggiungerne di nuove (solo fonti REALI)

TESTO ESISTENTE DA CONTINUARE:

{content[-3000:]}

═══════════════════════════════════════════════════════════════
SCRIVI la continuazione (almeno {missing_words} parole):"""

        try:
            continuation = client.generate_text(continuation_prompt, max_tokens=max_tokens)
            content = content.rstrip() + "\n\n" + continuation.strip()
        except Exception as e:
            logger.warning(f"Errore nella continuazione: {e}")
            break

    return content


def generate_content_task(thesis_id: str, user_id: str):
    """Task background per generare il contenuto completo."""
    db = SessionLocal()
    try:
        thesis = db.query(Thesis).get(thesis_id)
        if not thesis:
            return

        thesis_data = build_thesis_data_dict(thesis, db)
        chapters = thesis.chapters_structure.get("chapters", [])

        # Costruisci contesto allegati
        attachments = db.query(ThesisAttachment).filter(
            ThesisAttachment.thesis_id == thesis.id
        ).all()
        attachments_context = build_attachments_context(
            [a.to_dict() | {"extracted_text": a.extracted_text} for a in attachments]
        )

        # Verifica se c'è una sessione addestrata per umanizzazione avanzata
        trained_session_client = None
        author_style_context = ""
        if thesis.session_id:
            session = db.query(Session).get(thesis.session_id)
            if session and session.is_trained:
                author_style_context = "Applica lo stile dell'autore appreso durante l'addestramento."
                # Carica il client della sessione addestrata per umanizzazione completa
                try:
                    trained_session_client = session_manager.get_session(
                        session.session_id,
                        user_id
                    )
                    if not trained_session_client.is_trained:
                        trained_session_client = None
                        logger.info(f"Sessione {session.session_id} non addestrata, uso umanizzazione algoritmica")
                except Exception as e:
                    logger.warning(f"Impossibile caricare sessione addestrata: {e}")
                    trained_session_client = None

        # Usa il provider AI selezionato per la generazione contenuto
        provider = thesis.ai_provider or "openai"
        client = get_ai_client(provider)
        logger.info(f"Generazione contenuto con provider: {provider}")

        # Import prompt builders per capitoli speciali
        from thesis_prompts import build_introduction_prompt, build_conclusion_prompt, build_bibliography_prompt

        generated_chapters_content = []
        raw_chapters_content = []  # Contenuto PRE-umanizzazione per la bibliografia
        previous_summary = ""

        # Total: sezioni normali + 3 (introduzione, conclusione, bibliografia)
        total_sections = sum(len(c.get("sections", [])) for c in chapters) + 3
        completed_sections = 0

        # Calcola max_tokens dinamico per le generazioni
        words_per_section = thesis_data.get('words_per_section', 5000)
        dynamic_max_tokens = max(int(words_per_section * 2.5) + 2000, 16000)

        # Raccoglie titoli dei capitoli per i prompt di intro/conclusione
        chapters_titles = [
            c.get('chapter_title') or c.get('title', f"Capitolo {i+1}")
            for i, c in enumerate(chapters)
        ]

        # ===================================================================
        # FASE 1: Genera contenuto dei capitoli normali (con citazioni [x])
        # ===================================================================
        for chapter in chapters:
            chapter_content = f"\n\n# {chapter.get('chapter_title', 'Capitolo')}\n\n"
            raw_chapter_content = ""

            for section in chapter.get("sections", []):
                # Genera contenuto sezione
                raw_content = client.generate_section_content(
                    thesis_data=thesis_data,
                    chapter=chapter,
                    section=section,
                    previous_sections_summary=previous_summary,
                    attachments_context=attachments_context,
                    author_style_context=author_style_context
                )

                # Verifica word count e richiedi continuazione se troppo corto
                section_label = f"Cap. {chapter.get('chapter_index', '?')} - {section.get('title', 'Sezione')}"
                raw_content = _ensure_word_count(
                    client, raw_content, words_per_section,
                    section_label, dynamic_max_tokens
                )

                # Salva contenuto raw per la bibliografia (con citazioni [x] intatte)
                raw_chapter_content += f"\n{raw_content}\n"

                # Applica umanizzazione
                content = _humanize_content(raw_content, trained_session_client, section.get('title', 'Sezione'))

                section_text = f"\n## {section.get('title', 'Sezione')}\n\n{content}\n"
                chapter_content += section_text

                # Aggiorna riassunto per coerenza
                if len(content) > 500:
                    previous_summary += f"\n- {section.get('title', 'Sezione')}: {content[:300]}..."

                completed_sections += 1

                # Aggiorna progress
                progress = int((completed_sections / total_sections) * 100)
                thesis.generation_progress = progress
                thesis.total_words_generated += len(content.split())
                db.commit()

            generated_chapters_content.append(chapter_content)
            raw_chapters_content.append(raw_chapter_content)

        # ===================================================================
        # FASE 2: Genera INTRODUZIONE
        # ===================================================================
        logger.info("Generazione Introduzione...")
        intro_prompt = build_introduction_prompt(
            thesis_data=thesis_data,
            chapters_titles=chapters_titles,
            attachments_context=attachments_context,
            author_style_context=author_style_context
        )
        intro_content = client.generate_text(intro_prompt, max_tokens=dynamic_max_tokens)
        intro_content = _ensure_word_count(
            client, intro_content, words_per_section, "Introduzione", dynamic_max_tokens
        )
        intro_content = _humanize_content(intro_content, trained_session_client, "Introduzione")

        completed_sections += 1
        progress = int((completed_sections / total_sections) * 100)
        thesis.generation_progress = progress
        thesis.total_words_generated += len(intro_content.split())
        db.commit()

        # ===================================================================
        # FASE 3: Genera CONCLUSIONE
        # ===================================================================
        logger.info("Generazione Conclusione...")
        # Costruisci riassunto completo per la conclusione
        conclusion_summary = previous_summary
        conclusion_prompt = build_conclusion_prompt(
            thesis_data=thesis_data,
            content_summary=conclusion_summary,
            chapters_titles=chapters_titles,
            author_style_context=author_style_context
        )
        conclusion_content = client.generate_text(conclusion_prompt, max_tokens=dynamic_max_tokens)
        conclusion_content = _ensure_word_count(
            client, conclusion_content, words_per_section, "Conclusione", dynamic_max_tokens
        )
        conclusion_content = _humanize_content(conclusion_content, trained_session_client, "Conclusione")

        completed_sections += 1
        progress = int((completed_sections / total_sections) * 100)
        thesis.generation_progress = progress
        thesis.total_words_generated += len(conclusion_content.split())
        db.commit()

        # ===================================================================
        # FASE 4: Genera BIBLIOGRAFIA
        # ===================================================================
        logger.info("Generazione Bibliografia...")
        # Usa il contenuto RAW (pre-umanizzazione) per trovare le citazioni [x]
        # perché l'umanizzazione potrebbe averle alterate
        all_raw_text = "\n".join(raw_chapters_content)
        # Fallback: se il raw non ha citazioni, prova anche con il contenuto umanizzato
        import re as _re
        raw_citations = _re.findall(r'\[\d+\]', all_raw_text)
        if not raw_citations:
            # Prova con il contenuto umanizzato (l'anti-AI ora preserva le citazioni)
            all_raw_text = "\n".join(generated_chapters_content)
        bibliography_prompt = build_bibliography_prompt(
            thesis_data=thesis_data,
            all_content=all_raw_text
        )
        bibliography_content = client.generate_text(bibliography_prompt)
        # NON umanizzare la bibliografia (è una lista formale)

        completed_sections += 1
        thesis.generation_progress = 100
        db.commit()

        # ===================================================================
        # FASE 5: Assembla contenuto finale
        # ===================================================================
        # Ordine: Introduzione → Capitoli → Conclusione → Bibliografia
        final_content_parts = []

        # Introduzione
        final_content_parts.append(f"\n\n# Introduzione\n\n{intro_content}\n")

        # Capitoli normali
        final_content_parts.extend(generated_chapters_content)

        # Conclusione
        final_content_parts.append(f"\n\n# Conclusione\n\n{conclusion_content}\n")

        # Bibliografia
        final_content_parts.append(f"\n\n# Bibliografia\n\n{bibliography_content}\n")

        # Salva contenuto finale
        thesis.generated_content = "\n".join(final_content_parts)

        # ===================================================================
        # FASE 6: Aggiorna chapters_structure con capitoli speciali per TOC
        # ===================================================================
        updated_chapters = []

        # Introduzione (primo)
        updated_chapters.append({
            "chapter_index": 0,
            "chapter_title": "Introduzione",
            "is_special": True
        })

        # Capitoli normali (rinumerati da 1)
        for i, ch in enumerate(chapters):
            ch_copy = dict(ch)
            ch_copy["chapter_index"] = i + 1
            updated_chapters.append(ch_copy)

        # Conclusione (penultimo)
        updated_chapters.append({
            "chapter_index": len(chapters) + 1,
            "chapter_title": "Conclusione",
            "is_special": True
        })

        # Bibliografia (ultimo)
        updated_chapters.append({
            "chapter_index": len(chapters) + 2,
            "chapter_title": "Bibliografia",
            "is_special": True
        })

        thesis.chapters_structure = {"chapters": updated_chapters}
        thesis.status = 'completed'
        thesis.current_phase = 3
        thesis.generation_progress = 100
        thesis.completed_at = datetime.utcnow()

        # Aggiorna job
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis.id,
            ThesisGenerationJob.phase == 'content'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'completed'
            job.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        job = db.query(ThesisGenerationJob).filter(
            ThesisGenerationJob.thesis_id == thesis_id,
            ThesisGenerationJob.phase == 'content'
        ).order_by(ThesisGenerationJob.created_at.desc()).first()

        if job:
            job.status = 'failed'
            job.error = str(e)
            db.commit()

        thesis = db.query(Thesis).get(thesis_id)
        if thesis:
            thesis.status = 'failed'
            db.commit()

    finally:
        db.close()


@router.post("/{thesis_id}/generate-content", response_model=StartContentGenerationResponse)
async def start_content_generation(
    thesis_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    FASE 3: Avvia la generazione del contenuto.

    Genera ogni sezione una alla volta, applicando umanizzazione.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    if thesis.status != 'sections_confirmed':
        raise HTTPException(
            status_code=400,
            detail=f"Devi prima confermare le sezioni. Stato attuale: '{thesis.status}'"
        )

    chapters = thesis.chapters_structure.get("chapters", [])
    total_sections = sum(len(c.get("sections", [])) for c in chapters)

    # Aggiorna stato
    thesis.status = 'generating'
    thesis.current_phase = 3
    thesis.generation_progress = 0

    # Crea job
    job_id = f"thesis_content_{uuid.uuid4().hex[:8]}"
    job = ThesisGenerationJob(
        thesis_id=thesis.id,
        job_id=job_id,
        phase='content',
        status='pending'
    )
    db.add(job)
    db.commit()

    # Avvia task
    background_tasks.add_task(generate_content_task, str(thesis.id), str(current_user.id))

    return StartContentGenerationResponse(
        thesis_id=str(thesis.id),
        job_id=job_id,
        status='generating',
        message="Generazione contenuto avviata",
        total_sections=total_sections
    )


@router.get("/{thesis_id}/generation-status", response_model=GenerationStatusResponse)
async def get_generation_status(
    thesis_id: str,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Ottiene lo stato dettagliato della generazione.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    chapters = thesis.chapters_structure.get("chapters", []) if thesis.chapters_structure else []
    total_sections = sum(len(c.get("sections", [])) for c in chapters)
    completed_sections = int(total_sections * thesis.generation_progress / 100) if thesis.generation_progress else 0

    # Calcola capitolo/sezione corrente
    current_chapter = 0
    current_section = 0
    sections_counted = 0

    for i, ch in enumerate(chapters):
        ch_sections = len(ch.get("sections", []))
        if sections_counted + ch_sections > completed_sections:
            current_chapter = i
            current_section = completed_sections - sections_counted
            break
        sections_counted += ch_sections

    # Costruisci stato per capitolo
    chapters_status = []
    for i, ch in enumerate(chapters):
        ch_sections = len(ch.get("sections", []))
        ch_completed = 0

        if i < current_chapter:
            ch_completed = ch_sections
            ch_status = 'completed'
        elif i == current_chapter:
            ch_completed = current_section
            ch_status = 'in_progress' if thesis.status == 'generating' else 'pending'
        else:
            ch_status = 'pending'

        chapters_status.append(ChapterGenerationStatus(
            chapter_index=i,
            chapter_title=ch.get("chapter_title", f"Capitolo {i+1}"),
            total_sections=ch_sections,
            completed_sections=ch_completed,
            status=ch_status
        ))

    return GenerationStatusResponse(
        thesis_id=str(thesis.id),
        status=ThesisStatus(thesis.status),
        current_phase=thesis.current_phase,
        generation_progress=thesis.generation_progress,
        current_chapter=current_chapter if thesis.status == 'generating' else None,
        current_section=current_section if thesis.status == 'generating' else None,
        total_sections=total_sections,
        completed_sections=completed_sections,
        chapters=chapters_status,
        estimated_time_remaining=None  # TODO: calcolare in base a media
    )


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

def generate_table_of_contents(chapters_structure: dict, format_type: str = "txt") -> str:
    """
    Genera l'indice della tesi basato sulla struttura dei capitoli.

    Supporta capitoli speciali (Introduzione, Conclusione, Bibliografia)
    che non hanno sezioni e vengono mostrati solo come titolo.

    Args:
        chapters_structure: Dizionario con la struttura dei capitoli
        format_type: "txt", "md" o "pdf"

    Returns:
        Stringa formattata con l'indice
    """
    if not chapters_structure or "chapters" not in chapters_structure:
        return ""

    chapters = chapters_structure.get("chapters", [])
    if not chapters:
        return ""

    if format_type == "md":
        # Formato Markdown
        toc = "## Indice\n\n"
        for ch_idx, chapter in enumerate(chapters):
            ch_title = chapter.get("chapter_title") or chapter.get("title", f"Capitolo {ch_idx + 1}")
            is_special = chapter.get("is_special", False)

            if is_special:
                # Capitoli speciali (Introduzione, Conclusione, Bibliografia)
                toc += f"**{ch_title}**\n\n"
            else:
                ch_num = chapter.get("chapter_index", ch_idx + 1)
                toc += f"**Capitolo {ch_num}: {ch_title}**\n\n"

                sections = chapter.get("sections", [])
                for sec_idx, section in enumerate(sections):
                    sec_num = section.get("index", sec_idx + 1)
                    sec_title = section.get("title", f"Sezione {sec_num}")
                    toc += f"  - {ch_num}.{sec_num}: {sec_title}\n"
                toc += "\n"

        toc += "---\n\n"
        return toc

    else:
        # Formato TXT (anche per PDF e DOCX)
        separator = "═" * 65
        toc = f"{separator}\n"
        toc += "                           INDICE\n"
        toc += f"{separator}\n\n"

        for ch_idx, chapter in enumerate(chapters):
            ch_title = chapter.get("chapter_title") or chapter.get("title", f"Capitolo {ch_idx + 1}")
            is_special = chapter.get("is_special", False)

            if is_special:
                # Capitoli speciali senza sezioni
                toc += f"{ch_title}\n\n"
            else:
                ch_num = chapter.get("chapter_index", ch_idx + 1)
                toc += f"Capitolo {ch_num}: {ch_title}\n"

                sections = chapter.get("sections", [])
                for sec_idx, section in enumerate(sections):
                    sec_num = section.get("index", sec_idx + 1)
                    sec_title = section.get("title", f"Sezione {sec_num}")
                    toc += f"    {ch_num}.{sec_num}: {sec_title}\n"
                toc += "\n"

        toc += f"{separator}\n\n"
        return toc


@router.get("/{thesis_id}/export")
async def export_thesis(
    thesis_id: str,
    format: str = "pdf",
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_db)
):
    """
    Esporta la tesi completata nel formato richiesto.

    Formati supportati: pdf, txt, md, docx
    Include automaticamente l'indice all'inizio del documento.
    """
    thesis = get_thesis_by_id(db, thesis_id, str(current_user.id))

    if thesis.status != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"La tesi non è ancora completata. Stato: '{thesis.status}'"
        )

    if not thesis.generated_content:
        raise HTTPException(status_code=404, detail="Nessun contenuto generato")

    content = thesis.generated_content
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in thesis.title[:50] if c.isalnum() or c in ' _-').strip()

    # Genera l'indice
    toc = generate_table_of_contents(thesis.chapters_structure, format)

    if format == "txt":
        # Export TXT con indice
        full_content = f"{thesis.title}\n{'=' * len(thesis.title)}\n\n"
        if thesis.description:
            full_content += f"{thesis.description}\n\n"
        full_content += toc
        full_content += content

        file_path = config.RESULTS_DIR / f"thesis_{safe_title}_{timestamp}.txt"
        file_path.write_text(full_content, encoding='utf-8')

        return FileResponse(
            path=file_path,
            filename=f"tesi_{safe_title}.txt",
            media_type="text/plain"
        )

    elif format == "md":
        # Export Markdown con indice
        md_content = f"# {thesis.title}\n\n"
        if thesis.description:
            md_content += f"*{thesis.description}*\n\n---\n\n"
        md_content += toc
        md_content += content

        file_path = config.RESULTS_DIR / f"thesis_{safe_title}_{timestamp}.md"
        file_path.write_text(md_content, encoding='utf-8')

        return FileResponse(
            path=file_path,
            filename=f"tesi_{safe_title}.md",
            media_type="text/markdown"
        )

    elif format == "docx":
        # Export DOCX con indice
        from docx import Document as DocxDocument
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        file_path = config.RESULTS_DIR / f"thesis_{safe_title}_{timestamp}.docx"

        doc = DocxDocument()

        # Imposta stile del documento
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)

        # Titolo principale
        title_para = doc.add_heading(thesis.title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Descrizione
        if thesis.description:
            desc_para = doc.add_paragraph()
            desc_run = desc_para.add_run(thesis.description)
            desc_run.italic = True
            desc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph()  # Spazio

        # Indice
        chapters_for_toc = thesis.chapters_structure.get("chapters", []) if thesis.chapters_structure else []
        if chapters_for_toc:
            doc.add_heading('Indice', level=1)

            for ch_idx, chapter in enumerate(chapters_for_toc):
                ch_title = chapter.get("chapter_title") or chapter.get("title", f"Capitolo {ch_idx + 1}")
                is_special = chapter.get("is_special", False)

                if is_special:
                    # Capitoli speciali (Introduzione, Conclusione, Bibliografia)
                    toc_para = doc.add_paragraph()
                    toc_run = toc_para.add_run(ch_title)
                    toc_run.bold = True
                    toc_run.font.size = Pt(11)
                else:
                    ch_num = chapter.get("chapter_index", ch_idx + 1)
                    toc_para = doc.add_paragraph()
                    toc_run = toc_para.add_run(f"Capitolo {ch_num}: {ch_title}")
                    toc_run.bold = True
                    toc_run.font.size = Pt(11)

                    sections = chapter.get("sections", [])
                    for sec_idx, section in enumerate(sections):
                        sec_num = section.get("index", sec_idx + 1)
                        sec_title = section.get("title", f"Sezione {sec_num}")
                        sec_para = doc.add_paragraph(
                            f"    {ch_num}.{sec_num}: {sec_title}",
                            style='List Bullet'
                        )
                        sec_para.paragraph_format.left_indent = Inches(0.5)
                        for run in sec_para.runs:
                            run.font.size = Pt(10)

            doc.add_page_break()

        # Contenuto
        for line in content.split('\n'):
            if line.startswith('# '):
                doc.add_heading(line[2:], level=1)
            elif line.startswith('## '):
                doc.add_heading(line[3:], level=2)
            elif line.strip():
                para = doc.add_paragraph(line)
                para.paragraph_format.space_after = Pt(6)
            # Righe vuote: non aggiungere nulla (spazio naturale)

        doc.save(str(file_path))

        return FileResponse(
            path=file_path,
            filename=f"tesi_{safe_title}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    else:
        # Export PDF (default) con indice
        import fitz

        file_path = config.RESULTS_DIR / f"thesis_{safe_title}_{timestamp}.pdf"

        doc = fitz.open()
        page_width = 595
        page_height = 842
        margin = 50
        font_size = 11
        line_height = font_size * 1.5

        current_page = doc.new_page(width=page_width, height=page_height)
        y = margin

        # Titolo principale
        current_page.insert_text(
            (margin, y + 30),
            thesis.title,
            fontsize=20,
            fontname="helv"
        )
        y += 50

        # Descrizione (se presente)
        if thesis.description:
            current_page.insert_text(
                (margin, y + 10),
                thesis.description,
                fontsize=12,
                fontname="helv"
            )
            y += 40

        # Separatore
        y += 20

        # Indice
        if toc:
            current_page.insert_text(
                (margin, y),
                "INDICE",
                fontsize=14,
                fontname="helv"
            )
            y += 25

            # Linea separatrice
            current_page.draw_line(
                fitz.Point(margin, y),
                fitz.Point(page_width - margin, y),
                color=(0.7, 0.7, 0.7),
                width=1
            )
            y += 15

            # Contenuto indice
            chapters = thesis.chapters_structure.get("chapters", []) if thesis.chapters_structure else []
            for ch_idx, chapter in enumerate(chapters):
                if y + line_height * 2 > page_height - margin:
                    current_page = doc.new_page(width=page_width, height=page_height)
                    y = margin

                ch_title = chapter.get("chapter_title") or chapter.get("title", f"Capitolo {ch_idx + 1}")
                is_special = chapter.get("is_special", False)

                if is_special:
                    # Capitoli speciali senza sezioni
                    current_page.insert_text(
                        (margin, y),
                        ch_title,
                        fontsize=11,
                        fontname="helv"
                    )
                    y += line_height
                else:
                    ch_num = chapter.get("chapter_index", ch_idx + 1)

                    current_page.insert_text(
                        (margin, y),
                        f"Capitolo {ch_num}: {ch_title}",
                        fontsize=11,
                        fontname="helv"
                    )
                    y += line_height

                    sections = chapter.get("sections", [])
                    for sec_idx, section in enumerate(sections):
                        if y + line_height > page_height - margin:
                            current_page = doc.new_page(width=page_width, height=page_height)
                            y = margin

                        sec_num = section.get("index", sec_idx + 1)
                        sec_title = section.get("title", f"Sezione {sec_num}")

                        current_page.insert_text(
                            (margin + 20, y),
                            f"{ch_num}.{sec_num}: {sec_title}",
                            fontsize=10,
                            fontname="helv"
                        )
                        y += line_height * 0.9

                y += 5  # Spazio tra capitoli

            # Separatore dopo indice
            y += 15
            current_page.draw_line(
                fitz.Point(margin, y),
                fitz.Point(page_width - margin, y),
                color=(0.7, 0.7, 0.7),
                width=1
            )
            y += 30

        # Nuova pagina per il contenuto
        current_page = doc.new_page(width=page_width, height=page_height)
        y = margin

        # Contenuto
        for line in content.split('\n'):
            if y + line_height > page_height - margin:
                current_page = doc.new_page(width=page_width, height=page_height)
                y = margin

            # Gestisci titoli
            if line.startswith('# '):
                y += 20
                current_page.insert_text(
                    (margin, y),
                    line[2:],
                    fontsize=16,
                    fontname="helv"
                )
                y += 25
            elif line.startswith('## '):
                y += 15
                current_page.insert_text(
                    (margin, y),
                    line[3:],
                    fontsize=14,
                    fontname="helv"
                )
                y += 20
            elif line.strip():
                # Wrap text
                words = line.split()
                current_line = []
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if len(test_line) * (font_size * 0.5) < (page_width - margin * 2):
                        current_line.append(word)
                    else:
                        if current_line:
                            if y + line_height > page_height - margin:
                                current_page = doc.new_page(width=page_width, height=page_height)
                                y = margin
                            current_page.insert_text(
                                (margin, y),
                                ' '.join(current_line),
                                fontsize=font_size,
                                fontname="helv"
                            )
                            y += line_height
                        current_line = [word]

                if current_line:
                    if y + line_height > page_height - margin:
                        current_page = doc.new_page(width=page_width, height=page_height)
                        y = margin
                    current_page.insert_text(
                        (margin, y),
                        ' '.join(current_line),
                        fontsize=font_size,
                        fontname="helv"
                    )
                    y += line_height
            else:
                y += line_height * 0.5

        doc.save(file_path)
        doc.close()

        return FileResponse(
            path=file_path,
            filename=f"tesi_{safe_title}.pdf",
            media_type="application/pdf"
        )
