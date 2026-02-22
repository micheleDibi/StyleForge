import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader, Sparkles, Home } from 'lucide-react';

// Components
import StepIndicator from '../components/thesis/StepIndicator';
import ThesisParametersForm from '../components/thesis/ThesisParametersForm';
import ThesisAudienceForm from '../components/thesis/ThesisAudienceForm';
import ThesisAttachmentsForm from '../components/thesis/ThesisAttachmentsForm';
import ChapterEditor from '../components/thesis/ChapterEditor';
import SectionEditor from '../components/thesis/SectionEditor';
import GenerationProgress from '../components/thesis/GenerationProgress';
import ThesisPreview from '../components/thesis/ThesisPreview';

// API
import {
  getThesisLookupData,
  createThesis,
  getThesis,
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

const STEPS = [
  { id: 1, label: 'Parametri' },
  { id: 2, label: 'Pubblico' },
  { id: 3, label: 'Allegati' },
  { id: 4, label: 'Capitoli' },
  { id: 5, label: 'Sezioni' },
  { id: 6, label: 'Generazione' },
  { id: 7, label: 'Download' }
];

const ThesisGenerator = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAdmin, credits, refreshUser } = useAuth();
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
    ai_provider: 'openai'
  });

  const [audienceData, setAudienceData] = useState({
    knowledge_level_id: null,
    audience_size_id: null,
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

  // Helper: extract error message with credit error detection
  const handleApiError = (err, fallbackMessage) => {
    if (err.isInsufficientCredits || err.response?.status === 402) {
      const msg = err.creditErrorMessage || err.response?.data?.detail || 'Crediti AI insufficienti.';
      setError(msg);
      setIsCreditError(true);
    } else {
      setError(err.response?.data?.detail || fallbackMessage);
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
        const thesisData = await getThesis(resumeId);
        setThesisId(thesisData.id);
        setThesis(thesisData);

        // Restore form data
        setParametersData(prev => ({
          ...prev,
          title: thesisData.title || '',
          description: thesisData.description || '',
          key_topics: thesisData.key_topics || [],
          num_chapters: thesisData.num_chapters || 5,
          sections_per_chapter: thesisData.sections_per_chapter || 3,
          words_per_section: thesisData.words_per_section || 1000,
        }));

        // Determine the correct step based on thesis status
        const status = thesisData.status;
        if (status === 'completed') {
          setGeneratedContent(thesisData.generated_content || '');
          setCurrentStep(7);
        } else if (status === 'generating') {
          setCurrentStep(6);
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
          setCurrentStep(6);
          setGenerationStatus({ status: 'failed', error: thesisData.error || 'Generazione fallita' });
        } else if (status === 'sections_pending' || status === 'sections_confirmed') {
          if (thesisData.chapters) {
            setSectionsData(thesisData.chapters);
          }
          setCurrentStep(5);
        } else if (status === 'chapters_pending' || status === 'chapters_confirmed') {
          if (thesisData.chapters) {
            setChapters(thesisData.chapters.map(c => ({ title: c.title, description: c.description })));
          }
          setCurrentStep(4);
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

    const newThesis = await createThesis(thesisData);
    setThesisId(newThesis.id);
    setThesis(newThesis);
    return newThesis.id;
  };

  // Helper: mostra dialog crediti e poi esegui azione
  const showCreditConfirmation = async (operationType, params, operationLabel, action) => {
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

  // Generate chapters when moving from step 3 to step 4
  const generateChaptersForThesis = async () => {
    // Prima: stima crediti
    await showCreditConfirmation(
      'thesis_chapters',
      {},
      'Genera Struttura Capitoli',
      async () => {
        setIsLoading(true);
        setError(null);
        setIsCreditError(false);

        try {
          const currentThesisId = await ensureThesisCreated();

          // Move to step 4 and generate chapters
          setCurrentStep(4);
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

          // Move to step 5 and generate sections
          setCurrentStep(5);
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

          // Move to step 6
          setCurrentStep(6);

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
      setCurrentStep(7);
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
      setCurrentStep(7);
    } catch (err) {
      console.error('Errore caricamento tesi completata:', err);
    }
  };

  // Navigation
  const handleNext = async () => {
    if (currentStep === 2) {
      // Create thesis before entering step 3 so thesisId is available for uploads
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
      generateChaptersForThesis();
    } else if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1 && currentStep <= 3) {
      setCurrentStep(currentStep - 1);
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return parametersData.title.trim().length > 0;
      case 2:
        return true; // Audience is optional
      case 3:
        return true; // Attachments are optional
      default:
        return false;
    }
  };

  // Loading state
  if (isLoading && !lookupData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-orange-50/30">
        <div className="text-center">
          <div className="relative inline-block mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl flex items-center justify-center shadow-xl">
              <Sparkles className="w-10 h-10 text-white animate-pulse" />
            </div>
            <Loader className="absolute -bottom-2 -right-2 w-8 h-8 text-orange-500 animate-spin" />
          </div>
          <p className="text-slate-600 font-medium">Caricamento...</p>
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
              <h1 className="text-xl font-bold text-slate-900">Genera Tesi / Relazione</h1>
            </div>
            <div className="w-20"></div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Step Indicator */}
        <StepIndicator steps={STEPS} currentStep={currentStep} />

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

        {/* Step Content */}
        <div className="mt-8">
          {currentStep === 1 && (
            <ThesisParametersForm
              data={parametersData}
              onChange={setParametersData}
              lookupData={lookupData}
              sessions={sessions}
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
            <ChapterEditor
              chapters={chapters}
              onChange={setChapters}
              onConfirm={confirmChaptersAndGenerateSections}
              isLoading={isLoading}
              isGenerating={isGeneratingChapters}
            />
          )}

          {currentStep === 5 && (
            <SectionEditor
              chapters={sectionsData}
              onChange={setSectionsData}
              onConfirm={confirmSectionsAndGenerate}
              isLoading={isLoading}
              isGenerating={isGeneratingSections}
            />
          )}

          {currentStep === 6 && (
            <GenerationProgress
              status={generationStatus}
              onComplete={loadCompletedThesis}
            />
          )}

          {currentStep === 7 && thesis && (
            <ThesisPreview
              thesis={thesis}
              content={generatedContent}
              isAdmin={isAdmin}
            />
          )}
        </div>

        {/* Navigation Buttons - Migliorati */}
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
                ) : currentStep === 3 ? (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>Genera Capitoli</span>
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
