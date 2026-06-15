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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    total_tool_calls: int = 0
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

@dataclass
class ToolLoopStats:
    iterations: int = 0
    total_tool_calls: int = 0
    write_calls: int = 0
    read_calls: int = 0
    list_calls: int = 0
    last_stop_reason: str = ""


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
    force_first_tool: bool = False,
    api_timeout: float = 180.0,
) -> Tuple[anthropic.types.Message, ToolLoopStats]:
    """
    Esegue un loop messages.create -> apply tool_use -> append tool_result.
    Termina quando stop_reason != 'tool_use' o max_iterations.
    Ritorna (last_response, stats).
    """
    last_response: Optional[anthropic.types.Message] = None
    stats = ToolLoopStats()
    for iteration in range(max_iterations):
        stats.iterations = iteration + 1
        if deadline_ts is not None and time.time() > deadline_ts:
            raise TimeoutError(
                f"Wiki runner timeout dopo {iteration} iter "
                f"(modalita' {'RO' if read_only else 'RW'}, tool_calls={stats.total_tool_calls})"
            )

        # Forza tool_use al primo turno per evitare che il modello risponda solo testualmente.
        # Dal secondo turno in poi lascia decidere autonomamente (puo' chiudere con end_turn).
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
            "timeout": api_timeout,
        }
        if iteration == 0 and force_first_tool and not read_only:
            kwargs["tool_choice"] = {"type": "any"}

        t0 = time.time()
        resp = client.messages.create(**kwargs)
        latency = time.time() - t0
        last_response = resp
        stats.last_stop_reason = resp.stop_reason or ""

        # Conta i blocchi tool_use in questa risposta
        n_tool_use = sum(1 for b in resp.content if getattr(b, "type", None) == "tool_use")
        n_text = sum(1 for b in resp.content if getattr(b, "type", None) == "text")
        # Uso WARNING (non INFO) cosi' i log diagnostici escono sempre anche se il
        # root logger e' configurato a livello WARNING/ERROR.
        logger.warning(
            "wiki_runner iter=%d stop=%s text_blocks=%d tool_use=%d latency=%.1fs ro=%s",
            iteration, resp.stop_reason, n_text, n_tool_use, latency, read_only,
        )

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
                # Log + counter per categoria
                if tool_name == wiki_tools.TOOL_WRITE_FILE:
                    stats.write_calls += 1
                elif tool_name == wiki_tools.TOOL_APPEND_FILE:
                    stats.write_calls += 1
                elif tool_name == wiki_tools.TOOL_READ_FILE:
                    stats.read_calls += 1
                elif tool_name == wiki_tools.TOOL_LIST_DIR:
                    stats.list_calls += 1
                try:
                    parsed = json.loads(result_str)
                    logger.warning(
                        "wiki_runner tool=%s path=%s ok=%s err=%s",
                        tool_name,
                        tool_input.get("path", "?"),
                        parsed.get("ok"),
                        (parsed.get("error") or "")[:120],
                    )
                except Exception:  # noqa: BLE001
                    pass
                stats.total_tool_calls += 1
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
        if not tool_results:
            # Stop reason "tool_use" ma niente tool_use blocks: anomalia, esci.
            logger.warning("wiki_runner: stop_reason=tool_use ma 0 blocchi tool_use, esco")
            break
        messages.append({"role": "user", "content": tool_results})

    if last_response is None:
        raise RuntimeError("messages.create non ha mai risposto")
    return last_response, stats


def _chunked(seq: List, size: int) -> List[List]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


# ---------------------------------------------------------------------------
# INGEST
# ---------------------------------------------------------------------------

def run_ingest(
    thesis_id: str,
    on_progress: Optional[Callable[..., None]] = None,
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

        # Nome dei documenti del batch (per la UI di avanzamento).
        _names = [Path(p).name for p in rel_paths]
        _doc_word = "documento" if len(batch) == 1 else "documenti"
        # Progresso a INIZIO batch: cosa sta per essere elaborato.
        if on_progress:
            on_progress(
                int((idx - 1) / total_batches * 100),
                f"Analizzo {len(batch)} {_doc_word} (batch {idx}/{total_batches})",
                _names,
            )

        if idx == 1:
            user_msg = (
                f"{INGEST_TRIGGER}\n\n"
                f"In `raw/` ci sono {len(raw_files)} file da ingerire (in {total_batches} batch). "
                f"Batch corrente {idx}/{total_batches}:\n\n{files_block}\n\n"
                "**PROCEDURA OBBLIGATORIA** (esegui tutti gli step, non fermarti dopo aver letto):\n\n"
                "1. Per OGNI file del batch (uno alla volta):\n"
                "   a. `read_file(path)` per leggere la fonte raw\n"
                "   b. **SUBITO DOPO**: `write_file('wiki/fonti/<slug>.md', content)` con il "
                "contenuto completo della pagina fonte (frontmatter YAML + sezioni Riassunto, "
                "Punti chiave, Citazioni notevoli, Entità menzionate, Concetti introdotti, "
                "Connessioni — vedi sez. 7 di CLAUDE.md)\n"
                "   c. **Per ogni entità rilevante** che vuoi linkare con `[[X]]`: crea SUBITO "
                "`write_file('wiki/entita/<slug>.md', content)` con frontmatter (`tipo: entita, "
                "sottotipo: persona|organizzazione|prodotto|...`) + 3+ righe sostantive. "
                "Esempi: prodotti software (PyTorch, TensorFlow, AlexNet), autore primario, "
                "organizzazione editrice. Coautori e nomi di passaggio: NIENTE wikilink, testo semplice.\n"
                "   d. **Per ogni concetto sostantivo** che vuoi linkare con `[[X]]`: crea SUBITO "
                "`write_file('wiki/concetti/<slug>.md', content)`. Concetti di passaggio: NIENTE "
                "wikilink, testo semplice.\n"
                "2. Quando hai processato TUTTI i file del batch:\n"
                "   - `write_file('index.md', content)` aggiornando il catalogo content-oriented "
                "(deduplicato: ogni pagina compare una sola volta)\n"
                "   - `append_file('log.md', '\\n## [YYYY-MM-DD] ingest | batch X\\n- Creata: ...\\n')` "
                "con una entry per il batch\n"
                "3. Solo DOPO aver completato tutti i write, rispondi con un breve riepilogo "
                "testuale (1-3 righe) e attendi il batch successivo.\n\n"
                "**REGOLE FERREE SUI WIKILINKS** (sez. 5 CLAUDE.md):\n"
                "- Se scrivi `[[X]]`, la pagina `wiki/*/X.md` DEVE esistere o essere creata "
                "in questo stesso batch. Nessuna eccezione.\n"
                "- Se non vuoi creare la pagina (menzione di passaggio): usa testo semplice, "
                "niente parentesi quadre.\n"
                "- Per le fonti, usa lo SLUG della pagina fonte (es. "
                "`[[2019-pytorch-imperative-style-high-performance-dl]]`), NON il nome del file raw.\n\n"
                "**NON limitarti a leggere i file e fare un riepilogo: il tuo compito principale "
                "e' SCRIVERE le pagine wiki. Se non chiami `write_file`, non hai completato "
                "l'ingest.**"
            )
        else:
            user_msg = (
                f"Ottimo, prosegui con il batch {idx}/{total_batches}:\n\n{files_block}\n\n"
                "Stessa **PROCEDURA OBBLIGATORIA** del primo batch: per OGNI file → read_file + "
                "write_file della pagina fonte + write_file delle entita'/concetti rilevanti. "
                "Alla fine del batch, aggiorna index.md (deduplicato) e appendi una entry a log.md.\n"
                "**Ricorda: ogni `[[X]]` che scrivi deve avere il file `wiki/*/X.md` creato in "
                "questo stesso batch — niente wikilink rotti.**"
            )

        messages.append({"role": "user", "content": user_msg})

        batch_t0 = time.time()
        logger.warning(
            "wiki_runner BEGIN batch %d/%d tesi=%s files=%d",
            idx, total_batches, thesis_id, len(rel_paths),
        )
        try:
            _resp, batch_stats = _run_tool_loop(
                client=client,
                system=system,
                messages=messages,
                tools=wiki_tools.WIKI_FS_TOOLS_RW,
                wiki_root=wiki_root,
                model=model,
                max_tokens=config.WIKI_INGEST_MAX_TOKENS,
                read_only=False,
                deadline_ts=deadline_ts,
                force_first_tool=True,
            )
            summary.total_tool_calls += batch_stats.total_tool_calls

            # Follow-up: se il modello ha letto ma NON ha scritto nulla, rilancia
            # con un messaggio forzante. Massimo 2 retry per batch.
            retry = 0
            while batch_stats.write_calls == 0 and batch_stats.read_calls > 0 and retry < 2:
                retry += 1
                logger.warning(
                    "wiki_runner FOLLOWUP batch %d retry=%d (read=%d write=0)",
                    idx, retry, batch_stats.read_calls,
                )
                followup_msg = (
                    "Hai letto i file ma **non hai ancora chiamato `write_file` per le pagine wiki**. "
                    "L'ingest e' incompleto: il tuo riepilogo testuale deve essere salvato come pagina markdown sotto "
                    "`wiki/fonti/<slug>.md`, non solo nel testo della risposta.\n\n"
                    "**ORA chiama write_file** per ogni fonte appena letta. Frontmatter YAML "
                    "(tipo: fonte, titolo, autore, formato, raw_path, tag) + sezione `## Riassunto` "
                    "+ `## Punti chiave` + `## Entita' menzionate` + `## Concetti introdotti` "
                    "(vedi sez. 7 di CLAUDE.md). Inizia subito con il primo write_file."
                )
                messages.append({"role": "user", "content": followup_msg})
                _resp2, fu_stats = _run_tool_loop(
                    client=client,
                    system=system,
                    messages=messages,
                    tools=wiki_tools.WIKI_FS_TOOLS_RW,
                    wiki_root=wiki_root,
                    model=model,
                    max_tokens=config.WIKI_INGEST_MAX_TOKENS,
                    read_only=False,
                    deadline_ts=deadline_ts,
                    force_first_tool=True,  # forza tool_use anche nel follow-up
                )
                summary.total_tool_calls += fu_stats.total_tool_calls
                # Aggiorna le statistiche del batch con il follow-up
                batch_stats.write_calls += fu_stats.write_calls
                batch_stats.read_calls += fu_stats.read_calls
                batch_stats.list_calls += fu_stats.list_calls
                batch_stats.total_tool_calls += fu_stats.total_tool_calls

            logger.warning(
                "wiki_runner END batch %d/%d tesi=%s read=%d write=%d list=%d duration=%.1fs",
                idx, total_batches, thesis_id,
                batch_stats.read_calls, batch_stats.write_calls, batch_stats.list_calls,
                time.time() - batch_t0,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Errore ingest batch %s/%s tesi %s", idx, total_batches, thesis_id)
            summary.errors.append(f"batch {idx}: {e}")
            # Procedi: errori parziali non bloccano l'intero ingest

        if on_progress:
            on_progress(
                int(idx / total_batches * 100),
                f"Completato batch {idx}/{total_batches}",
                _names,
            )

    # ----- AUTO-FIX FASE: scan wikilink rotti e chiedi al modello di fixare -----
    pages_pre_autofix = wiki_workspace.count_wiki_pages(thesis_id)
    if pages_pre_autofix > pages_before and len(summary.errors) == 0:
        try:
            broken = _scan_broken_wikilinks(wiki_root)
            if broken:
                logger.warning(
                    "wiki_runner AUTOFIX tesi=%s broken_links=%d",
                    thesis_id, len(broken),
                )
                _autofix_broken_links(
                    client=client,
                    system=system,
                    messages=messages,
                    wiki_root=wiki_root,
                    model=model,
                    deadline_ts=deadline_ts,
                    broken_links=broken,
                    summary=summary,
                )
        except Exception:  # noqa: BLE001
            logger.exception("Auto-fix wikilinks fallito tesi %s (non critico)", thesis_id)

    summary.duration_sec = time.time() - started
    pages_after = wiki_workspace.count_wiki_pages(thesis_id)
    summary.pages_created = max(0, pages_after - pages_before)
    summary.log_entries_added = max(0, _count_log_entries(wiki_root) - log_lines_before)
    summary.raw_log_tail = _tail_log(wiki_root, max_chars=2000)
    logger.warning(
        "wiki_runner FINAL tesi=%s pages_created=%d log_entries=%d tool_calls=%d duration=%.1fs errors=%d",
        thesis_id, summary.pages_created, summary.log_entries_added,
        summary.total_tool_calls, summary.duration_sec, len(summary.errors),
    )
    return summary


# ---------------------------------------------------------------------------
# Auto-fix: scan wikilink rotti e fai un round di correzione
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:\|[^\]]+)?\]\]")


def _scan_broken_wikilinks(wiki_root: Path) -> List[Dict[str, Any]]:
    """
    Scansiona tutte le pagine sotto wiki/ ed estrae i wikilink rotti.

    Ritorna lista di dict {in_page: <relpath>, target: <slug>} per ogni
    wikilink che non punta a un file esistente in wiki/*/<slug>.md.
    """
    wiki_dir = wiki_root / "wiki"
    if not wiki_dir.exists():
        return []

    # Costruisci set degli slug esistenti (senza .md)
    existing_slugs = set()
    for sub in wiki_workspace.WIKI_SUBDIRS:
        d = wiki_dir / sub
        if d.exists():
            for p in d.iterdir():
                if p.is_file() and p.suffix == ".md":
                    existing_slugs.add(p.stem)

    # Scan ogni pagina e raccogli i wikilink
    broken: List[Dict[str, Any]] = []
    for sub in wiki_workspace.WIKI_SUBDIRS:
        d = wiki_dir / sub
        if not d.exists():
            continue
        for p in d.iterdir():
            if not (p.is_file() and p.suffix == ".md"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            in_page = str(p.relative_to(wiki_root))
            for match in _WIKILINK_RE.finditer(text):
                target = match.group(1).strip()
                if target and target not in existing_slugs:
                    broken.append({"in_page": in_page, "target": target})

    return broken


def _autofix_broken_links(
    *,
    client: anthropic.Anthropic,
    system: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    wiki_root: Path,
    model: str,
    deadline_ts: float,
    broken_links: List[Dict[str, Any]],
    summary: IngestSummary,
) -> None:
    """
    Invia un follow-up al modello con la lista dei wikilink rotti e gli chiede:
    per ognuno, o crea la pagina mancante (almeno frontmatter + 3 righe), oppure
    riscrive la pagina sorgente sostituendo `[[X]]` con testo semplice.
    """
    # Raggruppa per target per ridurre rumore
    by_target: Dict[str, List[str]] = {}
    for b in broken_links:
        by_target.setdefault(b["target"], []).append(b["in_page"])

    # Limita a max 30 link rotti per non far esplodere il prompt
    items = list(by_target.items())[:30]
    truncated = len(by_target) > 30

    listing = "\n".join(
        f"- `[[{tgt}]]` (citato in: {', '.join(sorted(set(pages))[:3])}"
        f"{', ...' if len(set(pages)) > 3 else ''})"
        for tgt, pages in items
    )
    if truncated:
        listing += f"\n- ...e altri {len(by_target) - 30} link rotti"

    user_msg = (
        "**Pass di auto-fix dei wikilink rotti** (sez. 7 di CLAUDE.md, step 8).\n\n"
        "Ho rilevato i seguenti wikilink che NON puntano a una pagina esistente nel wiki:\n\n"
        f"{listing}\n\n"
        "Per ognuno, decidi e applica:\n"
        "1. **Se l'elemento merita una pagina propria** (entita' rilevante o concetto sostantivo, "
        "vedi sez. 7 di CLAUDE.md): chiama `write_file('wiki/<categoria>/<slug>.md', content)` "
        "creando la pagina con frontmatter completo + almeno 3 righe sostantive. "
        "Categorie: `entita` per persone/organizzazioni/prodotti/dataset/architetture, "
        "`concetti` per idee/teorie/framework astratti.\n"
        "2. **Se l'elemento e' una menzione di passaggio**: chiama `read_file` sulla pagina che "
        "lo contiene, poi `write_file` riscrivendola con `[[X]]` sostituito da testo semplice "
        "(rimuovi le parentesi quadre).\n\n"
        "Procedi ora. Quando hai sistemato tutti i link, aggiorna anche `index.md` con le "
        "eventuali nuove pagine create e appendi a `log.md` una riga "
        "`- Auto-fix: N link rotti corretti`."
    )

    messages.append({"role": "user", "content": user_msg})

    try:
        _resp, fix_stats = _run_tool_loop(
            client=client,
            system=system,
            messages=messages,
            tools=wiki_tools.WIKI_FS_TOOLS_RW,
            wiki_root=wiki_root,
            model=model,
            max_tokens=config.WIKI_INGEST_MAX_TOKENS,
            read_only=False,
            deadline_ts=deadline_ts,
            force_first_tool=True,
        )
        summary.total_tool_calls += fix_stats.total_tool_calls
        logger.warning(
            "wiki_runner AUTOFIX done broken=%d tool_calls=%d",
            len(broken_links), fix_stats.total_tool_calls,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Auto-fix loop fallito")
        summary.errors.append(f"autofix: {e}")


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
    response, _stats = _run_tool_loop(
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
