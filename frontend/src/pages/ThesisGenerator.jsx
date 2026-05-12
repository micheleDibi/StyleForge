import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader, Sparkles, Home } from 'lucide-react';

// Components
import StepIndicator from '../components/thesis/StepIndicator';
import ThesisParametersForm from '../components/thesis/ThesisParametersForm';
import ThesisAudienceForm from '../components/thesis/ThesisAudienceForm';
import ThesisPapersForm from '../components/thesis/ThesisPapersForm';
import ThesisAttachmentsForm from '../components/thesis/ThesisAttachmentsForm';
import ThesisKnowledgeBaseStep from '../components/thesis/ThesisKnowledgeBaseStep';
import ChapterEditor from '../components/thesis/ChapterEditor';
import SectionEditor from '../components/thesis/SectionEditor';
import GenerationProgress from '../components/thesis/GenerationProgress';
import ThesisPreview from '../components/thesis/ThesisPreview';

// API
import {
  getThesisLookupData,
  createThesis,
  getThesis,
  getThesisAttachments,
  generateThesisChapters,
  confirmThesisChapters,
  generateThesisSections,
  confirmThesisSections,
  startThesisContentGeneration,
  pollThesisGenerationStatus,
  getSessions,
  estimateCredits
} from '../services/api';

// Auth & Credits
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';
import ApiCostEstimate from '../components/ApiCostEstimate';
import CreditEstimatePreview from '../components/CreditEstimatePreview';


const STEPS = [
  { id: 1, label: 'Parametri' },
  { id: 2, label: 'Pubblico' },
  { id: 3, label: 'Allegati' },
  { id: 4, label: 'Paper' },
  { id: 5, label: 'Knowledge Base' },
  { id: 6, label: 'Capitoli' },
  { id: 7, label: 'Sezioni' },
  { id: 8, label: 'Generazione' },
  { id: 9, label: 'Download' }
];

const PAPER_MIME = 'application/x-research-paper';

const ThesisGenerator = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, isAdmin, credits, refreshUser } = useAuth();
  const entityType = (user?.entity_type || 'private');
  // Una volta creata la tesi, l'addebito flat e' gia' avvenuto (oppure utente admin):
  // gli step successivi (paper, capitoli, sezioni, contenuto) non vanno mostrati come a pagamento.
  // `thesis.credits_charged` viene impostato a true dal backend al momento della create_thesis.
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Lookup data
  const [lookupData, setLookupData] = useState(null);
  const [sessions, setSessions] = useState([]);

  // Thesis data
  const [thesisId, setThesisId] = useState(null);
  const [thesis, setThesis] = useState(null);

  // Form data
  const [parametersData, setParametersData] = useState({
    title: '',
    session_id: null,
    description: '',
    key_topics: [],
    writing_style_id: null,
    content_depth_id: null,
    num_chapters: 5,
    sections_per_chapter: 3,
    words_per_section: 1000,
    ai_provider: 'openai',
    citation_style: 'footnotes',
    restrict_to_sources: true,
    use_custom_outline: false,
    custom_outline: null,
  });

  const [audienceData, setAudienceData] = useState({
    knowledge_level_id: null,
    industry_id: null,
    target_audience_id: null
  });

  const [attachmentsData, setAttachmentsData] = useState({
    attachments: []
  });

  // Generated data
  const [chapters, setChapters] = useState([]);
  const [sectionsData, setSectionsData] = useState([]);
  const [generationStatus, setGenerationStatus] = useState(null);
  const [generatedContent, setGeneratedContent] = useState('');
  const [isCreditError, setIsCreditError] = useState(false);

  // Generation states
  const [isGeneratingChapters, setIsGeneratingChapters] = useState(false);
  const [isGeneratingSections, setIsGeneratingSections] = useState(false);

  // Credit confirmation state
  const [showCreditDialog, setShowCreditDialog] = useState(false);
  const [creditEstimate, setCreditEstimate] = useState(null);
  const [creditLoading, setCreditLoading] = useState(false);
  const [creditOperationName, setCreditOperationName] = useState('');
  const [pendingCreditAction, setPendingCreditAction] = useState(null);

  // Costo della tariffa flat tesi per il tipo ente dell'utente (configurabile da admin).
  const [thesisFlatCost, setThesisFlatCost] = useState(null);
  useEffect(() => {
    if (isAdmin) return;
    let cancelled = false;
    estimateCredits('thesis_total', { entity_type: entityType }).then((res) => {
      if (!cancelled && res?.credits_needed != null) setThesisFlatCost(res.credits_needed);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [isAdmin, entityType]);

  // Helper: extract error message with credit error detection
  const handleApiError = (err, fallbackMessage) => {
    if (err.isInsufficientCredits || err.response?.status === 402) {
      const msg = err.creditErrorMessage || err.response?.data?.detail || 'Crediti AI insufficienti.';
      setError(typeof msg === 'string' ? msg : fallbackMessage);
      setIsCreditError(true);
    } else if (err.isClientValidation && err.message) {
      setError(err.message);
      setIsCreditError(false);
    } else {
      const detail = err.response?.data?.detail;
      // Pydantic 422 restituisce un array di errori di validazione
      let msg = fallbackMessage;
      if (typeof detail === 'string') {
        msg = detail;
      } else if (Array.isArray(detail)) {
        msg = detail.map(e => e.msg || JSON.stringify(e)).join(', ');
      }
      setError(msg);
      setIsCreditError(false);
    }
  };

  // Load lookup data on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        const [lookup, sessionsResponse] = await Promise.all([
          getThesisLookupData(),
          getSessions()
        ]);
        setLookupData(lookup);
        // getSessions returns { sessions: [...] }
        const sessionsArray = sessionsResponse?.sessions || sessionsResponse || [];
        setSessions(Array.isArray(sessionsArray) ? sessionsArray.filter(s => s.is_trained) : []);
      } catch (err) {
        console.error('Errore caricamento dati:', err);
        setError('Errore nel caricamento dei dati. Riprova.');
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  // Resume thesis from ?resume=ID
  useEffect(() => {
    const resumeId = searchParams.get('resume');
    if (!resumeId) return;

    const resumeThesis = async () => {
      try {
        setIsLoading(true);
        const [thesisData, attachmentsResp] = await Promise.all([
          getThesis(resumeId),
          getThesisAttachments(resumeId).catch(() => ({ attachments: [] })),
        ]);
        setThesisId(thesisData.id);
        setThesis(thesisData);

        // Ripristina gli allegati (documenti + paper aggiunti come fonti)
        // — senza questo passaggio, tornando a step 3/4 dopo la rientrata in
        // resume l'utente non vedeva i file caricati in precedenza.
        setAttachmentsData({
          attachments: attachmentsResp?.attachments || [],
        });

        // Restore form data — TUTTI i parametri salvati nella tesi, cosi'
        // tornando agli step 1/2 dopo il resume l'utente li vede compilati.
        setParametersData(prev => ({
          ...prev,
          title: thesisData.title || '',
          session_id: thesisData.session_id || null,
          description: thesisData.description || '',
          key_topics: thesisData.key_topics || [],
          writing_style_id: thesisData.writing_style_id ?? null,
          content_depth_id: thesisData.content_depth_id ?? null,
          num_chapters: thesisData.num_chapters || 5,
          sections_per_chapter: thesisData.sections_per_chapter || 3,
          words_per_section: thesisData.words_per_section || 1000,
          ai_provider: thesisData.ai_provider || 'openai',
          citation_style: thesisData.citation_style || 'footnotes',
          use_custom_outline: !!thesisData.use_custom_outline,
          custom_outline: thesisData.custom_outline || null,
          restrict_to_sources: thesisData.restrict_to_sources !== false,
        }));

        // Restore audience data — anche questi non venivano ripristinati
        setAudienceData({
          knowledge_level_id: thesisData.knowledge_level_id ?? null,
          audience_size_id: thesisData.audience_size_id ?? null,
          industry_id: thesisData.industry_id ?? null,
          target_audience_id: thesisData.target_audience_id ?? null,
        });

        // Restore chapters/sections gia' generate dalla chapters_structure
        // (la tesi salva tutto in JSONB. Il vecchio codice cercava un
        // thesisData.chapters che NON esiste — chapters_structure e' il campo)
        const cs = thesisData.chapters_structure;
        if (cs && Array.isArray(cs.chapters) && cs.chapters.length > 0) {
          const hasSections = cs.chapters.some(c => Array.isArray(c.sections) && c.sections.length > 0);
          // ChapterEditor usa c.title, c.description/brief_description
          setChapters(cs.chapters.map(c => ({
            title: c.title || c.chapter_title || '',
            description: c.description || c.brief_description || '',
          })));
          if (hasSections) {
            // SectionEditor usa c.chapter_title + c.sections
            setSectionsData(cs.chapters.map(c => ({
              chapter_index: c.chapter_index ?? c.index,
              chapter_title: c.chapter_title || c.title || '',
              sections: c.sections || [],
            })));
          }
        }

        // Determine the correct step based on thesis status
        const status = thesisData.status;
        if (status === 'completed') {
          setGeneratedContent(thesisData.generated_content || '');
          setCurrentStep(9);
        } else if (status === 'generating') {
          setCurrentStep(8);
          // Start polling
          pollThesisGenerationStatus(
            thesisData.id,
            (genStatus) => {
              setGenerationStatus(genStatus);
              if (genStatus.status === 'completed') {
                loadCompletedThesisById(thesisData.id);
              }
            },
            3000,
            1800000
          );
        } else if (status === 'failed') {
          setCurrentStep(8);
          setGenerationStatus({ status: 'failed', error: thesisData.error || 'Generazione fallita' });
        } else if (status === 'sections_pending' || status === 'sections_confirmed') {
          if (thesisData.chapters) {
            setSectionsData(thesisData.chapters);
          }
          setCurrentStep(7);
        } else if (status === 'chapters_pending' || status === 'chapters_confirmed') {
          if (thesisData.chapters) {
            setChapters(thesisData.chapters.map(c => ({ title: c.title, description: c.description })));
          }
          setCurrentStep(6);
        } else {
          // draft or other early status
          setCurrentStep(1);
        }
      } catch (err) {
        console.error('Errore nel resume della tesi:', err);
        setError('Errore nel caricamento della tesi. Potrebbe essere stata eliminata.');
      } finally {
        setIsLoading(false);
      }
    };

    resumeThesis();
  }, [searchParams]);

  // Create thesis before entering step 3 (needed for file uploads)
  const ensureThesisCreated = async () => {
    if (thesisId) return thesisId;

    const thesisData = {
      ...parametersData,
      ...audienceData
    };

    // Sanifica il payload custom_outline:
    //  - Se il toggle e' OFF, NON inviamo l'outline (anche se in state per UX-friendly:
    //    l'utente puo' tornare ad attivarlo). Pydantic validerebbe i campi interni
    //    anche con use_custom_outline=false e darebbe 422 sui titoli vuoti.
    //  - Se ON, rimuovo capitoli/sezioni con titolo vuoto.
    if (!thesisData.use_custom_outline) {
      thesisData.custom_outline = null;
    } else if (thesisData.custom_outline) {
      const cleaned = {
        chapters: (thesisData.custom_outline.chapters || [])
          .map((c) => ({
            title: (c.title || '').trim(),
            brief_description: (c.brief_description || '').trim(),
            sections: (c.sections || [])
              .map((s) => ({
                title: (s.title || '').trim(),
                key_points: (s.key_points || []).map((k) => (k || '').trim()).filter(Boolean),
              }))
              .filter((s) => s.title),
          }))
          .filter((c) => c.title && c.sections.length > 0),
      };
      thesisData.custom_outline = cleaned;
      if (cleaned.chapters.length === 0) {
        const err = new Error('L\'indice personalizzato deve avere almeno 1 capitolo con titolo e almeno 1 paragrafo con titolo.');
        err.isClientValidation = true;
        throw err;
      }
    }

    const newThesis = await createThesis(thesisData);
    setThesisId(newThesis.id);
    setThesis(newThesis);
    return newThesis.id;
  };

  // Indica che la tesi ha gia' pagato la tariffa flat (o utente admin):
  // tutti gli step interni non devono piu' chiedere o scalare crediti.
  const isThesisPaid = isAdmin || thesis?.credits_charged === true;

  // Helper: mostra dialog crediti e poi esegui azione
  const showCreditConfirmation = async (operationType, params, operationLabel, action) => {
    // Se la tesi ha gia' pagato il flat (o utente admin), niente dialog: esegui direttamente.
    if (isThesisPaid) {
      await action();
      refreshUser();
      return;
    }

    setCreditLoading(true);
    setCreditOperationName(operationLabel);
    setPendingCreditAction(() => action);
    setShowCreditDialog(true);

    try {
      const estimate = await estimateCredits(operationType, params);
      setCreditEstimate(estimate);
    } catch (err) {
      console.error('Errore stima crediti:', err);
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleCreditConfirmed = async () => {
    setShowCreditDialog(false);
    if (pendingCreditAction) {
      await pendingCreditAction();
      refreshUser();
    }
    setPendingCreditAction(null);
  };

  // Generate chapters when moving from step 5 (Knowledge Base) to step 6 (Capitoli)
  const generateChaptersForThesis = async () => {
    // Prima: stima crediti
    const attChars = Math.round((attachmentsData.attachments?.reduce((sum, a) => sum + (a.file_size || 0), 0) || 0) * 0.5);
    await showCreditConfirmation(
      'thesis_chapters',
      { attachment_chars: attChars },
      'Genera Struttura Capitoli',
      async () => {
        setIsLoading(true);
        setError(null);
        setIsCreditError(false);

        try {
          const currentThesisId = await ensureThesisCreated();

          // Move to step 6 (Capitoli) and generate chapters
          setCurrentStep(6);
          setIsGeneratingChapters(true);

          const chaptersResponse = await generateThesisChapters(currentThesisId);
          setChapters(chaptersResponse.chapters);
          setIsGeneratingChapters(false);

          // Update thesis
          const updatedThesis = await getThesis(currentThesisId);
          setThesis(updatedThesis);
        } catch (err) {
          console.error('Errore creazione tesi:', err);
          handleApiError(err, 'Errore nella creazione della tesi');
          setIsGeneratingChapters(false);
        } finally {
          setIsLoading(false);
        }
      }
    );
  };

  // Confirm chapters and generate sections
  const confirmChaptersAndGenerateSections = async () => {
    // Prima: stima crediti per generazione sezioni
    await showCreditConfirmation(
      'thesis_sections',
      {},
      'Genera Struttura Sezioni',
      async () => {
        setIsLoading(true);
        setError(null);
        setIsCreditError(false);

        try {
          await confirmThesisChapters(thesisId, chapters);

          // Move to step 7 (Sezioni) and generate sections
          setCurrentStep(7);
          setIsGeneratingSections(true);

          const sectionsResponse = await generateThesisSections(thesisId);
          setSectionsData(sectionsResponse.chapters);
          setIsGeneratingSections(false);

          // Update thesis
          const updatedThesis = await getThesis(thesisId);
          setThesis(updatedThesis);
        } catch (err) {
          console.error('Errore conferma capitoli/generazione sezioni:', err);
          handleApiError(err, 'Errore nella conferma dei capitoli');
          setIsGeneratingSections(false);
        } finally {
          setIsLoading(false);
        }
      }
    );
  };

  // Confirm sections and start content generation
  const confirmSectionsAndGenerate = async () => {
    // Stima crediti per generazione contenuto completo
    const thesisParams = {
      num_chapters: parametersData.num_chapters || 5,
      sections_per_chapter: parametersData.sections_per_chapter || 3,
      words_per_section: parametersData.words_per_section || 5000
    };

    await showCreditConfirmation(
      'thesis_content',
      thesisParams,
      'Genera Contenuto Tesi',
      async () => {
        setIsLoading(true);
        setError(null);
        setIsCreditError(false);

        try {
          await confirmThesisSections(thesisId, sectionsData);

          // Move to step 8 (Generazione)
          setCurrentStep(8);

          // Start content generation
          await startThesisContentGeneration(thesisId);

          // Start polling for status
          pollThesisGenerationStatus(
            thesisId,
            (status) => {
              setGenerationStatus(status);
              if (status.status === 'completed') {
                loadCompletedThesis();
              }
            },
            3000,
            1800000 // 30 minutes timeout
          );
        } catch (err) {
          console.error('Errore avvio generazione:', err);
          handleApiError(err, 'Errore nell\'avvio della generazione');
        } finally {
          setIsLoading(false);
        }
      }
    );
  };

  // Load completed thesis
  const loadCompletedThesis = async () => {
    try {
      const completedThesis = await getThesis(thesisId);
      setThesis(completedThesis);
      setGeneratedContent(completedThesis.generated_content || '');
      setCurrentStep(9);
    } catch (err) {
      console.error('Errore caricamento tesi completata:', err);
    }
  };

  // Load completed thesis by ID (used in resume)
  const loadCompletedThesisById = async (id) => {
    try {
      const completedThesis = await getThesis(id);
      setThesis(completedThesis);
      setGeneratedContent(completedThesis.generated_content || '');
      setCurrentStep(9);
    } catch (err) {
      console.error('Errore caricamento tesi completata:', err);
    }
  };

  // Navigation
  const handleNext = async () => {
    if (currentStep === 2) {
      // Create thesis before entering step 3 so thesisId is available for paper/uploads
      setIsLoading(true);
      setError(null);
      setIsCreditError(false);
      try {
        await ensureThesisCreated();
        setCurrentStep(3);
      } catch (err) {
        console.error('Errore creazione tesi:', err);
        handleApiError(err, 'Errore nella creazione della tesi');
      } finally {
        setIsLoading(false);
      }
    } else if (currentStep === 3) {
      // Paper scientifici → Allegati (step opzionale, nessuna chiamata)
      setCurrentStep(4);
    } else if (currentStep === 4) {
      // Allegati → step Knowledge Base (l'utente decide quando avviare l'ingest)
      setCurrentStep(5);
    } else if (currentStep === 5) {
      // Knowledge Base → genera Capitoli (chiamato anche da onComplete dello step KB)
      generateChaptersForThesis();
    } else if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    // Go-back libero: l'utente puo' tornare a qualsiasi step precedente.
    // I capitoli/sezioni generati restano salvati su DB (vedi banner avviso).
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Step accessibili dinamicamente: una volta arrivati a step N, l'utente
  // puo' rientrare in N e in tutti i precedenti — anche dopo aver generato.
  // Sblocco progressivo basato sullo stato della tesi e dei dati locali.
  const maxAccessibleStep = (() => {
    if (thesis?.status === 'completed' || generatedContent) return 9;
    if (thesis?.status === 'generating' || thesis?.status === 'failed') return 8;
    if (sectionsData && sectionsData.length > 0) return 7;
    if (chapters && chapters.length > 0) return 6;
    // Se siamo gia' visivamente oltre, mantenere quello (es. arrivati a KB)
    return Math.max(currentStep, 1);
  })();

  const isStepAccessible = (stepNum) => stepNum <= maxAccessibleStep;

  const handleStepClick = (stepNum) => {
    if (stepNum === currentStep) return;
    if (!isStepAccessible(stepNum)) return;
    setCurrentStep(stepNum);
  };

  // Banner di avviso: se l'utente torna prima dello step 5 dopo aver gia'
  // generato capitoli, lo informiamo che i dati restano salvati.
  const showBackToParamsWarning =
    currentStep < 5 && (chapters?.length > 0 || sectionsData?.length > 0 || thesis?.status === 'completed');

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return parametersData.title.trim().length > 0;
      case 2:
        return true; // Audience is optional
      case 3:
        return true; // Papers are optional
      case 4:
        return true; // Attachments are optional
      case 5:
        return true; // KB-step ha la propria logica interna
      default:
        return false;
    }
  };

  // Loading state
  if (isLoading && !lookupData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-orange-50">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-[3px] border-slate-200"></div>
            <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-orange-500 animate-spin"></div>
          </div>
          <p className="text-sm text-slate-500 font-medium">Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50/30">
      {/* Header fisso */}
      <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-2 text-slate-600 hover:text-orange-600 transition-colors"
            >
              <Home className="w-5 h-5" />
              <span className="hidden sm:inline font-medium">Dashboard</span>
            </button>
            <div className="text-center">
              <h1 className="text-xl font-bold text-slate-900">Tesi</h1>
            </div>
            <div className="w-20"></div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Step Indicator (cliccabile per step gia' raggiunti) */}
        <StepIndicator
          steps={STEPS}
          currentStep={currentStep}
          onStepClick={handleStepClick}
          isStepAccessible={isStepAccessible}
        />

        {/* Error Message */}
        {error && (
          <div className={`mb-6 p-4 rounded-xl flex items-start gap-3 ${
            isCreditError
              ? 'bg-amber-50 border border-amber-300 text-amber-800'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            <span className={`text-xl ${isCreditError ? 'text-amber-500' : 'text-red-500'}`}>
              {isCreditError ? '💳' : '⚠️'}
            </span>
            <div>
              <p className="font-medium">
                {isCreditError ? 'Crediti AI Insufficienti' : 'Errore'}
              </p>
              <p className="text-sm">{error}</p>
              {isCreditError && (
                <p className="text-xs mt-2 opacity-75">
                  Verifica il saldo del tuo account AI e ricarica i crediti per continuare.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Avviso go-back: l'utente e' tornato prima dello step KB dopo aver gia'
            generato capitoli o sezioni. I dati restano salvati su DB. */}
        {showBackToParamsWarning && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 flex items-start gap-3">
            <span className="text-xl">ℹ️</span>
            <div>
              <p className="font-medium">I capitoli e le sezioni generate restano salvati</p>
              <p className="text-sm">
                Puoi modificare liberamente parametri, allegati o paper. Per rigenerare la struttura,
                torna allo step <strong>Knowledge Base</strong> e premi <strong>Continua</strong>.
              </p>
            </div>
          </div>
        )}

        {/* Nav top per step 5-9 (KB, Capitoli, Sezioni, Generazione, Download):
            solo bottone Indietro; il bottone "Avanti" e' all'interno di ogni step
            (es. "Procedi ai capitoli", "Conferma capitoli", ecc.). Per step 1-4
            la nav bar c'e' gia' (in cima per Paper, in fondo per gli altri). */}
        {currentStep >= 5 && (
          <div className="mb-6 flex items-center justify-between gap-3 p-3 bg-white rounded-2xl border border-slate-200">
            <button
              onClick={handleBack}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 font-semibold transition-all active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Indietro</span>
            </button>
            <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
              <span className="font-medium text-orange-600">Step {currentStep}</span>
              <span>di</span>
              <span>{STEPS.length}</span>
            </div>
          </div>
        )}

        {/* Step Content */}
        <div className="mt-8">
          {currentStep === 1 && (
            <ThesisParametersForm
              data={parametersData}
              onChange={setParametersData}
              lookupData={lookupData}
              sessions={sessions}
              isAdmin={isAdmin}
              thesisId={thesisId}
              attachmentsCount={attachmentsData.attachments?.length || 0}
              attachmentsTotalSize={attachmentsData.attachments?.reduce((sum, a) => sum + (a.file_size || 0), 0) || 0}
            />
          )}

          {currentStep === 2 && (
            <ThesisAudienceForm
              data={audienceData}
              onChange={setAudienceData}
              lookupData={lookupData}
            />
          )}

          {currentStep === 3 && (
            <ThesisAttachmentsForm
              data={attachmentsData}
              onChange={setAttachmentsData}
              thesisId={thesisId}
            />
          )}

          {currentStep === 4 && (
            <>
              {/* Nav bar in cima allo step Paper: la lista risultati può essere lunga,
                  qui i pulsanti restano sempre raggiungibili senza scroll. */}
              <div className="mb-6">
                <div className="flex items-center justify-between gap-4 p-4 bg-white rounded-2xl shadow-lg border border-slate-200">
                  <button
                    onClick={handleBack}
                    disabled={currentStep === 1}
                    className={`
                      flex items-center gap-2 px-6 py-3 rounded-xl font-semibold transition-all
                      ${currentStep === 1
                        ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 active:scale-95'
                      }
                    `}
                  >
                    <ArrowLeft className="w-5 h-5" />
                    <span>Indietro</span>
                  </button>

                  <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
                    <span className="font-medium text-orange-600">Step {currentStep}</span>
                    <span>di</span>
                    <span>{STEPS.length}</span>
                  </div>

                  <button
                    onClick={handleNext}
                    disabled={!canProceed() || isLoading}
                    className={`
                      flex items-center gap-2 px-8 py-3 rounded-xl font-semibold transition-all shadow-md
                      ${!canProceed() || isLoading
                        ? 'bg-slate-300 text-slate-500 cursor-not-allowed shadow-none'
                        : 'bg-gradient-to-r from-orange-500 to-red-500 text-white hover:from-orange-600 hover:to-red-600 hover:shadow-lg hover:shadow-orange-500/30 active:scale-95'
                      }
                    `}
                  >
                    {isLoading ? (
                      <>
                        <Loader className="w-5 h-5 animate-spin" />
                        <span>Elaborazione...</span>
                      </>
                    ) : (
                      <>
                        <span>Continua</span>
                        <ArrowRight className="w-5 h-5" />
                      </>
                    )}
                  </button>
                </div>
              </div>

              <ThesisPapersForm
                data={attachmentsData}
                onChange={setAttachmentsData}
                thesisId={thesisId}
                onCreditsChanged={refreshUser}
                isThesisPaid={isThesisPaid}
              />
            </>
          )}

          {currentStep === 5 && thesisId && (
            <ThesisKnowledgeBaseStep
              thesisId={thesisId}
              paperCount={(attachmentsData.attachments || []).filter(a => a.mime_type === PAPER_MIME).length}
              attachmentCount={(attachmentsData.attachments || []).filter(a => a.mime_type !== PAPER_MIME).length}
              restrictToSources={!!parametersData.restrict_to_sources}
              onComplete={generateChaptersForThesis}
              onBack={() => setCurrentStep(4)}
            />
          )}

          {currentStep === 6 && (
            <ChapterEditor
              chapters={chapters}
              onChange={setChapters}
              onConfirm={confirmChaptersAndGenerateSections}
              isLoading={isLoading}
              isGenerating={isGeneratingChapters}
              thesisTitle={parametersData.title}
              thesisDescription={parametersData.description}
            />
          )}

          {currentStep === 7 && (
            <SectionEditor
              chapters={sectionsData}
              onChange={setSectionsData}
              onConfirm={confirmSectionsAndGenerate}
              isLoading={isLoading}
              isGenerating={isGeneratingSections}
              thesisTitle={parametersData.title}
              thesisDescription={parametersData.description}
            />
          )}

          {currentStep === 8 && (
            <GenerationProgress
              status={generationStatus}
              onComplete={loadCompletedThesis}
            />
          )}

          {currentStep === 9 && thesis && (
            <ThesisPreview
              thesis={thesis}
              content={generatedContent}
            />
          )}
        </div>

        {/* Credit + API Cost Estimate (step 2-7).
            Per i non-admin la preview "tesi flat" si mostra SOLO finche' la tesi non e' stata creata
            (quindi prima dell'addebito); subito dopo non ha piu' senso mostrarla. */}
        {currentStep >= 2 && currentStep <= 8 && parametersData.title && (isAdmin || !isThesisPaid) && (
          <div className="mt-4">
            <CreditEstimatePreview
              operations={
                isAdmin
                  ? [
                      { type: 'thesis_chapters', params: { attachment_chars: Math.round((attachmentsData.attachments?.reduce((sum, a) => sum + (a.file_size || 0), 0) || 0) * 0.5) }, label: 'Capitoli + allegati' },
                      { type: 'thesis_sections', params: {}, label: 'Sezioni' },
                      { type: 'thesis_content', params: { num_chapters: parametersData.num_chapters, sections_per_chapter: parametersData.sections_per_chapter, words_per_section: parametersData.words_per_section }, label: 'Contenuto' },
                    ]
                  : [
                      { type: 'thesis_total', params: { entity_type: entityType }, label: entityType === 'training' ? 'Tesi (flat - ente formazione)' : 'Tesi (flat - ente privato)' },
                    ]
              }
            />
          </div>
        )}
        {/* Banner di conferma "tesi gia' pagata" per non-admin durante gli step successivi alla creazione. */}
        {!isAdmin && isThesisPaid && currentStep >= 3 && currentStep <= 8 && (
          <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>
              Tesi gia' pagata. Tutti gli step (paper, allegati, capitoli, sezioni, contenuto) sono inclusi: nessun ulteriore credito verra' addebitato.
            </span>
          </div>
        )}
        {isAdmin && currentStep >= 2 && currentStep <= 8 && parametersData.title && (
          <div className="mt-1">
            <ApiCostEstimate
              mode="thesis"
              numChapters={parametersData.num_chapters}
              sectionsPerChapter={parametersData.sections_per_chapter}
              wordsPerSection={parametersData.words_per_section}
              aiProvider={parametersData.ai_provider}
              thesisId={thesisId}
              attachmentsCount={attachmentsData.attachments?.length || 0}
              attachmentsTotalSize={attachmentsData.attachments?.reduce((sum, a) => sum + (a.file_size || 0), 0) || 0}
            />
          </div>
        )}

        {/* Avviso "addebito non rimborsabile" prima di lasciare lo step 2.
            La creazione tesi (passaggio 2 → 3) addebita la tariffa flat in base al tipo ente. */}
        {currentStep === 2 && !isAdmin && !thesisId && (
          <div className="mt-6 rounded-2xl border-2 border-amber-300 bg-amber-50 p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1 text-sm">
                <p className="font-semibold text-amber-900 mb-1">
                  Addebito alla creazione: {thesisFlatCost != null ? thesisFlatCost : '—'} crediti
                </p>
                <p className="text-amber-800">
                  Cliccando su <strong>Continua</strong> verrà creata la tesi e verrà addebitata in un'unica
                  soluzione la tariffa flat per il tuo ente ({entityType === 'training' ? 'ente di formazione' : 'ente privato'}).
                  Tutti gli step successivi (paper, allegati, capitoli, sezioni, contenuto) sono inclusi.
                  <strong> L'importo non è rimborsabile in caso di abbandono del wizard.</strong>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation Buttons - Migliorati
            Lo step 4 (Paper) ha la propria nav bar in cima, vista la lunghezza dei risultati.
            Quindi qui rendiamo la nav bar solo per gli step 1, 2, 3 (Parametri/Pubblico/Allegati). */}
        {currentStep <= 3 && (
          <div className="mt-10 pb-8">
            <div className="flex items-center justify-between gap-4 p-4 bg-white rounded-2xl shadow-lg border border-slate-200">
              {/* Pulsante Indietro */}
              <button
                onClick={handleBack}
                disabled={currentStep === 1}
                className={`
                  flex items-center gap-2 px-6 py-3 rounded-xl font-semibold transition-all
                  ${currentStep === 1
                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 active:scale-95'
                  }
                `}
              >
                <ArrowLeft className="w-5 h-5" />
                <span>Indietro</span>
              </button>

              {/* Indicatore Step */}
              <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
                <span className="font-medium text-orange-600">Step {currentStep}</span>
                <span>di</span>
                <span>{STEPS.length}</span>
              </div>

              {/* Pulsante Continua */}
              <button
                onClick={handleNext}
                disabled={!canProceed() || isLoading}
                className={`
                  flex items-center gap-2 px-8 py-3 rounded-xl font-semibold transition-all shadow-md
                  ${!canProceed() || isLoading
                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed shadow-none'
                    : 'bg-gradient-to-r from-orange-500 to-red-500 text-white hover:from-orange-600 hover:to-red-600 hover:shadow-lg hover:shadow-orange-500/30 active:scale-95'
                  }
                `}
              >
                {isLoading ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    <span>Elaborazione...</span>
                  </>
                ) : (
                  <>
                    <span>Continua</span>
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Credit Confirmation Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleCreditConfirmed}
        onCancel={() => {
          setShowCreditDialog(false);
          setPendingCreditAction(null);
        }}
        operationName={creditOperationName}
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : (creditEstimate?.current_balance ?? credits)}
        loading={creditLoading}
      />
    </div>
  );
};

export default ThesisGenerator;
