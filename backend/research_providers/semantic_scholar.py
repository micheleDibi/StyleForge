"""
Provider Semantic Scholar — https://api.semanticscholar.org/graph/v1/paper/search
"""

import hashlib
import logging
import os
from typing import List, Optional

import httpx

from .base import BaseProvider, UnifiedPaper

logger = logging.getLogger(__name__)

S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,authors,abstract,year,venue,citationCount,openAccessPdf,externalIds,url"


def _stable_id(doi: Optional[str], paper_id: Optional[str], title: str) -> str:
    if doi:
        return doi.lower().strip()
    if paper_id:
        return f"s2_{paper_id}"
    return "s2_" + hashlib.sha1(title.lower().encode("utf-8", errors="ignore")).hexdigest()[:16]


class SemanticScholarProvider(BaseProvider):
    name = "semantic_scholar"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 8.0):
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
        self.timeout = timeout

    async def search(self, query: str, limit: int = 30) -> List[UnifiedPaper]:
        params = {
            "query": query,
            "limit": min(limit, 50),
            "fields": FIELDS,
        }
        headers = {"User-Agent": "StyleForge/1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(S2_API, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()

        papers: List[UnifiedPaper] = []
        for rank, work in enumerate(data.get("data", []), start=1):
            title = work.get("title") or "(senza titolo)"
            ext_ids = work.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            doi_norm = doi.lower().strip() if doi else None

            authors_raw = work.get("authors") or []
            authors = [a.get("name") for a in authors_raw if a.get("name")]

            oa_pdf = work.get("openAccessPdf") or {}
            full_text_url = oa_pdf.get("url") or work.get("url")
            open_access = bool(oa_pdf.get("url"))

            papers.append(UnifiedPaper(
                id=_stable_id(doi_norm, work.get("paperId"), title),
                title=title,
                authors=authors[:20],
                abstract=work.get("abstract"),
                doi=doi_norm,
                year=work.get("year"),
                venue=work.get("venue"),
                citation_count=work.get("citationCount"),
                full_text_url=full_text_url,
                open_access=open_access,
                sources=[self.name],
                relevance_rank=rank,
                relevance_raw=None,
            ))
        return papers
