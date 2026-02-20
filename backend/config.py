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
THESIS_CLAUDE_MODEL = os.getenv("THESIS_CLAUDE_MODEL", "claude-sonnet-4-6")

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

# Configurazione Prompt
PROMPT_ADDESTRAMENTO_PATH = Path(os.getenv("PROMPT_ADDESTRAMENTO_PATH", "prompt_addestramento.txt"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Rate Limiting (requests per minute)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Versione API
API_VERSION = "1.0.0"
API_TITLE = "StyleForge API"
API_DESCRIPTION = """
API per la generazione di contenuti utilizzando Claude Opus 4.5.

## Funzionalità principali:

- **Training**: Addestra Claude su un documento PDF per apprendere lo stile di scrittura
- **Generation**: Genera contenuti basati sullo stile appreso
- **AI Detection**: Rileva se un testo è stato generato da AI
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
