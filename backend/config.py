"""
Configurazione per l'applicazione FastAPI.
"""

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Carica variabili d'ambiente
load_dotenv(find_dotenv())

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI Configuration
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "o3")  # o3 reasoning model
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))

# AI Provider per Thesis Generation
# Valori: "openai" (default) o "claude"
THESIS_AI_PROVIDER = os.getenv("THESIS_AI_PROVIDER", "openai")
THESIS_CLAUDE_MODEL = os.getenv("THESIS_CLAUDE_MODEL", "claude-opus-4-6")

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Configurazione Claude
MAX_TOKENS_TRAIN = int(os.getenv("MAX_TOKENS_TRAIN", "4096"))
MAX_TOKENS_TEST = int(os.getenv("MAX_TOKENS_TEST", "8192"))
CLAUDE_MODEL_ID = "claude-opus-4-6"

# Configurazione Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
RELOAD = os.getenv("RELOAD", "False").lower() == "true"

# Configurazione Job Manager
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
JOB_CLEANUP_HOURS = int(os.getenv("JOB_CLEANUP_HOURS", "24"))
SESSION_CLEANUP_HOURS = int(os.getenv("SESSION_CLEANUP_HOURS", "24"))

# Configurazione File Upload
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "100")) * 1024 * 1024  # MB to bytes
ALLOWED_EXTENSIONS = {".pdf"}

# Configurazione Results
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "./results"))
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Configurazione Thesis Uploads
THESIS_UPLOADS_DIR = Path(os.getenv("THESIS_UPLOADS_DIR", "./thesis_uploads"))
THESIS_UPLOADS_DIR.mkdir(exist_ok=True, parents=True)
THESIS_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
THESIS_MAX_UPLOAD_SIZE = int(os.getenv("THESIS_MAX_UPLOAD_SIZE", "50")) * 1024 * 1024  # 50MB
THESIS_MAX_ATTACHMENTS = int(os.getenv("THESIS_MAX_ATTACHMENTS", "10"))
THESIS_MAX_CONTEXT_CHARS = int(os.getenv("THESIS_MAX_CONTEXT_CHARS", "50000"))

# LLM Wiki (second-brain per-tesi)
# Path del template del wiki: contiene CLAUDE.md (la "costituzione") + struttura
# di sottocartelle vuote che viene clonata in thesis_uploads/{tid}/llm_wiki/.
WIKI_TEMPLATE_DIR = Path(os.getenv("WIKI_TEMPLATE_DIR", str(Path(__file__).resolve().parent.parent / "llm_wiki")))
# Modello Claude usato per ingest/lint. Sonnet e' il default (good cost/perf ratio
# con prompt caching del CLAUDE.md). L'utente puo' overridare via env.
WIKI_CLAUDE_MODEL = os.getenv("WIKI_CLAUDE_MODEL", "claude-sonnet-4-6")
# Max fonti raw per tesi prima di andare in errore (taglia il costo dell'ingest)
WIKI_MAX_SOURCES = int(os.getenv("WIKI_MAX_SOURCES", "15"))
# Timeout HTTP per il download dei PDF dei paper (secondi)
WIKI_PAPER_DOWNLOAD_TIMEOUT = int(os.getenv("WIKI_PAPER_DOWNLOAD_TIMEOUT", "30"))
# Max bytes per un PDF scaricato (25 MB)
WIKI_PAPER_MAX_BYTES = int(os.getenv("WIKI_PAPER_MAX_BYTES", str(25 * 1024 * 1024)))
# Timeout duro sul job di ingest (secondi). Dopo wiki_status diventa 'failed'.
WIKI_INGEST_TIMEOUT_SEC = int(os.getenv("WIKI_INGEST_TIMEOUT_SEC", "900"))  # 15 min
# Numero di fonti per turno SDK Anthropic durante l'ingest
WIKI_INGEST_BATCH_SIZE = int(os.getenv("WIKI_INGEST_BATCH_SIZE", "5"))
# Max tokens output per turno (ingest)
WIKI_INGEST_MAX_TOKENS = int(os.getenv("WIKI_INGEST_MAX_TOKENS", "8000"))
# Max tokens output per il lint (uno shot read-only)
WIKI_LINT_MAX_TOKENS = int(os.getenv("WIKI_LINT_MAX_TOKENS", "4000"))

# Configurazione Prompt
PROMPT_ADDESTRAMENTO_PATH = Path(os.getenv("PROMPT_ADDESTRAMENTO_PATH", "prompt_addestramento.txt"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Email di contatto per il "polite pool" delle API accademiche (OpenAlex, Crossref)
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "")

# Opzionale: API key Semantic Scholar (aumenta i rate limit)
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# Rate Limiting (requests per minute)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Compilatio Integration (Admin-only AI Detection)
COMPILATIO_USERNAME = os.getenv("COMPILATIO_USERNAME", "")
COMPILATIO_PASSWORD = os.getenv("COMPILATIO_PASSWORD", "")
COMPILATIO_BASE_URL = os.getenv("COMPILATIO_BASE_URL", "https://app.compilatio.net")
COMPILATIO_RECIPE = os.getenv("COMPILATIO_RECIPE", "anasim-studium")
COMPILATIO_REPORT_LANG = os.getenv("COMPILATIO_REPORT_LANG", "it")
COMPILATIO_POLL_INTERVAL = int(os.getenv("COMPILATIO_POLL_INTERVAL", "5"))
COMPILATIO_MAX_RETRIES = int(os.getenv("COMPILATIO_MAX_RETRIES", "120"))
COMPILATIO_REPORTS_DIR = Path(os.getenv("COMPILATIO_REPORTS_DIR", "./compilatio_reports"))
COMPILATIO_REPORTS_DIR.mkdir(exist_ok=True, parents=True)

# Configurazione Carousel Creator
CAROUSEL_CLAUDE_MODEL = os.getenv("CAROUSEL_CLAUDE_MODEL", "claude-opus-4-6")

# Configurazione Image Enhancement
IMAGE_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_MAX_UPLOAD_SIZE = int(os.getenv("IMAGE_MAX_UPLOAD_SIZE", "10")) * 1024 * 1024  # 10MB
IMAGE_MAX_DIMENSION = int(os.getenv("IMAGE_MAX_DIMENSION", "4096"))
IMAGE_ENHANCE_MODEL = os.getenv("IMAGE_ENHANCE_MODEL", "claude-opus-4-6")

# MiniMax Video Generation (Admin-only)
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.chat/v1")
MINIMAX_DEFAULT_MODEL = os.getenv("MINIMAX_DEFAULT_MODEL", "MiniMax-Hailuo-2.3")
VIDEO_MAX_UPLOAD_SIZE = int(os.getenv("VIDEO_MAX_UPLOAD_SIZE", "10")) * 1024 * 1024
VIDEO_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# API Pricing (Claude Opus 4-6) — per stima costi admin
CLAUDE_OPUS_INPUT_PRICE_USD = 15.0   # $ per 1M input tokens
CLAUDE_OPUS_OUTPUT_PRICE_USD = 75.0  # $ per 1M output tokens
USD_TO_EUR_RATE = 0.88               # Tasso di cambio approssimativo

# API Pricing (OpenAI o3) — per stima costi admin thesis
OPENAI_O3_INPUT_PRICE_USD = 10.0     # $ per 1M input tokens
OPENAI_O3_OUTPUT_PRICE_USD = 40.0    # $ per 1M output tokens

# ============================================================================
# PAGOPA / SOLUTIONPA — integrazione pagamenti per acquisto crediti
# ============================================================================
# Ente creditore = ERSAF, Partner Tecnologico = SolutionPA (Intesa Sanpaolo).
# Test env (collaudo): https://solutionpa-coll.intesasanpaolo.com/...
# Production:          https://solutionpa.intesasanpaolo.com/... (URL da confermare con SolutionPA)

PAGOPA_TEST_MODE = os.getenv("PAGOPA_TEST_MODE", "true").lower() == "true"

# WSDL del DataProvider (operazioni VERSO SolutionPA: pdpCaricaPagamentoInAttesa,
# pdpAttivaRPT, pdpModificaPosizioneDebitoria, pdpEsitRT). Default = ambiente test.
PAGOPA_WSDL_URL = os.getenv(
    "PAGOPA_WSDL_URL",
    "https://solutionpa-coll.intesasanpaolo.com/IntermediarioPAWebService/WEBSDataProviderInterface?wsdl",
)

# Credenziali Basic Auth verso SolutionPA (forniti da SolutionPA per ogni Ente)
PAGOPA_USERNAME = os.getenv("PAGOPA_USERNAME", "")
PAGOPA_PASSWORD = os.getenv("PAGOPA_PASSWORD", "")

# Identificativi dell'Ente Creditore configurati in SolutionPA
PAGOPA_DOMINIO = os.getenv("PAGOPA_DOMINIO", "")        # es. 80005570561 (codice fiscale ERSAF)
PAGOPA_UB = os.getenv("PAGOPA_UB", "")                  # es. ERSAFQUOTATST (Unita' Beneficiaria)
PAGOPA_COD_TRIBUTO = os.getenv("PAGOPA_COD_TRIBUTO", "") # es. ERSAFINCATST (codice servizio/tributo)

# URL pubblico del frontend a cui pagoPA Checkout reindirizza l'utente al termine
# del pagamento. Viene passato come callbackURL in pdpAttivaRPT.
PAGOPA_RETURN_URL_BASE = os.getenv("PAGOPA_RETURN_URL_BASE", "https://styleforge.ersaf.it/payments/return")

# Credenziali Basic Auth che SolutionPA usa per chiamare i nostri webhook
# (esito push). Sono distinti dalle credenziali outbound.
PAGOPA_NOTIFY_AUTH_USER = os.getenv("PAGOPA_NOTIFY_AUTH_USER", "")
PAGOPA_NOTIFY_AUTH_PASS = os.getenv("PAGOPA_NOTIFY_AUTH_PASS", "")

# TTL della posizione caricata (giorni). Lo standard PagoPA ammette tipicamente
# fino a 90; impostiamo 60 per ridurre il numero di IUV scaduti che restano in DB.
PAGOPA_POSITION_TTL_DAYS = int(os.getenv("PAGOPA_POSITION_TTL_DAYS", "60"))

# Timeout HTTP (secondi) per le chiamate SOAP outbound.
PAGOPA_SOAP_TIMEOUT = int(os.getenv("PAGOPA_SOAP_TIMEOUT", "30"))

# Versione API
API_VERSION = "1.0.0"
API_TITLE = "StyleForge API"
API_DESCRIPTION = """
API per la generazione di contenuti utilizzando Claude Opus 4.5.

## Funzionalità principali:

- **Training**: Addestra Claude su un documento PDF per apprendere lo stile di scrittura
- **Generation**: Genera contenuti basati sullo stile appreso
- **Session Management**: Gestisce multiple sessioni indipendenti
- **Job Management**: Esegue operazioni in background con gestione della coda
- **Thesis Generation**: Genera tesi e relazioni complete con AI

## Workflow tipico:

1. Crea una sessione di training caricando un PDF
2. Attendi il completamento del training
3. Richiedi la generazione di contenuti
4. Recupera i risultati quando il job è completato
5. (Opzionale) Verifica il testo con AI detection
"""

# Validazione configurazione
def validate_config():
    """Valida la configurazione e solleva eccezioni se mancano valori critici."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY non configurata. "
            "Aggiungi la chiave al file .env o come variabile d'ambiente."
        )

    if not PROMPT_ADDESTRAMENTO_PATH.exists():
        raise FileNotFoundError(
            f"File prompt_addestramento.txt non trovato: {PROMPT_ADDESTRAMENTO_PATH}. "
            "Crea il file con il prompt di addestramento."
        )
