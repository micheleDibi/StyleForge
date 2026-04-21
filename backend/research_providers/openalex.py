"""
Provider OpenAlex — https://api.openalex.org/works
"""

import hashlib
import logging
from typing import List, Optional

import httpx

from .base import BaseProvider, ProviderError, RateLimitError, UnifiedPaper

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """
    OpenAlex ritorna l'abstract come inverted index {word: [positions]}.
    Ricostruisce il testo originale.
    """
    if not inverted_index:
        return None
    try:
        positions = []
        for word, idxs in inverted_index.items():
            for idx in idxs:
                positions.append((idx, word))
        positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in positions)
    except Exception:
        return None


def _stable_id(doi: Optional[str], title: str) -> str:
    if doi:
        return doi.lower().strip()
    return "oa_" + hashlib.sha1(title.lower().encode("utf-8", errors="ignore")).hexdigest()[:16]


class OpenAlexProvider(BaseProvider):
    name = "openalex"

    def __init__(self, contact_email: Optional[str] = None, timeout: float = 8.0):
        self.contact_email = contact_email
        self.timeout = timeout

    async def search(self, query: str, limit: int = 30) -> List[UnifiedPaper]:
        params = {
            "search": query,
            "per-page": min(limit, 50),
        }
        # "mailto" parameter entra nel pool educato di OpenAlex
        if self.contact_email:
            params["mailto"] = self.contact_email

        headers = {"User-Agent": "StyleForge/1.0"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(OPENALEX_API, params=params, headers=headers)
            if r.status_code == 429:
                raise RateLimitError(self.name)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ProviderError(self.name, f"HTTP {e.response.status_code}")
            data = r.json()

        papers: List[UnifiedPaper] = []
        for rank, work in enumerate(data.get("results", []), start=1):
            title = work.get("title") or work.get("display_name") or "(senza titolo)"
            doi_raw = work.get("doi")
            doi = doi_raw.replace("https://doi.org/", "").lower() if doi_raw else None

            authorships = work.get("authorships") or []
            authors = [a.get("author", {}).get("display_name") for a in authorships if a.get("author")]
            authors = [a for a in authors if a]

            host_venue = work.get("primary_location", {}).get("source", {}) if work.get("primary_location") else {}
            venue = host_venue.get("display_name") if isinstance(host_venue, dict) else None

            oa = work.get("open_access") or {}
            open_access = bool(oa.get("is_oa"))
            full_text_url = oa.get("oa_url") or (doi_raw if doi_raw else None)

            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

            papers.append(UnifiedPaper(
                id=_stable_id(doi, title),
                title=title,
                authors=authors[:20],
                abstract=abstract,
                doi=doi,
                year=work.get("publication_year"),
                venue=venue,
                citation_count=work.get("cited_by_count"),
                full_text_url=full_text_url,
                open_access=open_access,
                sources=[self.name],
                relevance_rank=rank,
                relevance_raw=work.get("relevance_score"),
            ))
        return papers
