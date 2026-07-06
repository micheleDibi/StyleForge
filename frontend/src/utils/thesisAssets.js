/**
 * Parser client-side degli elementi visivi della tesi (tabelle/grafici/HINT).
 *
 * SPECCHIA backend/thesis_assets.py (sintassi e numerazione devono restare
 * allineate):
 *   [TABELLA: didascalia] ... | celle | ... [/TABELLA]
 *   [GRAFICO: didascalia] { spec JSON } [/GRAFICO]
 *   HINT: "testo del segnaposto"
 */

const TABLE_OPEN_RE = /^\s*\[TABELLA\s*:?\s*(.*?)\]\s*$/;
const TABLE_CLOSE_RE = /^\s*\[\/TABELLA\]\s*$/;
const CHART_OPEN_RE = /^\s*\[GRAFICO\s*:?\s*(.*?)\]\s*$/;
const CHART_CLOSE_RE = /^\s*\[\/GRAFICO\]\s*$/;
const HINT_RE = /^\s*HINT\s*:\s*(.+?)\s*$/;
const SOURCE_LINE_RE = /^\s*Fonte\s*:\s*(.+?)\s*$/i;
const MD_SEPARATOR_RE = /^\s*\|?[\s:|-]+\|?\s*$/;
const MAX_BLOCK_LINES = 80;
const CHART_TYPES = new Set(['bar', 'line', 'pie', 'scatter']);
const SPECIAL_TITLES = new Set(['introduzione', 'conclusione', 'conclusioni', 'bibliografia']);

const stripOuterQuotes = (s) => {
  let out = (s || '').trim();
  const pairs = [['"', '"'], ['“', '”'], ["'", "'"]];
  for (const [a, b] of pairs) {
    if (out.length >= 2 && out.startsWith(a) && out.endsWith(b)) {
      return out.slice(1, -1).trim();
    }
  }
  return out.replace(/^"+|"+$/g, '').trim();
};

const parseTableRow = (line) =>
  line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

const inlineNoteTokens = (cell) =>
  cell.replace(/\{\{\s*nota\s*:\s*(.*?)\}\}/g, '($1)');

const buildTable = (caption, bodyLines) => {
  let header = null;
  const rows = [];
  let source = null;
  for (const line of bodyLines) {
    if (!line.trim()) continue;
    if (MD_SEPARATOR_RE.test(line) && line.includes('|') && line.includes('-')) continue;
    const srcMatch = SOURCE_LINE_RE.exec(line);
    if (srcMatch && !line.trimStart().startsWith('|')) {
      source = srcMatch[1];
      continue;
    }
    if (line.trimStart().startsWith('|')) {
      const cells = parseTableRow(line).map(inlineNoteTokens);
      if (header === null) header = cells;
      else rows.push(cells);
    }
  }
  if (!header) return null;
  const n = header.length;
  const normRows = rows.map((r) => {
    const padded = [...r];
    while (padded.length < n) padded.push('');
    return padded.slice(0, n);
  });
  return { caption: caption.trim(), header, rows: normRows, source, label: null };
};

const validateChartSpec = (spec) => {
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return 'spec non valida';
  const ctype = String(spec.type || '').toLowerCase().trim();
  if (!CHART_TYPES.has(ctype)) return `tipo non supportato: ${ctype || '?'}`;
  if (!Array.isArray(spec.labels) || spec.labels.length === 0) return "'labels' mancante";
  if (!Array.isArray(spec.series) || spec.series.length === 0) return "'series' mancante";
  for (const s of spec.series) {
    if (!s || !Array.isArray(s.values) || s.values.length === 0) return "serie senza 'values'";
    if (s.values.some((v) => typeof v !== 'number' || Number.isNaN(v))) return 'valori non numerici';
  }
  return null;
};

const buildChart = (caption, bodyLines) => {
  const body = bodyLines.join('\n').trim();
  const start = body.indexOf('{');
  const end = body.lastIndexOf('}');
  if (start === -1 || end <= start) {
    return { caption: caption.trim(), spec: null, error: 'JSON mancante', label: null };
  }
  let spec;
  try {
    spec = JSON.parse(body.slice(start, end + 1));
  } catch {
    return { caption: caption.trim(), spec: null, error: 'JSON non valido', label: null };
  }
  const error = validateChartSpec(spec);
  return { caption: caption.trim(), spec, error, label: null };
};

/**
 * Divide il contenuto piatto della tesi in segmenti:
 *   {kind: 'text', text} | {kind: 'table', table} | {kind: 'chart', chart} | {kind: 'hint', text}
 * e assegna le etichette "Tabella N.M" / "Figura N.M" per capitolo.
 */
export function parseThesisContent(content, chaptersStructure) {
  const lines = (content || '').split('\n');
  const segments = [];
  let textBuf = [];

  const flushText = () => {
    if (textBuf.length) {
      const joined = textBuf.join('\n');
      if (joined.trim()) segments.push({ kind: 'text', text: joined });
      textBuf = [];
    }
  };

  const findClose = (start, closeRe) => {
    const limit = Math.min(start + MAX_BLOCK_LINES + 1, lines.length);
    for (let j = start; j < limit; j += 1) {
      if (closeRe.test(lines[j])) return j;
    }
    return -1;
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    const tOpen = TABLE_OPEN_RE.exec(line);
    if (tOpen) {
      const close = findClose(i + 1, TABLE_CLOSE_RE);
      if (close === -1) { i += 1; continue; }
      const table = buildTable(tOpen[1], lines.slice(i + 1, close));
      if (table) {
        flushText();
        segments.push({ kind: 'table', table });
      }
      i = close + 1;
      continue;
    }

    const cOpen = CHART_OPEN_RE.exec(line);
    if (cOpen) {
      const close = findClose(i + 1, CHART_CLOSE_RE);
      if (close === -1) { i += 1; continue; }
      flushText();
      segments.push({ kind: 'chart', chart: buildChart(cOpen[1], lines.slice(i + 1, close)) });
      i = close + 1;
      continue;
    }

    if (TABLE_CLOSE_RE.test(line) || CHART_CLOSE_RE.test(line)) { i += 1; continue; }

    const hint = HINT_RE.exec(line);
    if (hint) {
      flushText();
      segments.push({ kind: 'hint', text: stripOuterQuotes(hint[1]) });
      i += 1;
      continue;
    }

    textBuf.push(line);
    i += 1;
  }
  flushText();

  assignAssetNumbers(segments, chaptersStructure);
  return segments;
}

const normalizeTitle = (t) => (t || '').trim().toLowerCase();

function assignAssetNumbers(segments, chaptersStructure) {
  const titleToNum = new Map();
  const specialTitles = new Set(SPECIAL_TITLES);
  const chapters = (chaptersStructure && chaptersStructure.chapters) || [];
  let seq = 0;
  for (const ch of chapters) {
    const title = normalizeTitle(ch.chapter_title || ch.title || '');
    if (!title) continue;
    if (ch.is_special) specialTitles.add(title);
    else {
      seq += 1;
      titleToNum.set(title, ch.chapter_index || seq);
    }
  }

  let currentCh = null;
  let fallbackCounter = Math.max(0, ...titleToNum.values());
  let tableN = 0;
  let figureN = 0;
  let globalTableN = 0;
  let globalFigureN = 0;

  for (const seg of segments) {
    if (seg.kind === 'text') {
      for (const line of seg.text.split('\n')) {
        if (line.startsWith('# ') && !line.startsWith('## ')) {
          const title = normalizeTitle(line.slice(2));
          tableN = 0;
          figureN = 0;
          if (specialTitles.has(title)) currentCh = null;
          else if (titleToNum.has(title)) {
            currentCh = titleToNum.get(title);
            fallbackCounter = Math.max(fallbackCounter, currentCh);
          } else {
            fallbackCounter += 1;
            currentCh = fallbackCounter;
          }
        }
      }
    } else if (seg.kind === 'table') {
      if (currentCh !== null) {
        tableN += 1;
        seg.table.label = `Tabella ${currentCh}.${tableN}`;
      } else {
        globalTableN += 1;
        seg.table.label = `Tabella ${globalTableN}`;
      }
    } else if (seg.kind === 'chart') {
      if (currentCh !== null) {
        figureN += 1;
        seg.chart.label = `Figura ${currentCh}.${figureN}`;
      } else {
        globalFigureN += 1;
        seg.chart.label = `Figura ${globalFigureN}`;
      }
    }
  }
}

/** "Tabella 1.2 – didascalia" (o solo didascalia/label se manca l'altro). */
export function formatAssetCaption(asset) {
  const label = asset?.label;
  const caption = (asset?.caption || '').trim();
  if (label && caption) return `${label} – ${caption}`;
  return label || caption;
}

/** {tables: [{label, caption}], figures: [{label, caption}]} in ordine di documento. */
export function buildAssetIndices(segments) {
  const tables = [];
  const figures = [];
  for (const seg of segments) {
    if (seg.kind === 'table') tables.push({ label: seg.table.label || 'Tabella', caption: seg.table.caption });
    else if (seg.kind === 'chart') figures.push({ label: seg.chart.label || 'Figura', caption: seg.chart.caption });
  }
  return { tables, figures };
}
