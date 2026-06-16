"""
Modelli SQLAlchemy per il database.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, BigInteger, DECIMAL, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM, JSONB
from database import Base
from models import JobStatus, JobType

# Definisci gli ENUM PostgreSQL che corrispondono a quelli creati in Supabase
# Usando create_type=False perché gli ENUM esistono già nel database
pg_job_status = PG_ENUM(
    'pending', 'training', 'ready', 'generating', 'completed', 'failed',
    name='job_status',
    create_type=False
)

pg_job_type = PG_ENUM(
    'training', 'generation', 'humanization', 'thesis_generation', 'compilatio_scan',
    'wiki_ingest', 'wiki_lint',
    name='job_type',
    create_type=False
)

# ENUM per lo stato della tesi
pg_thesis_status = PG_ENUM(
    'draft', 'chapters_pending', 'chapters_confirmed', 'sections_pending',
    'sections_confirmed', 'generating', 'completed', 'failed',
    name='thesis_status',
    create_type=False
)

# ENUM per lo stato del wiki (LLM Wiki, second-brain) di una tesi
pg_thesis_wiki_status = PG_ENUM(
    'none', 'ingesting', 'ingested', 'linting', 'linted', 'failed',
    name='thesis_wiki_status',
    create_type=False
)


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    """Modello per gli utenti."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    # Nullable: gli utenti creati dall'admin impostano la password via invito email.
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    # Verifica email: l'utente deve confermare l'email prima di poter accedere.
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    credits = Column(Integer, default=0, nullable=False)
    # Sottotipo dell'utente normale: 'distributore' | 'rivenditore' | 'privato'
    # (default). Determina i pacchetti crediti acquistabili. Asse indipendente dal Role.
    entity_type = Column(String(20), default='privato', nullable=False)
    # Distributore di riferimento (solo per i rivenditori). FK self, assegnata dall'admin.
    distributor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Dati anagrafici per pagamenti PagoPA (opzionali, salvati al primo acquisto se l'utente sceglie di memorizzarli).
    codice_fiscale = Column(String(16), nullable=True)
    partita_iva = Column(String(11), nullable=True)
    ragione_sociale = Column(String(255), nullable=True)
    indirizzo_fatturazione = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relazioni
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    role = relationship("Role", back_populates="users")
    user_permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Session(Base):
    """Modello per le sessioni di training."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=True)
    is_trained = Column(Boolean, default=False)
    conversation_history = Column(Text, nullable=True)  # JSON serializzato
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relazioni
    user = relationship("User", back_populates="sessions")
    jobs = relationship("Job", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session(id={self.id}, session_id={self.session_id}, name={self.name})>"


class Job(Base):
    """Modello per i job (training, generazione, umanizzazione)."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(50), unique=True, nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(pg_job_type, nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(pg_job_status, default='pending')
    progress = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relazioni
    session = relationship("Session", back_populates="jobs")
    user = relationship("User")

    def __repr__(self):
        return f"<Job(id={self.id}, job_id={self.job_id}, type={self.job_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """Converte il job in un dizionario."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "session_id": self.session.session_id if self.session else None,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at
        }


class RefreshToken(Base):
    """Modello per i refresh token."""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(500), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)

    # Relazioni
    user = relationship("User")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"


class EmailToken(Base):
    """Token monouso per email: verifica registrazione, reset password, invito (set password).
    Si memorizza solo lo SHA-256 del token grezzo (il raw viene inviato nel link)."""
    __tablename__ = "email_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)
    purpose = Column(String(20), nullable=False)  # 'verify' | 'reset' | 'set_password'
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relazioni
    user = relationship("User")

    def __repr__(self):
        return f"<EmailToken(user_id={self.user_id}, purpose={self.purpose}, used={self.used_at is not None})>"


# ============================================================================
# API KEYS
# ============================================================================

class APIKey(Base):
    """API keys per accesso programmatico esterno."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    key_prefix = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    rate_limit_per_minute = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.key_prefix})>"


# ============================================================================
# ROLES & PERMISSIONS
# ============================================================================

class Role(Base):
    """Modello per i ruoli utente."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relazioni
    users = relationship("User", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "permissions": [rp.permission_code for rp in self.permissions] if self.permissions else [],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class RolePermission(Base):
    """Permessi assegnati a ciascun ruolo."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_code = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relazioni
    role = relationship("Role", back_populates="permissions")

    # Constraint di unicita
    __table_args__ = (
        # UniqueConstraint gestito in SQL
    )

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, code={self.permission_code})>"


class UserPermission(Base):
    """Override permessi per singolo utente."""
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_code = Column(String(50), nullable=False)
    granted = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relazioni
    user = relationship("User", back_populates="user_permissions")

    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, code={self.permission_code}, granted={self.granted})>"


# ============================================================================
# CREDIT TRANSACTIONS
# ============================================================================

class CreditTransaction(Base):
    """Storico transazioni crediti."""
    __tablename__ = "credit_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)  # positivo=aggiunta, negativo=consumo
    balance_after = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # 'purchase', 'consumption', 'admin_adjustment', 'refund'
    description = Column(Text, nullable=True)
    related_job_id = Column(String(50), nullable=True)
    operation_type = Column(String(50), nullable=True)  # 'train', 'generate', 'humanize', 'thesis_chapters', etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relazioni
    user = relationship("User", back_populates="credit_transactions")

    def __repr__(self):
        return f"<CreditTransaction(user_id={self.user_id}, amount={self.amount}, type={self.transaction_type})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "amount": self.amount,
            "balance_after": self.balance_after,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "related_job_id": self.related_job_id,
            "operation_type": self.operation_type,
            "created_at": self.created_at
        }


# ============================================================================
# LOOKUP TABLES per Thesis Generation
# ============================================================================

class WritingStyle(Base):
    """Stili di scrittura disponibili."""
    __tablename__ = "writing_styles"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    prompt_hint = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "prompt_hint": self.prompt_hint
        }


class ContentDepthLevel(Base):
    """Livelli di profondità del contenuto."""
    __tablename__ = "content_depth_levels"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    detail_multiplier = Column(DECIMAL(3, 2), default=1.0)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "detail_multiplier": float(self.detail_multiplier) if self.detail_multiplier else 1.0
        }


class AudienceKnowledgeLevel(Base):
    """Livelli di conoscenza del pubblico."""
    __tablename__ = "audience_knowledge_levels"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    prompt_hint = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "prompt_hint": self.prompt_hint
        }


class AudienceSize(Base):
    """Dimensioni del pubblico."""
    __tablename__ = "audience_sizes"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description
        }


class Industry(Base):
    """Settori/industrie."""
    __tablename__ = "industries"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    keywords = Column(ARRAY(Text), nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords or []
        }


class TargetAudience(Base):
    """Destinatari target."""
    __tablename__ = "target_audiences"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    prompt_hint = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "prompt_hint": self.prompt_hint
        }


# ============================================================================
# THESIS TABLES
# ============================================================================

class Thesis(Base):
    """Modello per le tesi/relazioni."""
    __tablename__ = "theses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    # Parametri di base
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    key_topics = Column(ARRAY(Text), nullable=True)

    # Parametri di generazione
    writing_style_id = Column(Integer, ForeignKey("writing_styles.id"), nullable=True)
    content_depth_id = Column(Integer, ForeignKey("content_depth_levels.id"), nullable=True)
    num_chapters = Column(Integer, default=5)
    sections_per_chapter = Column(Integer, default=3)
    words_per_section = Column(Integer, default=5000)

    # Caratteristiche pubblico
    knowledge_level_id = Column(Integer, ForeignKey("audience_knowledge_levels.id"), nullable=True)
    audience_size_id = Column(Integer, ForeignKey("audience_sizes.id"), nullable=True)
    industry_id = Column(Integer, ForeignKey("industries.id"), nullable=True)
    target_audience_id = Column(Integer, ForeignKey("target_audiences.id"), nullable=True)

    # Provider AI (openai o claude)
    ai_provider = Column(String(20), default='openai')

    # Stile citazioni: 'footnotes' (note a piè di pagina) o 'bibliography' (citazioni [x])
    citation_style = Column(String(20), default='footnotes')

    # Struttura generata (JSON)
    chapters_structure = Column(JSONB, nullable=True)

    # Contenuto generato
    generated_content = Column(Text, nullable=True)

    # Stato e metadati
    status = Column(pg_thesis_status, default='draft')
    current_phase = Column(Integer, default=0)
    generation_progress = Column(Integer, default=0)
    total_words_generated = Column(Integer, default=0)

    # File allegati
    attachments_path = Column(Text, nullable=True)

    # Flag tariffazione "tutto pagato / gratis": True per admin e per le vecchie
    # tesi a tariffa flat (hanno già pagato 1000 in un colpo) -> nessun addebito per step.
    # False per le tesi nuove non-admin: si paga PER STEP (vedi flag sotto).
    credits_charged = Column(Boolean, default=False, nullable=False)

    # Idempotenza dell'addebito per step (quote fisse che sommano a 1000): evita
    # doppi addebiti su rigenerazioni/retry. Azzerati in caso di rimborso su errore.
    chapters_charged = Column(Boolean, default=False, nullable=False)
    sections_charged = Column(Boolean, default=False, nullable=False)
    content_charged = Column(Boolean, default=False, nullable=False)
    # Analisi documenti/paper (ingest Knowledge Base): addebitata una sola volta.
    wiki_charged = Column(Boolean, default=False, nullable=False)

    # LLM Wiki (second-brain per-tesi). Se restrict_to_sources=True la generazione
    # si attiene SOLO alle fonti caricate (paper + upload). wiki_path e' la cartella
    # thesis_uploads/{thesis_id}/llm_wiki/ una volta materializzata.
    restrict_to_sources = Column(Boolean, default=True, nullable=False)
    wiki_status = Column(pg_thesis_wiki_status, default='none', nullable=False)
    wiki_path = Column(Text, nullable=True)
    wiki_lint_report = Column(JSONB, nullable=True)
    # Progresso granulare dell'ingest in corso (fase, %, messaggio, documenti).
    wiki_progress = Column(JSONB, nullable=True)
    wiki_ingested_at = Column(DateTime, nullable=True)
    wiki_linted_at = Column(DateTime, nullable=True)

    # Custom outline: se True, l'utente ha fornito direttamente l'indice
    # (capitoli + sezioni). generate_chapters/sections bypassano l'AI e
    # popolano chapters_structure da custom_outline senza addebito crediti.
    use_custom_outline = Column(Boolean, default=False, nullable=False)
    custom_outline = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relazioni
    user = relationship("User")
    session = relationship("Session")
    writing_style = relationship("WritingStyle")
    content_depth = relationship("ContentDepthLevel")
    knowledge_level = relationship("AudienceKnowledgeLevel")
    audience_size = relationship("AudienceSize")
    industry = relationship("Industry")
    target_audience = relationship("TargetAudience")
    attachments = relationship("ThesisAttachment", back_populates="thesis", cascade="all, delete-orphan")
    generation_jobs = relationship("ThesisGenerationJob", back_populates="thesis", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Thesis(id={self.id}, title={self.title[:50]}, status={self.status})>"

    def to_dict(self) -> dict:
        """Converte la tesi in un dizionario."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "title": self.title,
            "description": self.description,
            "key_topics": self.key_topics or [],
            "writing_style_id": self.writing_style_id,
            "content_depth_id": self.content_depth_id,
            "num_chapters": self.num_chapters,
            "sections_per_chapter": self.sections_per_chapter,
            "words_per_section": self.words_per_section,
            "knowledge_level_id": self.knowledge_level_id,
            "audience_size_id": self.audience_size_id,
            "industry_id": self.industry_id,
            "target_audience_id": self.target_audience_id,
            "ai_provider": self.ai_provider or "openai",
            "citation_style": self.citation_style or "footnotes",
            "credits_charged": bool(self.credits_charged),
            "chapters_charged": bool(self.chapters_charged),
            "sections_charged": bool(self.sections_charged),
            "content_charged": bool(self.content_charged),
            "wiki_charged": bool(self.wiki_charged),
            "chapters_structure": self.chapters_structure,
            "generated_content": self.generated_content,
            "status": self.status,
            "current_phase": self.current_phase,
            "generation_progress": self.generation_progress,
            "total_words_generated": self.total_words_generated,
            "restrict_to_sources": bool(self.restrict_to_sources) if self.restrict_to_sources is not None else True,
            "wiki_status": self.wiki_status or "none",
            "wiki_path": self.wiki_path,
            "wiki_lint_report": self.wiki_lint_report,
            "wiki_ingested_at": self.wiki_ingested_at,
            "wiki_linted_at": self.wiki_linted_at,
            "use_custom_outline": bool(self.use_custom_outline) if self.use_custom_outline is not None else False,
            "custom_outline": self.custom_outline,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at
        }

    def to_summary_dict(self) -> dict:
        """
        Versione leggera per la LISTA tesi (dashboard): esclude i campi pesanti
        (generated_content, chapters_structure, custom_outline, wiki_lint_report),
        che da soli costituiscono la quasi totalità del payload. Usato con il
        deferimento di quelle colonne nella query per non caricarle nemmeno dal DB.
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "title": self.title,
            "description": self.description,
            "key_topics": self.key_topics or [],
            "writing_style_id": self.writing_style_id,
            "content_depth_id": self.content_depth_id,
            "num_chapters": self.num_chapters,
            "sections_per_chapter": self.sections_per_chapter,
            "words_per_section": self.words_per_section,
            "knowledge_level_id": self.knowledge_level_id,
            "audience_size_id": self.audience_size_id,
            "industry_id": self.industry_id,
            "target_audience_id": self.target_audience_id,
            "ai_provider": self.ai_provider or "openai",
            "citation_style": self.citation_style or "footnotes",
            "credits_charged": bool(self.credits_charged),
            "chapters_charged": bool(self.chapters_charged),
            "sections_charged": bool(self.sections_charged),
            "content_charged": bool(self.content_charged),
            "wiki_charged": bool(self.wiki_charged),
            "chapters_structure": None,
            "generated_content": None,
            "status": self.status,
            "current_phase": self.current_phase,
            "generation_progress": self.generation_progress,
            "total_words_generated": self.total_words_generated,
            "restrict_to_sources": bool(self.restrict_to_sources) if self.restrict_to_sources is not None else True,
            "wiki_status": self.wiki_status or "none",
            "wiki_path": self.wiki_path,
            "wiki_lint_report": None,
            "wiki_ingested_at": self.wiki_ingested_at,
            "wiki_linted_at": self.wiki_linted_at,
            "use_custom_outline": bool(self.use_custom_outline) if self.use_custom_outline is not None else False,
            "custom_outline": None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


class ThesisAttachment(Base):
    """Allegati per le tesi."""
    __tablename__ = "thesis_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thesis_id = Column(UUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(100), nullable=True)
    extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relazioni
    thesis = relationship("Thesis", back_populates="attachments")

    def __repr__(self):
        return f"<ThesisAttachment(id={self.id}, filename={self.original_filename})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "thesis_id": str(self.thesis_id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "created_at": self.created_at
        }


class ThesisGenerationJob(Base):
    """Job per la generazione delle tesi."""
    __tablename__ = "thesis_generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thesis_id = Column(UUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(50), nullable=False)
    phase = Column(String(50), nullable=False)  # 'chapters', 'sections', 'content_chapter_X_section_Y'
    status = Column(String(50), default='pending')
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relazioni
    thesis = relationship("Thesis", back_populates="generation_jobs")

    def __repr__(self):
        return f"<ThesisGenerationJob(id={self.id}, phase={self.phase}, status={self.status})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "thesis_id": str(self.thesis_id),
            "job_id": self.job_id,
            "phase": self.phase,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


# ============================================================================
# COMPILATIO SCANS
# ============================================================================

class CompilatioScan(Base):
    """Modello per le scansioni Compilatio (AI Detection + Plagio)."""
    __tablename__ = "compilatio_scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(50), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Identificativi documento su Compilatio
    compilatio_doc_id = Column(String(255), nullable=True)
    compilatio_analysis_id = Column(String(255), nullable=True)
    compilatio_folder_id = Column(String(255), nullable=True)

    # Info documento
    document_filename = Column(String(500), nullable=False)
    document_text_hash = Column(String(64), nullable=True)  # SHA-256 per dedup
    word_count = Column(Integer, default=0)

    # Risultati analisi
    global_score_percent = Column(DECIMAL(5, 2), default=0)
    similarity_percent = Column(DECIMAL(5, 2), default=0)
    exact_percent = Column(DECIMAL(5, 2), default=0)
    ai_generated_percent = Column(DECIMAL(5, 2), default=0)
    same_meaning_percent = Column(DECIMAL(5, 2), default=0)
    translation_percent = Column(DECIMAL(5, 2), default=0)
    quotation_percent = Column(DECIMAL(5, 2), default=0)
    suspicious_fingerprint_percent = Column(DECIMAL(5, 2), default=0)
    points_of_interest = Column(Integer, default=0)

    # Report e dettagli
    report_pdf_path = Column(Text, nullable=True)
    scan_details = Column(JSONB, nullable=True)  # JSON completo risultati + POIs

    # Testo originale del documento analizzato.
    # Necessario per ri-generare il report StyleForge-branded con evidenziazioni.
    # Non viene esposto in to_dict() per ridurre il payload delle list response.
    document_text = Column(Text, nullable=True)

    # Sorgente della scansione
    source_type = Column(String(50), nullable=True)  # 'generate', 'humanize', 'thesis', 'manual'
    source_job_id = Column(String(50), nullable=True)  # job_id del contenuto originale

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relazioni
    user = relationship("User")

    def __repr__(self):
        return f"<CompilatioScan(id={self.id}, ai={self.ai_generated_percent}%, similarity={self.similarity_percent}%)>"

    def to_dict(self) -> dict:
        return {
            "scan_id": str(self.id),
            "job_id": self.job_id,
            "document_filename": self.document_filename,
            "word_count": self.word_count,
            "global_score_percent": float(self.global_score_percent or 0),
            "similarity_percent": float(self.similarity_percent or 0),
            "exact_percent": float(self.exact_percent or 0),
            "ai_generated_percent": float(self.ai_generated_percent or 0),
            "same_meaning_percent": float(self.same_meaning_percent or 0),
            "translation_percent": float(self.translation_percent or 0),
            "quotation_percent": float(self.quotation_percent or 0),
            "suspicious_fingerprint_percent": float(self.suspicious_fingerprint_percent or 0),
            "points_of_interest": self.points_of_interest or 0,
            "source_type": self.source_type,
            "source_job_id": self.source_job_id,
            "has_report": bool(self.report_pdf_path),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class SystemSetting(Base):
    """Impostazioni di sistema configurabili dall'admin."""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self):
        return f"<SystemSetting(key={self.key})>"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at,
            "updated_by": str(self.updated_by) if self.updated_by else None
        }


# ============================================================================
# PACCHETTI CREDITI (listino, editabile dall'admin)
# ============================================================================

class CreditPackage(Base):
    """Pacchetto di crediti del listino. Editabile dall'admin."""
    __tablename__ = "credit_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    credits = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    description = Column(Text, nullable=True)
    # Sottotipo destinatario: 'distributore' | 'rivenditore' | 'privato'
    entity_type = Column(String(20), default='privato', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CreditPackage(id={self.id}, name={self.name}, credits={self.credits}, price={self.price_cents}c)>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "credits": self.credits,
            "price_cents": self.price_cents,
            "price_eur": round(self.price_cents / 100.0, 2),
            "is_active": bool(self.is_active),
            "sort_order": self.sort_order,
            "description": self.description,
            "entity_type": self.entity_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# i18n: lingue + traduzioni
# ============================================================================

class Language(Base):
    """Lingua disponibile nell'app (gestita dall'admin)."""
    __tablename__ = "languages"

    code = Column(String(10), primary_key=True)              # es. 'it', 'en', 'fr'
    name = Column(String(100), nullable=False)               # es. 'Inglese'
    native_name = Column(String(100), nullable=False)        # es. 'English'
    flag_country_code = Column(String(8), nullable=False)    # codice ISO paese (flag-icons)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "native_name": self.native_name,
            "flag_country_code": self.flag_country_code,
            "is_active": bool(self.is_active),
            "is_default": bool(self.is_default),
            "sort_order": self.sort_order,
        }


class Translation(Base):
    """Traduzione di una label per una lingua. key = stringa italiana (chiave naturale)."""
    __tablename__ = "translations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    language_code = Column(String(10), ForeignKey("languages.code", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(Text, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "language_code": self.language_code,
            "key": self.key,
            "value": self.value,
        }
