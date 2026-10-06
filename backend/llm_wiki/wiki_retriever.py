"""
Costruisce il "context" che il prompt builder della tesi (chapters/sections/
content) deve passare al modello: legge il wiki materializzato e produce una
stringa formattata.

Algoritmo a 3 layer (priorita' decrescente, fino a saturazione max_chars):
  1. Sempre incluso (~5K char): index.md + frontmatter+H1+riassunto di tutti
     i wiki/temi/*.md. E' la TOC che il modello vede sempre.
  2. Selezionato per query (~25K char): TF-IDF leggero su query (titolo tesi
     + key_topics + descrizione + chapter/section corrente) contro
     wiki/sintesi/* (peso 3x), wiki/temi/* (2x), wiki/concetti/* (1.5x),
     wiki/entita/* (1x). Top-N integrali.
  3. Fonti citate (~20K char): dai layer 2 estrai i wikilink → carica le
     wiki/fonti/*.md referenziate (solo Riassunto + Punti chiave + Citazioni
     notevoli). Limita a 15 fonti.

Ritorna anche `coverage_score` per warning UI quando restrict_to_sources=ON.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from llm_wiki import wiki_workspace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    context: str                 # stringa formattata pronta per i prompt
    char_count: int              # caratteri totali
    coverage_score: float        # char_count / target (0..1+)
    pages_included: int          # numero pagine dal layer 2/3 incluse
    sources_cited: int           # fonti incluse nel layer 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.lower()


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da",
    "in", "con", "su", "per", "tra", "fra", "del", "dello", "della", "dei",
    "degli", "delle", "al", "allo", "alla", "ai", "agli", "alle", "che", "e",
    "o", "ma", "se", "non", "si", "ho", "ha", "hai", "abbiamo", "avete",
    "hanno", "essere", "sono", "siamo", "siete", "stato", "stata", "sue",
    "suo", "sua", "anche", "come", "piu", "meno", "molto", "ogni", "questo",
    "questa", "questi", "queste", "quello", "quella", "quelli", "quelle",
}


def _tokenize(text: str) -> List[str]:
    return [w for w in _WORD_RE.findall(_normalize(text)) if len(w) >= 3 and w not in _STOPWORDS_IT]


def _read_markdown(path: Path) -> Tuple[str, str]:
    """Ritorna (frontmatter_str, body)."""
    if not path.exists():
        return "", ""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER_RE.match(text)
    if m:
        return m.group(1), text[m.end():]
    return "", text


def _extract_h1(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _extract_section(body: str, header: str, max_chars: int = 1500) -> str:
    """Estrae la sezione tra `## header` e il successivo `## ...`."""
    pattern = re.compile(rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(body)
    if not m:
        return ""
    section = m.group(1).strip()
    return section[:max_chars]


def _extract_riassunto_compatto(body: str) -> str:
    """Per i temi: H1 + sezione 'Riassunto' (o le prime 600 char)."""
    h1 = _extract_h1(body)
    summary = _extract_section(body, "Riassunto", max_chars=600)
    if not summary:
        summary = body[:600]
    return f"### {h1}\n{summary}".strip() if h1 else summary


# ---------------------------------------------------------------------------
# TF-IDF leggero
# ---------------------------------------------------------------------------

def _build_corpus(pages: List[Tuple[Path, str, float]]) -> Tuple[Dict[str, float], List[Set[str]]]:
    """
    Calcola IDF su un mini-corpus (le pagine candidate) e ritorna i token-set
    per pagina. Pages: List[(path, body, weight)].
    """
    docs: List[Set[str]] = []
    df: Dict[str, int] = {}
    for _, body, _ in pages:
        tokens = set(_tokenize(body))
        docs.append(tokens)
        for t in tokens:
            df[t] = df.get(t, 0) + 1
    n = max(1, len(pages))
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    return idf, docs


def _score_page(query_tokens: Set[str], page_tokens: Set[str],
                idf: Dict[str, float], page_weight: float) -> float:
    if not query_tokens or not page_tokens:
        return 0.0
    score = sum(idf.get(t, 0.0) for t in (query_tokens & page_tokens))
    return score * page_weight


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def build_context(
    thesis_id: str,
    query: str,
    *,
    max_chars: int = 50000,
    restrict_to_sources: bool = True,
) -> RetrievalResult:
    """
    Costruisce la stringa di context da iniettare nei prompt (chapters,
    sections, content). Vedi docstring del modulo per l'algoritmo.
    """
    wiki_root = wiki_workspace.get_wiki_root(thesis_id)
    wiki_dir = wiki_root / "wiki"

    if not wiki_root.exists() or not wiki_dir.exists():
        return RetrievalResult(
            context="=== KNOWLEDGE BASE (LLM WIKI): vuota ===\n",
            char_count=0,
            coverage_score=0.0,
            pages_included=0,
            sources_cited=0,
        )

    target_l1 = int(max_chars * 0.10)   # ~5K
    target_l2 = int(max_chars * 0.50)   # ~25K
    target_l3 = int(max_chars * 0.40)   # ~20K

    out_parts: List[str] = []
    pages_included = 0
    sources_cited = 0

    # ---------- LAYER 1: index + temi compatti ----------
    out_parts.append("=== KNOWLEDGE BASE (LLM WIKI) ===")
    if restrict_to_sources:
        out_parts.append("[restrict] Solo le informazioni in questo blocco sono autorevoli.\n")
    else:
        out_parts.append("")

    # index.md
    index_path = wiki_root / "index.md"
    if index_path.exists():
        index_text = index_path.read_text(encoding="utf-8", errors="replace")
        # Rimuovi commenti HTML di esempio
        index_text = re.sub(r"<!--.*?-->", "", index_text, flags=re.DOTALL).strip()
        out_parts.append("## Indice")
        out_parts.append(index_text[:target_l1])

    # temi compatti
    temi_dir = wiki_dir / "temi"
    temi_compact: List[str] = []
    if temi_dir.exists():
        for tema_path in sorted(temi_dir.iterdir()):
            if tema_path.suffix != ".md":
                continue
            _, body = _read_markdown(tema_path)
            riass = _extract_riassunto_compatto(body)
            if riass:
                temi_compact.append(riass)
        if temi_compact:
            out_parts.append("\n## Temi")
            out_parts.append("\n\n".join(temi_compact)[:target_l1 * 2])

    # ---------- LAYER 2: ranking per query ----------
    candidates: List[Tuple[Path, str, float]] = []  # (path, body, weight)
    weights = {"sintesi": 3.0, "temi": 2.0, "concetti": 1.5, "entita": 1.0}
    for cat, weight in weights.items():
        d = wiki_dir / cat
        if not d.exists():
            continue
        for p in d.iterdir():
            if p.suffix != ".md":
                continue
            _, body = _read_markdown(p)
            if body.strip():
                candidates.append((p, body, weight))

    selected_pages: List[Tuple[Path, str]] = []
    cited_wikilinks: Set[str] = set()
    if candidates:
        idf, docs_tokens = _build_corpus(candidates)
        query_tokens = set(_tokenize(query))
        ranked: List[Tuple[float, int]] = []
        for i, (_, _, w) in enumerate(candidates):
            score = _score_page(query_tokens, docs_tokens[i], idf, w)
            if score > 0:
                ranked.append((score, i))
        ranked.sort(key=lambda x: x[0], reverse=True)

        budget = target_l2
        out_parts.append("\n## Sintesi e concetti rilevanti")
        for _, i in ranked:
            path, body, _ = candidates[i]
            cat = path.parent.name
            if budget <= 0:
                break
            chunk = body[:budget].strip()
            if not chunk:
                continue
            header = f"\n### [{cat}] {path.stem}"
            out_parts.append(header)
            out_parts.append(chunk)
            budget -= len(chunk) + len(header) + 1
            pages_included += 1
            selected_pages.append((path, chunk))
            for m in _WIKILINK_RE.finditer(chunk):
                cited_wikilinks.add(m.group(1).strip())

    # ---------- LAYER 3: fonti citate dai layer 2 ----------
    fonti_dir = wiki_dir / "fonti"
    if fonti_dir.exists() and cited_wikilinks:
        # Map slug -> path
        fonti_index = {p.stem: p for p in fonti_dir.iterdir() if p.suffix == ".md"}
        budget = target_l3
        printed_header = False
        for slug in sorted(cited_wikilinks):
            if sources_cited >= 15 or budget <= 0:
                break
            fp = fonti_index.get(slug)
            if not fp:
                continue
            _, body = _read_markdown(fp)
            riassunto = _extract_section(body, "Riassunto", max_chars=800)
            punti = _extract_section(body, "Punti chiave", max_chars=800)
            citazioni = _extract_section(body, "Citazioni notevoli", max_chars=600)
            block_parts = []
            if riassunto:
                block_parts.append(f"**Riassunto:** {riassunto}")
            if punti:
                block_parts.append(f"**Punti chiave:**\n{punti}")
            if citazioni:
                block_parts.append(f"**Citazioni:**\n{citazioni}")
            if not block_parts:
                continue
            if not printed_header:
                out_parts.append("\n## Fonti citate")
                printed_header = True
            block = f"\n### [[{slug}]]\n" + "\n\n".join(block_parts)
            if len(block) > budget:
                block = block[:budget] + "\n[...troncato...]"
            out_parts.append(block)
            budget -= len(block)
            sources_cited += 1

    out_parts.append("\n=== FINE KNOWLEDGE BASE ===\n")

    full = "\n".join(out_parts)
    if len(full) > max_chars:
        full = full[:max_chars] + "\n=== FINE KNOWLEDGE BASE (troncato) ==="
    coverage = round(len(full) / max(1, max_chars), 3)

    return RetrievalResult(
        context=full,
        char_count=len(full),
        coverage_score=coverage,
        pages_included=pages_included,
        sources_cited=sources_cited,
    )
