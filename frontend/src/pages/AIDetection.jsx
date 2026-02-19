import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Search, Download, AlertTriangle, CheckCircle2,
  RefreshCw, Sparkles, ShieldAlert, FileText, Info, Coins
} from 'lucide-react';
import { detectAICopyleaks, downloadAIDetectionReport, estimateCredits } from '../services/api';
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';

const AIDetection = () => {
  const navigate = useNavigate();
  const { isAdmin, credits, refreshUser } = useAuth();

  // Input state
  const [text, setText] = useState('');
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  // Results state
  const [result, setResult] = useState(null);
  const [downloadingReport, setDownloadingReport] = useState(false);

  // Credit confirmation
  const [showCreditDialog, setShowCreditDialog] = useState(false);
  const [creditEstimate, setCreditEstimate] = useState(null);
  const [creditLoading, setCreditLoading] = useState(false);

  const charCount = text.length;
  const minChars = 255;
  const maxChars = 25000;
  const isValidLength = charCount >= minChars && charCount <= maxChars;

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setError('');

    if (!isValidLength) {
      setError(`Il testo deve essere tra ${minChars} e ${maxChars.toLocaleString()} caratteri`);
      return;
    }

    // Stima crediti
    setCreditLoading(true);
    setShowCreditDialog(true);

    try {
      const estimate = await estimateCredits('ai_detection', { text_length: charCount });
      setCreditEstimate(estimate);
    } catch (err) {
      console.error('Errore stima crediti:', err);
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleConfirmedAnalysis = async () => {
    setShowCreditDialog(false);
    setScanning(true);
    setError('');
    setResult(null);

    try {
      const data = await detectAICopyleaks(text);
      setResult(data);
      refreshUser();
    } catch (err) {
      console.error('Errore analisi:', err);
      if (err.response?.status === 402) {
        setError('Crediti insufficienti per questa operazione.');
      } else if (err.response?.status === 502) {
        setError(err.response.data?.detail || 'Errore comunicazione con Copyleaks. Riprova.');
      } else {
        setError(err.response?.data?.detail || 'Errore durante l\'analisi. Riprova.');
      }
    } finally {
      setScanning(false);
    }
  };

  const handleDownloadReport = async () => {
    if (!result) return;
    setDownloadingReport(true);
    try {
      await downloadAIDetectionReport(
        text,
        result.segments,
        result.ai_percentage,
        result.human_percentage
      );
    } catch (err) {
      console.error('Errore download report:', err);
      setError('Errore nel download del report PDF.');
    } finally {
      setDownloadingReport(false);
    }
  };

  const handleReset = () => {
    setText('');
    setResult(null);
    setError('');
  };

  // Rendering del testo con evidenziazione
  const renderHighlightedText = () => {
    if (!result || !result.segments || result.segments.length === 0) return null;

    return (
      <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
        {result.segments.map((segment, idx) => (
          <span
            key={idx}
            className={`${
              segment.classification === 'ai'
                ? 'bg-red-100 border-b-2 border-red-400 text-red-900'
                : 'bg-green-100 border-b-2 border-green-400 text-green-900'
            } px-0.5 rounded-sm`}
            title={segment.classification === 'ai' ? 'Rilevato come AI' : 'Rilevato come umano'}
          >
            {segment.text}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen relative">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-red-100 to-orange-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-to-br from-orange-100 to-yellow-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-0 left-1/3 w-[400px] h-[400px] bg-gradient-to-br from-red-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <header className="relative z-10 glass border-b border-white/20">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="btn btn-ghost"
              >
                <ArrowLeft className="w-5 h-5" />
                Dashboard
              </button>
              <div className="h-8 w-px bg-gray-200"></div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-red-500 to-orange-600 rounded-xl flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">Rileva AI</h1>
                  <p className="text-xs text-gray-500">Copyleaks AI Detection</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 px-3 py-2 bg-orange-50 rounded-xl border border-orange-200">
              <Coins className="w-4 h-4 text-orange-600" />
              <span className="text-sm font-bold text-orange-600">
                {isAdmin ? '\u221E' : credits}
              </span>
              <span className="text-xs text-orange-500">crediti</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-5xl mx-auto px-6 py-8">

        {/* Info Banner */}
        <div className="glass rounded-2xl p-4 mb-6 border border-blue-100 bg-blue-50/50">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">Come funziona</p>
              <p className="text-blue-600">
                Incolla il testo che vuoi analizzare (minimo {minChars} caratteri, massimo {maxChars.toLocaleString()}).
                Il sistema analizza il testo con Copyleaks e evidenzia le parti rilevate come generate da AI
                in rosso e le parti umane in verde. Puoi anche scaricare un report PDF dettagliato.
              </p>
            </div>
          </div>
        </div>

        {/* Input Section */}
        {!result && (
          <form onSubmit={handleAnalyze} className="glass rounded-2xl p-6 mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Testo da analizzare
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Incolla qui il testo che vuoi analizzare per rilevamento AI..."
              className="w-full h-64 px-4 py-3 rounded-xl border border-gray-200 focus:border-orange-400 focus:ring-2 focus:ring-orange-100 resize-y text-sm font-mono transition-colors"
              disabled={scanning}
            />

            {/* Char counter */}
            <div className="flex items-center justify-between mt-3">
              <div className="flex items-center gap-3">
                <span className={`text-sm font-medium ${
                  charCount < minChars ? 'text-red-500' :
                  charCount > maxChars ? 'text-red-500' :
                  'text-green-600'
                }`}>
                  {charCount.toLocaleString()} / {maxChars.toLocaleString()} caratteri
                </span>
                {charCount > 0 && charCount < minChars && (
                  <span className="text-xs text-red-500">
                    (minimo {minChars} caratteri, ne mancano {minChars - charCount})
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-400">
                ~{Math.round(charCount / 5)} parole
              </span>
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
                <span className="text-sm text-red-700">{error}</span>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button
                type="submit"
                disabled={scanning || !isValidLength}
                className="btn btn-primary btn-lg flex-1"
              >
                {scanning ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Analisi in corso...
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    Analizza Testo
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Results Section */}
        {result && (
          <div className="space-y-6 animate-fade-in">
            {/* Percentage Bar */}
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-orange-600" />
                Risultato Analisi
              </h2>

              {/* Big percentage display */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className={`rounded-2xl p-6 text-center ${
                  result.ai_percentage > 50
                    ? 'bg-red-50 border-2 border-red-200'
                    : 'bg-red-50/50 border border-red-100'
                }`}>
                  <p className="text-4xl font-bold text-red-600">{result.ai_percentage.toFixed(1)}%</p>
                  <p className="text-sm text-red-500 mt-1 font-medium">Testo AI</p>
                </div>
                <div className={`rounded-2xl p-6 text-center ${
                  result.human_percentage > 50
                    ? 'bg-green-50 border-2 border-green-200'
                    : 'bg-green-50/50 border border-green-100'
                }`}>
                  <p className="text-4xl font-bold text-green-600">{result.human_percentage.toFixed(1)}%</p>
                  <p className="text-sm text-green-500 mt-1 font-medium">Testo Umano</p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="h-6 rounded-full overflow-hidden bg-gray-200 flex">
                <div
                  className="bg-gradient-to-r from-red-500 to-red-400 transition-all duration-700"
                  style={{ width: `${result.ai_percentage}%` }}
                />
                <div
                  className="bg-gradient-to-r from-green-400 to-green-500 transition-all duration-700"
                  style={{ width: `${result.human_percentage}%` }}
                />
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 mt-4">
                <div className="bg-gray-50 rounded-xl p-3 text-center">
                  <p className="text-lg font-bold text-gray-900">{result.total_words}</p>
                  <p className="text-xs text-gray-500">Parole analizzate</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-3 text-center">
                  <p className="text-lg font-bold text-gray-900">
                    {result.segments.filter(s => s.classification === 'ai').length}
                  </p>
                  <p className="text-xs text-gray-500">Segmenti AI</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-3 text-center">
                  <p className="text-lg font-bold text-gray-900">
                    {result.segments.filter(s => s.classification === 'human').length}
                  </p>
                  <p className="text-xs text-gray-500">Segmenti Umani</p>
                </div>
              </div>

              {/* Verdict */}
              <div className={`mt-4 p-4 rounded-xl flex items-center gap-3 ${
                result.ai_percentage > 70
                  ? 'bg-red-50 border border-red-200'
                  : result.ai_percentage > 40
                  ? 'bg-orange-50 border border-orange-200'
                  : 'bg-green-50 border border-green-200'
              }`}>
                {result.ai_percentage > 70 ? (
                  <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
                ) : result.ai_percentage > 40 ? (
                  <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0" />
                ) : (
                  <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                )}
                <p className={`text-sm font-medium ${
                  result.ai_percentage > 70
                    ? 'text-red-700'
                    : result.ai_percentage > 40
                    ? 'text-orange-700'
                    : 'text-green-700'
                }`}>
                  {result.ai_percentage > 70
                    ? 'Il testo risulta molto probabilmente generato da AI.'
                    : result.ai_percentage > 40
                    ? 'Il testo contiene porzioni significative probabilmente generate da AI.'
                    : 'Il testo risulta prevalentemente scritto da un essere umano.'}
                </p>
              </div>
            </div>

            {/* Highlighted Text */}
            <div className="glass rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-gray-600" />
                  Testo Evidenziato
                </h2>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-red-200 border border-red-400"></span>
                    AI
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-green-200 border border-green-400"></span>
                    Umano
                  </span>
                </div>
              </div>

              <div className="max-h-[500px] overflow-y-auto p-4 bg-white rounded-xl border border-gray-100">
                {renderHighlightedText()}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={handleDownloadReport}
                disabled={downloadingReport}
                className="btn btn-primary btn-lg flex-1"
              >
                {downloadingReport ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Generazione PDF...
                  </>
                ) : (
                  <>
                    <Download className="w-5 h-5" />
                    Scarica Report PDF
                  </>
                )}
              </button>
              <button
                onClick={handleReset}
                className="btn btn-secondary btn-lg"
              >
                <RefreshCw className="w-5 h-5" />
                Nuova Analisi
              </button>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
                <span className="text-sm text-red-700">{error}</span>
              </div>
            )}
          </div>
        )}

        {/* Scanning overlay */}
        {scanning && (
          <div className="glass rounded-2xl p-12 text-center animate-fade-in">
            <div className="relative inline-block mb-6">
              <div className="w-20 h-20 bg-gradient-to-br from-red-500 to-orange-600 rounded-2xl flex items-center justify-center animate-pulse">
                <Search className="w-10 h-10 text-white" />
              </div>
              <div className="absolute inset-0 border-4 border-orange-300 border-t-transparent rounded-2xl animate-spin"></div>
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Analisi in corso...</h3>
            <p className="text-gray-500">Copyleaks sta analizzando il testo per rilevare contenuto AI</p>
            <div className="mt-6 w-64 mx-auto">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-orange-500 via-red-500 to-orange-500 rounded-full animate-loading-bar"></div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Credit Confirm Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleConfirmedAnalysis}
        onCancel={() => setShowCreditDialog(false)}
        operationName="AI Detection (Copyleaks)"
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : creditEstimate?.current_balance ?? credits}
        loading={creditLoading}
      />
    </div>
  );
};

export default AIDetection;
