"""
Test unitari per thesis_math (nessun DB/rete/API key).

Esecuzione: python3 -m pytest test_thesis_math.py -q
"""

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")

import pytest

from thesis_math import (
    MathPng,
    MathRenderError,
    OMML_NS,
    has_inline_math,
    inline_math_to_unicode,
    iter_inline_math,
    latex_to_omml,
    latex_to_unicode,
    normalize_math_delimiters,
    protect_math_spans,
    render_math_png,
    restore_math_spans,
    sanitize_for_mathtext,
    sanitize_generated_math,
    strip_math_sentinels,
)

# Le due formule dello screenshot dell'utente
INLINE_BETA = r"\beta = \omega / \omega_n"
DISPLAY_D = r"D = \frac{1}{\sqrt{(1 - \beta^2)^2 + (2\xi\beta)^2}}"

FORMULAS_BATTERY = [
    INLINE_BETA,
    DISPLAY_D,
    r"\omega_n = \sqrt{k/m}",
    r"u_{st} = p_0/k",
    r"u_0 = u_{st} \cdot D",
    r"\xi = c / (2m\omega_n)",
    r"x^2 + y^2 = r^2",
    r"\sum_{i=1}^{n} x_i",
    r"\int_0^T f(t)\, dt",
    r"E = mc^2",
    r"\sigma = \frac{N}{A} \pm \frac{M}{W}",
    r"\lim_{x \to \infty} \frac{1}{x} = 0",
    r"\Delta = b^2 - 4ac",
    r"\alpha \leq \gamma \neq \delta \approx \epsilon",
    r"\mathbf{F} = m\mathbf{a}",
]


# ═══════════════════════════════════════════════════════════════════════════
# Tokenizer inline
# ═══════════════════════════════════════════════════════════════════════════

def spans(text):
    return list(iter_inline_math(text))


def kinds(text):
    return [k for k, _, _ in spans(text)]


class TestInlineTokenizer:
    def test_simple_inline(self):
        out = spans(f"il rapporto ${INLINE_BETA}$ tra le frequenze")
        assert [k for k, _, _ in out] == ['text', 'math', 'text']
        assert out[1][1] == INLINE_BETA
        assert out[1][2] == f"${INLINE_BETA}$"

    def test_multiple_inline_same_line(self):
        out = spans(r"con $\xi$ e $\beta$ si ottiene")
        assert [k for k, _, _ in out] == ['text', 'math', 'text', 'math', 'text']
        assert out[1][1] == r"\xi"
        assert out[3][1] == r"\beta"

    def test_display_span_mid_line(self):
        out = spans(rf"si scrive come $${DISPLAY_D}$$ dove")
        assert [k for k, _, _ in out] == ['text', 'math', 'text']
        assert out[1][1] == DISPLAY_D

    def test_currency_amounts_stay_text(self):
        for s in ("costa $50$", "tra $5 e $10", "il prezzo è 100$ al giorno",
                  "budget di $1.500$ euro", "paga 5$ e 10$"):
            assert kinds(s) == ['text'], s

    def test_escaped_dollar_not_delimiter(self):
        assert kinds(r"il simbolo \$ resta letterale \$") == ['text']

    def test_no_match_across_lines(self):
        assert kinds("apre $x\ne chiude$ dopo") == ['text']

    def test_whitespace_inside_delimiters_rejected(self):
        assert kinds("testo $ x $ testo") == ['text']

    def test_too_long_rejected(self):
        assert kinds("$" + "x+" * 150 + "x$") == ['text']

    def test_unbalanced_single_dollar(self):
        assert kinds("un solo $ nel testo") == ['text']

    def test_has_inline_math(self):
        assert has_inline_math(r"con $\beta$ si vede")
        assert not has_inline_math("nessuna formula qui")
        assert not has_inline_math("costa $50$")


# ═══════════════════════════════════════════════════════════════════════════
# Normalizzazione / sanitize
# ═══════════════════════════════════════════════════════════════════════════

class TestSanitize:
    def test_paren_bracket_delimiters(self):
        text = r"vale \( \beta \) e \[ E = mc^2 \]"
        out = normalize_math_delimiters(text)
        assert r"$\beta$" in out
        assert "$$E = mc^2$$" in out

    def test_display_canonicalized_on_isolated_line(self):
        text = f"si scrive come $${DISPLAY_D}$$ dove si vede"
        out = sanitize_generated_math(text)
        lines = out.split('\n')
        assert f"$${DISPLAY_D}$$" in lines
        idx = lines.index(f"$${DISPLAY_D}$$")
        assert lines[idx - 1] == '' and lines[idx + 1] == ''

    def test_multiline_display_collapsed(self):
        text = "prima\n\n$$\nD =\n\\frac{1}{2}\n$$\n\ndopo"
        out = sanitize_generated_math(text)
        assert "$$D = \\frac{1}{2}$$" in out.split('\n')

    def test_empty_display_removed(self):
        out = sanitize_generated_math("prima\n$$   $$\ndopo")
        assert '$$' not in out

    def test_unbalanced_dollars_untouched(self):
        text = "resta un $ solo nel testo"
        assert sanitize_generated_math(text) == text

    def test_text_without_math_identity(self):
        text = "capitolo senza formule.\n\nSeconda riga."
        assert sanitize_generated_math(text) == text


# ═══════════════════════════════════════════════════════════════════════════
# Protezione sentinelle
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE = (
    "# Capitolo uno\n"
    "\n"
    f"Il rapporto ${INLINE_BETA}$ governa la risposta e con $\\xi$ si ha:\n"
    "\n"
    f"$${DISPLAY_D}$$\n"
    "\n"
    "Testo di chiusura senza formule.\n"
)


class TestProtectRestore:
    def test_roundtrip_identity(self):
        protected, mapping = protect_math_spans(SAMPLE)
        assert len(mapping) == 3
        assert '$' not in protected
        assert 'ZZMATH0ZZ' in protected and 'ZZMATH2ZZ' in protected
        assert restore_math_spans(protected, mapping) == SAMPLE

    def test_display_sentinel_isolated_line(self):
        protected, mapping = protect_math_spans(SAMPLE)
        display_sentinels = [s for s, raw in mapping.items() if raw.startswith('$$')]
        assert len(display_sentinels) == 1
        assert display_sentinels[0] in protected.split('\n')

    def test_lost_sentinel_reappended(self):
        protected, mapping = protect_math_spans(SAMPLE)
        display_sentinel = next(s for s, raw in mapping.items() if raw.startswith('$$'))
        mangled = protected.replace(display_sentinel, '')
        restored = restore_math_spans(mangled, mapping)
        assert f"$${DISPLAY_D}$$" in restored  # mai persa

    def test_duplicated_sentinel_deduped(self):
        protected, mapping = protect_math_spans(SAMPLE)
        mangled = protected + "\nZZMATH0ZZ"
        restored = restore_math_spans(mangled, mapping)
        assert restored.count(f"${INLINE_BETA}$") == 1
        assert 'ZZMATH' not in restored

    def test_spurious_sentinel_stripped(self):
        restored = restore_math_spans("testo ZZMATH7ZZ pulito", {})
        assert restored == "testo  pulito"

    def test_no_math_no_change(self):
        text = "testo semplice senza dollari"
        protected, mapping = protect_math_spans(text)
        assert protected == text and mapping == {}

    def test_strip_math_sentinels(self):
        assert strip_math_sentinels("a ZZMATH0ZZ b ZZMATH12ZZ") == "a  b "

    def test_composes_with_asset_blocks(self):
        # La matematica dentro le celle tabella è già sequestrata da
        # protect_asset_blocks: protect_math_spans non deve toccarla.
        from thesis_assets import protect_asset_blocks, restore_asset_blocks
        text = (
            "Testo con $\\beta$ inline.\n"
            "\n"
            "[TABELLA: Valori]\n"
            "| Grandezza | Valore |\n"
            "| $\\omega_n$ | 12 |\n"
            "[/TABELLA]\n"
        )
        step1, asset_map = protect_asset_blocks(text)
        step2, math_map = protect_math_spans(step1)
        assert len(math_map) == 1  # solo il $\beta$ inline
        restored = restore_asset_blocks(restore_math_spans(step2, math_map), asset_map)
        assert "$\\omega_n$" in restored and "$\\beta$" in restored


# ═══════════════════════════════════════════════════════════════════════════
# Unicode
# ═══════════════════════════════════════════════════════════════════════════

class TestUnicode:
    def test_beta(self):
        assert latex_to_unicode(r"\beta") == "β"

    def test_frac_sqrt(self):
        out = latex_to_unicode(r"D = \frac{1}{\sqrt{(1-\beta^2)^2}}")
        assert "√" in out and "β" in out and "D" in out

    def test_inline_replacement(self):
        out = inline_math_to_unicode(r"il rapporto $\beta = \omega/\omega_n$ cresce")
        assert "β" in out and "ω" in out and "$" not in out

    def test_error_returns_source(self):
        assert latex_to_unicode("") == ""


# ═══════════════════════════════════════════════════════════════════════════
# Render PNG (mathtext)
# ═══════════════════════════════════════════════════════════════════════════

class TestRenderPng:
    def test_battery_renders_png(self):
        for latex in FORMULAS_BATTERY:
            mp = render_math_png(latex, fontsize=11.0, dpi=150)
            assert isinstance(mp, MathPng)
            assert mp.png[:8] == b'\x89PNG\r\n\x1a\n', latex
            assert mp.width_pt > 0 and mp.height_pt > 0

    def test_frac_has_depth(self):
        mp = render_math_png(DISPLAY_D, fontsize=11.0, dpi=150, display=True)
        assert mp.depth_pt > 0  # la frazione scende sotto il baseline

    def test_environment_raises(self):
        with pytest.raises(MathRenderError):
            render_math_png(r"\begin{matrix} a & b \end{matrix}", fontsize=11.0)

    def test_linebreak_raises(self):
        with pytest.raises(MathRenderError):
            render_math_png(r"a = b \\ c = d", fontsize=11.0)

    def test_sanitize_for_mathtext_rewrites(self):
        assert sanitize_for_mathtext(r"\text{IRR} > 0") == r"\mathrm{IRR} > 0"
        assert sanitize_for_mathtext(r"\dfrac{1}{2}") == r"\frac{1}{2}"
        assert sanitize_for_mathtext(r"x \label{eq:1} + \tag{3}") == "x  +"
        with pytest.raises(MathRenderError):
            sanitize_for_mathtext(r"\begin{align}x\end{align}")


# ═══════════════════════════════════════════════════════════════════════════
# OMML
# ═══════════════════════════════════════════════════════════════════════════

class TestOmml:
    def test_battery_converts(self):
        for latex in FORMULAS_BATTERY:
            el = latex_to_omml(latex)
            assert el.tag == f"{{{OMML_NS}}}oMath", latex

    def test_block_mode(self):
        el = latex_to_omml(DISPLAY_D, block=True)
        assert el.tag == f"{{{OMML_NS}}}oMath"

    def test_garbage_raises(self):
        with pytest.raises(MathRenderError):
            latex_to_omml("\\left(  aperto senza chiusura")


# ═══════════════════════════════════════════════════════════════════════════
# Parità con il parser frontend (fixture condivisa)
# ═══════════════════════════════════════════════════════════════════════════

class TestParityFixture:
    """La stessa fixture è verificata lato JS da frontend/tests/thesisMath.parity.test.mjs."""

    @staticmethod
    def _fixture():
        import json
        from pathlib import Path
        path = Path(__file__).parent / "fixtures" / "math_parity.json"
        return json.loads(path.read_text(encoding='utf-8'))

    def test_content_cases(self):
        from thesis_assets import assign_asset_numbers, parse_segments
        fx = self._fixture()
        for case in fx["content_cases"]:
            segs = parse_segments(case["content"])
            assign_asset_numbers(segs, fx["chapters_structure"])
            assert [s.kind for s in segs] == case["kinds"], case["name"]
            maths = [s.asset for s in segs if s.kind == 'math']
            assert [m.latex for m in maths] == case["math_latex"], case["name"]
            assert [m.label for m in maths] == case["math_labels"], case["name"]

    def test_inline_cases(self):
        fx = self._fixture()
        for case in fx["inline_cases"]:
            got = [[k, v] for k, v, _ in iter_inline_math(case["line"])]
            assert got == case["spans"], case["line"]


# ═══════════════════════════════════════════════════════════════════════════
# Regressioni dalla review avversariale
# ═══════════════════════════════════════════════════════════════════════════

from thesis_math import DISPLAY_LINE_RE, unprotect_math_spans


class TestReviewRegressions:
    def test_orphan_display_never_swallows_paragraphs(self):
        # $$ orfano (output troncato da max_tokens): la prosa dei paragrafi
        # successivi NON deve finire dentro una pseudo-formula
        text = ("Formula incompleta $$x = 1\n\n"
                "Questo paragrafo e' testo normale della tesi.\n\n"
                "$$y = 2$$\n\n"
                "Altro testo.")
        out = sanitize_generated_math(text)
        lines = out.split('\n')
        assert "Questo paragrafo e' testo normale della tesi." in lines
        assert "$$y = 2$$" in lines
        assert "Formula incompleta $$x = 1" in out  # orfano lasciato letterale

    def test_adjacent_inline_sequence_not_split(self):
        text = "Siano $a$$b$$c$ i coefficienti."
        assert sanitize_generated_math(text) == text

    def test_escaped_citation_brackets_untouched(self):
        # i modelli escapano spesso [1] in markdown: NON è una display
        text = r"Come dimostrato in \[1\], il fenomeno cresce."
        assert sanitize_generated_math(text) == text

    def test_escaped_parens_untouched(self):
        text = r"Il valore \(in euro\) raddoppia."
        assert sanitize_generated_math(text) == text

    def test_mathish_bracket_still_converted(self):
        out = sanitize_generated_math(r"vale \[ E = mc^2 \] sempre")
        assert "$$E = mc^2$$" in out.split('\n')

    def test_orphan_bracket_does_not_cross_lines(self):
        text = "Apro \\[ senza chiudere.\n\nParagrafo intermedio.\n\n\\[E = mc^2\\]"
        out = sanitize_generated_math(text)
        assert "Paragrafo intermedio." in out.split('\n')
        assert "$$E = mc^2$$" in out.split('\n')

    def test_display_line_accepts_escaped_dollar(self):
        line = r"$$\mathrm{costo\ in\ \$} = 5$$"
        assert DISPLAY_LINE_RE.match(line)
        protected, mapping = protect_math_spans(f"prima\n{line}\ndopo")
        assert len(mapping) == 1 and '$' not in protected

    def test_fence_with_escaped_dollar_collapsed_and_protected(self):
        text = "prima\n\n$$\n\\mathrm{costo\\ \\$} = 5\n$$\n\ndopo"
        out = sanitize_generated_math(text)
        assert "$$\\mathrm{costo\\ \\$} = 5$$" in out.split('\n')
        _, mapping = protect_math_spans(out)
        assert len(mapping) == 1

    def test_display_too_long_raises(self):
        with pytest.raises(MathRenderError):
            render_math_png("x+" * 1500, fontsize=11.0)
        with pytest.raises(MathRenderError):
            latex_to_omml("{" * 2500)

    def test_unprotect_partial_fragments(self):
        text = r"prima $\beta$ e poi $\xi$ fine"
        protected, mapping = protect_math_spans(text)
        s0, s1 = list(mapping)
        left, right = protected.split(' e poi ')
        assert unprotect_math_spans(left, mapping) == r"prima $\beta$"
        assert unprotect_math_spans(right, mapping) == r"$\xi$ fine"
        # nessun ri-append delle sentinelle assenti nel frammento
        assert s1 not in unprotect_math_spans(left, mapping)
