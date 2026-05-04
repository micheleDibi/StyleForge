import { jsPDF } from 'jspdf';

const PAGE_MARGIN_X = 15;
const PAGE_MARGIN_TOP = 18;
const PAGE_MARGIN_BOTTOM = 18;

function safeFilename(name) {
  return (name || 'tesi')
    .trim()
    .replace(/[^\p{L}\p{N}\-_ ]+/gu, '')
    .replace(/\s+/g, '_')
    .slice(0, 60) || 'tesi';
}

function ensureSpace(doc, y, neededMm = 8) {
  const pageH = doc.internal.pageSize.getHeight();
  if (y + neededMm > pageH - PAGE_MARGIN_BOTTOM) {
    doc.addPage();
    return PAGE_MARGIN_TOP;
  }
  return y;
}

function writeWrapped(doc, text, x, y, maxWidth, options = {}) {
  const {
    fontSize = 11,
    fontStyle = 'normal',
    lineHeightMm = 5.5,
    color = [30, 30, 30],
  } = options;

  doc.setFontSize(fontSize);
  doc.setFont('helvetica', fontStyle);
  doc.setTextColor(color[0], color[1], color[2]);

  const lines = doc.splitTextToSize(text || '', maxWidth);
  for (const line of lines) {
    y = ensureSpace(doc, y, lineHeightMm);
    doc.text(line, x, y);
    y += lineHeightMm;
  }
  return y;
}

/**
 * Esporta la struttura corrente della tesi in PDF.
 *
 * @param {Object}   params
 * @param {string}   params.title           Titolo della tesi
 * @param {string}   [params.description]   Descrizione/abstract opzionale
 * @param {Array}    params.chapters        Array di capitoli (formato wizard)
 * @param {'chapters'|'sections'} params.scope  'chapters' = solo capitoli; 'sections' = capitoli + sezioni
 */
export function exportThesisStructureToPdf({ title, description, chapters, scope = 'chapters' }) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const contentWidth = pageW - PAGE_MARGIN_X * 2;
  let y = PAGE_MARGIN_TOP;

  // Titolo principale
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(20);
  doc.setTextColor(20, 20, 20);
  const titleLines = doc.splitTextToSize(title || 'Tesi senza titolo', contentWidth);
  for (const line of titleLines) {
    y = ensureSpace(doc, y, 9);
    doc.text(line, PAGE_MARGIN_X, y);
    y += 9;
  }

  // Sottotitolo (scope)
  y += 2;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(11);
  doc.setTextColor(120, 120, 120);
  const subtitle = scope === 'sections'
    ? 'Struttura provvisoria — capitoli e sezioni'
    : 'Struttura provvisoria — capitoli';
  doc.text(subtitle, PAGE_MARGIN_X, y);
  y += 6;

  // Linea separatrice
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.3);
  doc.line(PAGE_MARGIN_X, y, pageW - PAGE_MARGIN_X, y);
  y += 8;

  // Descrizione (se presente)
  if (description && description.trim()) {
    y = writeWrapped(doc, 'Descrizione', PAGE_MARGIN_X, y, contentWidth, {
      fontSize: 12, fontStyle: 'bold', lineHeightMm: 6, color: [60, 60, 60],
    });
    y += 1;
    y = writeWrapped(doc, description.trim(), PAGE_MARGIN_X, y, contentWidth, {
      fontSize: 10.5, fontStyle: 'normal', lineHeightMm: 5, color: [60, 60, 60],
    });
    y += 5;
  }

  // Capitoli
  const list = Array.isArray(chapters) ? chapters : [];
  if (list.length === 0) {
    y = writeWrapped(doc, 'Nessun capitolo disponibile.', PAGE_MARGIN_X, y, contentWidth, {
      fontSize: 11, fontStyle: 'italic', color: [120, 120, 120],
    });
  } else {
    list.forEach((chapter, idx) => {
      const chNum = chapter.chapter_index || chapter.index || (idx + 1);
      const chTitle = chapter.chapter_title || chapter.title || `Capitolo ${chNum}`;

      y = ensureSpace(doc, y, 12);
      y += 4;
      y = writeWrapped(
        doc,
        `Capitolo ${chNum}: ${chTitle}`,
        PAGE_MARGIN_X,
        y,
        contentWidth,
        { fontSize: 13, fontStyle: 'bold', lineHeightMm: 6.5, color: [220, 90, 30] }
      );

      const chDesc = chapter.description || chapter.brief_description;
      if (chDesc && chDesc.trim()) {
        y = writeWrapped(doc, chDesc.trim(), PAGE_MARGIN_X, y, contentWidth, {
          fontSize: 10.5, fontStyle: 'italic', lineHeightMm: 5, color: [80, 80, 80],
        });
      }

      // Sezioni (se richieste)
      if (scope === 'sections') {
        const sections = Array.isArray(chapter.sections) ? chapter.sections : [];
        if (sections.length === 0) {
          y = writeWrapped(doc, '— nessuna sezione definita —', PAGE_MARGIN_X + 6, y, contentWidth - 6, {
            fontSize: 10, fontStyle: 'italic', color: [150, 150, 150],
          });
        } else {
          sections.forEach((section, sIdx) => {
            const sNum = section.index || (sIdx + 1);
            const sTitle = section.title || `Sezione ${sNum}`;
            y = ensureSpace(doc, y, 8);
            y = writeWrapped(
              doc,
              `${chNum}.${sNum}  ${sTitle}`,
              PAGE_MARGIN_X + 6,
              y,
              contentWidth - 6,
              { fontSize: 11, fontStyle: 'bold', lineHeightMm: 5.5, color: [50, 50, 50] }
            );

            const keyPoints = Array.isArray(section.key_points) ? section.key_points : [];
            for (const kp of keyPoints) {
              if (!kp || !kp.trim()) continue;
              y = writeWrapped(
                doc,
                `• ${kp.trim()}`,
                PAGE_MARGIN_X + 12,
                y,
                contentWidth - 12,
                { fontSize: 10, fontStyle: 'normal', lineHeightMm: 4.6, color: [80, 80, 80] }
              );
            }
            y += 1;
          });
        }
      }
      y += 2;
    });
  }

  // Footer pagina
  const totalPages = doc.getNumberOfPages();
  const pageH = doc.internal.pageSize.getHeight();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(160, 160, 160);
    const stamp = `Bozza struttura — pagina ${i} di ${totalPages}`;
    const w = doc.getTextWidth(stamp);
    doc.text(stamp, (pageW - w) / 2, pageH - 8);
  }

  const filename = `${safeFilename(title)}_${scope === 'sections' ? 'capitoli_sezioni' : 'capitoli'}.pdf`;
  doc.save(filename);
}

export default exportThesisStructureToPdf;
