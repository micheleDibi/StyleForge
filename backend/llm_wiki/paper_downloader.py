"""
Download dei paper scientifici nella cartella raw/paper/ del wiki di una tesi.

Per ogni ThesisAttachment di tipo paper:
  1. Se ha full_text_url o DOI risolvibile -> tenta download PDF via httpx
       - Se risposta application/pdf entro WIKI_PAPER_MAX_BYTES: salva in
         raw/assets/{slug}.pdf, estrae testo e salva markdown in raw/paper/
  2. Se download fallisce -> fallback abstract+metadata in raw/paper/{slug}.md
     con annotazione "> Nota: PDF non disponibile, materiale da abstract+metadata".

Il file markdown risultante ha frontmatter compatibile con CLAUDE.md sez. 4
(tipo: fonte, ecc.) cosi' l'ingest lo riconosce come fonte paper.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx

import config
import ssrf_guard
from db_models import ThesisAttachment
from llm_wiki.wiki_workspace import (
    PAPER_MIME_TYPE,
    bootstrap,
    get_wiki_root,
    make_raw_filename,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PaperMaterializationResult:
    attachment_id: str
    title: str
    raw_path: str            # path relativo a wiki_root (es. "raw/paper/2024_x.md")
    pdf_downloaded: bool
    fallback_used: bool      # True se abstract-only
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_paper_metadata(att: ThesisAttachment) -> dict:
    """
    L'extracted_text dei paper e' costruito da `paper_to_attachment_text`
    (research_summarizer.py). Ne ricaviamo il blocco metadati come dict.
    """
    meta = {
        "title": att.original_filename or "Paper accademico",
        "authors": [],
        "year": None,
        "venue": None,
        "doi": None,
        "abstract": "",
    }
    text = att.extracted_text or ""
    # Parsing best-effort delle linee "- Titolo: ..." dal blocco METADATI
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, _, val = line[2:].partition(":")
        key = key.strip().lower()
        val = val.strip()
        if not val or val == "n/d":
            continue
        if key == "titolo":
            meta["title"] = val
        elif key == "autori":
            meta["authors"] = [a.strip() for a in val.split(",") if a.strip()]
        elif key == "anno":
            try:
                meta["year"] = int(val.split()[0])
            except (ValueError, IndexError):
                pass
        elif key == "venue":
            meta["venue"] = val
        elif key == "doi":
            meta["doi"] = val
    # ABSTRACT
    if "ABSTRACT ORIGINALE:" in text:
        meta["abstract"] = text.split("ABSTRACT ORIGINALE:", 1)[1].strip()
    return meta


def _resolve_url(att: ThesisAttachment, meta: dict) -> Optional[str]:
    """Determina l'URL effettivo da cui tentare il download del PDF."""
    fp = att.file_path or ""
    if fp.startswith("http://") or fp.startswith("https://"):
        return fp
    if fp.startswith("doi:") and meta.get("doi"):
        return f"https://doi.org/{meta['doi']}"
    if meta.get("doi"):
        return f"https://doi.org/{meta['doi']}"
    return None


def _slug_for_paper(meta: dict) -> str:
    """Slug del file markdown: anno_titolo (max 80 char)."""
    from llm_wiki.wiki_workspace import _slugify  # noqa: WPS437

    year = meta.get("year")
    title = meta.get("title") or "paper"
    base = _slugify(title)
    if year:
        return f"{year}_{base}"
    return base


def _frontmatter(meta: dict, raw_assets_path: Optional[str], pdf_downloaded: bool) -> str:
    """Frontmatter YAML conforme a CLAUDE.md sez. 4 (tipo: fonte_raw -> da promuovere a fonte da ingest)."""
    authors_str = ", ".join(meta["authors"][:8]) if meta["authors"] else ""
    title_safe = (meta.get("title") or "Paper").replace('"', "'")
    venue = (meta.get("venue") or "").replace('"', "'")
    fm = [
        "---",
        "tipo: fonte_raw",
        f'titolo: "{title_safe}"',
        f'autore: "{authors_str}"',
        f'data_fonte: {meta.get("year") or ""}',
        f"data_ingest: {datetime.utcnow().date().isoformat()}",
        "formato: paper",
        f'venue: "{venue}"',
        f'doi: "{meta.get("doi") or ""}"',
        f"pdf_disponibile: {str(pdf_downloaded).lower()}",
    ]
    if raw_assets_path:
        fm.append(f'raw_pdf_path: "{raw_assets_path}"')
    fm.append("---")
    return "\n".join(fm)


def _build_markdown_fallback(meta: dict, slug: str) -> str:
    """Markdown abstract-only quando il PDF non e' scaricabile."""
    front = _frontmatter(meta, None, pdf_downloaded=False)
    body_parts = [
        front,
        "",
        f"# {meta.get('title') or 'Paper accademico'}",
        "",
        "> Nota: PDF non disponibile (open access non trovato o errore download)."
        " Il materiale ingerito e' limitato all'abstract e ai metadati.",
        "",
        "## Metadati",
        "",
        f"- Autori: {', '.join(meta['authors']) or '(non riportati)'}",
        f"- Anno: {meta.get('year') or '(non riportato)'}",
        f"- Venue: {meta.get('venue') or '(non riportata)'}",
        f"- DOI: {meta.get('doi') or '(n/d)'}",
        "",
        "## Abstract",
        "",
        meta.get("abstract") or "(abstract non disponibile)",
        "",
    ]
    return "\n".join(body_parts) + "\n"


def _build_markdown_with_pdf(meta: dict, slug: str, pdf_text: str, raw_assets_path: str) -> str:
    """Markdown completo con testo estratto dal PDF."""
    front = _frontmatter(meta, raw_assets_path, pdf_downloaded=True)
    body = (
        f"{front}\n\n"
        f"# {meta.get('title') or 'Paper accademico'}\n\n"
        f"## Metadati\n\n"
        f"- Autori: {', '.join(meta['authors']) or '(non riportati)'}\n"
        f"- Anno: {meta.get('year') or '(non riportato)'}\n"
        f"- Venue: {meta.get('venue') or '(non riportata)'}\n"
        f"- DOI: {meta.get('doi') or '(n/d)'}\n"
        f"- PDF: `{raw_assets_path}`\n\n"
    )
    if meta.get("abstract"):
        body += f"## Abstract\n\n{meta['abstract']}\n\n"
    body += f"## Testo completo (estratto dal PDF)\n\n{pdf_text}\n"
    return body


# ---------------------------------------------------------------------------
# Download HTTP del PDF
# ---------------------------------------------------------------------------

def _download_pdf(url: str, dst: Path) -> bool:
    """
    Scarica il PDF dall'URL in dst. Ritorna True se ottenuto un PDF valido.

    L'URL non e' fidato: arriva da ThesisAttachment.file_path, che l'endpoint
    /attachments/papers riempie con `full_text_url` preso dal payload del
    client. Era quindi una SSRF differita (e persistente: le righe restano in
    tabella), per giunta dentro un BackgroundTask. Il fetch passa per la guard,
    che valida la destinazione, pinna l'IP e ri-valida ogni redirect.
    """
    try:
        resp = ssrf_guard.safe_get_sync(
            url,
            max_bytes=config.WIKI_PAPER_MAX_BYTES,
            deadline_s=config.WIKI_PAPER_DOWNLOAD_TIMEOUT,
            allowed_content_types={"pdf"},
            headers={"User-Agent": "StyleForge-LLMWiki/1.0 (+https://styleforge)"},
        )
    except ssrf_guard.SsrfBlocked as e:
        logger.warning("Download paper bloccato dalla guard SSRF: %s", e)
        return False
    except ssrf_guard.ContentTypeNotAllowed as e:
        logger.info("Download paper: content-type non PDF (%s)", e)
        return False
    except ssrf_guard.GuardError as e:
        logger.info("Download paper abortito (%s): %s", e, url)
        return False
    except (httpx.HTTPError, OSError) as e:
        logger.info("Errore download paper %s: %s", url, e)
        return False

    if resp.status_code != 200:
        logger.info("Download paper non OK (HTTP %s): %s", resp.status_code, url)
        return False

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(resp.content)
    except OSError as e:
        logger.info("Errore scrittura PDF %s: %s", dst, e)
        return False

    return True


def _extract_pdf_text(pdf_path: Path) -> str:
    """Riusa attachment_processor per estrarre testo dal PDF (gia' sanitizzato per Postgres)."""
    from attachment_processor import extract_text_from_pdf
    try:
        return extract_text_from_pdf(pdf_path) or ""
    except Exception:  # noqa: BLE001
        logger.exception("Errore estrazione testo PDF: %s", pdf_path)
        return ""


# ---------------------------------------------------------------------------
# Main entrypoint: materialize tutti i paper della tesi in raw/paper/
# ---------------------------------------------------------------------------

def materialize_papers(thesis_id: str, attachments: List[ThesisAttachment]) -> List[PaperMaterializationResult]:
    """
    Per ogni paper della tesi crea un file markdown in raw/paper/.
    Tenta download PDF; fallback automatico ad abstract+metadata.
    Ritorna la lista risultati per logging/UI.
    """
    bootstrap(thesis_id)
    root = get_wiki_root(thesis_id)
    out: List[PaperMaterializationResult] = []

    for att in attachments:
        if att.mime_type != PAPER_MIME_TYPE:
            continue

        # Un paper che esplode non deve portarsi dietro tutti gli altri: questo
        # gira in un BackgroundTask dentro un ingest a pagamento, e il chiamante
        # (thesis_routes) ha un solo try attorno all'INTERA materializzazione.
        # Senza questo, un URL bloccato dalla guard = zero paper, in silenzio.
        try:
            out.append(_materialize_one(att, root))
        except Exception:  # noqa: BLE001
            logger.exception(
                "Materializzazione paper fallita (allegato %s): si prosegue con gli altri",
                att.id,
            )

    return out


def _materialize_one(att: ThesisAttachment, root: Path) -> PaperMaterializationResult:
    """Materializza un singolo paper. Solleva: il chiamante isola il fallimento."""
    meta = _parse_paper_metadata(att)
    slug = _slug_for_paper(meta)
    md_filename = make_raw_filename(None, slug)  # gia' include slug, no prefisso data
    md_dst = root / "raw" / "paper" / md_filename

    # Anti-collisione
    i = 1
    while md_dst.exists():
        md_dst = root / "raw" / "paper" / make_raw_filename(None, f"{slug}-{i}")
        i += 1

    url = _resolve_url(att, meta)
    pdf_downloaded = False
    pdf_text = ""
    raw_assets_path = ""

    if url:
        pdf_dst = root / "raw" / "assets" / f"{md_dst.stem}.pdf"
        if _download_pdf(url, pdf_dst):
            pdf_text = _extract_pdf_text(pdf_dst)
            if pdf_text.strip():
                pdf_downloaded = True
                raw_assets_path = str(pdf_dst.relative_to(root))
            else:
                # PDF scaricato ma estrazione vuota -> fallback
                try:
                    pdf_dst.unlink()
                except OSError:
                    pass

    if pdf_downloaded:
        md_dst.write_text(
            _build_markdown_with_pdf(meta, slug, pdf_text, raw_assets_path),
            encoding="utf-8",
        )
    else:
        # Il PDF non si e' scaricato (fonte giu', non-PDF, o destinazione
        # bloccata): il paper resta, con abstract e metadati.
        md_dst.write_text(_build_markdown_fallback(meta, slug), encoding="utf-8")

    return PaperMaterializationResult(
        attachment_id=str(att.id),
        title=meta.get("title") or "Paper",
        raw_path=str(md_dst.relative_to(root)),
        pdf_downloaded=pdf_downloaded,
        fallback_used=not pdf_downloaded,
    )
