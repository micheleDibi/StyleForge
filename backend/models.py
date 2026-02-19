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


# ============================================================================
# CREDITS & PERMISSIONS MODELS
# ============================================================================

class CreditEstimateRequest(BaseModel):
    """Request per stimare i crediti di un'operazione."""
    operation_type: str = Field(..., description="Tipo operazione: train, generate, humanize, thesis_chapters, thesis_sections, thesis_content")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parametri dell'operazione")

    class Config:
        json_schema_extra = {
            "example": {
                "operation_type": "generate",
                "params": {"numero_parole": 2000}
            }
        }


class CreditEstimateResponse(BaseModel):
    """Response con stima crediti."""
    credits_needed: int
    breakdown: Dict[str, Any]
    current_balance: int
    sufficient: bool


class CreditTransactionResponse(BaseModel):
    """Response per una singola transazione crediti."""
    id: str
    user_id: str
    amount: int
    balance_after: int
    transaction_type: str
    description: Optional[str] = None
    related_job_id: Optional[str] = None
    operation_type: Optional[str] = None
    created_at: datetime


class CreditTransactionListResponse(BaseModel):
    """Lista transazioni crediti."""
    transactions: List[CreditTransactionResponse]
    total: int


# ============================================================================
# ADMIN MODELS
# ============================================================================

class AdminUserResponse(BaseModel):
    """Response utente dettagliata per admin panel."""
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    credits: int
    permissions: List[str] = []
    user_overrides: Dict[str, bool] = {}  # {permission_code: granted}
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    """Lista utenti per admin."""
    users: List[AdminUserResponse]
    total: int


class AdminUpdateUserRequest(BaseModel):
    """Request per aggiornare un utente (admin)."""
    is_active: Optional[bool] = None
    full_name: Optional[str] = None


class AdminChangeRoleRequest(BaseModel):
    """Request per cambiare il ruolo di un utente."""
    role_id: int


class AdminSetPermissionsRequest(BaseModel):
    """Request per impostare override permessi per un utente."""
    permissions: Dict[str, Optional[bool]] = Field(
        ...,
        description="Dict {permission_code: granted}. null = rimuovi override (eredita dal ruolo)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "permissions": {
                    "train": True,
                    "generate": True,
                    "humanize": None,
                    "thesis": True
                }
            }
        }


class AdminAdjustCreditsRequest(BaseModel):
    """Request per aggiungere/rimuovere crediti."""
    amount: int = Field(..., description="Crediti da aggiungere (positivo) o rimuovere (negativo)")
    description: str = Field(..., min_length=1, description="Motivazione")


class RoleResponse(BaseModel):
    """Response per un ruolo."""
    id: int
    name: str
    description: Optional[str] = None
    is_default: bool
    permissions: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class RoleListResponse(BaseModel):
    """Lista ruoli."""
    roles: List[RoleResponse]


class AdminUpdateRolePermissionsRequest(BaseModel):
    """Request per aggiornare i permessi di un ruolo."""
    permissions: List[str] = Field(..., description="Lista codici permesso da assegnare")

    class Config:
        json_schema_extra = {
            "example": {
                "permissions": ["train", "thesis"]
            }
        }


class AdminStatsResponse(BaseModel):
    """Statistiche per admin dashboard."""
    total_users: int
    active_users: int
    total_credits_distributed: int
    total_credits_consumed: int
    operations_today: int
    operations_this_week: int


# ============================================================================
# ADMIN - CREAZIONE UTENTI
# ============================================================================

class AdminCreateUserRequest(BaseModel):
    """Request per creare un utente dal pannello admin."""
    email: str = Field(..., description="Email dell'utente")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, description="Password")
    full_name: Optional[str] = Field(None, description="Nome completo")
    role_id: Optional[int] = Field(None, description="ID ruolo (default: ruolo 'user')")
    credits: int = Field(0, ge=0, description="Crediti iniziali")
    is_active: bool = Field(True, description="Utente attivo")


# ============================================================================
# ADMIN - CONFIGURAZIONE COSTI CREDITI
# ============================================================================

class CreditCostsUpdateRequest(BaseModel):
    """Request per aggiornare i costi dei crediti."""
    costs: dict = Field(..., description="Dizionario costi crediti per operazione")


class CreditCostsResponse(BaseModel):
    """Response con i costi dei crediti correnti."""
    costs: dict
    is_default: bool = Field(..., description="True se sono i costi default (non personalizzati)")


# ============================================================================
# AI DETECTION - COPYLEAKS
# ============================================================================

class CopyleaksDetectionRequest(BaseModel):
    """Request per il rilevamento AI con Copyleaks."""
    text: str = Field(..., min_length=255, max_length=25000, description="Testo da analizzare (255-25000 caratteri)")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Il testo da analizzare per rilevamento AI..."
            }
        }


class CopyleaksSegment(BaseModel):
    """Segmento di testo classificato da Copyleaks."""
    text: str = Field(..., description="Testo del segmento")
    classification: str = Field(..., description="'ai' o 'human'")
    start: int = Field(..., description="Posizione carattere inizio")
    length: int = Field(..., description="Lunghezza in caratteri")


class CopyleaksDetectionResponse(BaseModel):
    """Response del rilevamento AI con Copyleaks."""
    ai_percentage: float = Field(..., description="Percentuale testo AI (0-100)")
    human_percentage: float = Field(..., description="Percentuale testo umano (0-100)")
    total_words: int = Field(..., description="Parole totali analizzate")
    segments: List[CopyleaksSegment] = Field(default_factory=list, description="Segmenti classificati")
    model_version: str = Field("", description="Versione modello Copyleaks")
    scan_id: str = Field("", description="ID scansione")


class CopyleaksReportRequest(BaseModel):
    """Request per generare il report PDF del rilevamento AI."""
    text: str = Field(..., description="Testo originale analizzato")
    segments: List[CopyleaksSegment] = Field(..., description="Segmenti classificati")
    ai_percentage: float = Field(..., description="Percentuale AI")
    human_percentage: float = Field(..., description="Percentuale umano")


# ============================================================================
# EXPORT TEMPLATES
# ============================================================================

class PdfTemplateSettings(BaseModel):
    """Impostazioni template PDF."""
    page_size: str = Field("A4", description="Formato pagina: A4, Letter, A5")
    margin_top: int = Field(50, ge=20, le=150, description="Margine superiore (pt)")
    margin_bottom: int = Field(50, ge=20, le=150, description="Margine inferiore (pt)")
    margin_left: int = Field(50, ge=20, le=150, description="Margine sinistro (pt)")
    margin_right: int = Field(50, ge=20, le=150, description="Margine destro (pt)")
    font_body: str = Field("helv", description="Font corpo testo")
    font_body_size: int = Field(11, ge=8, le=16, description="Dimensione font corpo (pt)")
    font_title_size: int = Field(24, ge=14, le=36, description="Dimensione font titolo (pt)")
    font_chapter_size: int = Field(18, ge=12, le=28, description="Dimensione font capitoli (pt)")
    font_section_size: int = Field(14, ge=10, le=22, description="Dimensione font sezioni (pt)")
    line_height_multiplier: float = Field(1.5, ge=1.0, le=3.0, description="Moltiplicatore interlinea")
    include_toc: bool = Field(True, description="Includere indice")
    include_page_numbers: bool = Field(True, description="Includere numeri pagina")
    page_number_position: str = Field("bottom_center", description="Posizione numeri pagina")
    include_header: bool = Field(False, description="Includere intestazione")
    header_text: str = Field("", description="Testo intestazione")
    include_footer: bool = Field(False, description="Includere pie' di pagina")
    footer_text: str = Field("", description="Testo pie' di pagina")
    title_alignment: str = Field("center", description="Allineamento titolo: left, center, right")
    body_alignment: str = Field("left", description="Allineamento corpo: left, center, right, justify")
    chapter_spacing_before: int = Field(20, ge=0, le=60, description="Spazio prima capitolo (pt)")
    section_spacing_before: int = Field(15, ge=0, le=40, description="Spazio prima sezione (pt)")
    paragraph_spacing: int = Field(0, ge=0, le=20, description="Spazio tra paragrafi (pt)")

    class Config:
        extra = "allow"


class DocxTemplateSettings(BaseModel):
    """Impostazioni template DOCX."""
    font_name: str = Field("Times New Roman", description="Nome font")
    font_size: int = Field(12, ge=8, le=16, description="Dimensione font corpo (pt)")
    title_alignment: str = Field("center", description="Allineamento titolo")
    line_spacing: float = Field(1.5, ge=1.0, le=3.0, description="Interlinea")
    paragraph_spacing_after: int = Field(6, ge=0, le=24, description="Spazio dopo paragrafo (pt)")
    include_toc: bool = Field(True, description="Includere indice")
    include_page_numbers: bool = Field(True, description="Includere numeri pagina")
    toc_indent: float = Field(0.5, ge=0.0, le=2.0, description="Indentazione indice (inches)")
    heading1_size: int = Field(16, ge=12, le=28, description="Dimensione heading 1 (pt)")
    heading2_size: int = Field(14, ge=10, le=24, description="Dimensione heading 2 (pt)")

    class Config:
        extra = "allow"


class ExportTemplate(BaseModel):
    """Template di esportazione completo."""
    id: str = Field(..., description="ID univoco template")
    name: str = Field(..., min_length=1, max_length=100, description="Nome template")
    is_default: bool = Field(False, description="Se questo e' il template predefinito")
    pdf: PdfTemplateSettings = Field(default_factory=PdfTemplateSettings)
    docx: DocxTemplateSettings = Field(default_factory=DocxTemplateSettings)


class ExportTemplateListResponse(BaseModel):
    """Response con lista template."""
    templates: List[ExportTemplate]
    help: Dict[str, Any] = Field(default_factory=dict, description="Descrizioni parametri per tooltip")


class ExportTemplateUpdateRequest(BaseModel):
    """Request per aggiornare i template."""
    templates: List[ExportTemplate] = Field(..., description="Lista completa template")
