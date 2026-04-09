import { useState, useEffect } from 'react';
import { GripVertical, Plus, Trash2, Edit3, Check, X, Sparkles, Loader, ChevronDown, ChevronRight, Brain, FileText, ListTree } from 'lucide-react';

const SectionEditor = ({ chapters = [], onChange, onConfirm, isLoading, isGenerating }) => {
  // Assicurati che chapters sia sempre un array
  const safeChapters = Array.isArray(chapters) ? chapters : [];

  const [expandedChapters, setExpandedChapters] = useState({});
  const [editingSection, setEditingSection] = useState(null); // { chapterIndex, sectionIndex }
  const [editValue, setEditValue] = useState('');
  const [editKeyPoints, setEditKeyPoints] = useState([]);
  const [generationStep, setGenerationStep] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');
  const [currentChapterGen, setCurrentChapterGen] = useState(1);

  // Inizializza expandedChapters quando safeChapters cambia
  useEffect(() => {
    if (safeChapters.length > 0) {
      setExpandedChapters(
        safeChapters.reduce((acc, ch) => ({ ...acc, [ch.chapter_index]: true }), {})
      );
    }
  }, [safeChapters.length]);

  // Simula progressi durante la generazione
  useEffect(() => {
    if (isGenerating) {
      const numChapters = safeChapters.length || 5;
      const stepsPerChapter = 2;
      const totalSteps = numChapters * stepsPerChapter;

      let currentStep = 0;
      const messages = [
        'Analisi della struttura del capitolo...',
        'Definizione delle sezioni...',
      ];

      const updateProgress = () => {
        currentStep++;
        const chapterNum = Math.ceil(currentStep / stepsPerChapter);
        const stepInChapter = ((currentStep - 1) % stepsPerChapter);

        setCurrentChapterGen(Math.min(chapterNum, numChapters));
        setGenerationStep(currentStep);
        setGenerationMessage(messages[stepInChapter] || 'Elaborazione...');
      };

      updateProgress();
      const interval = setInterval(() => {
        if (currentStep < totalSteps) {
          updateProgress();
        }
      }, 1500);

      return () => clearInterval(interval);
    } else {
      setGenerationStep(0);
      setGenerationMessage('');
      setCurrentChapterGen(1);
    }
  }, [isGenerating, safeChapters.length]);

  const toggleChapter = (chapterIndex) => {
    setExpandedChapters(prev => ({
      ...prev,
      [chapterIndex]: !prev[chapterIndex]
    }));
  };

  const handleEdit = (chapterIndex, sectionIndex) => {
    const chapter = safeChapters.find(ch => ch.chapter_index === chapterIndex);
    if (!chapter || !chapter.sections || !chapter.sections[sectionIndex]) return;
    const section = chapter.sections[sectionIndex];
    setEditingSection({ chapterIndex, sectionIndex });
    setEditValue(section.title || '');
    setEditKeyPoints(section.key_points || []);
  };

  const handleSave = () => {
    if (editValue.trim()) {
      const updated = safeChapters.map(ch => {
        if (ch.chapter_index === editingSection.chapterIndex) {
          const sections = [...(ch.sections || [])];
          sections[editingSection.sectionIndex] = {
            ...sections[editingSection.sectionIndex],
            title: editValue.trim(),
            key_points: editKeyPoints.filter(kp => kp.trim())
          };
          return { ...ch, sections };
        }
        return ch;
      });
      onChange(updated);
    }
    setEditingSection(null);
    setEditValue('');
    setEditKeyPoints([]);
  };

  const handleCancel = () => {
    setEditingSection(null);
    setEditValue('');
    setEditKeyPoints([]);
  };

  const handleDeleteSection = (chapterIndex, sectionIndex) => {
    const updated = safeChapters.map(ch => {
      if (ch.chapter_index === chapterIndex) {
        const sections = (ch.sections || []).filter((_, i) => i !== sectionIndex);
        // Reindex sections
        const reindexed = sections.map((s, i) => ({ ...s, index: i + 1 }));
        return { ...ch, sections: reindexed };
      }
      return ch;
    });
    onChange(updated);
  };

  const handleAddSection = (chapterIndex) => {
    const updated = safeChapters.map(ch => {
      if (ch.chapter_index === chapterIndex) {
        const sections = ch.sections || [];
        const newSection = {
          index: sections.length + 1,
          title: `Sezione ${sections.length + 1}`,
          key_points: []
        };
        return { ...ch, sections: [...sections, newSection] };
      }
      return ch;
    });
    onChange(updated);

    const chapter = updated.find(ch => ch.chapter_index === chapterIndex);
    if (chapter && chapter.sections) {
      handleEdit(chapterIndex, chapter.sections.length - 1);
    }
  };

  const handleAddKeyPoint = () => {
    setEditKeyPoints([...editKeyPoints, '']);
  };

  const handleKeyPointChange = (index, value) => {
    const updated = [...editKeyPoints];
    updated[index] = value;
    setEditKeyPoints(updated);
  };

  const handleRemoveKeyPoint = (index) => {
    setEditKeyPoints(editKeyPoints.filter((_, i) => i !== index));
  };

  if (isGenerating) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Sezioni</h2>
          <p className="text-slate-600">
            Stiamo generando le sezioni per ogni capitolo della tua tesi.
          </p>
        </div>

        <div className="card py-12">
          <div className="flex flex-col items-center gap-5">
            <div className="relative w-14 h-14">
              <div className="absolute inset-0 rounded-full border-[3px] border-slate-200"></div>
              <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-orange-500 animate-spin"></div>
            </div>
            <div className="text-center">
              <h3 className="text-lg font-semibold text-slate-800 mb-1">Generazione in corso...</h3>
              <p className="text-sm text-slate-500">
                {generationMessage || 'Elaborazione delle sezioni'}
              </p>
              {currentChapterGen > 0 && (
                <p className="text-xs text-slate-400 mt-2">
                  Capitolo {currentChapterGen} di {safeChapters.length || '...'}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Calcola totale sezioni
  const totalSections = safeChapters.reduce((sum, ch) => sum + (ch.sections || []).length, 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Struttura Sezioni</h2>
        <p className="text-slate-600">
          Rivedi e modifica le sezioni di ogni capitolo. Puoi aggiungere punti chiave per guidare la generazione.
        </p>
      </div>

      {/* Riepilogo */}
      {safeChapters.length > 0 && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2 text-green-700">
            <Check className="w-5 h-5" />
            <span className="font-medium">
              {totalSections} sezioni generate in {safeChapters.length} capitoli
            </span>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {safeChapters.length === 0 ? (
          <div className="card text-center py-8 text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>Nessun capitolo disponibile.</p>
          </div>
        ) : (
          safeChapters.map((chapter) => (
            <div key={chapter.chapter_index} className="card p-0 overflow-hidden">
              {/* Chapter Header */}
              <button
                onClick={() => toggleChapter(chapter.chapter_index)}
                className="w-full p-4 flex items-center gap-3 bg-gradient-to-r from-slate-50 to-white hover:from-slate-100 transition-colors"
              >
                <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center text-white font-bold">
                  {chapter.chapter_index}
                </div>
                <div className="flex-1 text-left">
                  <h3 className="font-semibold text-slate-900">{chapter.chapter_title}</h3>
                  <p className="text-sm text-slate-500">{(chapter.sections || []).length} sezioni</p>
                </div>
                {expandedChapters[chapter.chapter_index] ? (
                  <ChevronDown className="w-5 h-5 text-slate-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-slate-400" />
                )}
              </button>

              {/* Sections */}
              {expandedChapters[chapter.chapter_index] && (
                <div className="border-t border-slate-200 p-4 space-y-3">
                  {(chapter.sections || []).map((section, sectionIndex) => (
                    <div
                      key={section.index}
                      className="group flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200 hover:border-orange-300 transition-colors"
                    >
                      {/* Section Number */}
                      <div className="flex-shrink-0 w-8 h-8 bg-slate-200 rounded flex items-center justify-center text-slate-600 font-medium text-sm">
                        {chapter.chapter_index}.{section.index}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        {editingSection?.chapterIndex === chapter.chapter_index &&
                         editingSection?.sectionIndex === sectionIndex ? (
                          <div className="space-y-3">
                            <input
                              type="text"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="input w-full"
                              placeholder="Titolo della sezione"
                              autoFocus
                            />

                            {/* Key Points */}
                            <div className="space-y-2">
                              <label className="text-sm font-medium text-slate-700">
                                Punti chiave (opzionali)
                              </label>
                              {editKeyPoints.map((kp, i) => (
                                <div key={i} className="flex gap-2">
                                  <input
                                    type="text"
                                    value={kp}
                                    onChange={(e) => handleKeyPointChange(i, e.target.value)}
                                    className="input flex-1"
                                    placeholder={`Punto chiave ${i + 1}`}
                                  />
                                  <button
                                    onClick={() => handleRemoveKeyPoint(i)}
                                    className="p-2 hover:bg-red-50 rounded-lg"
                                  >
                                    <X className="w-4 h-4 text-red-500" />
                                  </button>
                                </div>
                              ))}
                              <button
                                onClick={handleAddKeyPoint}
                                className="text-sm text-orange-600 hover:text-orange-700"
                              >
                                + Aggiungi punto chiave
                              </button>
                            </div>

                            <div className="flex gap-2">
                              <button
                                onClick={handleSave}
                                className="btn-primary text-sm py-1.5 px-3"
                              >
                                <Check className="w-4 h-4 mr-1" />
                                Salva
                              </button>
                              <button
                                onClick={handleCancel}
                                className="btn-secondary text-sm py-1.5 px-3"
                              >
                                <X className="w-4 h-4 mr-1" />
                                Annulla
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <h4 className="font-medium text-slate-900">{section.title}</h4>
                            {section.key_points && section.key_points.length > 0 && (
                              <ul className="mt-1 text-sm text-slate-600 list-disc list-inside">
                                {section.key_points.map((kp, i) => (
                                  <li key={i}>{kp}</li>
                                ))}
                              </ul>
                            )}
                          </>
                        )}
                      </div>

                      {/* Actions */}
                      {!editingSection && (
                        <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleEdit(chapter.chapter_index, sectionIndex)}
                            className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
                            title="Modifica"
                          >
                            <Edit3 className="w-4 h-4 text-slate-600" />
                          </button>
                          <button
                            onClick={() => handleDeleteSection(chapter.chapter_index, sectionIndex)}
                            className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                            title="Elimina"
                            disabled={(chapter.sections || []).length <= 1}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Add Section Button */}
                  <button
                    onClick={() => handleAddSection(chapter.chapter_index)}
                    className="w-full p-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-orange-400 hover:text-orange-600 transition-colors flex items-center justify-center gap-2 text-sm"
                  >
                    <Plus className="w-4 h-4" />
                    Aggiungi Sezione
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Confirm Button */}
      <div className="flex justify-end">
        <button
          onClick={onConfirm}
          disabled={isLoading || safeChapters.length === 0 || safeChapters.some(ch => (ch.sections || []).length === 0)}
          className="btn-primary"
        >
          {isLoading ? (
            <>
              <Loader className="w-5 h-5 mr-2 animate-spin" />
              Salvataggio...
            </>
          ) : (
            <>
              <Check className="w-5 h-5 mr-2" />
              Conferma Sezioni e Genera Contenuto
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default SectionEditor;
