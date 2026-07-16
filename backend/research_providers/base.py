"""
Modello base per paper accademici e interfaccia provider.
"""

import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


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

    @field_validator("full_text_url")
    @classmethod
    def _solo_url_http(cls, v: Optional[str]) -> Optional[str]:
        """
        Prima barriera su full_text_url.

        Serve perche' questo modello non viene costruito solo dai provider: in
        POST /thesis/{id}/attachments/papers arriva dal payload del CLIENT
        (UnifiedPaper(**item.paper)), finisce in ThesisAttachment.file_path e la
        pipeline wiki lo scarica. E' un URL controllato dall'utente a tutti gli
        effetti.

        Un valore non-http(s) si azzera invece di far fallire la validazione:
        cosi' un risultato strano di un provider perde il link al full text ma
        il paper resta, mentre uno schema tipo file:// sparisce. Il blocco vero
        (IP interni, rebinding) e' della guard, al salvataggio e al fetch.
        """
        if v is None:
            return None
        valore = str(v).strip()
        if not valore:
            return None
        if not (valore.startswith("http://") or valore.startswith("https://")):
            logger.warning("full_text_url ignorato, non e' un URL http(s): %.100r", valore)
            return None
        return valore


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
