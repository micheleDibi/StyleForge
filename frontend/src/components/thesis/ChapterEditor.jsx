import { useState, useEffect } from 'react';
import { GripVertical, Plus, Trash2, Edit3, Check, X, Sparkles, Loader, BookOpen, Brain, ListTree } from 'lucide-react';

const ChapterEditor = ({ chapters = [], onChange, onConfirm, isLoading, isGenerating }) => {
  const [editingIndex, setEditingIndex] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [generationStep, setGenerationStep] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');

  // Assicurati che chapters sia sempre un array
  const safeChapters = Array.isArray(chapters) ? chapters : [];

  // Simula progressi durante la generazione
  useEffect(() => {
    if (isGenerating) {
      const steps = [
        { step: 1, message: 'Analisi del titolo e della descrizione...' },
        { step: 2, message: 'Valutazione degli argomenti chiave...' },
        { step: 3, message: 'Determinazione dello stile di scrittura...' },
        { step: 4, message: 'Analisi del pubblico target...' },
        { step: 5, message: 'Strutturazione della progressione logica...' },
        { step: 6, message: 'Generazione dei titoli dei capitoli...' },
        { step: 7, message: 'Creazione delle descrizioni...' },
        { step: 8, message: 'Ottimizzazione della struttura...' },
        { step: 9, message: 'Verifica della coerenza...' },
        { step: 10, message: 'Finalizzazione dei capitoli...' }
      ];

      let currentIndex = 0;
      setGenerationStep(steps[0].step);
      setGenerationMessage(steps[0].message);

      const interval = setInterval(() => {
        currentIndex++;
        if (currentIndex < steps.length) {
          setGenerationStep(steps[currentIndex].step);
          setGenerationMessage(steps[currentIndex].message);
        }
      }, 2500);

      return () => clearInterval(interval);
    } else {
      setGenerationStep(0);
      setGenerationMessage('');
    }
  }, [isGenerating]);

  const handleEdit = (index) => {
    setEditingIndex(index);
    setEditValue(safeChapters[index]?.title || '');
    setEditDescription(safeChapters[index]?.description || safeChapters[index]?.brief_description || '');
  };

  const handleSave = () => {
    if (editValue.trim()) {
      const updated = [...safeChapters];
      updated[editingIndex] = {
        ...updated[editingIndex],
        title: editValue.trim(),
        description: editDescription.trim(),
        brief_description: editDescription.trim()
      };
      onChange(updated);
    }
    setEditingIndex(null);
    setEditValue('');
    setEditDescription('');
  };

  const handleCancel = () => {
    setEditingIndex(null);
    setEditValue('');
    setEditDescription('');
  };

  const handleDelete = (index) => {
    const updated = safeChapters.filter((_, i) => i !== index);
    // Aggiorna gli indici
    const reindexed = updated.map((ch, i) => ({ ...ch, index: i + 1 }));
    onChange(reindexed);
  };

  const handleAdd = () => {
    const newChapter = {
      index: safeChapters.length + 1,
      title: `Capitolo ${safeChapters.length + 1}`,
      description: '',
      brief_description: ''
    };
    onChange([...safeChapters, newChapter]);
    handleEdit(safeChapters.length);
  };

  const handleDragStart = (e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const updated = [...safeChapters];
    const [removed] = updated.splice(draggedIndex, 1);
    updated.splice(index, 0, removed);

    // Reindex
    const reindexed = updated.map((ch, i) => ({ ...ch, index: i + 1 }));
    onChange(reindexed);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  // Mostra loading durante la generazione
  if (isGenerating) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Capitoli</h2>
          <p className="text-slate-600">
            Stiamo generando la struttura dei capitoli in base ai tuoi parametri.
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
                {generationMessage || 'Elaborazione della struttura dei capitoli'}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Struttura Capitoli</h2>
        <p className="text-slate-600">
          Rivedi e modifica i capitoli generati dall'AI. Puoi riordinare, aggiungere o rimuovere capitoli.
        </p>
      </div>

      <div className="card space-y-4">
        {safeChapters.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <BookOpen className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>Nessun capitolo generato.</p>
            <p className="text-sm">Clicca "Aggiungi Capitolo" per iniziare.</p>
          </div>
        ) : (
          <>
            {/* Riepilogo */}
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg mb-4">
              <div className="flex items-center gap-2 text-green-700">
                <Check className="w-5 h-5" />
                <span className="font-medium">{safeChapters.length} capitoli generati</span>
              </div>
            </div>

            <div className="space-y-3">
              {safeChapters.map((chapter, index) => (
                <div
                  key={chapter.index || index}
                  draggable={editingIndex === null}
                  onDragStart={(e) => handleDragStart(e, index)}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDragEnd={handleDragEnd}
                  className={`
                    group flex items-start gap-3 p-4 bg-slate-50 rounded-lg border transition-all
                    ${draggedIndex === index ? 'border-orange-400 bg-orange-50' : 'border-slate-200'}
                    ${editingIndex === null ? 'cursor-move hover:border-orange-300' : ''}
                  `}
                >
                  {/* Drag Handle */}
                  <div className="flex-shrink-0 pt-1">
                    <GripVertical className="w-5 h-5 text-slate-400" />
                  </div>

                  {/* Chapter Number */}
                  <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center text-white font-bold">
                    {chapter.index || index + 1}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    {editingIndex === index ? (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="input w-full"
                          placeholder="Titolo del capitolo"
                          autoFocus
                        />
                        <textarea
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                          className="input w-full resize-none"
                          rows={2}
                          placeholder="Breve descrizione (opzionale)"
                        />
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
                        <h3 className="font-semibold text-slate-900">{chapter.title}</h3>
                        {(chapter.description || chapter.brief_description) && (
                          <p className="text-sm text-slate-600 mt-1">
                            {chapter.description || chapter.brief_description}
                          </p>
                        )}
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  {editingIndex === null && (
                    <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEdit(index)}
                        className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
                        title="Modifica"
                      >
                        <Edit3 className="w-4 h-4 text-slate-600" />
                      </button>
                      <button
                        onClick={() => handleDelete(index)}
                        className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                        title="Elimina"
                        disabled={safeChapters.length <= 1}
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Add Chapter Button */}
        <button
          onClick={handleAdd}
          className="w-full p-3 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-orange-400 hover:text-orange-600 transition-colors flex items-center justify-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Aggiungi Capitolo
        </button>
      </div>

      {/* Confirm Button */}
      <div className="flex justify-end mt-6">
        <button
          onClick={onConfirm}
          disabled={isLoading || safeChapters.length === 0}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader className="w-5 h-5 animate-spin" />
              Salvataggio...
            </>
          ) : (
            <>
              <Check className="w-5 h-5" />
              Conferma Capitoli e Continua
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default ChapterEditor;
