"""
Modelli Pydantic per le API di StyleForge.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    """Stati possibili di un job."""
    PENDING = "pending"
    TRAINING = "training"
    READY = "ready"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingRequest(BaseModel):
    """Request per l'addestramento di una sessione."""
    session_id: Optional[str] = Field(None, description="ID sessione (auto-generato se non fornito)")
    max_pages: int = Field(50, ge=1, le=500, description="Numero massimo di pagine PDF da leggere")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "max_pages": 50
            }
        }


class TrainingResponse(BaseModel):
    """Response dell'addestramento."""
    session_id: str
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class GenerationRequest(BaseModel):
    """Request per la generazione di contenuto."""
    session_id: str = Field(..., description="ID della sessione addestrata")
    argomento: str = Field(..., min_length=1, description="Argomento su cui generare contenuto")
    numero_parole: int = Field(..., ge=100, le=10000, description="Numero approssimativo di parole")
    destinatario: str = Field("Pubblico Generale", description="Pubblico destinatario")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "argomento": "Psicopatologia",
                "numero_parole": 1000,
                "destinatario": "Pubblico Generale"
            }
        }


class GenerationResponse(BaseModel):
    """Response della generazione."""
    session_id: str
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class JobType(str, Enum):
    """Tipi di job disponibili."""
    TRAINING = "training"
    GENERATION = "generation"
    HUMANIZATION = "humanization"
    THESIS_GENERATION = "thesis_generation"


class ThesisStatus(str, Enum):
    """Stati possibili di una tesi."""
    DRAFT = "draft"
    CHAPTERS_PENDING = "chapters_pending"
    CHAPTERS_CONFIRMED = "chapters_confirmed"
    SECTIONS_PENDING = "sections_pending"
    SECTIONS_CONFIRMED = "sections_confirmed"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatusResponse(BaseModel):
    """Response per lo stato di un job."""
    job_id: str
    session_id: str
    job_type: JobType
    status: JobStatus
    progress: Optional[int] = Field(None, ge=0, le=100, description="Percentuale completamento")
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class SessionInfo(BaseModel):
    """Informazioni su una sessione."""
    session_id: str
    name: Optional[str] = Field(None, description="Nome descrittivo della sessione")
    is_trained: bool
    conversation_length: int
    created_at: datetime
    last_activity: datetime
    jobs: List[str] = Field(default_factory=list, description="Lista job IDs associati")


class SessionListResponse(BaseModel):
    """Lista di tutte le sessioni attive."""
    sessions: List[SessionInfo]
    total: int


class HumanizeRequest(BaseModel):
    """Request per l'umanizzazione di un testo AI."""
    session_id: str = Field(..., description="ID della sessione addestrata")
    testo: str = Field(..., min_length=50, description="Testo generato da AI da riscrivere")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "testo": "Il testo generato da AI che deve essere riscritto per sembrare umano..."
            }
        }


class HumanizeResponse(BaseModel):
    """Response dell'umanizzazione."""
    session_id: str
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class DetectionRequest(BaseModel):
    """Request per il rilevamento AI."""
    text: str = Field(..., min_length=10, description="Testo da analizzare")
    model_name: str = Field("qwen2-1.5b", description="Modello da usare per il rilevamento")
    threshold: float = Field(0.9, ge=0.1, le=1.0, description="Soglia per la classificazione")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Il testo da analizzare...",
                "model_name": "qwen2-1.5b",
                "threshold": 0.9
            }
        }


class DetectionResponse(BaseModel):
    """Response del rilevamento AI."""
    score: float
    is_ai_generated: bool
    confidence: float
    perplexity_observer: float
    perplexity_performer: float
    threshold: float
    verdict: str


class ErrorResponse(BaseModel):
    """Response per errori."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """Response per health check."""
    status: str
    version: str
    active_sessions: int
    active_jobs: int
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# THESIS GENERATION MODELS
# ============================================================================

class LookupItem(BaseModel):
    """Item generico per lookup tables."""
    id: int
    code: str
    name: str
    description: Optional[str] = None


class WritingStyleResponse(LookupItem):
    """Stile di scrittura."""
    prompt_hint: Optional[str] = None


class ContentDepthResponse(LookupItem):
    """Livello di profondità contenuto."""
    detail_multiplier: float = 1.0


class AudienceKnowledgeLevelResponse(LookupItem):
    """Livello di conoscenza del pubblico."""
    prompt_hint: Optional[str] = None


class AudienceSizeResponse(LookupItem):
    """Dimensione del pubblico."""
    pass


class IndustryResponse(LookupItem):
    """Settore/industria."""
    keywords: List[str] = []


class TargetAudienceResponse(LookupItem):
    """Destinatario target."""
    prompt_hint: Optional[str] = None


class LookupDataResponse(BaseModel):
    """Response con tutti i dati di lookup."""
    writing_styles: List[WritingStyleResponse]
    content_depths: List[ContentDepthResponse]
    knowledge_levels: List[AudienceKnowledgeLevelResponse]
    audience_sizes: List[AudienceSizeResponse]
    industries: List[IndustryResponse]
    target_audiences: List[TargetAudienceResponse]


class AIProviderEnum(str, Enum):
    """Provider AI disponibili per la generazione."""
    OPENAI = "openai"
    CLAUDE = "claude"


class ThesisCreateRequest(BaseModel):
    """Request per creare una nuova tesi."""
    title: str = Field(..., min_length=5, max_length=500, description="Titolo della tesi")
    session_id: Optional[str] = Field(None, description="ID sessione addestrata per lo stile")
    description: Optional[str] = Field(None, description="Descrizione della tesi")
    key_topics: Optional[List[str]] = Field(None, description="Argomenti chiave")
    writing_style_id: int = Field(..., description="ID stile di scrittura")
    content_depth_id: int = Field(..., description="ID livello profondità")
    num_chapters: int = Field(5, ge=1, le=20, description="Numero di capitoli")
    sections_per_chapter: int = Field(3, ge=1, le=10, description="Sezioni per capitolo")
    words_per_section: int = Field(5000, ge=500, le=20000, description="Parole per sezione")
    knowledge_level_id: int = Field(..., description="ID livello conoscenza pubblico")
    audience_size_id: int = Field(..., description="ID dimensione pubblico")
    industry_id: int = Field(..., description="ID settore/industria")
    target_audience_id: int = Field(..., description="ID destinatario target")
    ai_provider: AIProviderEnum = Field(AIProviderEnum.OPENAI, description="Provider AI (openai o claude)")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Intelligenza Artificiale e il Futuro del Lavoro",
                "description": "Analisi dell'impatto dell'AI sul mercato del lavoro",
                "key_topics": ["AI", "automazione", "futuro del lavoro", "competenze"],
                "writing_style_id": 1,
                "content_depth_id": 2,
                "num_chapters": 5,
                "sections_per_chapter": 3,
                "words_per_section": 5000,
                "knowledge_level_id": 2,
                "audience_size_id": 3,
                "industry_id": 3,
                "target_audience_id": 1,
                "ai_provider": "openai"
            }
        }


class ChapterInfo(BaseModel):
    """Informazioni su un capitolo."""
    index: Optional[int] = None  # Opzionale per compatibilità
    title: str
    brief_description: Optional[str] = None
    description: Optional[str] = None  # Alias per compatibilità frontend
    sections: Optional[List[Dict[str, Any]]] = None

    class Config:
        extra = "allow"  # Permetti campi extra per flessibilità

    def model_dump(self, **kwargs):
        """Override per unificare description e brief_description."""
        data = super().model_dump(**kwargs)
        # Usa description se brief_description non è presente
        if not data.get('brief_description') and data.get('description'):
            data['brief_description'] = data['description']
        return data


class ThesisResponse(BaseModel):
    """Response con dati completi della tesi."""
    id: str
    title: str
    description: Optional[str] = None
    key_topics: Optional[List[str]] = None
    session_id: Optional[str] = None
    writing_style_id: Optional[int] = None
    content_depth_id: Optional[int] = None
    num_chapters: int
    sections_per_chapter: int
    words_per_section: int
    knowledge_level_id: Optional[int] = None
    audience_size_id: Optional[int] = None
    industry_id: Optional[int] = None
    target_audience_id: Optional[int] = None
    ai_provider: Optional[str] = Field("openai", description="Provider AI usato")
    chapters_structure: Optional[Dict[str, Any]] = None
    generated_content: Optional[str] = None
    status: ThesisStatus
    current_phase: int
    generation_progress: int
    total_words_generated: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ThesisListResponse(BaseModel):
    """Lista delle tesi dell'utente."""
    theses: List[ThesisResponse]
    total: int


class ThesisAttachmentResponse(BaseModel):
    """Response per un allegato."""
    id: str
    thesis_id: str
    filename: str
    original_filename: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime


class ThesisAttachmentsListResponse(BaseModel):
    """Lista degli allegati di una tesi."""
    attachments: List[ThesisAttachmentResponse]
    total: int


class GenerateChaptersResponse(BaseModel):
    """Response per la generazione dei capitoli."""
    thesis_id: str
    job_id: str
    status: str
    message: str


class ConfirmChaptersRequest(BaseModel):
    """Request per confermare i capitoli."""
    chapters: List[ChapterInfo]


class GenerateSectionsResponse(BaseModel):
    """Response per la generazione delle sezioni."""
    thesis_id: str
    job_id: str
    status: str
    message: str


class SectionInfo(BaseModel):
    """Informazioni su una sezione."""
    index: int
    title: str
    key_points: Optional[List[str]] = None


class ChapterWithSections(BaseModel):
    """Capitolo con le sue sezioni."""
    chapter_index: int
    chapter_title: str
    sections: List[SectionInfo]


class ConfirmSectionsRequest(BaseModel):
    """Request per confermare le sezioni."""
    chapters: List[ChapterWithSections]


class StartContentGenerationResponse(BaseModel):
    """Response per l'avvio della generazione contenuto."""
    thesis_id: str
    job_id: str
    status: str
    message: str
    total_sections: int


class SectionGenerationStatus(BaseModel):
    """Stato di generazione di una sezione."""
    section_index: int
    title: str
    status: str  # 'pending', 'in_progress', 'completed'
    words_count: int = 0


class ChapterGenerationStatus(BaseModel):
    """Stato di generazione di un capitolo."""
    chapter_index: int
    chapter_title: str
    total_sections: int
    completed_sections: int
    status: str  # 'pending', 'in_progress', 'completed'
    sections: List[SectionGenerationStatus] = []


class GenerationStatusResponse(BaseModel):
    """Response con lo stato dettagliato della generazione."""
    thesis_id: str
    status: ThesisStatus
    current_phase: int
    generation_progress: int
    current_chapter: Optional[int] = None
    current_section: Optional[int] = None
    total_sections: int
    completed_sections: int
    chapters: List[ChapterGenerationStatus]
    estimated_time_remaining: Optional[int] = None  # secondi
