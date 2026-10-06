"""
Definizione dei tool che il modello Claude puo' invocare durante INGEST/LINT
del wiki. Ogni tool ha sandbox path traversal-safe: ogni path viene risolto
e validato come `is_relative_to(wiki_root)`. Scrittura ammessa SOLO sotto
wiki/, log.md, index.md. raw/ e' read-only.

Public API:
    - WIKI_FS_TOOLS_RW   -> tool definitions per l'ingest (read+write)
    - WIKI_FS_TOOLS_RO   -> tool definitions per il lint (read-only)
    - dispatch_tool(name, params, wiki_root) -> dict (per tool_use_id)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tool names
TOOL_READ_FILE = "read_file"
TOOL_WRITE_FILE = "write_file"
TOOL_APPEND_FILE = "append_file"
TOOL_LIST_DIR = "list_dir"


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool-use format)
# ---------------------------------------------------------------------------

def _tool_def_read() -> Dict[str, Any]:
    return {
        "name": TOOL_READ_FILE,
        "description": (
            "Legge un file di testo dal wiki workspace. Path relativo a wiki_root. "
            "Esempio: 'raw/paper/2024_x.md', 'wiki/fonti/2024_x.md', 'index.md'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relativo a wiki_root, no '..' o assoluti.",
                },
            },
            "required": ["path"],
        },
    }


def _tool_def_write() -> Dict[str, Any]:
    return {
        "name": TOOL_WRITE_FILE,
        "description": (
            "Scrive un file di testo sotto wiki/, oppure sovrascrive log.md/index.md. "
            "Crea la pagina se non esiste. raw/ e' READ-ONLY (errore)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relativo a wiki_root. Solo wiki/**, log.md, index.md.",
                },
                "content": {
                    "type": "string",
                    "description": "Contenuto completo del file (UTF-8).",
                },
            },
            "required": ["path", "content"],
        },
    }


def _tool_def_append() -> Dict[str, Any]:
    return {
        "name": TOOL_APPEND_FILE,
        "description": (
            "Appende testo a log.md (preferito per nuove entry) o ad altri file sotto wiki/. "
            "Non sovrascrive."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    }


def _tool_def_list() -> Dict[str, Any]:
    return {
        "name": TOOL_LIST_DIR,
        "description": (
            "Lista i file in una directory del wiki workspace. Ritorna nomi relativi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relativo a wiki_root. Es: 'raw/paper', 'wiki/fonti'.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Se True, lista anche le sottocartelle (default False).",
                },
            },
            "required": ["path"],
        },
    }


WIKI_FS_TOOLS_RW: List[Dict[str, Any]] = [
    _tool_def_read(),
    _tool_def_write(),
    _tool_def_append(),
    _tool_def_list(),
]

WIKI_FS_TOOLS_RO: List[Dict[str, Any]] = [
    _tool_def_read(),
    _tool_def_list(),
]


# ---------------------------------------------------------------------------
# Sandbox: path resolution + validation
# ---------------------------------------------------------------------------

def _safe_resolve(wiki_root: Path, rel_path: str) -> Tuple[Optional[Path], Optional[str]]:
    """Ritorna (path_assoluto, None) se sicuro, oppure (None, errore) altrimenti."""
    if not rel_path:
        return None, "path vuoto"
    p = (wiki_root / rel_path).resolve()
    try:
        p.relative_to(wiki_root.resolve())
    except ValueError:
        return None, f"path traversal rifiutato: {rel_path!r}"
    return p, None


def _is_writable(wiki_root: Path, abs_path: Path) -> Tuple[bool, str]:
    """Whitelist scritture: wiki/**, log.md, index.md. Rifiuta CLAUDE.md e raw/**."""
    rel = abs_path.relative_to(wiki_root.resolve())
    parts = rel.parts
    if not parts:
        return False, "path vuoto"
    if parts[0] == "raw":
        return False, "raw/ e' READ-ONLY"
    if rel.as_posix() == "CLAUDE.md":
        return False, "CLAUDE.md e' la costituzione, non modificabile"
    if rel.as_posix() in {"log.md", "index.md"}:
        return True, ""
    if parts[0] == "wiki":
        return True, ""
    return False, f"path non consentito in scrittura: {rel.as_posix()}"


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _read_file(wiki_root: Path, path: str, max_chars: int = 100_000) -> Dict[str, Any]:
    abs_path, err = _safe_resolve(wiki_root, path)
    if err:
        return {"error": err, "ok": False}
    if not abs_path.exists():
        return {"error": f"file non trovato: {path}", "ok": False}
    if not abs_path.is_file():
        return {"error": f"non e' un file: {path}", "ok": False}
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": f"read error: {e}", "ok": False}
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "\n[...troncato...]"
    return {"ok": True, "path": path, "content": text, "truncated": truncated}


def _write_file(wiki_root: Path, path: str, content: str) -> Dict[str, Any]:
    abs_path, err = _safe_resolve(wiki_root, path)
    if err:
        return {"error": err, "ok": False}
    ok, why = _is_writable(wiki_root, abs_path)
    if not ok:
        return {"error": why, "ok": False}
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
    except OSError as e:
        return {"error": f"write error: {e}", "ok": False}
    return {"ok": True, "path": path, "bytes_written": len(content.encode("utf-8"))}


def _append_file(wiki_root: Path, path: str, content: str) -> Dict[str, Any]:
    abs_path, err = _safe_resolve(wiki_root, path)
    if err:
        return {"error": err, "ok": False}
    ok, why = _is_writable(wiki_root, abs_path)
    if not ok:
        return {"error": why, "ok": False}
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(abs_path, "a", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as e:
        return {"error": f"append error: {e}", "ok": False}
    return {"ok": True, "path": path, "bytes_appended": len(content.encode("utf-8"))}


def _list_dir(wiki_root: Path, path: str, recursive: bool = False) -> Dict[str, Any]:
    abs_path, err = _safe_resolve(wiki_root, path)
    if err:
        return {"error": err, "ok": False}
    if not abs_path.exists():
        return {"ok": True, "path": path, "entries": []}
    if not abs_path.is_dir():
        return {"error": f"non e' una directory: {path}", "ok": False}
    entries = []
    if recursive:
        for p in sorted(abs_path.rglob("*")):
            if p.is_file():
                entries.append(str(p.relative_to(abs_path)))
    else:
        for p in sorted(abs_path.iterdir()):
            label = p.name + ("/" if p.is_dir() else "")
            entries.append(label)
    return {"ok": True, "path": path, "entries": entries}


def dispatch_tool(name: str, params: Dict[str, Any], wiki_root: Path,
                  read_only: bool = False) -> str:
    """
    Esegue un tool e ritorna il risultato come stringa JSON (formato richiesto
    da Anthropic per il blocco tool_result).
    Se read_only=True, le tool di scrittura vengono rifiutate.
    """
    try:
        if name == TOOL_READ_FILE:
            result = _read_file(wiki_root, str(params.get("path", "")))
        elif name == TOOL_LIST_DIR:
            result = _list_dir(
                wiki_root,
                str(params.get("path", "")),
                bool(params.get("recursive", False)),
            )
        elif name == TOOL_WRITE_FILE:
            if read_only:
                result = {"error": "tool write_file disabilitato (modalita' lint read-only)", "ok": False}
            else:
                result = _write_file(
                    wiki_root,
                    str(params.get("path", "")),
                    str(params.get("content", "")),
                )
        elif name == TOOL_APPEND_FILE:
            if read_only:
                result = {"error": "tool append_file disabilitato (modalita' lint read-only)", "ok": False}
            else:
                result = _append_file(
                    wiki_root,
                    str(params.get("path", "")),
                    str(params.get("content", "")),
                )
        else:
            result = {"error": f"tool sconosciuto: {name}", "ok": False}
    except Exception as e:  # noqa: BLE001
        logger.exception("Tool dispatch error: %s", name)
        result = {"error": f"exception: {e}", "ok": False}
    return json.dumps(result, ensure_ascii=False)
