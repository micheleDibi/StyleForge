/**
 * Tokenizer client-side delle formule LaTeX della tesi.
 *
 * SPECCHIA backend/thesis_math.py (regex e guardie devono restare allineate):
 *   inline:  $\beta = \omega / \omega_n$   (mai attraverso newline)
 *   display: $$D = \frac{1}{\sqrt{...}}$$  su riga isolata (o blocco $$ ... $$)
 * Guardie anti-valuta: niente cifra adiacente ai delimitatori, niente spazio
 * subito dentro, contenuto solo-numerico rifiutato ("$50$" resta testo).
 */

export const INLINE_MATH_RE =
  /(?<![\\$])\$\$(?!\s)((?:\\\$|[^$\n])+?)(?<!\s)\$\$(?!\$)|(?<![\\$\d])\$(?!\s)((?:\\\$|[^$\n])+?)(?<!\s)\$(?![\d$])/g;

export const DISPLAY_LINE_RE = /^\s*\$\$([^$]+?)\$\$\s*$/;
export const DISPLAY_FENCE_RE = /^\s*\$\$\s*$/;

const MAX_INLINE_LATEX_LEN = 200;
const PURE_NUMBER_RE = /^\d+(?:[.,]\d+)*$/;

export function isValidInline(content) {
  const c = (content || '').trim();
  if (!c || c.length > MAX_INLINE_LATEX_LEN) return false;
  if (PURE_NUMBER_RE.test(c)) return false;
  return true;
}

/**
 * Divide una riga in span: {kind: 'text'|'math', value, raw}.
 * Per 'math' value è il LaTeX senza delimitatori, raw lo span originale.
 */
export function splitMathSpans(text) {
  const out = [];
  const s = text || '';
  let pos = 0;
  INLINE_MATH_RE.lastIndex = 0;
  let m;
  while ((m = INLINE_MATH_RE.exec(s)) !== null) {
    const latex = (m[1] !== undefined ? m[1] : m[2]).trim();
    if (!isValidInline(latex)) continue;
    if (m.index > pos) {
      const chunk = s.slice(pos, m.index);
      out.push({ kind: 'text', value: chunk, raw: chunk });
    }
    out.push({ kind: 'math', value: latex, raw: m[0] });
    pos = m.index + m[0].length;
  }
  if (pos < s.length) {
    const chunk = s.slice(pos);
    out.push({ kind: 'text', value: chunk, raw: chunk });
  }
  return out;
}

export function hasInlineMath(text) {
  return splitMathSpans(text).some((s) => s.kind === 'math');
}
