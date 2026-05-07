"""
Orchestrazione SDK Anthropic per i workflow INGEST e LINT del wiki tesi.

Strategia:
  - `CLAUDE.md` viene caricato dal template di repo e passato come `system`
    prompt (con prompt caching, e' grande ~7K token e statico).
  - INGEST: si itera in batch da WIKI_INGEST_BATCH_SIZE fonti per turno.
    Ogni turno e' un message "user" che dice esattamente la frase di trigger
    richiesta dall'utente: "Ho inserito dei documenti dentro raw, procedi
    con la fase di ingest." + l'elenco dei file del batch corrente.
    Il modello chiama tool_use (read_file, write_file, append_file) sandboxati.
  - LINT: un solo turno user "Adesso procedi con la fase di lint." con tool
    read-only. L'output deve contenere un blocco JSON con il report.

Il runner espone:
  - run_ingest(thesis_id, on_progress=None) -> IngestSummary
  - run_lint(thesis_id) -> dict (report)

Errori e timeout vengono propagati al chiamante (thesis_routes), che aggiorna
wiki_status='failed' e logga.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import anthropic

import config
from ai_client import get_claude_client
from llm_wiki import wiki_tools, wiki_workspace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trigger phrases — match esatto richiesto dall'utente
# ---------------------------------------------------------------------------

INGEST_TRIGGER = "Ho inserito dei documenti dentro raw, procedi con la fase di ingest."
LINT_TRIGGER = "Adesso procedi con la fase di lint."


# ---------------------------------------------------------------------------
# Risultati
# ---------------------------------------------------------------------------

@dataclass
class IngestSummary:
    sources_count: int = 0
    pages_created: int = 0
    pages_updated: int = 0
    log_entries_added: int = 0
    duration_sec: float = 0.0
    raw_log_tail: str = ""
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: lettura costituzione + system prompt building
# ---------------------------------------------------------------------------

def _load_constitution() -> str:
    path = Path(config.WIKI_TEMPLATE_DIR) / "CLAUDE.md"
    if not path.exists():
        raise RuntimeError(f"CLAUDE.md mancante in {config.WIKI_TEMPLATE_DIR}")
    return path.read_text(encoding="utf-8")


def _build_system(constitution: str, mode: str) -> List[Dict[str, Any]]:
    """
    System prompt = costituzione (con prompt caching) + nota di scoping.
    mode in {"ingest", "lint"}.
    """
    scope_note = (
        "\n\n---\n"
        "## Contesto operativo per questa sessione\n"
        f"- Modalità: **{mode.upper()}**\n"
        "- Stai lavorando in una cartella wiki *isolata* per una specifica tesi. Ogni "
        "scrittura deve passare per i tool `write_file` / `append_file`. Non avere "
        "accesso al filesystem del server o ad altre cartelle.\n"
        "- Tutti i path nei tool sono relativi a `wiki_root`. Esempi: "
        "`raw/paper/2024_x.md`, `wiki/fonti/2024_x.md`, `index.md`, `log.md`.\n"
        "- `raw/` e' READ-ONLY. Non puoi modificarlo. La costituzione vale anche qui.\n"
    )
    return [
        {
            "type": "text",
            "text": constitution,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": scope_note},
    ]


# ---------------------------------------------------------------------------
# Tool-loop helper: ripete la chiamata finche' il modello non si ferma o
# raggiunge max_iterations. Applica i tool_use, ritorna l'ultima risposta.
# ---------------------------------------------------------------------------

def _run_tool_loop(
    client: anthropic.Anthropic,
    system: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    wiki_root: Path,
    *,
    model: str,
    max_tokens: int,
    read_only: bool = False,
    max_iterations: int = 30,
    deadline_ts: Optional[float] = None,
) -> anthropic.types.Message:
    """
    Esegue un loop messages.create -> apply tool_use -> append tool_result.
    Termina quando stop_reason != 'tool_use' o max_iterations.
    """
    last_response: Optional[anthropic.types.Message] = None
    for iteration in range(max_iterations):
        if deadline_ts is not None and time.time() > deadline_ts:
            raise TimeoutError(f"Wiki runner timeout dopo {iteration} iter (modalita' {'RO' if read_only else 'RW'})")

        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        last_response = resp

        # Append assistant turn
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            break

        # Raccogli i tool_use blocks e produci i tool_result
        tool_results: List[Dict[str, Any]] = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                tool_name = block.name
                tool_input = block.input or {}
                result_str = wiki_tools.dispatch_tool(
                    name=tool_name,
                    params=tool_input,
                    wiki_root=wiki_root,
                    read_only=read_only,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
        if not tool_results:
            # Stop reason "tool_use" ma niente tool_use blocks: anomalia, esci.
            break
        messages.append({"role": "user", "content": tool_results})

    if last_response is None:
        raise RuntimeError("messages.create non ha mai risposto")
    return last_response


def _chunked(seq: List, size: int) -> List[List]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


# ---------------------------------------------------------------------------
# INGEST
# ---------------------------------------------------------------------------

def run_ingest(
    thesis_id: str,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> IngestSummary:
    """
    Esegue il workflow INGEST sul wiki di una tesi.
    Il modello legge i file in raw/ via tool e popola wiki/+log.md+index.md.
    """
    wiki_root = wiki_workspace.get_wiki_root(thesis_id).resolve()
    if not wiki_root.exists():
        raise RuntimeError(f"wiki_root non esiste: {wiki_root}")

    raw_files = wiki_workspace.list_raw_files(thesis_id)
    if len(raw_files) > config.WIKI_MAX_SOURCES:
        raise ValueError(
            f"Troppe fonti raw: {len(raw_files)} > limite {config.WIKI_MAX_SOURCES}. "
            "Riduci le fonti o aumenta WIKI_MAX_SOURCES."
        )

    summary = IngestSummary(sources_count=len(raw_files))
    pages_before = wiki_workspace.count_wiki_pages(thesis_id)
    log_lines_before = _count_log_entries(wiki_root)

    if not raw_files:
        # Nessuna fonte: ingest no-op (wiki resta vuoto, e' valido).
        if on_progress:
            on_progress(100, "Nessuna fonte da ingerire")
        return summary

    constitution = _load_constitution()
    system = _build_system(constitution, "ingest")

    claude_wrapper = get_claude_client()
    client = claude_wrapper.client  # underlying anthropic.Anthropic
    model = config.WIKI_CLAUDE_MODEL

    deadline_ts = time.time() + config.WIKI_INGEST_TIMEOUT_SEC
    started = time.time()

    messages: List[Dict[str, Any]] = []
    batches = _chunked(raw_files, config.WIKI_INGEST_BATCH_SIZE)
    total_batches = len(batches)

    for idx, batch in enumerate(batches, start=1):
        # `list_raw_files` puo' tornare path relativi (THESIS_UPLOADS_DIR e' "./thesis_uploads")
        # mentre wiki_root e' stato risolto ad assoluto. Risolviamo ogni p a assoluto
        # cosi' che relative_to funzioni in entrambi i casi.
        rel_paths = [str(p.resolve().relative_to(wiki_root)) for p in batch]
        files_block = "\n".join(f"- `{p}`" for p in rel_paths)

        if idx == 1:
            user_msg = (
                f"{INGEST_TRIGGER}\n\n"
                f"In `raw/` ci sono {len(raw_files)} file da ingerire (in {total_batches} batch). "
                f"Questo è il primo batch:\n\n{files_block}\n\n"
                "Per ogni file: leggilo con `read_file`, poi crea/aggiorna le pagine in "
                "`wiki/fonti/`, `wiki/entita/`, `wiki/concetti/`, `wiki/temi/` come da "
                "schema (sez. 7 di CLAUDE.md). Aggiorna anche `index.md` e appendi una "
                "entry a `log.md`. Quando hai finito questo batch, rispondi con un breve "
                "riepilogo (1-3 righe) di cosa hai creato/aggiornato e vado avanti col prossimo batch."
            )
        else:
            user_msg = (
                f"Ottimo, prosegui con il batch {idx}/{total_batches}:\n\n{files_block}\n\n"
                "Stessa procedura: ingest delle fonti, aggiornamento pagine sintetiche, "
                "index.md e log.md. Riepilogo finale dopo questo batch."
            )

        messages.append({"role": "user", "content": user_msg})

        try:
            _run_tool_loop(
                client=client,
                system=system,
                messages=messages,
                tools=wiki_tools.WIKI_FS_TOOLS_RW,
                wiki_root=wiki_root,
                model=model,
                max_tokens=config.WIKI_INGEST_MAX_TOKENS,
                read_only=False,
                deadline_ts=deadline_ts,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Errore ingest batch %s/%s tesi %s", idx, total_batches, thesis_id)
            summary.errors.append(f"batch {idx}: {e}")
            # Procedi: errori parziali non bloccano l'intero ingest

        if on_progress:
            on_progress(int(idx / total_batches * 100), f"batch {idx}/{total_batches}")

    summary.duration_sec = time.time() - started
    pages_after = wiki_workspace.count_wiki_pages(thesis_id)
    summary.pages_created = max(0, pages_after - pages_before)
    summary.log_entries_added = max(0, _count_log_entries(wiki_root) - log_lines_before)
    summary.raw_log_tail = _tail_log(wiki_root, max_chars=2000)
    return summary


# ---------------------------------------------------------------------------
# LINT
# ---------------------------------------------------------------------------

LINT_USER_PROMPT = (
    f"{LINT_TRIGGER}\n\n"
    "Esegui il workflow LINT come definito nella sez. 9 di CLAUDE.md. "
    "Esplora il wiki via `list_dir` + `read_file` (sei in modalità read-only, "
    "non puoi scrivere). Alla fine, **rispondi con un blocco JSON unico** "
    "tra ```json e ``` con i seguenti campi (lascia array vuoti se nulla "
    "da segnalare):\n"
    "{\n"
    "  \"orphan_pages\": [\"<file relpath>\"],\n"
    "  \"broken_wikilinks\": [{\"in_page\":\"<relpath>\",\"target\":\"<wikilink>\"}],\n"
    "  \"missing_concepts\": [\"<termine>\"],\n"
    "  \"contradictions\": [{\"claim\":\"<sintesi>\",\"sources\":[\"<relpath1>\",\"<relpath2>\"]}],\n"
    "  \"stale_pages\": [\"<relpath>\"],\n"
    "  \"frontmatter_issues\": [{\"page\":\"<relpath>\",\"issue\":\"<descrizione>\"}],\n"
    "  \"exploration_suggestions\": [\"<idea breve>\"],\n"
    "  \"gaps\": [\"<tema richiesto ma poco coperto>\"]\n"
    "}\n"
    "Prima del JSON, una sintesi di 2-3 righe a parole tue."
)


def run_lint(thesis_id: str) -> Dict[str, Any]:
    """Esegue LINT sul wiki di una tesi e ritorna il report come dict."""
    wiki_root = wiki_workspace.get_wiki_root(thesis_id).resolve()
    if not wiki_root.exists():
        raise RuntimeError(f"wiki_root non esiste: {wiki_root}")

    constitution = _load_constitution()
    system = _build_system(constitution, "lint")

    claude_wrapper = get_claude_client()
    client = claude_wrapper.client
    model = config.WIKI_CLAUDE_MODEL

    deadline_ts = time.time() + config.WIKI_INGEST_TIMEOUT_SEC

    messages: List[Dict[str, Any]] = [{"role": "user", "content": LINT_USER_PROMPT}]
    response = _run_tool_loop(
        client=client,
        system=system,
        messages=messages,
        tools=wiki_tools.WIKI_FS_TOOLS_RO,
        wiki_root=wiki_root,
        model=model,
        max_tokens=config.WIKI_LINT_MAX_TOKENS,
        read_only=True,
        deadline_ts=deadline_ts,
    )

    full_text = _extract_text(response)
    report = _parse_json_block(full_text)
    if report is None:
        # Fallback: report vuoto, summary testuale
        report = {
            "orphan_pages": [],
            "broken_wikilinks": [],
            "missing_concepts": [],
            "contradictions": [],
            "stale_pages": [],
            "frontmatter_issues": [],
            "exploration_suggestions": [],
            "gaps": [],
            "_raw_summary": full_text[:2000],
            "_warning": "Il modello non ha prodotto un blocco JSON valido. Vedi _raw_summary.",
        }
    else:
        report.setdefault("_raw_summary", full_text[:2000])
    return report


# ---------------------------------------------------------------------------
# Helpers privati
# ---------------------------------------------------------------------------

def _extract_text(response: anthropic.types.Message) -> str:
    parts: List[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Trova il primo blocco ```json {...}``` nel testo."""
    if not text:
        return None
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: prova a trovare il primo {...} bilanciato
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                blob = text[start:i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    return None
    return None


def _count_log_entries(wiki_root: Path) -> int:
    log = wiki_root / "log.md"
    if not log.exists():
        return 0
    return sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.startswith("## ["))


def _tail_log(wiki_root: Path, max_chars: int = 2000) -> str:
    log = wiki_root / "log.md"
    if not log.exists():
        return ""
    text = log.read_text(encoding="utf-8")
    return text[-max_chars:]
