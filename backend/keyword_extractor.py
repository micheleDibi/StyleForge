"""
Estrazione di termini di ricerca (keyword) dai documenti caricati dall'utente
in una tesi. Utilizzato dall'endpoint POST /api/thesis/{id}/suggest-paper-keywords
per aiutare l'utente a popolare la search bar dei paper accademici.

Strategia: prompt sintetico verso OpenAI (stesso client di research_summarizer)
che riceve i primi N estratti testuali e ritorna un JSON array di 5-8 keyword.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai_client import get_openai_client

logger = logging.getLogger(__name__)


MAX_ATTACHMENTS = 5
MAX_CHARS_PER_ATTACHMENT = 5000
TOTAL_CHAR_BUDGET = 25000


def _prepare_corpus(texts: List[str]) -> str:
    """Concatena fino a MAX_ATTACHMENTS testi, ciascuno limitato a MAX_CHARS_PER_ATTACHMENT."""
    truncated = []
    total = 0
    for idx, text in enumerate(texts[:MAX_ATTACHMENTS], start=1):
        if not text:
            continue
        cleaned = text.strip()
        if not cleaned:
            continue
        snippet = cleaned[:MAX_CHARS_PER_ATTACHMENT]
        budget_left = TOTAL_CHAR_BUDGET - total
        if budget_left <= 200:
            break
        snippet = snippet[:budget_left]
        truncated.append(f"--- Documento {idx} ---\n{snippet}")
        total += len(snippet)
    return "\n\n".join(truncated)


def _build_prompt(corpus: str, title: Optional[str], topics: Optional[List[str]]) -> str:
    title_hint = f"Titolo tesi: {title}\n" if title else ""
    topics_hint = ""
    if topics:
        topics_clean = [t.strip() for t in topics if t and t.strip()]
        if topics_clean:
            topics_hint = "Argomenti chiave gia' indicati: " + ", ".join(topics_clean) + "\n"

    return f"""Sei un assistente di ricerca accademica. Ti fornisco estratti dei documenti che un utente
sta usando per scrivere una tesi. Devi suggerire termini di ricerca utili per cercare
paper accademici correlati su database scientifici (OpenAlex, Semantic Scholar, Crossref).

{title_hint}{topics_hint}
REGOLE:
- Rispondi SOLO con un JSON valido, senza testo aggiuntivo prima o dopo.
- Lingua: usa la stessa dei documenti (italiano se documenti in italiano, inglese se in inglese).
- Le chiavi del JSON devono essere esattamente: keywords.
- keywords: array di 5-8 termini di ricerca. Ogni termine: 1-4 parole, specifico e mirato.
- Evita termini troppo generici ("intelligenza artificiale", "studio", "analisi"). Preferisci concetti
  tecnici, metodologie, autori chiave, framework specifici se presenti nei documenti.
- Evita duplicati semantici (es. "deep learning" e "apprendimento profondo": tieni uno solo).
- Se gli argomenti chiave dell'utente sono gia' presenti, NON ripeterli: cerca termini complementari
  o piu' specifici.

DOCUMENTI:
{corpus}

Rispondi ora con il JSON:"""


async def extract_paper_keywords_from_attachments(
    texts: List[str],
    *,
    title: Optional[str] = None,
    topics: Optional[List[str]] = None,
) -> List[str]:
    """
    Estrae 5-8 keyword di ricerca dai testi degli allegati.

    Args:
        texts: Lista di testi estratti dagli allegati (extracted_text).
        title: Titolo della tesi (hint opzionale per il modello).
        topics: Lista di argomenti chiave gia' indicati dall'utente
                (hint opzionale per evitare duplicati).

    Returns:
        Lista di stringhe (keyword), max 8 elementi, deduplicate (case-insensitive).
        In caso di errore del modello, ritorna lista vuota.
    """
    corpus = _prepare_corpus(texts)
    if not corpus:
        return []

    prompt = _build_prompt(corpus, title, topics)
    client = get_openai_client()

    def _call() -> Dict[str, Any]:
        return client.generate_json(prompt, max_tokens=800)

    try:
        data = await asyncio.to_thread(_call)
    except Exception:
        logger.exception("Estrazione keyword fallita")
        raise

    raw = data.get("keywords") or []
    if isinstance(raw, str):
        raw = [k.strip() for k in raw.split(",") if k.strip()]

    seen_lower: set[str] = set()
    keywords: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().strip('"').strip("'")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        keywords.append(cleaned)
        if len(keywords) >= 8:
            break

    return keywords
