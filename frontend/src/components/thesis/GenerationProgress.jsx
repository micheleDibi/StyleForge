import { useState, useEffect, useMemo } from 'react';
import { Loader, CheckCircle, AlertCircle, ChevronDown, ChevronRight, FileText } from 'lucide-react';

const GenerationProgress = ({ status, onComplete }) => {
  const [expandedChapters, setExpandedChapters] = useState({});

  useEffect(() => {
    if (status?.status === 'completed' && onComplete) {
      onComplete();
    }
  }, [status?.status, onComplete]);

  const toggleChapter = (chapterIndex) => {
    setExpandedChapters(prev => ({ ...prev, [chapterIndex]: !prev[chapterIndex] }));
  };

  const {
    generationStatus, progress, totalSections, completedSections,
    currentChapter, currentSection, chaptersData, errorMessage
  } = useMemo(() => {
    if (!status) return {
      generationStatus: 'pending', progress: 0, totalSections: 0,
      completedSections: 0, currentChapter: null, currentSection: null,
      chaptersData: [], errorMessage: null
    };
    return {
      generationStatus: status.status || 'generating',
      progress: status.generation_progress ?? status.overall_progress ?? 0,
      totalSections: status.total_sections ?? 0,
      completedSections: status.completed_sections ?? 0,
      currentChapter: status.current_chapter,
      currentSection: status.current_section,
      chaptersData: status.chapters || status.chapters_status || [],
      errorMessage: status.error || null
    };
  }, [status]);

  // Stato iniziale
  if (!status) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Contenuto</h2>
          <p className="text-slate-600">Preparazione della generazione in corso...</p>
        </div>
        <div className="card py-12">
          <div className="flex flex-col items-center gap-5">
            <div className="relative w-14 h-14">
              <div className="absolute inset-0 rounded-full border-[3px] border-slate-200"></div>
              <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-orange-500 animate-spin"></div>
            </div>
            <p className="text-sm text-slate-500">Inizializzazione...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Contenuto</h2>
        <p className="text-slate-600">
          {generationStatus === 'completed'
            ? 'Generazione completata! La tua tesi e pronta.'
            : generationStatus === 'failed'
            ? 'Si e verificato un errore durante la generazione.'
            : 'Il contenuto viene generato sezione per sezione.'}
        </p>
      </div>

      {/* Progress card */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {generationStatus === 'completed' ? (
              <CheckCircle className="w-6 h-6 text-green-500" />
            ) : generationStatus === 'failed' ? (
              <AlertCircle className="w-6 h-6 text-red-500" />
            ) : (
              <Loader className="w-6 h-6 text-orange-500 animate-spin" />
            )}
            <div>
              <p className="font-semibold text-slate-900">
                {generationStatus === 'completed' ? 'Completato' :
                 generationStatus === 'failed' ? 'Errore' : 'Generazione in corso...'}
              </p>
              {generationStatus === 'generating' && totalSections > 0 && (
                <p className="text-sm text-slate-500">
                  Sezione {completedSections + 1} di {totalSections}
                </p>
              )}
            </div>
          </div>
          <span className="text-2xl font-bold text-slate-900">{Math.round(progress)}%</span>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-700 ${
              generationStatus === 'completed' ? 'bg-green-500' :
              generationStatus === 'failed' ? 'bg-red-500' : 'bg-orange-500'
            }`}
            style={{ width: `${Math.max(progress, 1)}%` }}
          />
        </div>

        {/* Stats */}
        {totalSections > 0 && (
          <div className="flex gap-6 mt-4 text-sm text-slate-600">
            <span><strong className="text-slate-900">{completedSections}</strong> completate</span>
            <span><strong className="text-slate-900">{totalSections - completedSections}</strong> rimanenti</span>
            <span><strong className="text-slate-900">{totalSections}</strong> totali</span>
          </div>
        )}

        {/* Error */}
        {errorMessage && (
          <div className={`mt-4 p-3 rounded-lg text-sm ${
            errorMessage.toLowerCase().includes('crediti')
              ? 'bg-amber-50 border border-amber-200 text-amber-800'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            <p className="font-medium">
              {errorMessage.toLowerCase().includes('crediti') ? 'Crediti insufficienti' : 'Errore'}
            </p>
            <p className="mt-1">{errorMessage.replace('CREDITI_INSUFFICIENTI: ', '')}</p>
          </div>
        )}
      </div>

      {/* Dettaglio Capitoli */}
      {chaptersData.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Progresso per capitolo</h3>
          {chaptersData.map((chapter, idx) => {
            const chapterIndex = chapter.chapter_index ?? idx;
            const isCurrentChapter = currentChapter === chapterIndex;
            const chapterProgress = chapter.total_sections > 0
              ? Math.round(((chapter.completed_sections ?? 0) / chapter.total_sections) * 100) : 0;

            return (
              <div key={chapterIndex} className="border border-slate-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => toggleChapter(chapterIndex)}
                  className={`w-full px-4 py-3 flex items-center gap-3 text-left transition-colors ${
                    chapter.status === 'completed' ? 'bg-green-50' :
                    isCurrentChapter ? 'bg-orange-50' : 'bg-white hover:bg-slate-50'
                  }`}
                >
                  {chapter.status === 'completed' ? (
                    <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                  ) : isCurrentChapter ? (
                    <Loader className="w-4 h-4 text-orange-500 animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-300 flex-shrink-0" />
                  )}
                  <span className="flex-1 text-sm font-medium text-slate-800 truncate">
                    Cap. {chapterIndex + 1}: {chapter.chapter_title || `Capitolo ${chapterIndex + 1}`}
                  </span>
                  <span className="text-xs text-slate-500 mr-2">
                    {chapter.completed_sections ?? 0}/{chapter.total_sections ?? 0}
                  </span>
                  <div className="w-16 bg-slate-200 rounded-full h-1.5 overflow-hidden mr-2">
                    <div
                      className={`h-1.5 rounded-full ${chapter.status === 'completed' ? 'bg-green-500' : 'bg-orange-500'}`}
                      style={{ width: `${chapterProgress}%` }}
                    />
                  </div>
                  {expandedChapters[chapterIndex] ? (
                    <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  )}
                </button>

                {expandedChapters[chapterIndex] && chapter.sections && (
                  <div className="border-t border-slate-100 px-4 py-2 space-y-1 bg-slate-50">
                    {chapter.sections.map((section, secIdx) => {
                      const sectionIndex = section.section_index ?? secIdx;
                      const isCurrentSec = isCurrentChapter && currentSection === sectionIndex;
                      return (
                        <div key={sectionIndex} className="flex items-center gap-2.5 py-1.5 text-sm">
                          {section.status === 'completed' ? (
                            <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                          ) : isCurrentSec ? (
                            <Loader className="w-3.5 h-3.5 text-orange-500 animate-spin flex-shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 flex-shrink-0" />
                          )}
                          <span className={`flex-1 truncate ${isCurrentSec ? 'text-orange-700 font-medium' : 'text-slate-600'}`}>
                            {section.section_title || section.title || `Sezione ${sectionIndex + 1}`}
                          </span>
                          {section.words_count > 0 && (
                            <span className="text-xs text-slate-400">{section.words_count.toLocaleString()} parole</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Completamento */}
      {generationStatus === 'completed' && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-xl flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          <div>
            <p className="font-semibold text-green-800">Tesi generata con successo!</p>
            <p className="text-sm text-green-700">
              Tutte le {totalSections} sezioni sono state generate. Puoi visualizzare l'anteprima e scaricare il documento.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default GenerationProgress;
