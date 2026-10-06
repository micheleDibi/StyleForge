/**
 * Parità del parser matematica col backend (fixture condivisa).
 *
 * Esecuzione: node --test tests/
 * La stessa fixture è verificata lato Python da backend/test_thesis_math.py.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { splitMathSpans } from '../src/utils/thesisMath.js';
import { parseThesisContent } from '../src/utils/thesisAssets.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(join(here, '..', '..', 'backend', 'fixtures', 'math_parity.json'), 'utf-8')
);

test('content cases: segmenti, latex e numerazione identici al backend', () => {
  for (const c of fixture.content_cases) {
    const segs = parseThesisContent(c.content, fixture.chapters_structure);
    assert.deepEqual(segs.map((s) => s.kind), c.kinds, c.name);
    const maths = segs.filter((s) => s.kind === 'math').map((s) => s.math);
    assert.deepEqual(maths.map((m) => m.latex), c.math_latex, c.name);
    assert.deepEqual(maths.map((m) => m.label), c.math_labels, c.name);
  }
});

test('inline cases: span identici al backend', () => {
  for (const c of fixture.inline_cases) {
    const got = splitMathSpans(c.line).map((s) => [s.kind, s.value]);
    assert.deepEqual(got, c.spans, c.line);
  }
});
