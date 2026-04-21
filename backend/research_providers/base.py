"""
Modello base per paper accademici e interfaccia provider.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class UnifiedPaper(BaseModel):
    """
    Rappresentazione normalizzata di un paper, indipendente dal provider di origine.
    """
    id: str = Field(..., description="Identificatore stabile (DOI normalizzato o hash di titolo+autore)")
    title: str
    authors: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    full_text_url: Optional[str] = None
    open_access: bool = False
    sources: List[str] = Field(default_factory=list, description="Provider che hanno restituito il paper (openalex, semantic_scholar, crossref)")
    relevance_rank: Optional[int] = Field(None, description="Posizione 1-based nel risultato della prima fonte: usato per relevance score")
    relevance_raw: Optional[float] = Field(None, description="Score di rilevanza nativo del provider (se disponibile)")
    composite_score: Optional[float] = Field(None, description="Punteggio composito 0-1 calcolato dopo dedup")
    score_breakdown: Optional[Dict[str, float]] = Field(
        None,
        description="Componenti normalizzate 0-1 del composite_score: relevance, citations, recency, abstract, open_access, venue",
    )


class ProviderError(Exception):
    """Errore generico sollevato da un provider di ricerca accademica."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    """Il provider ha risposto 429 (rate limit superato)."""

    def __init__(self, provider: str):
        super().__init__(provider, "rate limit raggiunto (HTTP 429) — riprova piu' tardi o configura l'API key")


class BaseProvider:
    """
    Interfaccia che ogni provider deve implementare.
    """

    name: str = "base"

    async def search(self, query: str, limit: int = 30) -> List[UnifiedPaper]:
        raise NotImplementedError
