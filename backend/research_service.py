"""
Servizio di ricerca accademica: orchestrazione multi-provider, dedup, ranking, filtri.
"""

import asyncio
import logging
import math
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from research_providers import (
    BaseProvider,
    CrossrefProvider,
    OpenAlexProvider,
    ProviderError,
    RateLimitError,
    SemanticScholarProvider,
    UnifiedPaper,
)

logger = logging.getLogger(__name__)


PROVIDER_REGISTRY = {
    "openalex": OpenAlexProvider,
    "semantic_scholar": SemanticScholarProvider,
    "crossref": CrossrefProvider,
}

DEFAULT_SOURCES = ["openalex", "semantic_scholar", "crossref"]


# ============================================================================
# NORMALIZZAZIONE E DEDUPLICAZIONE
# ============================================================================

_WORD_RE = re.compile(r"[^a-z0-9]+")


def _doi_key(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    d = doi.lower().strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d or None


def _title_key(title: str, authors: List[str], year: Optional[int]) -> str:
    t = _WORD_RE.sub("", title.lower())[:120]
    first_surname = ""
    if authors:
        parts = authors[0].split()
        if parts:
            first_surname = parts[-1].lower()
    return f"{t}|{first_surname}|{year or ''}"


def _merge_into(base: UnifiedPaper, new: UnifiedPaper) -> UnifiedPaper:
    """Fonde `new` dentro `base` preferendo i valori più informativi."""
    for src in new.sources:
        if src not in base.sources:
            base.sources.append(src)

    if not base.abstract and new.abstract:
        base.abstract = new.abstract
    if not base.doi and new.doi:
        base.doi = new.doi
    if not base.year and new.year:
        base.year = new.year
    if not base.venue and new.venue:
        base.venue = new.venue
    if not base.full_text_url and new.full_text_url:
        base.full_text_url = new.full_text_url
    if new.open_access and not base.open_access:
        base.open_access = True
    # Prendi il valore più alto di citazioni (i provider possono divergere)
    if (new.citation_count or 0) > (base.citation_count or 0):
        base.citation_count = new.citation_count
    # Unisci autori unici (preservando ordine di base)
    if len(new.authors) > len(base.authors):
        base.authors = new.authors
    # Tieni il miglior rank (più basso = migliore)
    if new.relevance_rank and (not base.relevance_rank or new.relevance_rank < base.relevance_rank):
        base.relevance_rank = new.relevance_rank
    if new.relevance_raw and (not base.relevance_raw or new.relevance_raw > base.relevance_raw):
        base.relevance_raw = new.relevance_raw
    return base


def deduplicate(papers: List[UnifiedPaper]) -> List[UnifiedPaper]:
    seen: Dict[str, UnifiedPaper] = {}
    for p in papers:
        key = _doi_key(p.doi) or _title_key(p.title, p.authors, p.year)
        if key in seen:
            _merge_into(seen[key], p)
        else:
            seen[key] = p
    return list(seen.values())


# ============================================================================
# PUNTEGGIO COMPOSITO
# ============================================================================

def _recency_decay(year: Optional[int]) -> float:
    if not year:
        return 0.0
    current_year = datetime.now().year
    delta = max(0, current_year - year)
    return math.exp(-delta / 8.0)


def _relevance_norm(rank: Optional[int], total: int) -> float:
    if not rank or total <= 0:
        return 0.0
    # rank=1 -> 1.0 ; rank=total -> ~0.0
    return max(0.0, 1.0 - (rank - 1) / max(total, 1))


def _citation_norm(citations: Optional[int], max_in_set: int) -> float:
    if not citations or citations <= 0 or max_in_set <= 0:
        return 0.0
    return math.log10(1 + citations) / math.log10(1 + max_in_set)


def _venue_quality_norm(paper: UnifiedPaper, venue_citation_max: Dict[str, int], overall_max: int) -> float:
    if not paper.venue or overall_max <= 0:
        return 0.0
    v_max = venue_citation_max.get(paper.venue.lower(), 0)
    if v_max <= 0:
        return 0.0
    return math.log10(1 + v_max) / math.log10(1 + overall_max)


SCORE_WEIGHTS = {
    "relevance": 0.35,
    "citations": 0.25,
    "recency": 0.15,
    "abstract": 0.10,
    "open_access": 0.05,
    "venue": 0.10,
}


def compute_composite_scores(papers: List[UnifiedPaper]) -> List[UnifiedPaper]:
    if not papers:
        return papers

    total = len(papers)
    max_citations = max((p.citation_count or 0 for p in papers), default=0)

    venue_citation_max: Dict[str, int] = {}
    for p in papers:
        if p.venue:
            key = p.venue.lower()
            venue_citation_max[key] = max(venue_citation_max.get(key, 0), p.citation_count or 0)
    overall_venue_max = max(venue_citation_max.values()) if venue_citation_max else 0

    for p in papers:
        components = {
            "relevance": _relevance_norm(p.relevance_rank, total),
            "citations": _citation_norm(p.citation_count, max_citations),
            "recency": _recency_decay(p.year),
            "abstract": 1.0 if p.abstract else 0.0,
            "open_access": 1.0 if p.open_access else 0.0,
            "venue": _venue_quality_norm(p, venue_citation_max, overall_venue_max),
        }
        p.score_breakdown = {k: round(v, 4) for k, v in components.items()}
        p.composite_score = round(
            sum(SCORE_WEIGHTS[k] * v for k, v in components.items()), 4
        )
    return papers


# ============================================================================
# FILTRI
# ============================================================================

def apply_filters(papers: List[UnifiedPaper], filters: Optional[dict]) -> List[UnifiedPaper]:
    if not filters:
        return papers

    year_min = filters.get("year_min")
    year_max = filters.get("year_max")
    open_access_only = filters.get("open_access_only", False)
    min_citations = filters.get("min_citations")
    venue_contains = (filters.get("venue_contains") or "").strip().lower()
    author_contains = (filters.get("author_contains") or "").strip().lower()

    out: List[UnifiedPaper] = []
    for p in papers:
        if year_min and (not p.year or p.year < year_min):
            continue
        if year_max and (not p.year or p.year > year_max):
            continue
        if open_access_only and not p.open_access:
            continue
        if min_citations is not None and (p.citation_count or 0) < min_citations:
            continue
        if venue_contains and (not p.venue or venue_contains not in p.venue.lower()):
            continue
        if author_contains:
            if not any(author_contains in a.lower() for a in p.authors):
                continue
        out.append(p)
    return out


def sort_papers(papers: List[UnifiedPaper], sort_by: str) -> List[UnifiedPaper]:
    if sort_by == "citations":
        return sorted(papers, key=lambda p: (p.citation_count or 0), reverse=True)
    if sort_by == "recency":
        return sorted(papers, key=lambda p: (p.year or 0), reverse=True)
    if sort_by == "title":
        return sorted(papers, key=lambda p: p.title.lower())
    # default: composite
    return sorted(papers, key=lambda p: (p.composite_score or 0.0), reverse=True)


# ============================================================================
# ORCHESTRAZIONE
# ============================================================================

async def search_all(
    topic: str,
    sources: Optional[List[str]] = None,
    per_provider_limit: int = 30,
    contact_email: Optional[str] = None,
    semantic_scholar_api_key: Optional[str] = None,
) -> Tuple[List[UnifiedPaper], List[str], List[dict]]:
    """
    Ritorna (papers_uniti_non_dedup, used_sources, failed_sources).
    Ogni paper mantiene il proprio source; la dedup avviene dopo.
    """
    sources = sources or DEFAULT_SOURCES
    providers: List[BaseProvider] = []
    for s in sources:
        klass = PROVIDER_REGISTRY.get(s)
        if not klass:
            logger.warning(f"Provider sconosciuto ignorato: {s}")
            continue
        if klass is OpenAlexProvider:
            providers.append(OpenAlexProvider(contact_email=contact_email))
        elif klass is SemanticScholarProvider:
            providers.append(SemanticScholarProvider(api_key=semantic_scholar_api_key))
        elif klass is CrossrefProvider:
            providers.append(CrossrefProvider(contact_email=contact_email))

    if not providers:
        return [], [], [{"source": "unknown", "error": "Nessun provider valido"}]

    tasks = [p.search(topic, limit=per_provider_limit) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers: List[UnifiedPaper] = []
    used: List[str] = []
    failed: List[dict] = []

    for provider, res in zip(providers, results):
        if isinstance(res, RateLimitError):
            logger.info("Provider %s rate-limited (HTTP 429) — saltato", provider.name)
            failed.append({
                "source": provider.name,
                "error": "rate_limit",
                "message": "Rate limit raggiunto. Riprova tra qualche minuto o configura un'API key.",
            })
            continue
        if isinstance(res, ProviderError):
            logger.warning("Provider %s errore: %s", provider.name, res.message)
            failed.append({"source": provider.name, "error": "provider_error", "message": res.message})
            continue
        if isinstance(res, Exception):
            logger.warning("Provider %s fallito: %s", provider.name, str(res)[:200])
            failed.append({"source": provider.name, "error": "unknown", "message": str(res)[:200]})
            continue
        all_papers.extend(res)
        used.append(provider.name)

    return all_papers, used, failed


async def run_search_pipeline(
    topic: str,
    sources: Optional[List[str]] = None,
    filters: Optional[dict] = None,
    sort_by: str = "composite",
    per_provider_limit: int = 30,
    final_limit: int = 40,
    contact_email: Optional[str] = None,
    semantic_scholar_api_key: Optional[str] = None,
) -> dict:
    """
    Esegue l'intera pipeline: fetch → dedup → score → filtri → sort → cap.
    Ritorna un dict pronto per la response.
    """
    raw_papers, used, failed = await search_all(
        topic,
        sources=sources,
        per_provider_limit=per_provider_limit,
        contact_email=contact_email,
        semantic_scholar_api_key=semantic_scholar_api_key,
    )

    total_by_source: Dict[str, int] = {}
    for p in raw_papers:
        for s in p.sources:
            total_by_source[s] = total_by_source.get(s, 0) + 1

    deduped = deduplicate(raw_papers)
    scored = compute_composite_scores(deduped)
    filtered = apply_filters(scored, filters)
    sorted_papers = sort_papers(filtered, sort_by)
    limited = sorted_papers[:max(1, min(final_limit, 100))]

    return {
        "papers": [p.model_dump() for p in limited],
        "total_raw": len(raw_papers),
        "total_unique": len(deduped),
        "total_after_filters": len(filtered),
        "total_by_source": total_by_source,
        "used_sources": used,
        "failed_sources": failed,
    }
