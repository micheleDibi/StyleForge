import { useState, useEffect, useMemo } from 'react';
import { Sparkles, Loader, CheckCircle, Clock, AlertCircle, ChevronDown, ChevronRight, FileText, Brain, Zap } from 'lucide-react';

// Messaggi dinamici per la generazione
const GENERATION_MESSAGES = [
  { message: "Analisi della struttura del documento...", icon: FileText },
  { message: "Elaborazione del contesto e delle fonti...", icon: Brain },
  { message: "Generazione del contenuto in corso...", icon: Sparkles },
  { message: "Applicazione dello stile di scrittura...", icon: Zap },
  { message: "Ottimizzazione della coerenza testuale...", icon: Brain },
  { message: "Revisione e rifinitura del testo...", icon: FileText },
];

const GenerationProgress = ({ status, onComplete }) => {
  const [expandedChapters, setExpandedChapters] = useState({});
  const [messageIndex, setMessageIndex] = useState(0);
  const [dots, setDots] = useState('');

  // Cicla i messaggi dinamici
  useEffect(() => {
    const messageInterval = setInterval(() => {
      setMessageIndex(prev => (prev + 1) % GENERATION_MESSAGES.length);
    }, 4000);

    return () => clearInterval(messageInterval);
  }, []);

  // Animazione puntini
  useEffect(() => {
    const dotsInterval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => clearInterval(dotsInterval);
  }, []);

  useEffect(() => {
    if (status?.status === 'completed' && onComplete) {
      onComplete();
    }
  }, [status?.status, onComplete]);

  const toggleChapter = (chapterIndex) => {
    setExpandedChapters(prev => ({
      ...prev,
      [chapterIndex]: !prev[chapterIndex]
    }));
  };

  const getStatusIcon = (itemStatus) => {
    switch (itemStatus) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'in_progress':
        return <Loader className="w-5 h-5 text-orange-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getStatusColor = (itemStatus) => {
    switch (itemStatus) {
      case 'completed':
        return 'bg-green-50 border-green-200';
      case 'in_progress':
        return 'bg-orange-50 border-orange-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-slate-50 border-slate-200';
    }
  };

  // Estrai e normalizza i dati dallo status (gestisce nomi diversi dal backend)
  const {
    generationStatus,
    progress,
    totalSections,
    completedSections,
    currentChapter,
    currentSection,
    chaptersData,
    errorMessage
  } = useMemo(() => {
    if (!status) {
      return {
        generationStatus: 'pending',
        progress: 0,
        totalSections: 0,
        completedSections: 0,
        currentChapter: null,
        currentSection: null,
        chaptersData: [],
        errorMessage: null
      };
    }

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

  // Messaggio corrente basato sullo stato
  const currentMessage = useMemo(() => {
    if (generationStatus === 'completed') return 'Generazione completata!';
    if (generationStatus === 'failed') return 'Errore nella generazione';
    return GENERATION_MESSAGES[messageIndex].message;
  }, [generationStatus, messageIndex]);

  const CurrentIcon = GENERATION_MESSAGES[messageIndex].icon;

  // Stato iniziale: in attesa di dati
  if (!status) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Contenuto</h2>
          <p className="text-slate-600">Preparazione della generazione in corso...</p>
        </div>

        {/* Card principale con animazione */}
        <div className="card bg-gradient-to-br from-orange-50 to-red-50 border-orange-200">
          <div className="flex flex-col items-center justify-center py-12">
            {/* Icona animata */}
            <div className="relative mb-6">
              <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg">
                <Brain className="w-10 h-10 text-white animate-pulse" />
              </div>
              <div className="absolute -bottom-2 -right-2 w-8 h-8 bg-white rounded-full flex items-center justify-center shadow-md">
                <Loader className="w-5 h-5 text-orange-500 animate-spin" />
              </div>
            </div>

            {/* Messaggio */}
            <p className="text-lg font-medium text-slate-700 mb-2">
              Inizializzazione{dots}
            </p>
            <p className="text-sm text-slate-500">
              L'AI sta preparando la generazione del contenuto
            </p>
          </div>
        </div>

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="font-medium text-blue-800">Cosa sta succedendo?</p>
              <p className="text-sm text-blue-700 mt-1">
                L'AI sta analizzando la struttura della tua tesi e si prepara a generare il contenuto
                per ogni sezione. Questo processo potrebbe richiedere alcuni minuti.
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
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Generazione Contenuto</h2>
        <p className="text-slate-600">
          {generationStatus === 'completed'
            ? 'Generazione completata! La tua tesi è pronta.'
            : generationStatus === 'failed'
            ? 'Si è verificato un errore durante la generazione.'
            : 'L\'AI sta generando il contenuto per ogni sezione della tua tesi.'}
        </p>
      </div>

      {/* Card Principale Progress */}
      <div className="card bg-gradient-to-br from-orange-50 to-red-50 border-orange-200">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            {generationStatus === 'completed' ? (
              <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center shadow-md">
                <CheckCircle className="w-9 h-9 text-green-500" />
              </div>
            ) : generationStatus === 'failed' ? (
              <div className="w-16 h-16 bg-red-100 rounded-2xl flex items-center justify-center shadow-md">
                <AlertCircle className="w-9 h-9 text-red-500" />
              </div>
            ) : (
              <div className="relative">
                <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-lg">
                  <CurrentIcon className="w-8 h-8 text-white" />
                </div>
                <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow">
                  <Loader className="w-4 h-4 text-orange-500 animate-spin" />
                </div>
              </div>
            )}
            <div>
              <p className="font-bold text-slate-900 text-lg">
                {currentMessage}
              </p>
              <p className="text-slate-600 mt-1">
                {generationStatus === 'generating' && totalSections > 0 ? (
                  <>Sezione {completedSections + 1} di {totalSections}</>
                ) : generationStatus === 'completed' ? (
                  <>{totalSections} sezioni generate</>
                ) : (
                  <>Elaborazione in corso{dots}</>
                )}
              </p>
            </div>
          </div>

          {/* Percentuale grande */}
          <div className="text-right">
            <p className="text-4xl font-bold bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent">
              {Math.round(progress)}%
            </p>
            <p className="text-xs text-slate-500 mt-1">completato</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="relative">
          <div className="w-full bg-white/50 rounded-full h-4 overflow-hidden shadow-inner">
            <div
              className={`h-4 rounded-full transition-all duration-700 ease-out ${
                generationStatus === 'completed'
                  ? 'bg-gradient-to-r from-green-400 to-green-500'
                  : generationStatus === 'failed'
                  ? 'bg-gradient-to-r from-red-400 to-red-500'
                  : 'bg-gradient-to-r from-orange-500 to-red-500'
              }`}
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
          {generationStatus === 'generating' && (
            <div
              className="absolute top-0 h-4 w-20 bg-gradient-to-r from-transparent via-white/30 to-transparent rounded-full animate-pulse"
              style={{ left: `${Math.min(progress, 80)}%` }}
            />
          )}
        </div>

        {/* Stats rapide */}
        {totalSections > 0 && (
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="bg-white/60 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-orange-600">{completedSections}</p>
              <p className="text-xs text-slate-600">Completate</p>
            </div>
            <div className="bg-white/60 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-slate-600">{totalSections - completedSections}</p>
              <p className="text-xs text-slate-600">Rimanenti</p>
            </div>
            <div className="bg-white/60 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-slate-900">{totalSections}</p>
              <p className="text-xs text-slate-600">Totali</p>
            </div>
          </div>
        )}

        {/* Error Message */}
        {errorMessage && (
          <div className={`mt-4 p-4 rounded-lg text-sm ${
            errorMessage.includes('CREDITI_INSUFFICIENTI') || errorMessage.toLowerCase().includes('crediti')
              ? 'bg-amber-100 border border-amber-300 text-amber-800'
              : 'bg-red-100 border border-red-300 text-red-700'
          }`}>
            <p className="font-medium">
              {errorMessage.includes('CREDITI_INSUFFICIENTI') || errorMessage.toLowerCase().includes('crediti')
                ? '💳 Crediti AI Insufficienti:'
                : 'Errore:'}
            </p>
            <p>{errorMessage.replace('CREDITI_INSUFFICIENTI: ', '')}</p>
            {(errorMessage.includes('CREDITI_INSUFFICIENTI') || errorMessage.toLowerCase().includes('crediti')) && (
              <p className="text-xs mt-2 opacity-75">
                Verifica il saldo del tuo account AI e ricarica i crediti per continuare.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Dettaglio Capitoli */}
      {chaptersData && chaptersData.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-slate-700 flex items-center gap-2">
            <FileText className="w-5 h-5 text-orange-500" />
            Progresso per Capitolo
          </h3>

          {chaptersData.map((chapter, idx) => {
            const chapterIndex = chapter.chapter_index ?? idx;
            const isCurrentChapter = currentChapter === chapterIndex;

            return (
              <div key={chapterIndex} className="card p-0 overflow-hidden">
                {/* Chapter Header */}
                <button
                  onClick={() => toggleChapter(chapterIndex)}
                  className={`w-full p-4 flex items-center gap-3 transition-colors ${
                    isCurrentChapter ? 'bg-orange-50 border-orange-200' : getStatusColor(chapter.status)
                  }`}
                >
                  {isCurrentChapter ? (
                    <Loader className="w-5 h-5 text-orange-500 animate-spin" />
                  ) : (
                    getStatusIcon(chapter.status)
                  )}
                  <div className="flex-1 text-left">
                    <h4 className="font-medium text-slate-900">
                      Capitolo {chapterIndex + 1}: {chapter.chapter_title || `Capitolo ${chapterIndex + 1}`}
                    </h4>
                    <p className="text-sm text-slate-500">
                      {chapter.completed_sections ?? 0} / {chapter.total_sections ?? 0} sezioni
                      {isCurrentChapter && currentSection !== null && (
                        <span className="ml-2 text-orange-600 font-medium">
                          • Sezione {currentSection + 1} in corso
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {/* Mini progress bar per capitolo */}
                    <div className="w-20 bg-slate-200 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          chapter.status === 'completed' ? 'bg-green-500' : 'bg-orange-500'
                        }`}
                        style={{
                          width: `${chapter.total_sections > 0
                            ? ((chapter.completed_sections ?? 0) / chapter.total_sections) * 100
                            : 0}%`
                        }}
                      />
                    </div>
                    {expandedChapters[chapterIndex] ? (
                      <ChevronDown className="w-5 h-5 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-slate-400" />
                    )}
                  </div>
                </button>

                {/* Sections Detail */}
                {expandedChapters[chapterIndex] && chapter.sections && (
                  <div className="border-t border-slate-200 p-4 space-y-2 bg-slate-50/50">
                    {chapter.sections.map((section, secIdx) => {
                      const sectionIndex = section.section_index ?? secIdx;
                      const isCurrentSection = isCurrentChapter && currentSection === sectionIndex;

                      return (
                        <div
                          key={sectionIndex}
                          className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                            isCurrentSection
                              ? 'bg-orange-50 border-orange-300 shadow-sm'
                              : getStatusColor(section.status)
                          }`}
                        >
                          {isCurrentSection ? (
                            <Loader className="w-4 h-4 text-orange-500 animate-spin" />
                          ) : (
                            getStatusIcon(section.status)
                          )}
                          <div className="flex-1">
                            <p className={`text-sm font-medium ${isCurrentSection ? 'text-orange-700' : 'text-slate-700'}`}>
                              {chapterIndex + 1}.{sectionIndex + 1}: {section.section_title || section.title || `Sezione ${sectionIndex + 1}`}
                            </p>
                          </div>
                          {section.words_count > 0 && (
                            <span className="text-xs text-slate-500 bg-white px-2 py-1 rounded">
                              {section.words_count.toLocaleString()} parole
                            </span>
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

      {/* Completion Message */}
      {generationStatus === 'completed' && (
        <div className="card bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center shadow-md">
              <CheckCircle className="w-9 h-9 text-green-500" />
            </div>
            <div>
              <h3 className="font-bold text-green-800 text-xl">Tesi Generata con Successo!</h3>
              <p className="text-green-700 mt-1">
                Tutte le {totalSections} sezioni sono state generate. Puoi visualizzare l'anteprima e scaricare il documento.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Info durante la generazione */}
      {generationStatus === 'generating' && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <Brain className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="font-medium text-blue-800">Generazione in corso</p>
              <p className="text-sm text-blue-700 mt-1">
                L'AI sta generando il contenuto analizzando il contesto, gli allegati e applicando lo stile
                richiesto. Ogni sezione viene elaborata singolarmente per garantire coerenza e qualità.
                Puoi attendere il completamento o tornare più tardi.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GenerationProgress;
