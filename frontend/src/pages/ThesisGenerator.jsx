import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
  getSessions
} from '../services/api';

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
    words_per_section: 5000,
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

  // Generation states
  const [isGeneratingChapters, setIsGeneratingChapters] = useState(false);
  const [isGeneratingSections, setIsGeneratingSections] = useState(false);

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

  // Create thesis when moving from step 3 to step 4
  const createThesisAndGenerateChapters = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Create thesis
      const thesisData = {
        ...parametersData,
        ...audienceData
      };

      const newThesis = await createThesis(thesisData);
      setThesisId(newThesis.id);
      setThesis(newThesis);

      // Move to step 4 and generate chapters
      setCurrentStep(4);
      setIsGeneratingChapters(true);

      const chaptersResponse = await generateThesisChapters(newThesis.id);
      setChapters(chaptersResponse.chapters);
      setIsGeneratingChapters(false);

      // Update thesis
      const updatedThesis = await getThesis(newThesis.id);
      setThesis(updatedThesis);
    } catch (err) {
      console.error('Errore creazione tesi:', err);
      setError(err.response?.data?.detail || 'Errore nella creazione della tesi');
      setIsGeneratingChapters(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Confirm chapters and generate sections
  const confirmChaptersAndGenerateSections = async () => {
    setIsLoading(true);
    setError(null);

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
      console.error('Errore conferma capitoli:', err);
      setError(err.response?.data?.detail || 'Errore nella conferma dei capitoli');
      setIsGeneratingSections(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Confirm sections and start content generation
  const confirmSectionsAndGenerate = async () => {
    setIsLoading(true);
    setError(null);

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
      setError(err.response?.data?.detail || 'Errore nell\'avvio della generazione');
    } finally {
      setIsLoading(false);
    }
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

  // Navigation
  const handleNext = () => {
    if (currentStep === 3) {
      createThesisAndGenerateChapters();
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
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-start gap-3">
            <span className="text-red-500 text-xl">⚠️</span>
            <div>
              <p className="font-medium">Errore</p>
              <p className="text-sm">{error}</p>
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
    </div>
  );
};

export default ThesisGenerator;
