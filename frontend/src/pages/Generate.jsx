import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Sparkles, Download, Copy, Check, ShieldAlert, RefreshCw, AlertTriangle } from 'lucide-react';
import { getSessions, generateContent, pollJobStatus, getResultText, estimateCredits, detectAICopyleaks, downloadAIDetectionReport } from '../services/api';
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';
import { jsPDF } from 'jspdf';

const Generate = () => {
  const navigate = useNavigate();
  const { isAdmin, credits, refreshUser } = useAuth();
  const [searchParams] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(searchParams.get('session') || '');
  const [argomento, setArgomento] = useState('');
  const [numeroParole, setNumeroParole] = useState(1000);
  const [destinatario, setDestinatario] = useState('Pubblico Generale');
  const [generating, setGenerating] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [result, setResult] = useState('');
  const [copied, setCopied] = useState(false);

  // AI Detection state
  const [aiDetecting, setAiDetecting] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiError, setAiError] = useState('');
  const [aiReportLoading, setAiReportLoading] = useState(false);

  // Credit confirmation state
  const [showCreditDialog, setShowCreditDialog] = useState(false);
  const [creditEstimate, setCreditEstimate] = useState(null);
  const [creditLoading, setCreditLoading] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      const trainedSessions = data.sessions.filter(s => s.is_trained);
      setSessions(trainedSessions);

      if (trainedSessions.length > 0 && !selectedSession) {
        setSelectedSession(trainedSessions[0].session_id);
      }
    } catch (error) {
      console.error('Errore nel caricamento:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Stima crediti e mostra dialog di conferma
    setCreditLoading(true);
    setShowCreditDialog(true);

    try {
      const estimate = await estimateCredits('generate', { numero_parole: numeroParole });
      setCreditEstimate(estimate);
    } catch (err) {
      console.error('Errore stima crediti:', err);
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleConfirmedGeneration = async () => {
    setShowCreditDialog(false);
    setGenerating(true);

    try {
      const response = await generateContent(selectedSession, argomento, numeroParole, destinatario);
      setJobStatus({ ...response, status: 'pending', progress: 0 });

      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => setJobStatus(status),
        3000
      );

      if (finalStatus.status === 'completed') {
        const text = finalStatus.result;
        setResult(text);
      }

      // Aggiorna saldo crediti
      refreshUser();
    } catch (error) {
      console.error('Errore nella generazione:', error);
      if (error.response?.status === 402) {
        alert('Crediti insufficienti per questa operazione.');
      } else {
        alert('Errore nella generazione del contenuto');
      }
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const doc = new jsPDF();

    // Configurazione
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 15;
    const maxWidth = pageWidth - (margin * 2);
    const lineHeight = 7;
    const fontSize = 11;

    doc.setFontSize(fontSize);

    // Dividi il testo in righe rispettando i limiti della pagina
    const lines = doc.splitTextToSize(result, maxWidth);

    let y = margin;

    for (let i = 0; i < lines.length; i++) {
      // Se raggiungiamo il fondo della pagina, aggiungi una nuova pagina
      if (y + lineHeight > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }

      doc.text(lines[i], margin, y);
      y += lineHeight;
    }

    // Scarica il PDF
    doc.save(`contenuto_${Date.now()}.pdf`);
  };

  const handleAIDetect = async () => {
    if (!result || result.length < 255) {
      setAiError('Il testo deve essere di almeno 255 caratteri per l\'analisi AI.');
      return;
    }
    setAiDetecting(true);
    setAiError('');
    setAiResult(null);
    try {
      const data = await detectAICopyleaks(result.substring(0, 25000));
      setAiResult(data);
      refreshUser();
    } catch (err) {
      setAiError(err.response?.data?.detail || 'Errore durante l\'analisi AI.');
    } finally {
      setAiDetecting(false);
    }
  };

  const handleAIReport = async () => {
    if (!aiResult) return;
    setAiReportLoading(true);
    try {
      await downloadAIDetectionReport(result, aiResult.segments, aiResult.ai_percentage, aiResult.human_percentage);
    } catch (err) {
      setAiError('Errore nel download del report.');
    } finally {
      setAiReportLoading(false);
    }
  };

  if (sessions.length === 0) {
    return (
      <div className="min-h-screen p-6 flex items-center justify-center">
        <div className="card max-w-md text-center">
          <Sparkles className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-900 mb-2">
            Nessuna sessione addestrata
          </h2>
          <p className="text-slate-600 mb-6">
            Devi prima addestrare una sessione prima di poter generare contenuti
          </p>
          <button
            onClick={() => navigate('/train')}
            className="btn btn-primary"
          >
            Avvia Training
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="btn btn-secondary gap-2 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Torna alla Dashboard
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form */}
          <div>
            <h1 className="text-3xl font-bold text-slate-900 mb-2">
              Genera Contenuto
            </h1>
            <p className="text-slate-600 mb-6">
              Crea contenuti basati sullo stile appreso
            </p>

            <form onSubmit={handleSubmit} className="card space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Sessione
                </label>
                <select
                  value={selectedSession}
                  onChange={(e) => setSelectedSession(e.target.value)}
                  className="input w-full"
                  required
                >
                  {sessions.map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.name || session.session_id}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Argomento
                </label>
                <input
                  type="text"
                  value={argomento}
                  onChange={(e) => setArgomento(e.target.value)}
                  className="input w-full"
                  placeholder="es. Intelligenza emotiva"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Numero di parole
                </label>
                <input
                  type="number"
                  value={numeroParole}
                  onChange={(e) => setNumeroParole(parseInt(e.target.value))}
                  className="input w-full"
                  min="100"
                  max="10000"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Destinatario
                </label>
                <input
                  type="text"
                  value={destinatario}
                  onChange={(e) => setDestinatario(e.target.value)}
                  className="input w-full"
                  placeholder="Pubblico Generale"
                />
              </div>

              <button
                type="submit"
                disabled={generating}
                className="w-full btn btn-primary h-12 text-base gap-2"
              >
                {generating ? (
                  <>
                    <div className="loading-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    Generazione in corso...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Genera Contenuto
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Result */}
          <div>
            <h2 className="text-xl font-semibold text-slate-900 mb-4">
              Risultato
            </h2>

            {jobStatus && jobStatus.status !== 'completed' && (
              <div className="card">
                <div className="text-center py-8">
                  <Sparkles className="w-12 h-12 text-blue-600 animate-pulse mx-auto mb-4" />
                  <p className="text-slate-600 mb-2">Generazione in corso...</p>
                  {jobStatus.progress > 0 && (
                    <div className="max-w-xs mx-auto">
                      <div className="w-full bg-slate-200 rounded-full h-2 mt-4">
                        <div
                          className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all"
                          style={{ width: `${jobStatus.progress}%` }}
                        ></div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {result && (
              <div className="card">
                <div className="flex justify-between items-center mb-4">
                  <p className="text-sm text-slate-600">
                    {result.split(' ').length} parole
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleCopy}
                      className="btn btn-secondary gap-2 text-sm"
                    >
                      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      {copied ? 'Copiato!' : 'Copia'}
                    </button>
                    <button
                      onClick={handleDownload}
                      className="btn btn-primary gap-2 text-sm"
                    >
                      <Download className="w-4 h-4" />
                      Scarica
                    </button>
                  </div>
                </div>

                <div className="bg-slate-50 rounded-lg p-6 max-h-[600px] overflow-y-auto">
                  <pre className="whitespace-pre-wrap font-sans text-slate-900 leading-relaxed">
                    {result}
                  </pre>
                </div>

                {/* AI Detection Button */}
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleAIDetect}
                    disabled={aiDetecting || result.length < 255}
                    className="btn btn-secondary gap-2 text-sm w-full justify-center"
                    style={{ backgroundColor: '#fef2f2', borderColor: '#fecaca', color: '#991b1b' }}
                  >
                    {aiDetecting ? (
                      <><RefreshCw className="w-4 h-4 animate-spin" /> Analisi AI in corso...</>
                    ) : (
                      <><ShieldAlert className="w-4 h-4" /> Rileva AI (Copyleaks)</>
                    )}
                  </button>

                  {aiError && (
                    <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
                      <span className="text-xs text-red-700">{aiError}</span>
                    </div>
                  )}

                  {aiResult && (
                    <div className="mt-4 space-y-3">
                      {/* Percentages */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className={`rounded-xl p-3 text-center ${aiResult.ai_percentage > 50 ? 'bg-red-50 border border-red-200' : 'bg-red-50/50'}`}>
                          <p className="text-2xl font-bold text-red-600">{aiResult.ai_percentage.toFixed(1)}%</p>
                          <p className="text-xs text-red-500">AI</p>
                        </div>
                        <div className={`rounded-xl p-3 text-center ${aiResult.human_percentage > 50 ? 'bg-green-50 border border-green-200' : 'bg-green-50/50'}`}>
                          <p className="text-2xl font-bold text-green-600">{aiResult.human_percentage.toFixed(1)}%</p>
                          <p className="text-xs text-green-500">Umano</p>
                        </div>
                      </div>
                      {/* Progress bar */}
                      <div className="h-3 rounded-full overflow-hidden bg-gray-200 flex">
                        <div className="bg-red-400" style={{ width: `${aiResult.ai_percentage}%` }} />
                        <div className="bg-green-400" style={{ width: `${aiResult.human_percentage}%` }} />
                      </div>
                      {/* Highlighted text */}
                      <div className="bg-white rounded-lg p-4 max-h-[300px] overflow-y-auto border">
                        <div className="font-mono text-xs leading-relaxed whitespace-pre-wrap">
                          {aiResult.segments.map((seg, i) => (
                            <span key={i} className={seg.classification === 'ai' ? 'bg-red-100 border-b border-red-400' : 'bg-green-100 border-b border-green-400'}>
                              {seg.text}
                            </span>
                          ))}
                        </div>
                      </div>
                      {/* Download report */}
                      <button
                        onClick={handleAIReport}
                        disabled={aiReportLoading}
                        className="btn btn-primary gap-2 text-sm w-full justify-center"
                      >
                        {aiReportLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        Scarica Report PDF
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {!jobStatus && !result && (
              <div className="card text-center py-12">
                <Sparkles className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-600">
                  Il contenuto generato apparirà qui
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Credit Confirmation Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleConfirmedGeneration}
        onCancel={() => setShowCreditDialog(false)}
        operationName="Genera Contenuto"
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : (creditEstimate?.current_balance ?? credits)}
        loading={creditLoading}
      />
    </div>
  );
};

export default Generate;
