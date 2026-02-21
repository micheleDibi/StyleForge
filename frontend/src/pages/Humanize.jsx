import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Wand2, Download, Copy, Check, AlertTriangle, RefreshCw, Shield, Sparkles } from 'lucide-react';
import { getSessions, humanizeContent, antiAICorrection, pollJobStatus, estimateCredits } from '../services/api';
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';
import { jsPDF } from 'jspdf';

const Humanize = () => {
  const navigate = useNavigate();
  const { isAdmin, credits, refreshUser } = useAuth();
  const [searchParams] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(searchParams.get('session') || '');
  const [testoOriginale, setTestoOriginale] = useState('');
  const [processing, setProcessing] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [result, setResult] = useState('');
  const [copied, setCopied] = useState(false);

  // Mode: 'correction' (Anti-AI) or 'full' (Umanizzazione con Profilo)
  const [mode, setMode] = useState('correction');

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

    if (testoOriginale.trim().length < 50) {
      alert('Il testo deve contenere almeno 50 caratteri');
      return;
    }

    if (mode === 'full' && !selectedSession) {
      alert('Seleziona una sessione addestrata');
      return;
    }

    // Stima crediti e mostra dialog di conferma
    setCreditLoading(true);
    setShowCreditDialog(true);

    try {
      const estimate = await estimateCredits('humanize', { text_length: testoOriginale.length });
      setCreditEstimate(estimate);
    } catch (err) {
      console.error('Errore stima crediti:', err);
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleConfirmedHumanize = async () => {
    setShowCreditDialog(false);
    setProcessing(true);
    setResult('');

    try {
      let response;
      if (mode === 'correction') {
        response = await antiAICorrection(testoOriginale);
      } else {
        response = await humanizeContent(selectedSession, testoOriginale);
      }
      setJobStatus({ ...response, status: 'pending', progress: 0 });

      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => setJobStatus(status),
        3000
      );

      if (finalStatus.status === 'completed') {
        setResult(finalStatus.result);
      } else if (finalStatus.status === 'failed') {
        alert('Errore durante l\'elaborazione: ' + (finalStatus.error || 'Errore sconosciuto'));
      }

      // Aggiorna saldo crediti
      refreshUser();
    } catch (error) {
      console.error('Errore nell\'elaborazione:', error);
      if (error.response?.status === 402) {
        alert('Crediti insufficienti per questa operazione.');
      } else {
        alert('Errore nell\'elaborazione del testo');
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const doc = new jsPDF();

    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 15;
    const maxWidth = pageWidth - (margin * 2);
    const lineHeight = 7;
    const fontSize = 11;

    doc.setFontSize(fontSize);

    const lines = doc.splitTextToSize(result, maxWidth);

    let y = margin;

    for (let i = 0; i < lines.length; i++) {
      if (y + lineHeight > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }

      doc.text(lines[i], margin, y);
      y += lineHeight;
    }

    const filename = mode === 'correction' ? 'testo_corretto' : 'testo_umanizzato';
    doc.save(`${filename}_${Date.now()}.pdf`);
  };

  const countWords = (text) => {
    return text.trim().split(/\s+/).filter(word => word.length > 0).length;
  };

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

        {/* Mode Toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => { setMode('correction'); setResult(''); setJobStatus(null); setAiResult(null); }}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-semibold text-sm transition-all border-2 ${
              mode === 'correction'
                ? 'bg-orange-50 border-orange-400 text-orange-700 shadow-md'
                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
            }`}
          >
            <Shield className="w-5 h-5" />
            Correzione Anti-AI
          </button>
          <button
            onClick={() => { setMode('full'); setResult(''); setJobStatus(null); setAiResult(null); }}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-semibold text-sm transition-all border-2 ${
              mode === 'full'
                ? 'bg-purple-50 border-purple-400 text-purple-700 shadow-md'
                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
            }`}
          >
            <Wand2 className="w-5 h-5" />
            Umanizzazione con Profilo Stilistico
          </button>
        </div>

        {/* Check: full mode needs trained sessions */}
        {mode === 'full' && sessions.length === 0 && (
          <div className="card max-w-md mx-auto text-center mb-6">
            <Wand2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-900 mb-2">
              Nessuna sessione addestrata
            </h2>
            <p className="text-slate-600 mb-6">
              Per l'umanizzazione con profilo stilistico devi prima addestrare una sessione.
              Puoi comunque usare la <strong>Correzione Anti-AI</strong>.
            </p>
            <div className="flex gap-2 justify-center">
              <button
                onClick={() => navigate('/train')}
                className="btn btn-primary"
              >
                Avvia Training
              </button>
              <button
                onClick={() => setMode('correction')}
                className="btn btn-secondary"
              >
                Usa Correzione Anti-AI
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form */}
          <div>
            <h1 className="text-3xl font-bold text-slate-900 mb-2">
              {mode === 'correction' ? 'Correzione Anti-AI' : 'Umanizza Testo AI'}
            </h1>
            <p className="text-slate-600 mb-6">
              {mode === 'correction'
                ? 'Micro-correzioni per ridurre la rilevabilita AI'
                : 'Riscrivi testi generati da AI nello stile appreso'
              }
            </p>

            {/* Info Box */}
            {mode === 'correction' ? (
              <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-6">
                <div className="flex gap-3">
                  <Shield className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-orange-800 mb-1">Come funziona</h4>
                    <p className="text-sm text-orange-700">
                      Applica <strong>micro-correzioni</strong> al tuo testo per ridurre la percentuale di rilevamento AI.
                      Il testo <strong>non viene riscritto</strong> ma solo ritoccato con sinonimi mirati, leggere variazioni
                      sintattiche e piccole imperfezioni naturali. Il risultato mantiene il <strong>90%+ del testo originale</strong>.
                    </p>
                    <p className="text-xs text-orange-600 mt-2">
                      Non richiede una sessione addestrata.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 mb-6">
                <div className="flex gap-3">
                  <Wand2 className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-purple-800 mb-1">Come funziona</h4>
                    <p className="text-sm text-purple-700">
                      Riscrive testi generati da AI applicando lo <strong>stile dell'autore</strong> appreso
                      durante l'addestramento e tecniche avanzate per aumentare la perplessita e la variabilita,
                      rendendolo indistinguibile da un testo scritto da un umano. Ideale per superare
                      i controlli di Compilatio, GPTZero e altri detector AI.
                    </p>
                    <p className="text-xs text-purple-600 mt-2">
                      Richiede una sessione addestrata.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="card space-y-6">
              {/* Session selector - only in full mode */}
              {mode === 'full' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Sessione (Profilo Stilistico)
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
                  <p className="text-xs text-slate-500 mt-1">
                    Il testo verra riscritto nello stile dell'autore di questa sessione
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {mode === 'correction' ? 'Testo da Correggere' : 'Testo da Umanizzare'}
                </label>
                <textarea
                  value={testoOriginale}
                  onChange={(e) => setTestoOriginale(e.target.value)}
                  className="input w-full h-96 resize-y min-h-64"
                  placeholder={mode === 'correction'
                    ? "Incolla qui il testo su cui applicare micro-correzioni anti-AI...\n\nIl testo verra mantenuto quasi identico all'originale con sole piccole modifiche mirate per ridurre la percentuale di rilevamento AI."
                    : "Incolla qui il testo generato da AI che vuoi riscrivere...\n\nPuoi incollare articoli, saggi, relazioni o qualsiasi testo generato da intelligenza artificiale.\n\nIl testo verra riscritto applicando lo stile dell'autore della sessione selezionata e tecniche avanzate per evitare la detection AI."
                  }
                  required
                />
                <p className="text-xs text-slate-500 mt-2">
                  {countWords(testoOriginale)} parole - {testoOriginale.length} caratteri
                </p>
              </div>

              <button
                type="submit"
                disabled={processing || testoOriginale.trim().length < 50 || (mode === 'full' && !selectedSession)}
                className={`w-full btn h-12 text-base gap-2 ${
                  mode === 'correction'
                    ? 'bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white border-0'
                    : 'btn-primary'
                }`}
              >
                {processing ? (
                  <>
                    <div className="loading-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    {mode === 'correction' ? 'Correzione in corso...' : 'Umanizzazione in corso...'}
                  </>
                ) : (
                  <>
                    {mode === 'correction' ? <Shield className="w-5 h-5" /> : <Wand2 className="w-5 h-5" />}
                    {mode === 'correction' ? 'Avvia Correzione Anti-AI' : 'Umanizza Testo'}
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

            {jobStatus && jobStatus.status !== 'completed' && jobStatus.status !== 'failed' && (
              <div className="card">
                <div className="text-center py-8">
                  {mode === 'correction' ? (
                    <Shield className="w-12 h-12 text-orange-600 animate-pulse mx-auto mb-4" />
                  ) : (
                    <Wand2 className="w-12 h-12 text-purple-600 animate-pulse mx-auto mb-4" />
                  )}
                  <p className="text-slate-600 mb-2">
                    {mode === 'correction' ? 'Correzione in corso...' : 'Umanizzazione in corso...'}
                  </p>
                  <p className="text-sm text-slate-500">
                    {mode === 'correction'
                      ? 'Sto applicando micro-correzioni al testo'
                      : 'Sto riscrivendo il testo nello stile appreso'
                    }
                  </p>
                  {jobStatus.progress > 0 && (
                    <div className="max-w-xs mx-auto">
                      <div className="w-full bg-slate-200 rounded-full h-2 mt-4">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            mode === 'correction'
                              ? 'bg-gradient-to-r from-orange-500 to-orange-600'
                              : 'bg-gradient-to-r from-purple-500 to-pink-500'
                          }`}
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
                    {countWords(result)} parole
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

              </div>
            )}

            {!jobStatus && !result && (
              <div className="card text-center py-12">
                {mode === 'correction' ? (
                  <Shield className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                ) : (
                  <Wand2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                )}
                <p className="text-slate-600">
                  {mode === 'correction'
                    ? 'Il testo corretto apparira qui'
                    : 'Il testo umanizzato apparira qui'
                  }
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Credit Confirmation Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleConfirmedHumanize}
        onCancel={() => setShowCreditDialog(false)}
        operationName={mode === 'correction' ? 'Correzione Anti-AI' : 'Umanizza Testo'}
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : (creditEstimate?.current_balance ?? credits)}
        loading={creditLoading}
      />
    </div>
  );
};

export default Humanize;
