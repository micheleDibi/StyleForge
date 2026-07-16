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

# ============================================================================
# JWT — chiave di firma
# ============================================================================
# NESSUN default: un default hardcoded e' un segreto pubblico, e chi firma i
# token con un segreto pubblico non ha autenticazione. La validazione NON sta a
# livello di modulo perche' config e' importato da mezzo backend (llm_wiki,
# thesis_assets, thesis_prompts, email_service...) che col JWT non c'entra
# nulla: la fa auth.py, l'unico che il segreto lo usa davvero.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Lunghezza minima. Il placeholder storico e' lungo 42 caratteri: una soglia
# tipo "almeno 32" lo lascerebbe passare e il fix sarebbe decorativo.
JWT_SECRET_MIN_LENGTH = 64

# Valori che NON sono segreti, per quanto lunghi. E' questa lista a fare il
# lavoro: il placeholder non arriva dal default di os.getenv, e' scritto nel
# .env reale, quindi togliere il default da auth.py non farebbe fallire niente.
_JWT_PLACEHOLDERS = frozenset({
    "your-super-secret-key-change-in-production",
    "your-secret-key",
    "change-me",
    "changeme",
    "secret",
    "supersecret",
    "test",
    "dev",
    "development",
    "production",
})

_JWT_SECRET_HOWTO = (
    'Generane uno con: python3 -c "import secrets; print(secrets.token_urlsafe(64))" '
    "e impostalo come JWT_SECRET_KEY (nel .env in locale, come variabile d'ambiente "
    "in produzione). Ruotarlo invalida tutti i token esistenti: gli utenti dovranno "
    "rifare il login."
)


def validate_jwt_secret(value):
    """
    Valida la chiave di firma JWT, o solleva RuntimeError.

    Funzione pura (nessun accesso a os.environ): il chiamante passa il valore.
    """
    if value is None or not str(value).strip():
        raise RuntimeError(
            "JWT_SECRET_KEY non configurata: l'applicazione non parte senza una "
            f"chiave di firma. {_JWT_SECRET_HOWTO}"
        )

    secret = str(value).strip()

    if secret.lower() in _JWT_PLACEHOLDERS:
        raise RuntimeError(
            "JWT_SECRET_KEY e' un valore segnaposto pubblico, non un segreto: "
            "chiunque puo' forgiare token per qualsiasi utente, admin inclusi. "
            f"{_JWT_SECRET_HOWTO}"
        )

    if len(secret) < JWT_SECRET_MIN_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET_KEY troppo corta ({len(secret)} caratteri, minimo "
            f"{JWT_SECRET_MIN_LENGTH}). {_JWT_SECRET_HOWTO}"
        )

    return secret

# OpenAI Configuration
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "o3")  # o3 reasoning model
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))

# AI Provider per Thesis Generation
# Valori: "openai" (default) o "claude"
# Provider per la generazione del contenuto tesi. Default "claude": rispetta
# temperature/top_p (più varietà/perplessità => meno rilevabile) a differenza dei
# modelli reasoning OpenAI (o3) che li ignorano.
THESIS_AI_PROVIDER = os.getenv("THESIS_AI_PROVIDER", "claude")
THESIS_CLAUDE_MODEL = os.getenv("THESIS_CLAUDE_MODEL", "claude-opus-4-8")

# ----------------------------------------------------------------------------
# Anti-AI per la tesi (riduzione del punteggio "Rilevamento AI" dei detector)
# ----------------------------------------------------------------------------
# Master switch: applica gli stage anti-rilevamento al contenuto generato.
THESIS_ANTI_AI_ENABLED = os.getenv("THESIS_ANTI_AI_ENABLED", "true").lower() == "true"
# Stage 1: riscrittura "de-AI accademica" via LLM. OFF di default: rompe i
# pattern visibili a un lettore umano ma NON abbassa il punteggio Compilatio
# (anzi può alzarlo). Attivabile se serve prosa più "de-patternizzata".
THESIS_REWRITE_ENABLED = os.getenv("THESIS_REWRITE_ENABLED", "false").lower() == "true"
# Stage 2: pass algoritmico (profilo accademico) di anti_ai_processor.
THESIS_ALGO_ENABLED = os.getenv("THESIS_ALGO_ENABLED", "true").lower() == "true"
# Modello usato per la riscrittura de-AI (sempre Claude: miglior controllo stilistico).
THESIS_REWRITE_MODEL = os.getenv("THESIS_REWRITE_MODEL", "claude-opus-4-8")
# Profilo del pass algoritmico: "academic" (no colloquialismi) per le tesi.
THESIS_ANTI_AI_PROFILE = os.getenv("THESIS_ANTI_AI_PROFILE", "academic")

# Riscrittura controllata (DIPPER-style): leva principale anti-rilevamento.
# Parafrasi per sezione che massimizza diversità lessicale + riordino, applicata
# in modo RICORSIVO (la ricerca mostra che la ricorsività abbatte di più il
# rilevamento). Preserva registro accademico, citazioni [x], note e lunghezza.
THESIS_PARAPHRASE_ENABLED = os.getenv("THESIS_PARAPHRASE_ENABLED", "true").lower() == "true"
THESIS_PARAPHRASE_ROUNDS = int(os.getenv("THESIS_PARAPHRASE_ROUNDS", "2"))
THESIS_PARAPHRASE_MODEL = os.getenv("THESIS_PARAPHRASE_MODEL", "claude-opus-4-8")
# Temperatura/top_p alti = più varietà (perplessità) nella generazione del contenuto.
# NB: i modelli reasoning OpenAI (o3) li ignorano; per varietà reale usare un modello
# sampling-capable (es. Claude) come provider del contenuto.
THESIS_GEN_TEMPERATURE = float(os.getenv("THESIS_GEN_TEMPERATURE", "1.0"))
THESIS_GEN_TOP_P = float(os.getenv("THESIS_GEN_TOP_P", "0.95"))

# Elementi visivi nella tesi (tabelle [TABELLA], grafici [GRAFICO], HINT).
# THESIS_ASSETS_ENABLED inietta le istruzioni nel prompt di sezione (producer);
# gli exporter riconoscono comunque la sintassi anche a flag spento.
# THESIS_CHARTS_ENABLED = kill-switch dei grafici: se False i [GRAFICO] degradano
# a box HINT negli export e il prompt chiede sempre un HINT al posto del grafico.
THESIS_ASSETS_ENABLED = os.getenv("THESIS_ASSETS_ENABLED", "true").lower() == "true"
THESIS_CHARTS_ENABLED = os.getenv("THESIS_CHARTS_ENABLED", "true").lower() == "true"

# Formule matematiche LaTeX nella tesi ($...$ inline, $$...$$ display).
# THESIS_MATH_ENABLED inietta le istruzioni nel prompt di sezione (producer);
# renderer e protezione sentinelle riconoscono comunque la sintassi anche a
# flag spento (le tesi già generate con formule si sistemano all'export).
THESIS_MATH_ENABLED = os.getenv("THESIS_MATH_ENABLED", "true").lower() == "true"

# ----------------------------------------------------------------------------
# Anti-AI per Genera/Umanizza (stesso meccanismo della Tesi, applicato alle
# funzioni di generazione e umanizzazione su sessione addestrata).
# Default = comportamento della pipeline Tesi. La parafrasi controllata è la leva
# principale; disattivabile se costo/latenza preoccupano.
# ----------------------------------------------------------------------------
ANTI_AI_PARAPHRASE_ENABLED = os.getenv("ANTI_AI_PARAPHRASE_ENABLED", "true").lower() == "true"
ANTI_AI_PARAPHRASE_ROUNDS = int(os.getenv("ANTI_AI_PARAPHRASE_ROUNDS", "2"))
ANTI_AI_PARAPHRASE_MODEL = os.getenv("ANTI_AI_PARAPHRASE_MODEL", "claude-opus-4-8")
ANTI_AI_REWRITE_ENABLED = os.getenv("ANTI_AI_REWRITE_ENABLED", "false").lower() == "true"
ANTI_AI_REWRITE_MODEL = os.getenv("ANTI_AI_REWRITE_MODEL", "claude-opus-4-8")
ANTI_AI_ALGO_ENABLED = os.getenv("ANTI_AI_ALGO_ENABLED", "true").lower() == "true"

# Massimo output token del modello (claude-opus-4-8: 128000). Tetto di sicurezza
# usato per limitare max_tokens ed evitare il 400 "max_tokens > 128000".
MODEL_MAX_OUTPUT_TOKENS = int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "120000"))
# Parole per batch nel round-trip docx (umanizzazione documento col template).
# Stile più forte sui documenti: batch piccoli (più focus per paragrafo) + passate
# extra di rifinitura stilistica (cap a 2 totali per evitare deriva di significato).
DOC_HUMANIZE_BATCH_WORDS = int(os.getenv("DOC_HUMANIZE_BATCH_WORDS", "1000"))
DOC_STYLE_REFINE_PASSES = int(os.getenv("DOC_STYLE_REFINE_PASSES", "1"))

# Addestramento: analisi dell'INTERO documento (nessun cap di pagine) tramite
# map-reduce iterativo, con profilo finale lungo e dettagliato.
TRAIN_CHUNK_WORDS = int(os.getenv("TRAIN_CHUNK_WORDS", "6000"))          # parole per blocco di analisi
TRAIN_PROFILE_MAX_TOKENS = int(os.getenv("TRAIN_PROFILE_MAX_TOKENS", "16000"))  # output del profilo finale
TRAIN_MAP_MAX_TOKENS = int(os.getenv("TRAIN_MAP_MAX_TOKENS", "4000"))    # output delle osservazioni per blocco
TRAIN_REDUCE_MAX_OBS_WORDS = int(os.getenv("TRAIN_REDUCE_MAX_OBS_WORDS", "40000"))  # soglia reduce gerarchico

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Configurazione Claude
MAX_TOKENS_TRAIN = int(os.getenv("MAX_TOKENS_TRAIN", "4096"))
MAX_TOKENS_TEST = int(os.getenv("MAX_TOKENS_TEST", "8192"))
CLAUDE_MODEL_ID = "claude-opus-4-8"

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
# Allegati-URL: tetto sulla pagina scaricata. Ne servono ~8000 caratteri di
# testo (il resto viene troncato), quindi 5 MB di HTML sono gia' abbondanti.
# Prima non c'era limite: response.text scaricava tutto e troncava DOPO.
THESIS_URL_MAX_BYTES = int(os.getenv("THESIS_URL_MAX_MB", "5")) * 1024 * 1024
# Time budget per URL: era il timeout httpx dell'implementazione precedente.
THESIS_URL_TIMEOUT = int(os.getenv("THESIS_URL_TIMEOUT", "20"))

# LLM Wiki (second-brain per-tesi)
# Path del template del wiki: contiene CLAUDE.md (la "costituzione") + struttura
# di sottocartelle vuote che viene clonata in thesis_uploads/{tid}/llm_wiki/.
WIKI_TEMPLATE_DIR = Path(os.getenv("WIKI_TEMPLATE_DIR", str(Path(__file__).resolve().parent.parent / "llm_wiki")))
# Modello Claude usato per ingest/lint. Opus 4.8 e' il default (massima qualita'
# sull'ingest, con prompt caching del CLAUDE.md). L'utente puo' overridare via env.
WIKI_CLAUDE_MODEL = os.getenv("WIKI_CLAUDE_MODEL", "claude-opus-4-8")
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

# ============================================================================
# EMAIL / SMTP (verifica registrazione, reset password, invito)
# ============================================================================
# OVH: host ssl0.ovh.net, porta 587 STARTTLS (la porta 465 NON è utilizzabile).
# Se SMTP_HOST è vuoto le email non vengono inviate: il link viene loggato
# (utile in sviluppo/test prima di configurare le credenziali).
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"  # default STARTTLS (587)
MAIL_FROM = os.getenv("MAIL_FROM", "noreply@styleforge.us")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "StyleForge")

# Base URL del frontend per i link nelle email (verifica/reset/invito/spostamento)
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://app.styleforge.us")

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

# MiniMax Video Generation (Admin-only)
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.chat/v1")
MINIMAX_DEFAULT_MODEL = os.getenv("MINIMAX_DEFAULT_MODEL", "MiniMax-Hailuo-2.3")
VIDEO_MAX_UPLOAD_SIZE = int(os.getenv("VIDEO_MAX_UPLOAD_SIZE", "10")) * 1024 * 1024
VIDEO_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
# Tetto sul video scaricato dal proxy: prima non c'era alcun limite e il body
# finiva intero in RAM (resp.content).
VIDEO_MAX_PROXY_BYTES = int(os.getenv("VIDEO_MAX_PROXY_MB", "200")) * 1024 * 1024
# Time budget del proxy: era il timeout httpx dell'implementazione precedente.
VIDEO_PROXY_TIMEOUT = int(os.getenv("VIDEO_PROXY_TIMEOUT", "120"))

# API Pricing (Claude Opus 4.8) — per stima costi admin
CLAUDE_OPUS_INPUT_PRICE_USD = 5.0    # $ per 1M input tokens
CLAUDE_OPUS_OUTPUT_PRICE_USD = 25.0  # $ per 1M output tokens
USD_TO_EUR_RATE = 0.88               # Tasso di cambio approssimativo

# API Pricing (OpenAI o3) — per stima costi admin thesis
OPENAI_O3_INPUT_PRICE_USD = 10.0     # $ per 1M input tokens
OPENAI_O3_OUTPUT_PRICE_USD = 40.0    # $ per 1M output tokens

# Versione API
API_VERSION = "1.0.0"
API_TITLE = "StyleForge API"
API_DESCRIPTION = """
API per la generazione di contenuti utilizzando Claude Opus 4.8.

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
    # Rete per chi importa solo config: nel percorso dell'app questo controllo
    # non viene mai raggiunto per il JWT, perche' api.py importa auth (che alza
    # a import time) prima di chiamare validate_config().
    validate_jwt_secret(JWT_SECRET_KEY)

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
