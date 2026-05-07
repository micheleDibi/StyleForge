"""
Filesystem layer per il second-brain LLM Wiki di una tesi.

Ogni tesi ha la sua cartella isolata in:
    {THESIS_UPLOADS_DIR}/{thesis_id}/llm_wiki/

con la stessa struttura del template /llm_wiki/ della repo:
    raw/{articoli,libri,paper,note,trascrizioni,assets}/
    wiki/{fonti,entita,concetti,temi,sintesi,domande}/
    CLAUDE.md  (la "costituzione" del wiki, copiata dal template)
    index.md   (catalogo)
    log.md     (registro operazioni)

Le funzioni qui sono FS-only: niente chiamate LLM. L'orchestrazione SDK Anthropic
sta in wiki_runner.py.
"""

from __future__ import annotations

import logging
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from filelock import FileLock, Timeout

import config
from db_models import ThesisAttachment

logger = logging.getLogger(__name__)

# Sottocartelle obbligatorie del template
RAW_SUBDIRS = ["articoli", "libri", "paper", "note", "trascrizioni", "assets"]
WIKI_SUBDIRS = ["fonti", "entita", "concetti", "temi", "sintesi", "domande"]
CONSTITUTION_FILES = ["CLAUDE.md", "index.md", "log.md"]

# MIME type del paper (definito anche in research_summarizer per coerenza)
PAPER_MIME_TYPE = "application/x-research-paper"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_wiki_root(thesis_id: str) -> Path:
    """Ritorna il path della cartella wiki di una tesi (anche se non esiste)."""
    return config.THESIS_UPLOADS_DIR / str(thesis_id) / "llm_wiki"


def is_initialized(thesis_id: str) -> bool:
    """True se la cartella e' gia' stata clonata dal template."""
    root = get_wiki_root(thesis_id)
    return root.exists() and (root / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# Bootstrap: clona template /llm_wiki/ in thesis_uploads/{tid}/llm_wiki/
# ---------------------------------------------------------------------------

def bootstrap(thesis_id: str) -> Path:
    """
    Crea (se necessario) la cartella wiki per la tesi clonando il template.
    Idempotente: se la cartella esiste, ritorna senza errori.
    Ritorna il path root.
    """
    root = get_wiki_root(thesis_id)
    template = config.WIKI_TEMPLATE_DIR

    if not template.exists():
        raise RuntimeError(
            f"Template wiki non trovato: {template}. "
            "Verifica WIKI_TEMPLATE_DIR in config.py."
        )

    # Crea sempre la struttura di sottocartelle (idempotente)
    root.mkdir(parents=True, exist_ok=True)
    for sub in RAW_SUBDIRS:
        (root / "raw" / sub).mkdir(parents=True, exist_ok=True)
    for sub in WIKI_SUBDIRS:
        (root / "wiki" / sub).mkdir(parents=True, exist_ok=True)

    # Copia i file di costituzione solo se non esistono gia' (preserva
    # eventuali modifiche fatte dalla sessione di ingest precedente)
    for fname in CONSTITUTION_FILES:
        dst = root / fname
        if not dst.exists():
            src = template / fname
            if src.exists():
                shutil.copy2(src, dst)

    return root


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, max_length: int = 80) -> str:
    """kebab-case lowercase, no accenti, no caratteri speciali."""
    if not text:
        return "untitled"
    # Rimuovi accenti
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        return "untitled"
    return text[:max_length].rstrip("-")


def make_raw_filename(date_iso: Optional[str], title: str, ext: str = ".md") -> str:
    """Genera un nome file kebab-case per raw/, opzionalmente prefissato con data."""
    slug = _slugify(title)
    prefix = f"{date_iso}_" if date_iso else ""
    return f"{prefix}{slug}{ext}"


# ---------------------------------------------------------------------------
# Materializzazione user uploads in raw/
# ---------------------------------------------------------------------------

def _user_upload_subdir(mime_type: Optional[str], filename: str) -> str:
    """
    Determina la sottocartella di raw/ per un upload utente.
    PDF/articoli web -> articoli, libri voluminosi -> libri, txt brevi -> note.
    Default sicuro: articoli.
    """
    if not filename:
        return "articoli"
    name_lower = filename.lower()
    if mime_type == "text/plain" or name_lower.endswith(".txt"):
        return "note"
    if "libro" in name_lower or "book" in name_lower:
        return "libri"
    return "articoli"


def materialize_user_uploads(thesis_id: str, attachments: List[ThesisAttachment]) -> int:
    """
    Per ogni allegato utente (NON paper) crea un file markdown in raw/.
    Il testo e' gia' estratto in attachment.extracted_text.
    Ritorna il numero di file creati.
    """
    root = get_wiki_root(thesis_id)
    if not root.exists():
        bootstrap(thesis_id)

    created = 0
    for att in attachments:
        # Skip paper (gestiti dal paper_downloader)
        if att.mime_type == PAPER_MIME_TYPE:
            continue
        if not att.extracted_text:
            continue

        subdir = _user_upload_subdir(att.mime_type, att.original_filename or att.filename)
        title = (att.original_filename or att.filename or "documento").rsplit(".", 1)[0]
        fname = make_raw_filename(None, title)
        dst = root / "raw" / subdir / fname

        # Anti-collisione
        i = 1
        while dst.exists():
            fname = make_raw_filename(None, f"{title}-{i}")
            dst = root / "raw" / subdir / fname
            i += 1

        # Frontmatter minimo + corpo = testo estratto
        body = (
            f"---\n"
            f"tipo: fonte_raw\n"
            f"titolo: \"{(att.original_filename or 'Documento').replace(chr(34), chr(39))}\"\n"
            f"formato: {subdir.rstrip('i')}\n"  # articoli -> articolo, libri -> libro, note -> not
            f"data_ingest: {datetime.utcnow().date().isoformat()}\n"
            f"file_origine: \"{att.original_filename or att.filename}\"\n"
            f"---\n\n"
            f"{att.extracted_text}\n"
        )
        dst.write_text(body, encoding="utf-8")
        created += 1

    return created


# ---------------------------------------------------------------------------
# Listing: rileva fonti raw/ presenti per ingest e count pagine wiki/
# ---------------------------------------------------------------------------

def list_raw_files(thesis_id: str) -> List[Path]:
    """Tutti i file regolari sotto raw/, esclusi assets/ binari (PDF/img)."""
    root = get_wiki_root(thesis_id)
    raw = root / "raw"
    if not raw.exists():
        return []
    out: List[Path] = []
    for sub in RAW_SUBDIRS:
        if sub == "assets":
            continue  # raw/assets contiene binari, non ingeribili come testo
        d = raw / sub
        if d.exists():
            out.extend(p for p in sorted(d.iterdir()) if p.is_file())
    return out


def count_wiki_pages(thesis_id: str) -> int:
    """Conta le pagine .md sotto wiki/ (fonti+entita+concetti+temi+sintesi+domande)."""
    root = get_wiki_root(thesis_id)
    wiki = root / "wiki"
    if not wiki.exists():
        return 0
    return sum(
        1
        for sub in WIKI_SUBDIRS
        for p in (wiki / sub).iterdir()
        if (wiki / sub).exists() and p.is_file() and p.suffix == ".md"
    )


# ---------------------------------------------------------------------------
# Lock per impedire ingest concorrenti sulla stessa tesi
# ---------------------------------------------------------------------------

def _lock_path(thesis_id: str) -> Path:
    return get_wiki_root(thesis_id) / ".ingest.lock"


def acquire_lock(thesis_id: str, timeout: float = 0.0) -> FileLock:
    """
    Acquisisce il lock filesystem sulla cartella wiki della tesi.
    timeout=0 -> non bloccante: solleva filelock.Timeout se gia' acquisito.
    Caller responsible di usarlo come context manager o di rilasciarlo.
    """
    bootstrap(thesis_id)  # garantisce che la cartella esista
    lock = FileLock(str(_lock_path(thesis_id)), timeout=timeout)
    lock.acquire()
    return lock


def is_locked(thesis_id: str) -> bool:
    """Heuristica: prova ad acquisire e rilasciare immediatamente."""
    lock = FileLock(str(_lock_path(thesis_id)), timeout=0)
    try:
        lock.acquire()
        lock.release()
        return False
    except Timeout:
        return True


# ---------------------------------------------------------------------------
# Snapshot e restore (per rollback ingest fallito)
# ---------------------------------------------------------------------------

def snapshot_wiki(thesis_id: str) -> Optional[Path]:
    """
    Sposta wiki/ in wiki.bak.<timestamp>/ per consentire rollback.
    Ritorna il path del backup (o None se non c'era nulla da snapshottare).
    """
    root = get_wiki_root(thesis_id)
    wiki = root / "wiki"
    if not wiki.exists() or not any(wiki.iterdir()):
        return None
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup = root / f"wiki.bak.{ts}"
    shutil.move(str(wiki), str(backup))
    # Ricrea struttura vuota
    for sub in WIKI_SUBDIRS:
        (wiki / sub).mkdir(parents=True, exist_ok=True)
    return backup


def restore_snapshot(thesis_id: str, backup: Path) -> None:
    """Ripristina un backup. Cancella la wiki/ corrente."""
    root = get_wiki_root(thesis_id)
    wiki = root / "wiki"
    if wiki.exists():
        shutil.rmtree(wiki)
    shutil.move(str(backup), str(wiki))


def cleanup_old_snapshots(thesis_id: str, keep: int = 2) -> None:
    """Rimuove snapshot wiki.bak.* lasciandone gli ultimi `keep`."""
    root = get_wiki_root(thesis_id)
    if not root.exists():
        return
    backups = sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("wiki.bak.")],
        reverse=True
    )
    for old in backups[keep:]:
        try:
            shutil.rmtree(old)
        except OSError:
            logger.warning("Impossibile rimuovere snapshot %s", old, exc_info=True)


# ---------------------------------------------------------------------------
# Cleanup totale (su delete tesi)
# ---------------------------------------------------------------------------

def cleanup(thesis_id: str) -> bool:
    """Rimuove l'intera cartella wiki della tesi. Ritorna True se rimossa."""
    root = get_wiki_root(thesis_id)
    if not root.exists():
        return False
    try:
        shutil.rmtree(root)
        return True
    except OSError:
        logger.exception("Impossibile rimuovere wiki di tesi %s", thesis_id)
        return False
