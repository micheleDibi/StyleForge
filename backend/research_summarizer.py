"""
Generazione di riassunti per paper accademici tramite OpenAI (modello di reasoning).
Input: metadati del paper (titolo, autori, venue, abstract quando disponibile).
Output: riassunto breve, riassunto tecnico, parole chiave, limiti dello studio.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from openai_client import get_openai_client
from research_providers import UnifiedPaper

logger = logging.getLogger(__name__)


class SummaryResult(BaseModel):
    summary_short: str
    summary_technical: str
    keywords: List[str] = Field(default_factory=list)
    limits: List[str] = Field(default_factory=list)
    limited_input: bool = Field(
        False,
        description="True se l'abstract era assente e il riassunto si basa solo su metadati",
    )


def paper_to_attachment_text(paper: UnifiedPaper) -> str:
    """
    Rendering testuale di un paper come fonte di contesto.
    Usato sia dal prompt del summarizer sia dal flusso tesi (extracted_text).
    """
    has_abstract = bool(paper.abstract and paper.abstract.strip())
    authors_str = ", ".join(paper.authors[:8]) if paper.authors else "(autori non riportati)"
    venue_str = paper.venue or "(rivista/venue non riportata)"
    year_str = str(paper.year) if paper.year else "(anno non riportato)"
    citations_str = str(paper.citation_count) if paper.citation_count is not None else "n/d"

    abstract_block = (
        f"ABSTRACT ORIGINALE:\n{paper.abstract.strip()}"
        if has_abstract
        else "ABSTRACT: non disponibile."
    )

    return (
        "METADATI DEL PAPER:\n"
        f"- Titolo: {paper.title}\n"
        f"- Autori: {authors_str}\n"
        f"- Anno: {year_str}\n"
        f"- Venue: {venue_str}\n"
        f"- Citazioni: {citations_str}\n"
        f"- DOI: {paper.doi or 'n/d'}\n"
        f"\n{abstract_block}"
    )


def _build_prompt(paper: UnifiedPaper) -> str:
    has_abstract = bool(paper.abstract and paper.abstract.strip())
    paper_block = paper_to_attachment_text(paper)
    if not has_abstract:
        paper_block = paper_block.replace(
            "ABSTRACT: non disponibile.",
            "ABSTRACT: non disponibile. Basati SOLO sui metadati; se non puoi inferire con ragionevole certezza, scrivi esplicitamente che l'informazione non è deducibile dai metadati.",
        )

    return f"""Sei un assistente scientifico. Ti fornisco i metadati di un paper accademico.
Genera un riassunto strutturato in italiano.

REGOLE:
- Rispondi SOLO con un JSON valido, senza testo aggiuntivo prima o dopo.
- Lingua: italiano.
- Non inventare risultati specifici non presenti nell'abstract. Se una sezione non è deducibile, scrivi che l'informazione non è disponibile.
- Le chiavi del JSON devono essere esattamente: summary_short, summary_technical, keywords, limits.
- summary_short: 2-3 frasi, linguaggio divulgativo.
- summary_technical: 4-7 frasi, linguaggio tecnico, includendo metodo/dati/risultati se deducibili.
- keywords: array di 4-8 parole chiave brevi (1-3 parole ciascuna), rilevanti per l'argomento.
- limits: array di 1-4 stringhe con limiti plausibili dello studio (ambito, metodologia, generalizzabilità). Se non deducibili, lascia un array con una sola stringa "Non deducibili dai metadati disponibili".

{paper_block}

Rispondi ora con il JSON:"""


def render_paper_with_summary(paper: UnifiedPaper, summary: Optional["SummaryResult"]) -> str:
    """
    Combina il rendering testuale del paper con il riassunto AI (se presente)
    per formare l'extracted_text di un ThesisAttachment di tipo paper.
    """
    base = paper_to_attachment_text(paper)
    if not summary:
        return base

    keywords = ", ".join(summary.keywords) if summary.keywords else ""
    limits_block = ""
    if summary.limits:
        limits_block = "\nLIMITI:\n" + "\n".join(f"- {l}" for l in summary.limits)

    summary_block = (
        "\n\n=== RIASSUNTO AI ===\n"
        f"Sintesi divulgativa: {summary.summary_short}\n\n"
        f"Sintesi tecnica: {summary.summary_technical}"
    )
    if keywords:
        summary_block += f"\n\nKeywords: {keywords}"
    summary_block += limits_block
    return base + summary_block


async def summarize_paper(paper: UnifiedPaper) -> SummaryResult:
    """
    Genera un riassunto per il paper dato. La chiamata al client OpenAI è sincrona
    internamente: la portiamo su un thread-pool per non bloccare l'event loop.
    """
    prompt = _build_prompt(paper)
    client = get_openai_client()

    def _call() -> Dict[str, Any]:
        return client.generate_json(prompt, max_tokens=2000)

    try:
        data = await asyncio.to_thread(_call)
    except Exception as e:
        logger.exception("Riassunto fallito")
        raise

    keywords = data.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    limits = data.get("limits") or []
    if isinstance(limits, str):
        limits = [limits]

    return SummaryResult(
        summary_short=str(data.get("summary_short") or "").strip(),
        summary_technical=str(data.get("summary_technical") or "").strip(),
        keywords=[str(k).strip() for k in keywords if str(k).strip()][:12],
        limits=[str(l).strip() for l in limits if str(l).strip()][:6],
        limited_input=not bool(paper.abstract and paper.abstract.strip()),
    )
