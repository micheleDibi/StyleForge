"""
Router FastAPI per la ricerca accademica multi-provider (OpenAlex, Semantic Scholar, Crossref).
Include endpoint di ricerca sincrono e di riassunto on-demand via OpenAI.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import require_permission
from credits import deduct_credits, estimate_credits
from database import get_db
from db_models import User
from research_providers import UnifiedPaper
from research_service import DEFAULT_SOURCES, PROVIDER_REGISTRY, run_search_pipeline
from research_summarizer import SummaryResult, summarize_paper
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["Academic Research"])


# ============================================================================
# SCHEMI REQUEST / RESPONSE
# ============================================================================

class ResearchFilters(BaseModel):
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    open_access_only: bool = False
    min_citations: Optional[int] = Field(None, ge=0)
    venue_contains: Optional[str] = None
    author_contains: Optional[str] = None


class ResearchSearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=500)
    sources: Optional[List[str]] = Field(None, description="Sottoinsieme di openalex/semantic_scholar/crossref")
    filters: Optional[ResearchFilters] = None
    sort_by: str = Field("composite", pattern="^(composite|citations|recency|title)$")
    per_provider_limit: int = Field(30, ge=5, le=50)
    final_limit: int = Field(40, ge=1, le=100)


class ResearchSearchResponse(BaseModel):
    papers: List[UnifiedPaper]
    total_raw: int
    total_unique: int
    total_after_filters: int
    total_by_source: Dict[str, int]
    used_sources: List[str]
    failed_sources: List[Dict[str, Any]]


class PaperSummarizeRequest(BaseModel):
    paper: UnifiedPaper


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/sources", response_model=Dict[str, List[str]])
async def list_sources():
    """Lista i provider disponibili."""
    return {"sources": list(PROVIDER_REGISTRY.keys())}


@router.post("/search", response_model=ResearchSearchResponse)
async def research_search(
    request: ResearchSearchRequest,
    current_user: User = Depends(require_permission('research')),
    db: Session = Depends(get_db),
):
    """
    Cerca paper accademici per argomento aggregando piu' fonti.
    I risultati non vengono salvati su database.
    """
    sources = request.sources
    if sources:
        invalid = [s for s in sources if s not in PROVIDER_REGISTRY]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Fonti non valide: {', '.join(invalid)}",
            )
    else:
        sources = DEFAULT_SOURCES

    # Deduzione crediti
    credit_estimate = estimate_credits("research_search", {"num_sources": len(sources)}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate["credits_needed"],
        operation_type="research_search",
        description=f"Ricerca accademica: {request.topic[:80]}",
        db=db,
    )

    try:
        result = await run_search_pipeline(
            topic=request.topic.strip(),
            sources=sources,
            filters=request.filters.model_dump() if request.filters else None,
            sort_by=request.sort_by,
            per_provider_limit=request.per_provider_limit,
            final_limit=request.final_limit,
            contact_email=(config.CONTACT_EMAIL or None),
            semantic_scholar_api_key=(config.SEMANTIC_SCHOLAR_API_KEY or None),
        )
    except httpx.RequestError as e:
        logger.error("Errore di rete nella ricerca accademica: %s", e)
        raise HTTPException(status_code=502, detail="Errore di rete nel contattare i provider accademici")
    except Exception as e:
        logger.exception("Errore imprevisto nella ricerca accademica")
        raise HTTPException(status_code=500, detail=f"Errore nella ricerca: {str(e)[:200]}")

    return ResearchSearchResponse(**result)


@router.post("/summarize", response_model=SummaryResult)
async def research_summarize(
    request: PaperSummarizeRequest,
    current_user: User = Depends(require_permission('research')),
    db: Session = Depends(get_db),
):
    """
    Genera un riassunto AI per un singolo paper.
    Input: il paper restituito da /search.
    Output: riassunto breve, tecnico, keywords, limiti.
    """
    # Deduzione crediti
    credit_estimate = estimate_credits("research_summary", {}, db=db)
    deduct_credits(
        user=current_user,
        amount=credit_estimate["credits_needed"],
        operation_type="research_summary",
        description=f"Riassunto paper: {request.paper.title[:80]}",
        db=db,
    )

    try:
        summary = await summarize_paper(request.paper)
    except Exception as e:
        logger.exception("Errore riassunto paper")
        raise HTTPException(status_code=500, detail=f"Errore nel riassunto: {str(e)[:200]}")

    return summary
