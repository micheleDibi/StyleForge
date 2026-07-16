"""
Modelli Pydantic per le API di StyleForge.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime

import config


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
    profile: Literal['informal', 'academic'] = Field(
        'academic',
        description="Profilo anti-AI: 'academic' (register-safe, autori formali) o 'informal' (colloquiale)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "argomento": "Psicopatologia",
                "numero_parole": 1000,
                "destinatario": "Pubblico Generale",
                "profile": "academic"
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
    COMPILATIO_SCAN = "compilatio_scan"
    WIKI_INGEST = "wiki_ingest"
    WIKI_LINT = "wiki_lint"


class ThesisWikiStatus(str, Enum):
    """Stati del wiki LLM (second-brain) di una tesi."""
    NONE = "none"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    LINTING = "linting"
    LINTED = "linted"
    FAILED = "failed"


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
    name: Optional[str] = Field(None, description="Nome descrittivo del job")
    session_id: Optional[str] = Field(None, description="ID sessione associata (opzionale)")
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
    profile: Literal['informal', 'academic'] = Field(
        'informal',
        description="Profilo anti-AI: 'informal' (più aggressivo) o 'academic' (registro formale, protegge citazioni e note)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "testo": "Il testo generato da AI che deve essere riscritto per sembrare umano...",
                "profile": "informal"
            }
        }


class HumanizeResponse(BaseModel):
    """Response dell'umanizzazione."""
    session_id: str
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class HumanizeDocumentResponse(BaseModel):
    """Response dell'umanizzazione di un documento .docx (mantiene il template)."""
    session_id: str
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class AntiAICorrectionRequest(BaseModel):
    """Request per la Correzione Anti-AI (senza sessione addestrata)."""
    testo: str = Field(..., min_length=50, description="Testo da correggere (micro-modifiche per ridurre AI detection)")
    profile: Literal['informal', 'academic'] = Field(
        'informal',
        description="Profilo anti-AI: 'informal' (più aggressivo) o 'academic' (registro formale, protegge citazioni e note)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "testo": "Il testo da correggere con micro-modifiche anti-AI...",
                "profile": "informal"
            }
        }


class ExtractTextResponse(BaseModel):
    """Response dell'estrazione testo da file caricato (file non persistito)."""
    text: str
    filename: str
    word_count: int
    char_count: int


class AntiAICorrectionResponse(BaseModel):
    """Response della Correzione Anti-AI."""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class RenameRequest(BaseModel):
    """Request per rinominare un'entita' (sessione o job)."""
    name: str = Field(..., min_length=1, max_length=255, description="Nuovo nome")



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


class CustomSectionInput(BaseModel):
    """Singola sezione/paragrafo dell'outline custom fornito dall'utente."""
    title: str = Field(..., min_length=1, max_length=500)
    key_points: List[str] = Field(default_factory=list)


class CustomChapterInput(BaseModel):
    """Singolo capitolo dell'outline custom fornito dall'utente."""
    title: str = Field(..., min_length=1, max_length=500)
    brief_description: Optional[str] = Field(None, max_length=2000)
    sections: List[CustomSectionInput] = Field(..., min_length=1)


class CustomOutlineInput(BaseModel):
    """
    Outline custom completo fornito dall'utente come alternativa
    ai parametri numerici (num_chapters, sections_per_chapter).
    """
    chapters: List[CustomChapterInput] = Field(..., min_length=1, max_length=100)


class ThesisCreateRequest(BaseModel):
    """Request per creare una nuova tesi."""
    title: str = Field(..., min_length=5, max_length=500, description="Titolo della tesi")
    session_id: Optional[str] = Field(None, description="ID sessione addestrata per lo stile")
    description: Optional[str] = Field(None, description="Descrizione della tesi")
    key_topics: Optional[List[str]] = Field(None, description="Argomenti chiave")
    writing_style_id: int = Field(..., description="ID stile di scrittura")
    content_depth_id: int = Field(..., description="ID livello profondità")
    num_chapters: int = Field(5, ge=1, le=100, description="Numero di capitoli")
    sections_per_chapter: int = Field(3, ge=1, le=30, description="Sezioni per capitolo")
    words_per_section: int = Field(5000, ge=500, le=20000, description="Parole per sezione")
    knowledge_level_id: int = Field(..., description="ID livello conoscenza pubblico")
    audience_size_id: Optional[int] = Field(None, description="ID dimensione pubblico (opzionale)")
    industry_id: int = Field(..., description="ID settore/industria")
    target_audience_id: int = Field(..., description="ID destinatario target")
    ai_provider: AIProviderEnum = Field(AIProviderEnum.OPENAI, description="Provider AI (openai o claude)")
    citation_style: Optional[str] = Field("footnotes", description="Stile citazioni: 'footnotes' (note a piè di pagina) o 'bibliography' (citazioni [x])")
    restrict_to_sources: bool = Field(True, description="Se True la generazione si attiene SOLO alle fonti caricate (paper + upload). Se False permette anche conoscenza generale del modello.")
    use_custom_outline: bool = Field(False, description="Se True l'utente fornisce l'indice custom (custom_outline). Salta la generazione AI di capitoli/sezioni e non addebita i relativi crediti.")
    custom_outline: Optional[CustomOutlineInput] = Field(None, description="Indice custom fornito dall'utente. Richiesto se use_custom_outline=True.")

    @model_validator(mode="after")
    def _validate_custom_outline_consistency(self):
        if self.use_custom_outline and self.custom_outline is None:
            raise ValueError("use_custom_outline=True richiede custom_outline non-null con almeno 1 capitolo")
        return self

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
                "ai_provider": "openai",
                "citation_style": "footnotes",
                "restrict_to_sources": True,
                "use_custom_outline": False,
                "custom_outline": None
            }
        }


class ThesisUrlAttachmentRequest(BaseModel):
    """Request per aggiungere URL come allegati alla tesi."""
    urls: List[str] = Field(
        ...,
        min_length=1,
        max_length=config.THESIS_MAX_ATTACHMENTS,
        description="Lista di URL da usare come fonti di riferimento",
    )

    @field_validator("urls")
    @classmethod
    def _urls_non_vuoti(cls, v: List[str]) -> List[str]:
        """
        Solo forma e igiene: la lista non e' un posto dove decidere se un URL e'
        sicuro. Un HttpUrl qui non fermerebbe ne' un IP interno ne' un
        rebinding, che e' il motivo per cui il vero controllo sta nella guard
        (ssrf_guard), prima di ogni fetch.
        """
        puliti = [str(u).strip() for u in v if str(u).strip()]
        if not puliti:
            raise ValueError("Inserisci almeno un URL")
        return puliti


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
    citation_style: Optional[str] = Field("footnotes", description="Stile citazioni")
    chapters_structure: Optional[Dict[str, Any]] = None
    generated_content: Optional[str] = None
    status: ThesisStatus
    current_phase: int
    generation_progress: int
    total_words_generated: int
    credits_charged: bool = False
    restrict_to_sources: bool = True
    wiki_status: ThesisWikiStatus = ThesisWikiStatus.NONE
    wiki_path: Optional[str] = None
    wiki_lint_report: Optional[Dict[str, Any]] = None
    wiki_ingested_at: Optional[datetime] = None
    wiki_linted_at: Optional[datetime] = None
    use_custom_outline: bool = False
    custom_outline: Optional[Dict[str, Any]] = None
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


class ThesisResearchFilters(BaseModel):
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    open_access_only: bool = False
    min_citations: Optional[int] = Field(None, ge=0)
    venue_contains: Optional[str] = None
    author_contains: Optional[str] = None


class ThesisResearchSearchRequest(BaseModel):
    """Request per cercare paper accademici dentro il wizard tesi."""
    topic: str = Field(..., min_length=2, max_length=500)
    sources: Optional[List[str]] = None
    filters: Optional[ThesisResearchFilters] = None
    sort_by: str = Field("composite", pattern="^(composite|citations|recency|title)$")
    per_provider_limit: int = Field(30, ge=5, le=50)
    final_limit: int = Field(40, ge=1, le=100)


class ThesisResearchSummarizeRequest(BaseModel):
    """Request per generare il riassunto AI di un paper dal wizard tesi."""
    paper: Dict[str, Any] = Field(..., description="UnifiedPaper serializzato")


class ThesisAddPaperItem(BaseModel):
    """Singolo paper da aggiungere come fonte alla tesi.

    Se `summary` viene passato (perché l'utente l'ha già richiesto manualmente),
    il backend lo riusa senza riaddebitare crediti. Se assente, lo genera.
    """
    paper: Dict[str, Any] = Field(..., description="UnifiedPaper serializzato")
    summary: Optional[Dict[str, Any]] = Field(None, description="SummaryResult serializzato (opzionale)")


class ThesisAddPapersRequest(BaseModel):
    """Request per salvare paper selezionati come allegati di tesi."""
    items: List[ThesisAddPaperItem] = Field(..., min_length=1, max_length=50)


class ThesisAddPapersResponse(BaseModel):
    """Response dell'aggiunta paper: include gli attachment creati e il riepilogo crediti."""
    attachments: List[ThesisAttachmentResponse]
    total: int
    summarized_count: int = Field(0, description="Numero di riassunti AI generati al volo")
    credits_consumed: int = Field(0, description="Crediti totali consumati per i riassunti AI")


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
# LLM WIKI (second-brain per-tesi) MODELS
# ============================================================================

class WikiIngestRequest(BaseModel):
    """Request opzionale per avviare l'ingest del wiki di una tesi.

    Se force=True, ricicla il wiki/ esistente (snapshot pre-overwrite); utile
    per ri-eseguire dopo aggiunte di nuove fonti.
    """
    force: bool = Field(False, description="Se True ricostruisce il wiki anche se gia' ingested")


class WikiStatusResponse(BaseModel):
    """Stato del wiki di una tesi (polling-friendly)."""
    thesis_id: str
    wiki_status: ThesisWikiStatus
    wiki_path: Optional[str] = None
    sources_count: int = Field(0, description="Numero di file in raw/")
    pages_count: int = Field(0, description="Numero di pagine generate in wiki/")
    job_id: Optional[str] = Field(None, description="ID del job in corso (se ingesting/linting)")
    job_progress: Optional[int] = Field(None, ge=0, le=100)
    job_error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = Field(
        None,
        description="Progresso granulare ingest: { phase, percent, message, files, started_at, updated_at }",
    )
    wiki_ingested_at: Optional[datetime] = None
    wiki_linted_at: Optional[datetime] = None


class WikiLintReportResponse(BaseModel):
    """Report di lint del wiki: pagine orfane, link rotti, contraddizioni, gaps."""
    thesis_id: str
    wiki_status: ThesisWikiStatus
    report: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON con {orphan_pages, broken_wikilinks, missing_concepts, contradictions, stale_pages, frontmatter_issues, exploration_suggestions, gaps}"
    )
    generated_at: Optional[datetime] = None


class WikiContentItem(BaseModel):
    """Una pagina estratta dal wiki, in forma leggibile per l'utente."""
    slug: str
    title: str
    summary: str = ""
    subtype: Optional[str] = None
    fonti: Optional[int] = None
    tag: List[str] = []


class WikiContentCategory(BaseModel):
    key: str
    label: str
    count: int
    items: List[WikiContentItem] = []


class WikiContentResponse(BaseModel):
    """Informazioni estratte dai documenti, raggruppate per categoria (vista utente)."""
    thesis_id: str
    wiki_status: ThesisWikiStatus
    totals: Dict[str, int] = {}
    categories: List[WikiContentCategory] = []


# ============================================================================
# PAPER KEYWORD SUGGESTIONS (estrazione keyword dai documenti caricati)
# ============================================================================

class PaperKeywordSuggestResponse(BaseModel):
    """Response dell'endpoint suggest-paper-keywords."""
    thesis_id: str
    keywords: List[str] = Field(
        default_factory=list,
        description="Lista di 5-8 termini di ricerca estratti dai documenti caricati"
    )
    eligible_attachments_count: int = Field(
        0, description="Numero di allegati testuali considerati"
    )
    credits_consumed: int = Field(
        0, description="Crediti effettivamente addebitati per l'operazione"
    )


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


class ApiCostEstimateRequest(BaseModel):
    """Request per stimare il costo API in EUR (solo admin)."""
    mode: str = Field(..., description="Modalita': correction, full, train, generate, thesis")
    word_count: int = Field(0, ge=0, description="Numero di parole del testo")
    session_id: Optional[str] = Field(None, description="ID sessione (per mode full/generate)")
    max_pages: Optional[int] = Field(None, description="Pagine PDF (per mode train)")
    num_words: Optional[int] = Field(None, description="Parole richieste (per mode generate)")
    num_chapters: Optional[int] = Field(None, description="Numero capitoli (per mode thesis)")
    sections_per_chapter: Optional[int] = Field(None, description="Sezioni per capitolo (per mode thesis)")
    words_per_section: Optional[int] = Field(None, description="Parole per sezione (per mode thesis)")
    ai_provider: Optional[str] = Field(None, description="Provider AI: openai o claude (per mode thesis)")
    thesis_id: Optional[str] = Field(None, description="ID tesi (per caricare allegati nella stima thesis)")
    attachments_total_size: Optional[int] = Field(None, description="Dimensione totale allegati in bytes (per stima thesis)")


class ApiCostEstimateResponse(BaseModel):
    """Response con stima costo API in EUR."""
    estimated_cost_eur: float
    breakdown: Dict[str, Any]


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
    email_verified: bool = False
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    credits: int
    permissions: List[str] = []
    user_overrides: Dict[str, bool] = {}  # {permission_code: granted}
    entity_type: Optional[str] = 'privato'
    parent_id: Optional[str] = None  # genitore nell'albero di distribuzione
    distributor_id: Optional[str] = None  # DEPRECATO: alias legacy di parent_id
    codice_fiscale: Optional[str] = None
    partita_iva: Optional[str] = None
    ragione_sociale: Optional[str] = None
    indirizzo_fatturazione: Optional[str] = None
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
    entity_type: Optional[str] = Field(
        None,
        description="Sottotipo utente: 'distributore', 'rivenditore' o 'privato'. Determina i pacchetti acquistabili.",
    )
    parent_id: Optional[str] = Field(
        None,
        description="Genitore nell'albero (rivenditore->distributore, privato->rivenditore|distributore). None = non modificare; '' = azzera.",
    )
    distributor_id: Optional[str] = Field(
        None,
        description="DEPRECATO: alias legacy di parent_id (solo rivenditori).",
    )
    codice_fiscale: Optional[str] = Field(None, max_length=16)
    partita_iva: Optional[str] = Field(None, max_length=11)
    ragione_sociale: Optional[str] = Field(None, max_length=255)
    indirizzo_fatturazione: Optional[str] = Field(None, max_length=255)


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
    """Request per creare un utente dal pannello admin.
    La password NON viene impostata qui: l'utente la sceglie via email di invito."""
    email: str = Field(..., description="Email dell'utente")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: Optional[str] = Field(None, min_length=6, description="(Deprecato) non usato: l'utente imposta la password via invito email")
    full_name: Optional[str] = Field(None, description="Nome completo")
    role_id: Optional[int] = Field(None, description="ID ruolo (default: ruolo 'user')")
    credits: int = Field(0, ge=0, description="Crediti iniziali")
    is_active: bool = Field(True, description="Utente attivo")
    entity_type: Optional[str] = Field(None, description="Sottotipo: 'distributore'|'rivenditore'|'privato'")
    parent_id: Optional[str] = Field(None, description="Genitore nell'albero di distribuzione")


# ============================================================================
# GERARCHIA DISTRIBUZIONE — creazione sotto-utenti, assegnazione, richieste, inviti
# ============================================================================

class HierarchyUserItem(BaseModel):
    """Riga di un utente del sottoalbero."""
    id: str
    username: str
    full_name: Optional[str] = None
    email: str
    entity_type: str
    credits: int
    parent_id: Optional[str] = None
    is_active: bool = True
    email_verified: bool = False


class HierarchyChildrenResponse(BaseModel):
    children: List[HierarchyUserItem]
    total: int


class HierarchyCreateUserRequest(BaseModel):
    """Creazione di un sotto-utente da parte di un manager (distributore/rivenditore)."""
    email: str = Field(..., description="Email del nuovo utente")
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    entity_type: str = Field(..., description="'rivenditore' o 'privato' secondo i permessi dell'attore")
    credits: int = Field(0, ge=0, description="Crediti iniziali (trasferiti dal creatore se >0)")


class AssignCreditsRequest(BaseModel):
    """Assegnazione di crediti a un sotto-utente (trasferimento dal proprio saldo)."""
    amount: int = Field(..., gt=0, description="Crediti da trasferire")
    description: Optional[str] = Field(None, max_length=255)


class CreditRequestCreate(BaseModel):
    """Richiesta crediti: scelta di un pacchetto del proprio listino."""
    package_id: int = Field(..., description="ID del pacchetto richiesto")


class CreditRequestItem(BaseModel):
    id: str
    requester_id: str
    requester_username: Optional[str] = None
    requester_email: Optional[str] = None
    requester_entity_type: Optional[str] = None
    approver_id: Optional[str] = None
    approver_is_admin: bool = False
    package_id: Optional[int] = None
    package_name: str
    package_credits: int
    package_price_cents: int
    package_price_eur: float
    status: str
    note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class CreditRequestListResponse(BaseModel):
    requests: List[CreditRequestItem]
    total: int


class ResolveRequestRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=255)


class InvitePrivatoRequest(BaseModel):
    """Invito di un privato via email (crea-o-sposta)."""
    email: str = Field(..., description="Email del privato da invitare/spostare")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username se va creato un nuovo account")
    full_name: Optional[str] = None


class MoveTokenRequest(BaseModel):
    token: str


# ============================================================================
# NOTIFICHE IN-APP
# ============================================================================

class NotificationItem(BaseModel):
    id: str
    type: str
    title: str
    message: Optional[str] = None
    link: Optional[str] = None
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


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
    font_title_size: int = Field(26, ge=14, le=36, description="Dimensione font titolo (pt)")
    title_alignment: str = Field("center", description="Allineamento titolo")
    body_alignment: str = Field("left", description="Allineamento corpo: left, center, right, justify")
    line_spacing: float = Field(1.5, ge=1.0, le=3.0, description="Interlinea")
    paragraph_spacing_after: int = Field(6, ge=0, le=24, description="Spazio dopo paragrafo (pt)")
    chapter_spacing_before: int = Field(18, ge=0, le=60, description="Spazio prima capitolo (pt)")
    section_spacing_before: int = Field(12, ge=0, le=40, description="Spazio prima sezione (pt)")
    include_toc: bool = Field(True, description="Includere indice")
    include_page_numbers: bool = Field(True, description="Includere numeri pagina")
    page_number_position: str = Field("bottom_center", description="Posizione numeri pagina")
    toc_indent: float = Field(0.5, ge=0.0, le=2.0, description="Indentazione indice (inches)")
    heading1_size: int = Field(16, ge=12, le=28, description="Dimensione heading 1 (pt)")
    heading2_size: int = Field(14, ge=10, le=24, description="Dimensione heading 2 (pt)")
    margin_top: int = Field(72, ge=20, le=200, description="Margine superiore (pt)")
    margin_bottom: int = Field(72, ge=20, le=200, description="Margine inferiore (pt)")
    margin_left: int = Field(72, ge=20, le=200, description="Margine sinistro (pt)")
    margin_right: int = Field(72, ge=20, le=200, description="Margine destro (pt)")
    include_header: bool = Field(False, description="Includere intestazione")
    header_text: str = Field("", description="Testo intestazione")
    include_footer: bool = Field(False, description="Includere pie' di pagina")
    footer_text: str = Field("", description="Testo pie' di pagina")

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


# ============================================================================
# COMPILATIO SCAN
# ============================================================================

class CompilatioScanRequest(BaseModel):
    """Request per avviare una scansione Compilatio."""
    text: str = Field(..., min_length=50, description="Testo da analizzare (min 50 caratteri)")
    source_type: Optional[str] = Field(None, description="Sorgente: 'generate', 'humanize', 'thesis', 'manual'")
    source_job_id: Optional[str] = Field(None, description="Job ID del contenuto originale")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Il testo da analizzare per rilevare contenuto AI...",
                "source_type": "generate",
                "source_job_id": "job_abc123"
            }
        }


class CompilatioScanResponse(BaseModel):
    """Response avvio scansione Compilatio."""
    job_id: str
    status: JobStatus
    message: str
    created_at: datetime
    cached: bool = Field(False, description="True se il risultato proviene dalla cache (dedup)")
    cached_scan: Optional[Dict[str, Any]] = Field(None, description="Risultato cached se disponibile")


class CompilatioScanResult(BaseModel):
    """Risultato completo di una scansione Compilatio."""
    scan_id: str
    job_id: str
    document_filename: str
    word_count: int
    global_score_percent: float
    similarity_percent: float
    exact_percent: float
    ai_generated_percent: float
    same_meaning_percent: float
    translation_percent: float
    quotation_percent: float
    suspicious_fingerprint_percent: float
    points_of_interest: int
    source_type: Optional[str] = None
    source_job_id: Optional[str] = None
    has_report: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None


class CompilatioScanListResponse(BaseModel):
    """Lista scansioni Compilatio."""
    scans: List[CompilatioScanResult]
    total: int


# ============================================================================
# API KEYS
# ============================================================================

class APIKeyCreateRequest(BaseModel):
    """Richiesta creazione API key."""
    user_id: str = Field(..., description="UUID dell'utente")
    name: str = Field(..., min_length=1, max_length=255, description="Nome descrittivo")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Giorni alla scadenza (null=mai)")
    rate_limit_per_minute: int = Field(30, ge=1, le=300, description="Rate limit al minuto")


class APIKeyCreateResponse(BaseModel):
    """Risposta creazione API key. Contiene la key completa (mostrata solo una volta)."""
    id: str
    name: str
    key: str
    key_prefix: str
    user_id: str
    expires_at: Optional[datetime] = None
    rate_limit_per_minute: int
    created_at: datetime
    message: str = "Salva questa chiave in modo sicuro. Non verra' mostrata di nuovo."


class APIKeyResponse(BaseModel):
    """Info API key (senza la key completa)."""
    id: str
    name: str
    key_prefix: str
    user_id: str
    user_email: Optional[str] = None
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    rate_limit_per_minute: int
    created_at: datetime


class APIKeyListResponse(BaseModel):
    """Lista API keys."""
    keys: List[APIKeyResponse]
    total: int


# ============================================================================
# EXTERNAL API v1
# ============================================================================

class ExternalHumanizeRequest(BaseModel):
    """Richiesta umanizzazione via API esterna."""
    session_id: str = Field(..., description="ID della sessione addestrata")
    text: str = Field(..., min_length=50, description="Testo da umanizzare")


class ExternalAntiAIRequest(BaseModel):
    """Richiesta correzione anti-AI via API esterna."""
    text: str = Field(..., min_length=50, description="Testo da correggere")


class ExternalJobSubmittedResponse(BaseModel):
    """Risposta dopo invio job via API esterna."""
    job_id: str
    status: str
    message: str


class ExternalJobStatusResponse(BaseModel):
    """Stato job via API esterna."""
    job_id: str
    status: str
    progress: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============================================================================
# PACCHETTI CREDITI — listino (CRUD admin) + dashboard distributore
# ============================================================================

class CreditPackageResponse(BaseModel):
    """Pacchetto crediti acquistabile."""
    id: int
    name: str
    credits: int
    price_cents: int
    price_eur: float
    is_active: bool
    sort_order: int
    description: Optional[str] = None
    entity_type: str = 'privato'  # sottotipo destinatario del pacchetto
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreditPackageListResponse(BaseModel):
    packages: List[CreditPackageResponse]


class AdminCreditPackageRequest(BaseModel):
    """Create/update di un pacchetto crediti."""
    name: str = Field(..., min_length=1, max_length=100)
    credits: int = Field(..., gt=0)
    price_cents: int = Field(..., gt=0, description="Prezzo in centesimi di euro")
    is_active: bool = True
    sort_order: int = 0
    description: Optional[str] = None
    entity_type: str = Field('privato', description="Sottotipo destinatario: distributore|rivenditore|privato")



class DistributorResellerItem(BaseModel):
    """Riga riepilogo di un rivenditore nella dashboard distributore (sola lettura)."""
    id: str
    username: str
    full_name: Optional[str] = None
    email: str
    credits: int


class DistributorResellerListResponse(BaseModel):
    resellers: List[DistributorResellerItem]
    total: int


# ============================================================================
# i18n: lingue + traduzioni
# ============================================================================

class LanguageResponse(BaseModel):
    code: str
    name: str
    native_name: str
    flag_country_code: str
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0


class LanguageListResponse(BaseModel):
    languages: List[LanguageResponse]


class LanguageCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., min_length=1, max_length=100)
    native_name: str = Field(..., min_length=1, max_length=100)
    flag_country_code: str = Field(..., min_length=2, max_length=8)
    is_active: bool = True
    sort_order: int = 0
    translate_all: bool = False  # se True, avvia subito la traduzione AT di tutte le label


class LanguageUpdateRequest(BaseModel):
    name: Optional[str] = None
    native_name: Optional[str] = None
    flag_country_code: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class TranslationEntry(BaseModel):
    key: str
    value: Optional[str] = None
    is_empty: bool = True


class LanguageDetailResponse(BaseModel):
    language: LanguageResponse
    entries: List[TranslationEntry]
    total: int
    translated: int
    empty: int


class TranslationsUpsertRequest(BaseModel):
    translations: Dict[str, str]  # { chiave: valore }


class TranslateJobResponse(BaseModel):
    job_id: str
    message: str


class TranslateStatusResponse(BaseModel):
    status: str            # 'running' | 'completed' | 'failed'
    total: int = 0
    done: int = 0
    error: Optional[str] = None
