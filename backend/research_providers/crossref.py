"""
Provider Crossref — https://api.crossref.org/works
"""

import hashlib
import logging
import re
from typing import List, Optional

import httpx

from .base import BaseProvider, UnifiedPaper

logger = logging.getLogger(__name__)

CROSSREF_API = "https://api.crossref.org/works"


def _stable_id(doi: Optional[str], title: str) -> str:
    if doi:
        return doi.lower().strip()
    return "cr_" + hashlib.sha1(title.lower().encode("utf-8", errors="ignore")).hexdigest()[:16]


def _clean_abstract(raw: Optional[str]) -> Optional[str]:
    """Crossref restituisce abstract in JATS XML. Togliamo i tag."""
    if not raw:
        return None
    # Rimuove tag XML/HTML
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    # Compatta whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


class CrossrefProvider(BaseProvider):
    name = "crossref"

    def __init__(self, contact_email: Optional[str] = None, timeout: float = 8.0):
        self.contact_email = contact_email
        self.timeout = timeout

    async def search(self, query: str, limit: int = 30) -> List[UnifiedPaper]:
        params = {
            "query": query,
            "rows": min(limit, 50),
            "select": "DOI,title,author,container-title,issued,abstract,is-referenced-by-count,URL,license,link",
        }
        # Crossref "polite pool": User-Agent con email di contatto
        ua = "StyleForge/1.0"
        if self.contact_email:
            ua = f"StyleForge/1.0 (mailto:{self.contact_email})"
        headers = {"User-Agent": ua}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(CROSSREF_API, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()

        items = (data.get("message") or {}).get("items") or []
        papers: List[UnifiedPaper] = []

        for rank, work in enumerate(items, start=1):
            title_list = work.get("title") or []
            title = title_list[0] if title_list else "(senza titolo)"

            doi = (work.get("DOI") or "").lower() or None

            authors_raw = work.get("author") or []
            authors = []
            for a in authors_raw:
                name = " ".join(p for p in [a.get("given"), a.get("family")] if p)
                if name:
                    authors.append(name)

            container = work.get("container-title") or []
            venue = container[0] if container else None

            year: Optional[int] = None
            issued = (work.get("issued") or {}).get("date-parts")
            if issued and issued[0]:
                try:
                    year = int(issued[0][0])
                except (ValueError, TypeError, IndexError):
                    year = None

            # Open access: inferito dalla licenza (approssimativo)
            license_info = work.get("license") or []
            open_access = any(
                "creativecommons" in (lic.get("URL") or "").lower() for lic in license_info
            )

            full_text_url = None
            links = work.get("link") or []
            if links:
                full_text_url = links[0].get("URL")
            if not full_text_url:
                full_text_url = work.get("URL")

            papers.append(UnifiedPaper(
                id=_stable_id(doi, title),
                title=title,
                authors=authors[:20],
                abstract=_clean_abstract(work.get("abstract")),
                doi=doi,
                year=year,
                venue=venue,
                citation_count=work.get("is-referenced-by-count"),
                full_text_url=full_text_url,
                open_access=open_access,
                sources=[self.name],
                relevance_rank=rank,
                relevance_raw=None,
            ))
        return papers
