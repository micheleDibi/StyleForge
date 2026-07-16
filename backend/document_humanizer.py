"""
Umanizzazione di testi/documenti lunghi.

Due capacità:
  1. humanize_long_text(): umanizza un testo arbitrariamente lungo dividendolo in
     CHUNK (mai a metà frase), applicando per ogni chunk la riscrittura nello stile
     appreso + il pipeline anti-AI completo. Risolve il crash su testi lunghi.
  2. humanize_docx_inplace(): round-trip di un .docx mantenendo il TEMPLATE originale
     (frontespizio, indice, titoli, font, margini, numerazione). Sostituisce SOLO il
     testo dei paragrafi del corpo, in batch che PRESERVANO la corrispondenza 1:1 coi
     paragrafi (così i titoli non si spostano). Niente controlled_paraphrase qui:
     riordina/fonde le frasi e romperebbe la mappatura dei paragrafi; l'anti-AI è dato
     dalla riscrittura nello stile + dal pass algoritmico per-paragrafo (gratis).
"""

import re
import logging

from ai_exceptions import InsufficientCreditsError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# CHUNKING (testo lungo)
# ═══════════════════════════════════════════════════════════════════════════
def split_into_chunks(text: str, target_words: int = 3000, max_words: int = 3500):
    """Divide il testo in chunk ~target_words, su confini di paragrafo; mai a metà
    frase. Un paragrafo più lungo di max_words viene spezzato su confini di frase."""
    paragraphs = re.split(r'\n\s*\n', text or '')
    chunks, buf, buf_words = [], [], 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        pw = len(para.split())
        if pw > max_words:
            if buf:
                chunks.append("\n\n".join(buf)); buf, buf_words = [], 0
            chunks.extend(_split_paragraph_on_sentences(para, target_words))
            continue
        if buf and buf_words + pw > target_words:
            chunks.append("\n\n".join(buf)); buf, buf_words = [], 0
        buf.append(para); buf_words += pw
    if buf:
        chunks.append("\n\n".join(buf))
    return [c for c in chunks if c.strip()]


def _split_paragraph_on_sentences(para: str, target_words: int):
    sentences = re.split(r'(?<=[.!?])\s+', para)
    chunks, buf, buf_words = [], [], 0
    for s in sentences:
        sw = len(s.split())
        if buf and buf_words + sw > target_words:
            chunks.append(" ".join(buf)); buf, buf_words = [], 0
        buf.append(s); buf_words += sw
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def humanize_long_text(text: str, session_client, profile: str = 'informal', progress_cb=None) -> str:
    """Umanizza un testo lungo a chunk, col pipeline anti-AI completo per chunk."""
    import config
    from anti_ai_pipeline import apply_anti_ai_pipeline

    chunks = split_into_chunks(text)
    if not chunks:
        return text
    out = []
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        rewritten = session_client.umanizzazione_chunk(chunk, profile=profile)
        rewritten = apply_anti_ai_pipeline(
            rewritten,
            profile=profile,
            target_words=len(chunk.split()),
            paraphrase_enabled=getattr(config, 'ANTI_AI_PARAPHRASE_ENABLED', True),
            paraphrase_rounds=getattr(config, 'ANTI_AI_PARAPHRASE_ROUNDS', 2),
            paraphrase_model=getattr(config, 'ANTI_AI_PARAPHRASE_MODEL', None),
            rewrite_enabled=getattr(config, 'ANTI_AI_REWRITE_ENABLED', False),
            rewrite_model=getattr(config, 'ANTI_AI_REWRITE_MODEL', None),
            algo_enabled=getattr(config, 'ANTI_AI_ALGO_ENABLED', True),
            label=f'chunk{i + 1}',
        )
        out.append(rewritten)
        if progress_cb:
            try:
                progress_cb(int((i + 1) / n * 100))
            except Exception:  # noqa: BLE001
                pass
    return "\n\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════
# DOCX ROUND-TRIP (mantiene il template originale)
# ═══════════════════════════════════════════════════════════════════════════
# Stili da NON umanizzare (titoli, indice, didascalie, bibliografia, citazioni).
_SKIP_STYLE_PREFIXES = (
    'Heading', 'Title', 'TOC', 'Caption', 'Subtitle',
    'Titolo', 'Sottotitolo', 'Didascalia', 'Indice', 'Sommario',
)
_SKIP_STYLE_NAMES = {
    'Bibliography', 'Bibliografia', 'Quote', 'Intense Quote', 'Citazione',
}


def is_body_paragraph(p) -> bool:
    """True se il paragrafo è testo del corpo da umanizzare (non titolo/indice/
    bibliografia/didascalia, non vuoto, almeno 4 parole)."""
    txt = (p.text or '').strip()
    if not txt:
        return False
    try:
        name = (p.style.name or '') if p.style else ''
    except Exception:  # noqa: BLE001
        name = ''
    if any(name.startswith(pre) for pre in _SKIP_STYLE_PREFIXES):
        return False
    if name in _SKIP_STYLE_NAMES:
        return False
    if len(txt.split()) < 4:
        return False
    return True


# Token segnaposto per elementi inline preservati (note, endnote, immagini, campi, hyperlink).
_NOTE_TOKEN_RE = re.compile(r'⟦N\d+⟧')


def _note_token(k: int) -> str:
    return f"⟦N{k}⟧"


def _ensure_note_superscript(run_el) -> None:
    """Garantisce che un run di riferimento a nota/endnote sia in APICE (superscript),
    anche se l'originale non aveva lo stile FootnoteReference (così i numeretti non
    appaiono come testo normale)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rpr = run_el.find(qn('w:rPr'))
    if rpr is None:
        rpr = OxmlElement('w:rPr')
        run_el.insert(0, rpr)
    if rpr.find(qn('w:vertAlign')) is None:
        va = OxmlElement('w:vertAlign'); va.set(qn('w:val'), 'superscript')
        rpr.append(va)


def extract_paragraph_with_placeholders(p):
    """Ritorna (text_with_tokens, token_map, base_rpr).

    Cammina i figli di p._element IN ORDINE: i run di solo testo diventano testo; i run
    con elementi speciali (riferimenti a nota/endnote, immagini, campi) e ogni altro
    elemento inline (hyperlink, bookmark...) diventano un token ⟦N{k}⟧ con l'elemento XML
    originale preservato (deepcopy) in token_map. base_rpr è il <w:rPr> del run di testo
    DOMINANTE (il più lungo): così un singolo run in corsivo non rende corsivo l'intero
    paragrafo. I riferimenti a nota vengono forzati in apice.
    """
    from copy import deepcopy
    from docx.oxml.ns import qn

    R = qn('w:r'); T = qn('w:t'); PPR = qn('w:pPr'); RPR = qn('w:rPr')
    NOTE_REFS = (qn('w:footnoteReference'), qn('w:endnoteReference'))
    OTHER_SPECIAL = (qn('w:drawing'), qn('w:object'), qn('w:pict'), qn('w:fldChar'), qn('w:instrText'))

    parts, token_map, base_rpr, base_len, k = [], {}, None, -1, 0
    for child in list(p._element):
        if child.tag == PPR:
            continue
        if child.tag == R:
            is_note = any(child.find(s) is not None for s in NOTE_REFS)
            is_special = is_note or any(child.find(s) is not None for s in OTHER_SPECIAL)
            if is_special:
                el = deepcopy(child)
                if is_note:
                    _ensure_note_superscript(el)
                tok = _note_token(k); k += 1
                token_map[tok] = el
                parts.append(tok)
            else:
                txt = ''.join(t.text or '' for t in child.findall(T))
                if len(txt) > base_len:   # formattazione del run dominante (più lungo)
                    rpr = child.find(RPR)
                    base_rpr = deepcopy(rpr) if rpr is not None else None
                    base_len = len(txt)
                parts.append(txt)
        else:
            tok = _note_token(k); k += 1
            token_map[tok] = deepcopy(child)
            parts.append(tok)
    return ''.join(parts), token_map, base_rpr


def rebuild_paragraph(p, new_text: str, token_map: dict, base_rpr) -> None:
    """Ricostruisce il paragrafo dal testo riscritto reinserendo gli elementi inline
    preservati al posto dei token ⟦N{k}⟧. Mantiene <w:pPr> (stile del paragrafo) e usa
    base_rpr per la formattazione dei nuovi run di testo. I token persi dal modello
    vengono ri-appesi in coda → le note non si perdono mai."""
    from copy import deepcopy
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    PPR = qn('w:pPr')
    for child in list(p._element):
        if child.tag != PPR:
            p._element.remove(child)

    used = set()
    parts = _NOTE_TOKEN_RE.split(new_text)
    tokens = _NOTE_TOKEN_RE.findall(new_text)
    for i, txt in enumerate(parts):
        if txt:
            r = OxmlElement('w:r')
            if base_rpr is not None:
                r.append(deepcopy(base_rpr))
            t = OxmlElement('w:t')
            t.set(qn('xml:space'), 'preserve')
            t.text = txt
            r.append(t)
            p._element.append(r)
        if i < len(tokens):
            tok = tokens[i]
            el = token_map.get(tok)
            if el is not None and tok not in used:
                p._element.append(el)
                used.add(tok)
    # Garanzia anti-perdita: elementi (note) mai ricomparsi → ri-appesi in coda.
    for tok, el in token_map.items():
        if tok not in used:
            p._element.append(el)


def _protect_note_tokens(text: str):
    """Sostituisce i token ⟦N{k}⟧ con un sentinel ASCII che il pass algoritmico non
    altera. Ritorna (testo_protetto, mapping)."""
    mapping = {}

    def repl(m):
        sentinel = f"ZZNOTE{len(mapping)}ZZ"
        mapping[sentinel] = m.group(0)
        return sentinel

    return _NOTE_TOKEN_RE.sub(repl, text or ''), mapping


def _restore_note_tokens(text: str, mapping: dict) -> str:
    for sentinel, tok in mapping.items():
        text = text.replace(sentinel, tok)
    return text


_MARKER_RE = re.compile(r'<<<\s*S\s*\d+\s*>>>')


def _build_segments_payload(texts) -> str:
    return "\n".join(f"<<<S{i}>>>\n{t}" for i, t in enumerate(texts))


def _parse_segments(rewritten: str, expected: int):
    """Ridivide la risposta sui marcatori <<<Sk>>>. Ritorna la lista dei segmenti
    se il conteggio combacia e nessuno è vuoto, altrimenti None."""
    parts = _MARKER_RE.split(rewritten or '')
    segs = [p.strip() for p in parts[1:]]  # scarta il preambolo prima del 1° marcatore
    if len(segs) != expected:
        return None
    if any(not s for s in segs):
        return None
    return segs


def _strip_markdown(s: str) -> str:
    """Rimuove la formattazione markdown che il modello a volte aggiunge (*x*, **x**,
    _x_, # titolo): nel .docx finirebbe come asterischi/cancelletti letterali."""
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'\*(.+?)\*', r'\1', s)
    s = re.sub(r'(?<![A-Za-zÀ-ÿ0-9])_(.+?)_(?![A-Za-zÀ-ÿ0-9])', r'\1', s)
    s = re.sub(r'^\s*#{1,6}\s+', '', s)
    s = s.replace('*', '')  # asterischi residui spaiati
    return s


def _clean_segment(s: str) -> str:
    s = _MARKER_RE.sub('', s or '')
    s = s.strip()
    s = re.sub(r'^\s*-{3,}\s*', '', s)
    s = re.sub(r'\s*-{3,}\s*$', '', s)
    s = _strip_markdown(s)
    return s.strip()


def _per_paragraph_fallback(texts, session_client, profile, intensify=False):
    """Fallback robusto: una riscrittura per paragrafo → corrispondenza 1:1 garantita."""
    out = []
    for t in texts:
        try:
            out.append(session_client.umanizzazione_chunk(t, profile=profile, intensify=intensify))
        except InsufficientCreditsError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Fallback per-paragrafo fallito: {e}; tengo l'originale")
            out.append(t)
    return out


def _base_rewrite(texts, session_client, profile, intensify=False):
    """Una riscrittura dei segmenti (batch) con fallback per-paragrafo se il modello
    sbaglia il conteggio. Garantisce len(out) == len(texts)."""
    n = len(texts)
    if n == 1:
        return _per_paragraph_fallback(texts, session_client, profile, intensify=intensify)
    joined = _build_segments_payload(texts)
    try:
        rewritten = session_client.umanizzazione_segments(joined, n, profile, intensify=intensify)
        segs = _parse_segments(rewritten, n)
    except InsufficientCreditsError:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Riscrittura a segmenti fallita: {e}; uso il fallback")
        segs = None
    if segs is None:
        segs = _per_paragraph_fallback(texts, session_client, profile, intensify=intensify)
    return segs


def _rewrite_segments(texts, session_client, profile, style_passes=0):
    """Riscrittura base + N passate di rifinitura stilistica (intensify). Una passata
    che fallisce o cambia il numero di segmenti viene scartata (si tiene la precedente)."""
    segs = _base_rewrite(texts, session_client, profile, intensify=False)
    for _ in range(max(0, int(style_passes))):
        refined = _base_rewrite(segs, session_client, profile, intensify=True)
        if refined and len(refined) == len(segs):
            segs = refined
    return segs


def humanize_docx_inplace(src_path, dst_path, session_client, profile: str = 'academic',
                          progress_cb=None, batch_words=None, style_passes=None) -> str:
    """
    Umanizza un .docx mantenendo il template originale: sostituisce SOLO il testo dei
    paragrafi del corpo, in batch che preservano la corrispondenza 1:1. Ritorna dst_path.
    """
    import config
    from docx import Document as DocxDocument
    from anti_ai_processor import humanize_text_post_processing

    if batch_words is None:
        batch_words = getattr(config, 'DOC_HUMANIZE_BATCH_WORDS', 1000)
    if style_passes is None:
        style_passes = getattr(config, 'DOC_STYLE_REFINE_PASSES', 1)

    doc = DocxDocument(str(src_path))
    body = [p for p in doc.paragraphs if is_body_paragraph(p)]
    total = len(body)
    if total == 0:
        doc.save(str(dst_path))
        return str(dst_path)

    # Pre-estrai testo tokenizzato + mappa elementi inline + rPr base per paragrafo.
    extracted = [extract_paragraph_with_placeholders(p) for p in body]

    # Raggruppa paragrafi-corpo consecutivi fino a ~batch_words parole.
    batches, cur, cur_words = [], [], 0
    for idx in range(total):
        w = len(extracted[idx][0].split())
        if cur and cur_words + w > batch_words:
            batches.append(cur); cur, cur_words = [], 0
        cur.append(idx); cur_words += w
    if cur:
        batches.append(cur)

    done = 0
    for batch in batches:
        texts = [extracted[i][0] for i in batch]
        segs = _rewrite_segments(texts, session_client, profile, style_passes)

        for i, seg in zip(batch, segs):
            seg = _clean_segment(seg)
            # Proteggi i token nota dal pass algoritmico, poi ripristinali.
            protected, tokmap = _protect_note_tokens(seg)
            try:
                protected = humanize_text_post_processing(protected, profile=profile)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Pass algoritmico per-paragrafo fallito: {e}")
            seg = _restore_note_tokens(protected, tokmap)
            if seg and seg.strip():
                _, token_map, base_rpr = extracted[i]
                rebuild_paragraph(body[i], seg.strip(), token_map, base_rpr)

        done += len(batch)
        if progress_cb:
            try:
                progress_cb(int(done / total * 100))
            except Exception:  # noqa: BLE001
                pass

    doc.save(str(dst_path))
    return str(dst_path)
