"""
Formule matematiche LaTeX nella tesi — unica fonte di verità.

Il modello genera formule in LaTeX dentro il contenuto piatto della tesi:
  - inline, dentro la frase:      $\\beta = \\omega / \\omega_n$
  - display, su riga isolata:     $$D = \\frac{1}{\\sqrt{(1-\\beta^2)^2}}$$

Questo modulo definisce il contratto della sintassi e tutto ciò che serve a:
  - riconoscerla (iter_inline_math, DISPLAY_LINE_RE) e normalizzarla a
    generazione (sanitize_generated_math: \\(..\\)/\\[..\\] → $/$$, blocchi
    display canonicalizzati su riga isolata);
  - proteggerla attraverso le riscritture LLM/anti-AI con sentinelle
    ZZMATH{k}ZZ (protect_math_spans / restore_math_spans), disgiunte dalle
    ZZASSET{k}ZZ di thesis_assets;
  - renderizzarla:
      * docx  → equazioni OMML native (latex_to_omml, latex2mathml+mathml2omml)
      * pdf   → PNG via matplotlib mathtext con metriche baseline
                (render_math_png: i font base-14 del PDF non hanno glifi greci)
      * txt   → testo Unicode (latex_to_unicode, pylatexenc)
      * md    → sintassi $ verbatim (gestita dai chiamanti)

Il frontend replica il tokenizer in frontend/src/utils/thesisMath.js: le due
implementazioni devono restare allineate.
"""

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import Iterator, Optional, Tuple

logger = logging.getLogger(__name__)

# Namespace OMML (Office Math Markup Language) dei .docx
OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


class MathRenderError(Exception):
    """La formula non è renderizzabile nel formato richiesto (si degrada al fallback)."""


@dataclass
class MathAsset:
    """Equazione display ($$...$$) come segmento di primo livello."""
    latex: str
    label: Optional[str] = None  # "(2.1)" — assegnata da assign_asset_numbers


@dataclass
class MathPng:
    """PNG di una formula con le metriche tipografiche in punti (a fontsize richiesto)."""
    png: bytes
    width_pt: float
    height_pt: float
    depth_pt: float  # porzione sotto il baseline (per l'allineamento inline nel PDF)
    dpi: int


# ═══════════════════════════════════════════════════════════════════════════
# SINTASSI / REGEX  (speculari a frontend/src/utils/thesisMath.js)
# ═══════════════════════════════════════════════════════════════════════════

# Span inline dentro una riga: $$...$$ (display in mezzo al testo, contenuto
# legacy) oppure $...$. Guardie anti-valuta: niente cifra subito prima/dopo i
# delimitatori, niente spazio subito dentro, mai attraverso un newline.
# NOTA PARITÀ: classi esplicite [0-9] e [ \t] (mai \d o \s) perché la loro
# semantica Unicode diverge tra il motore regex di Python e quello JS.
INLINE_MATH_RE = re.compile(
    r'(?<![\\$])\$\$(?![ \t])((?:\\\$|[^$\n])+?)(?<![ \t])\$\$(?!\$)'
    r'|(?<![\\$0-9])\$(?![ \t])((?:\\\$|[^$\n])+?)(?<![ \t])\$(?![0-9$])'
)

# Riga display canonica: solo $$...$$ (ammesso \$ letterale nel contenuto)
DISPLAY_LINE_RE = re.compile(r'^\s*\$\$((?:\\\$|[^$\n])+?)\$\$\s*$')
# Blocco display legacy multi-riga: riga di apertura/chiusura fatta di soli $$
DISPLAY_FENCE_RE = re.compile(r'^\s*\$\$\s*$')

MATH_SENTINEL_RE = re.compile(r'ZZMATH(\d+)ZZ')

# Contenuto inline oltre questa lunghezza: quasi certamente non è una formula
MAX_INLINE_LATEX_LEN = 200
# Cap difensivo per le display (KaTeX/mathtext/OMML su input patologici)
MAX_DISPLAY_LATEX_LEN = 2000
def _is_valid_inline(content: str) -> bool:
    # Il contenuto solo-numerico ("$1$") È matematica valida: le valute reali
    # non superano comunque le guardie posizionali ("$50" mai chiuso, "50$"
    # con cifra adiacente, "tra $5 e $10" con spazi dentro i delimitatori).
    content = content.strip()
    if not content or len(content) > MAX_INLINE_LATEX_LEN:
        return False
    return True


def iter_inline_math(text: str) -> Iterator[Tuple[str, str, str]]:
    """Divide una riga in span: ('text', testo, testo) | ('math', latex, span_originale).

    Gli span che non superano le guardie restano testo. Non attraversa newline.
    """
    pos = 0
    for m in INLINE_MATH_RE.finditer(text):
        latex = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        if not _is_valid_inline(latex):
            continue
        if m.start() > pos:
            yield ('text', text[pos:m.start()], text[pos:m.start()])
        yield ('math', latex, m.group(0))
        pos = m.end()
    if pos < len(text):
        yield ('text', text[pos:], text[pos:])


def has_inline_math(text: str) -> bool:
    return any(kind == 'math' for kind, _, _ in iter_inline_math(text))


# ═══════════════════════════════════════════════════════════════════════════
# NORMALIZZAZIONE A GENERAZIONE
# ═══════════════════════════════════════════════════════════════════════════

_PAREN_INLINE_RE = re.compile(r'\\\(\s*([^\n]*?)\s*\\\)')
_BRACKET_DISPLAY_RE = re.compile(r'\\\[\s*([^\n]*?)\s*\\\]')
# Il contenuto "sembra matematica" solo con marcatori LaTeX espliciti: evita
# di convertire escape markdown come le citazioni \[1\] o incisi \(in euro\).
_MATHISH_RE = re.compile(r'[\\^_={}]')
_MIDLINE_DISPLAY_RE = re.compile(r'\$\$((?:\\\$|[^$\n])+?)\$\$')


def normalize_math_delimiters(text: str) -> str:
    """Delimitatori alternativi → canonici: \\(..\\) → $..$, \\[..\\] → $$..$$.

    Solo sulla singola riga e solo se il contenuto contiene marcatori LaTeX
    (\\, ^, _, =, graffe): \\[1\\] (citazione escaped) e \\(in euro\\) restano testo.
    """
    def _sub(wrap):
        def inner(m):
            content = m.group(1)
            if not _MATHISH_RE.search(content):
                return m.group(0)
            return wrap.format(content)
        return inner

    text = _PAREN_INLINE_RE.sub(_sub("${0}$"), text)
    text = _BRACKET_DISPLAY_RE.sub(_sub("$${0}$$"), text)
    return text


def sanitize_generated_math(text: str) -> str:
    """Normalizza la matematica appena generata (mai distruttiva sul testo).

    Line-based, con criteri prudenti (un $$ orfano NON deve mai inghiottire
    la prosa dei paragrafi successivi):
    - \\(..\\) / \\[..\\] matematici → $ / $$;
    - blocco recintato ($$ / corpo / $$ senza righe vuote, max 10 righe) →
      collassato su una riga display canonica isolata;
    - riga già display → normalizzata (spazi interni compattati, righe vuote
      attorno); display vuota rimossa;
    - $$..$$ in mezzo a una riga → spostato su riga isolata SOLO se è l'unico
      span e la riga non contiene altri $ (mai spezzare "$a$$b$$c$");
    - $ o $$ spaiati lasciati intatti: degradano a testo letterale.

    NOTA: va chiamata sul testo FUORI dai blocchi [TABELLA]/[GRAFICO] (vedi
    thesis_assets.sanitize_math_outside_assets) per non rompere le celle.
    """
    if '$' not in text and '\\(' not in text and '\\[' not in text:
        return text
    text = normalize_math_delimiters(text)
    if '$$' not in text:
        return text

    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Blocco recintato: $$ / corpo senza righe vuote (max 10) / $$
        if DISPLAY_FENCE_RE.match(line):
            j = i + 1
            body = []
            while (j < len(lines) and j - i <= 10 and lines[j].strip()
                   and not DISPLAY_FENCE_RE.match(lines[j])):
                body.append(lines[j])
                j += 1
            if j < len(lines) and DISPLAY_FENCE_RE.match(lines[j]) and body:
                content = ' '.join(' '.join(body).split())
                out.extend(['', f"$${content}$$", ''])
                i = j + 1
                continue
            out.append(line)  # recinzione orfana: lasciata (il parser la ignora)
            i += 1
            continue

        m = DISPLAY_LINE_RE.match(line)
        if m:
            content = ' '.join(m.group(1).split())
            if content:
                out.extend(['', f"$${content}$$", ''])
            i += 1
            continue

        # Display in mezzo alla riga: solo caso non ambiguo
        if '$$' in line:
            spans = list(_MIDLINE_DISPLAY_RE.finditer(line))
            if len(spans) == 1 and '$' not in (line[:spans[0].start()] + line[spans[0].end():]):
                s = spans[0]
                content = ' '.join(s.group(1).split())
                before, after = line[:s.start()].rstrip(), line[s.end():].lstrip()
                if before:
                    out.append(before)
                if content:
                    out.extend(['', f"$${content}$$", ''])
                if after:
                    out.append(after)
                i += 1
                continue

        out.append(line)
        i += 1

    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out))


# ═══════════════════════════════════════════════════════════════════════════
# PROTEZIONE ATTRAVERSO LE RISCRITTURE (sentinelle ZZMATH{k}ZZ)
# ═══════════════════════════════════════════════════════════════════════════

def protect_math_spans(text: str) -> Tuple[str, dict]:
    """Sostituisce le formule con sentinelle ZZMATH{k}ZZ prima delle riscritture LLM.

    Display (riga $$...$$) → sentinella su riga isolata; inline → token dentro
    la frase. Va chiamata DOPO protect_asset_blocks, così la matematica dentro
    tabelle/JSON grafici è già sequestrata. Ritorna (testo, mapping).
    """
    mapping: dict = {}

    def _sentinel(raw_span: str) -> str:
        sentinel = f"ZZMATH{len(mapping)}ZZ"
        mapping[sentinel] = raw_span
        return sentinel

    out_lines = []
    for line in text.split('\n'):
        if '$' not in line:
            out_lines.append(line)
            continue
        m = DISPLAY_LINE_RE.match(line)
        if m:
            out_lines.append(_sentinel(f"$${m.group(1).strip()}$$"))
            continue
        parts = []
        for kind, _latex, raw in iter_inline_math(line):
            parts.append(_sentinel(raw) if kind == 'math' else raw)
        out_lines.append(''.join(parts))
    return '\n'.join(out_lines), mapping


def restore_math_spans(text: str, mapping: dict) -> str:
    """Ripristina le formule al posto delle sentinelle dopo le riscritture.

    Una sentinella persa non fa perdere la formula: viene ri-appesa in fondo
    su riga isolata (con warning). Duplicati e sentinelle spurie vengono rimossi.
    """
    if not mapping:
        return MATH_SENTINEL_RE.sub('', text) if 'ZZMATH' in text else text

    lost = []
    for sentinel, raw_span in mapping.items():
        if sentinel in text:
            before, _, after = text.partition(sentinel)
            after = after.replace(sentinel, '')  # eventuali duplicati
            text = before + raw_span + after
        else:
            lost.append((sentinel, raw_span))

    if lost:
        logger.warning(
            "restore_math_spans: %d sentinelle perse dalla riscrittura, "
            "formule ri-appese in fondo", len(lost)
        )
        tail = '\n\n'.join(raw for _, raw in lost)
        text = text.rstrip() + '\n\n' + tail + '\n'

    # Sentinelle spurie (inventate/duplicate dalla riscrittura)
    text = MATH_SENTINEL_RE.sub('', text)
    return text


def strip_math_sentinels(text: str) -> str:
    """Rimuove le sentinelle ZZMATH{k}ZZ (per conteggi parole/scansioni)."""
    return MATH_SENTINEL_RE.sub('', text)


def unprotect_math_spans(text: str, mapping: dict) -> str:
    """Sostituisce le sole sentinelle PRESENTI nel frammento (per pezzi di riga).

    A differenza di restore_math_spans non ri-appende le sentinelle assenti:
    serve quando una riga protetta viene spezzata in più frammenti (es.
    estrazione delle note a piè di pagina) e ogni frammento va ripristinato
    per conto suo.
    """
    if not mapping or 'ZZMATH' not in text:
        return text
    for sentinel, raw_span in mapping.items():
        if sentinel in text:
            text = text.replace(sentinel, raw_span)
    return text


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSIONE UNICODE (txt e fallback)
# ═══════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _latex_to_text_converter():
    from pylatexenc.latex2text import LatexNodes2Text
    return LatexNodes2Text()


def latex_to_unicode(latex: str) -> str:
    """LaTeX → testo Unicode leggibile (β, ω, √, ⋅). In caso di errore: sorgente."""
    try:
        out = _latex_to_text_converter().latex_to_text(f"${latex}$").strip()
        return out if out else latex
    except Exception:
        return latex


def inline_math_to_unicode(text: str) -> str:
    """Sostituisce gli span $...$ di una riga con la resa Unicode."""
    if '$' not in text:
        return text
    parts = []
    for kind, latex, raw in iter_inline_math(text):
        parts.append(latex_to_unicode(latex) if kind == 'math' else raw)
    return ''.join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# RENDER PNG (matplotlib mathtext — per il PDF e come fallback docx)
# ═══════════════════════════════════════════════════════════════════════════

# Comandi frequenti nel LaTeX dei modelli ma fuori dal subset mathtext
_MATHTEXT_REWRITES = [
    (re.compile(r'\\text\s*\{'), r'\\mathrm{'),
    (re.compile(r'\\operatorname\s*\{'), r'\\mathrm{'),
    (re.compile(r'\\[dt]frac\b'), r'\\frac'),
    (re.compile(r'\\displaystyle\b'), ''),
    (re.compile(r'\\(?:nonumber|notag)\b'), ''),
    (re.compile(r'\\(?:label|tag)\s*\{[^}]*\}'), ''),
]
_MATHTEXT_UNSUPPORTED_RE = re.compile(r'\\begin\s*\{|\\\\')


def sanitize_for_mathtext(latex: str) -> str:
    """Adatta il LaTeX al subset di matplotlib mathtext o solleva MathRenderError."""
    if _MATHTEXT_UNSUPPORTED_RE.search(latex):
        raise MathRenderError("costrutto multi-riga/ambiente non supportato da mathtext")
    for pattern, repl in _MATHTEXT_REWRITES:
        latex = pattern.sub(repl, latex)
    return latex.strip()


@lru_cache(maxsize=256)
def render_math_png(latex: str, fontsize: float = 11.0, dpi: int = 300,
                    display: bool = False) -> MathPng:
    """Renderizza una formula in PNG trasparente con metriche baseline in punti.

    Serif (dejavuserif) per coerenza con i grafici accademici; depth_pt è la
    porzione sotto il baseline, necessaria per allineare le formule inline nel
    PDF. Solleva MathRenderError su LaTeX non supportato.
    """
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import MathTextParser

    if len(latex) > MAX_DISPLAY_LATEX_LEN:
        raise MathRenderError("formula troppo lunga per essere renderizzata")
    mathtext = f"${sanitize_for_mathtext(latex)}$"
    size = fontsize * (1.15 if display else 1.0)
    prop = FontProperties(size=size)
    rc = {'mathtext.fontset': 'dejavuserif', 'font.family': 'serif'}
    try:
        with matplotlib.rc_context(rc):
            parsed = MathTextParser('path').parse(mathtext, dpi=72, prop=prop)
            width_pt, height_pt, depth_pt = parsed[0], parsed[1], parsed[2]
            if width_pt <= 0 or height_pt <= 0:
                raise MathRenderError("formula con dimensioni nulle")
            fig = Figure(figsize=(width_pt / 72.0, height_pt / 72.0))
            fig.text(0, depth_pt / height_pt, mathtext,
                     fontproperties=prop, color='#111111')
            buf = BytesIO()
            fig.savefig(buf, dpi=dpi, format='png', transparent=True)
    except MathRenderError:
        raise
    except Exception as exc:
        raise MathRenderError(f"mathtext non renderizza la formula: {exc}") from exc
    return MathPng(png=buf.getvalue(), width_pt=float(width_pt),
                   height_pt=float(height_pt), depth_pt=float(depth_pt), dpi=dpi)


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSIONE OMML (equazioni native Word)
# ═══════════════════════════════════════════════════════════════════════════

def latex_to_omml(latex: str, block: bool = False):
    """LaTeX → elemento lxml `m:oMath` pronto da appendere a un `w:p` python-docx.

    `block=True` converte il MathML in stile display (frazioni/limiti grandi).
    Solleva MathRenderError se la catena latex2mathml → mathml2omml fallisce.
    """
    if len(latex) > MAX_DISPLAY_LATEX_LEN:
        raise MathRenderError("formula troppo lunga per essere convertita")
    try:
        import latex2mathml.converter
        import mathml2omml
        from lxml import etree

        mathml = latex2mathml.converter.convert(
            latex, display='block' if block else 'inline')
        omml_str = mathml2omml.convert(mathml)
        root = etree.fromstring(
            f'<root xmlns:m="{OMML_NS}">{omml_str}</root>'.encode('utf-8'))
        if len(root) != 1 or not root[0].tag.endswith('}oMath'):
            raise MathRenderError("output OMML inatteso")
        return root[0]
    except MathRenderError:
        raise
    except Exception as exc:
        raise MathRenderError(f"conversione OMML fallita: {exc}") from exc
