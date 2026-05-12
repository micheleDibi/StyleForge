import { useMemo } from 'react';
import { Plus, Trash2, ChevronUp, ChevronDown, ListTree, BookText } from 'lucide-react';

/**
 * Editor strutturato per l'indice custom della tesi.
 * Permette all'utente di definire manualmente capitoli e paragrafi (sezioni),
 * con add/remove/riordino (bottoni ↑↓, no drag-and-drop per evitare dipendenze).
 *
 * Props:
 *   value:    { chapters: [{ title, brief_description, sections: [{ title, key_points: [] }] }] }
 *             oppure null/undefined (in cui caso si inizializza con 1 capitolo + 1 sezione vuoti)
 *   onChange: (newValue) => void  — invocato ad ogni modifica
 */

const newSection = () => ({ title: '', key_points: [] });
const newChapter = () => ({ title: '', brief_description: '', sections: [newSection()] });

const ensureValid = (value) => {
  if (!value || !Array.isArray(value.chapters) || value.chapters.length === 0) {
    return { chapters: [newChapter()] };
  }
  // Sanifica: ogni capitolo deve avere almeno 1 sezione
  return {
    chapters: value.chapters.map((c) => ({
      title: c?.title || '',
      brief_description: c?.brief_description || '',
      sections: (c?.sections && c.sections.length > 0)
        ? c.sections.map((s) => ({
            title: s?.title || '',
            key_points: Array.isArray(s?.key_points) ? s.key_points : [],
          }))
        : [newSection()],
    })),
  };
};

const CustomOutlineEditor = ({ value, onChange }) => {
  const outline = useMemo(() => ensureValid(value), [value]);

  const update = (next) => onChange(next);

  const setChapterField = (chIdx, field, val) => {
    const next = { chapters: outline.chapters.map((c, i) => i === chIdx ? { ...c, [field]: val } : c) };
    update(next);
  };

  const setSectionField = (chIdx, secIdx, field, val) => {
    const next = {
      chapters: outline.chapters.map((c, i) => i !== chIdx ? c : {
        ...c,
        sections: c.sections.map((s, j) => j === secIdx ? { ...s, [field]: val } : s),
      })
    };
    update(next);
  };

  const setSectionKeyPoints = (chIdx, secIdx, text) => {
    const kps = text
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    setSectionField(chIdx, secIdx, 'key_points', kps);
  };

  const addChapter = () => {
    update({ chapters: [...outline.chapters, newChapter()] });
  };

  const removeChapter = (chIdx) => {
    if (outline.chapters.length <= 1) return; // almeno 1 capitolo
    update({ chapters: outline.chapters.filter((_, i) => i !== chIdx) });
  };

  const moveChapter = (chIdx, dir) => {
    const newIdx = chIdx + dir;
    if (newIdx < 0 || newIdx >= outline.chapters.length) return;
    const arr = [...outline.chapters];
    [arr[chIdx], arr[newIdx]] = [arr[newIdx], arr[chIdx]];
    update({ chapters: arr });
  };

  const addSection = (chIdx) => {
    update({
      chapters: outline.chapters.map((c, i) => i !== chIdx ? c : {
        ...c,
        sections: [...c.sections, newSection()],
      })
    });
  };

  const removeSection = (chIdx, secIdx) => {
    const chapter = outline.chapters[chIdx];
    if (chapter.sections.length <= 1) return; // almeno 1 sezione
    update({
      chapters: outline.chapters.map((c, i) => i !== chIdx ? c : {
        ...c,
        sections: c.sections.filter((_, j) => j !== secIdx),
      })
    });
  };

  const moveSection = (chIdx, secIdx, dir) => {
    const chapter = outline.chapters[chIdx];
    const newIdx = secIdx + dir;
    if (newIdx < 0 || newIdx >= chapter.sections.length) return;
    const arr = [...chapter.sections];
    [arr[secIdx], arr[newIdx]] = [arr[newIdx], arr[secIdx]];
    update({
      chapters: outline.chapters.map((c, i) => i !== chIdx ? c : { ...c, sections: arr })
    });
  };

  const totalChapters = outline.chapters.length;
  const totalSections = outline.chapters.reduce((acc, c) => acc + c.sections.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
        <ListTree className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold">Stai definendo manualmente l'indice della tesi</p>
          <p className="text-xs mt-1">
            Inserisci capitoli e paragrafi. L'AI <strong>non genererà</strong> la struttura: useremo
            esattamente l'ordine e i titoli che fornisci qui. Negli step Capitoli e Sezioni potrai
            comunque rifinire prima della generazione del contenuto.
          </p>
        </div>
      </div>

      {/* Riepilogo */}
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <BookText className="w-4 h-4" />
        <span>
          <strong>{totalChapters}</strong> capitoli, <strong>{totalSections}</strong> paragrafi totali
        </span>
      </div>

      {/* Lista capitoli */}
      <div className="space-y-3">
        {outline.chapters.map((chapter, chIdx) => (
          <div
            key={chIdx}
            className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden"
          >
            {/* Header capitolo */}
            <div className="flex items-start gap-2 p-4 bg-gradient-to-r from-orange-50/50 to-amber-50/30 border-b border-slate-100">
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 text-white text-sm font-bold flex items-center justify-center mt-1">
                {chIdx + 1}
              </div>
              <div className="flex-1 min-w-0 space-y-2">
                <input
                  type="text"
                  value={chapter.title}
                  onChange={(e) => setChapterField(chIdx, 'title', e.target.value)}
                  placeholder={`Titolo capitolo ${chIdx + 1}`}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-slate-900 font-semibold focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400"
                />
                <textarea
                  value={chapter.brief_description}
                  onChange={(e) => setChapterField(chIdx, 'brief_description', e.target.value)}
                  placeholder="Descrizione breve del capitolo (opzionale)"
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 resize-y focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400"
                />
              </div>
              {/* Bottoni capitolo */}
              <div className="flex flex-col gap-1 ml-2">
                <button
                  type="button"
                  onClick={() => moveChapter(chIdx, -1)}
                  disabled={chIdx === 0}
                  className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                  title="Sposta su"
                >
                  <ChevronUp className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => moveChapter(chIdx, 1)}
                  disabled={chIdx === outline.chapters.length - 1}
                  className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                  title="Sposta giù"
                >
                  <ChevronDown className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => removeChapter(chIdx)}
                  disabled={outline.chapters.length <= 1}
                  className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                  title="Rimuovi capitolo"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Lista sezioni */}
            <div className="p-4 space-y-2">
              {chapter.sections.map((section, secIdx) => (
                <div
                  key={secIdx}
                  className="flex items-start gap-2 p-3 rounded-xl border border-slate-100 bg-slate-50/50"
                >
                  <div className="flex-shrink-0 w-7 h-7 rounded-md bg-white border border-slate-200 text-slate-600 text-xs font-medium flex items-center justify-center mt-1">
                    {chIdx + 1}.{secIdx + 1}
                  </div>
                  <div className="flex-1 min-w-0 space-y-2">
                    <input
                      type="text"
                      value={section.title}
                      onChange={(e) => setSectionField(chIdx, secIdx, 'title', e.target.value)}
                      placeholder={`Titolo paragrafo ${chIdx + 1}.${secIdx + 1}`}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-900 font-medium bg-white focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400"
                    />
                    <textarea
                      value={(section.key_points || []).join('\n')}
                      onChange={(e) => setSectionKeyPoints(chIdx, secIdx, e.target.value)}
                      placeholder="Punti chiave (uno per riga, opzionali)"
                      rows={2}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 bg-white resize-y focus:outline-none focus:ring-2 focus:ring-orange-400/30 focus:border-orange-400"
                    />
                  </div>
                  <div className="flex flex-col gap-0.5 ml-1">
                    <button
                      type="button"
                      onClick={() => moveSection(chIdx, secIdx, -1)}
                      disabled={secIdx === 0}
                      className="p-1 rounded text-slate-500 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                      title="Sposta su"
                    >
                      <ChevronUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveSection(chIdx, secIdx, 1)}
                      disabled={secIdx === chapter.sections.length - 1}
                      className="p-1 rounded text-slate-500 hover:bg-white disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                      title="Sposta giù"
                    >
                      <ChevronDown className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeSection(chIdx, secIdx)}
                      disabled={chapter.sections.length <= 1}
                      className="p-1 rounded text-red-500 hover:bg-red-50 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                      title="Rimuovi paragrafo"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}

              <button
                type="button"
                onClick={() => addSection(chIdx)}
                className="mt-1 inline-flex items-center gap-2 text-sm font-medium text-orange-700 hover:text-orange-800 hover:bg-orange-50 px-2.5 py-1.5 rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Aggiungi paragrafo
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addChapter}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl border-2 border-dashed border-orange-300 bg-orange-50/50 text-orange-700 font-semibold hover:bg-orange-100 hover:border-orange-400 transition-colors"
      >
        <Plus className="w-5 h-5" />
        Aggiungi capitolo
      </button>
    </div>
  );
};

export default CustomOutlineEditor;
