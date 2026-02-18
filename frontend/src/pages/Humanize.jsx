import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Wand2, Download, Copy, Check, AlertTriangle } from 'lucide-react';
import { getSessions, humanizeContent, pollJobStatus, estimateCredits } from '../services/api';
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

    if (!selectedSession) {
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
      const response = await humanizeContent(selectedSession, testoOriginale);
      setJobStatus({ ...response, status: 'pending', progress: 0 });

      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => setJobStatus(status),
        3000
      );

      if (finalStatus.status === 'completed') {
        setResult(finalStatus.result);
      } else if (finalStatus.status === 'failed') {
        alert('Errore durante l\'umanizzazione: ' + (finalStatus.error || 'Errore sconosciuto'));
      }

      // Aggiorna saldo crediti
      refreshUser();
    } catch (error) {
      console.error('Errore nell\'umanizzazione:', error);
      if (error.response?.status === 402) {
        alert('Crediti insufficienti per questa operazione.');
      } else {
        alert('Errore nell\'umanizzazione del testo');
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

    doc.save(`testo_umanizzato_${Date.now()}.pdf`);
  };

  const countWords = (text) => {
    return text.trim().split(/\s+/).filter(word => word.length > 0).length;
  };

  if (sessions.length === 0) {
    return (
      <div className="min-h-screen p-6 flex items-center justify-center">
        <div className="card max-w-md text-center">
          <Wand2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-900 mb-2">
            Nessuna sessione addestrata
          </h2>
          <p className="text-slate-600 mb-6">
            Devi prima addestrare una sessione prima di poter umanizzare testi
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
              Umanizza Testo AI
            </h1>
            <p className="text-slate-600 mb-6">
              Riscrivi testi generati da AI nello stile appreso
            </p>

            {/* Info Box */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
              <div className="flex gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-medium text-amber-800 mb-1">Come funziona</h4>
                  <p className="text-sm text-amber-700">
                    Questa funzione riscrive testi generati da AI applicando lo <strong>stile dell'autore</strong> appreso
                    durante l'addestramento e tecniche avanzate per aumentare la perplessita e la variabilita,
                    rendendolo indistinguibile da un testo scritto da un umano. Ideale per superare
                    i controlli di Compilatio, Copyleaks e GPTZero.
                  </p>
                </div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="card space-y-6">
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

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Testo da Umanizzare
                </label>
                <textarea
                  value={testoOriginale}
                  onChange={(e) => setTestoOriginale(e.target.value)}
                  className="input w-full h-96 resize-y min-h-64"
                  placeholder="Incolla qui il testo generato da AI che vuoi riscrivere...

Puoi incollare articoli, saggi, relazioni o qualsiasi testo generato da intelligenza artificiale.

Il testo verra riscritto applicando lo stile dell'autore della sessione selezionata e tecniche avanzate per evitare la detection AI."
                  required
                />
                <p className="text-xs text-slate-500 mt-2">
                  {countWords(testoOriginale)} parole - {testoOriginale.length} caratteri
                </p>
              </div>

              <button
                type="submit"
                disabled={processing || testoOriginale.trim().length < 50}
                className="w-full btn btn-primary h-12 text-base gap-2"
              >
                {processing ? (
                  <>
                    <div className="loading-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    Umanizzazione in corso...
                  </>
                ) : (
                  <>
                    <Wand2 className="w-5 h-5" />
                    Umanizza Testo
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
                  <Wand2 className="w-12 h-12 text-purple-600 animate-pulse mx-auto mb-4" />
                  <p className="text-slate-600 mb-2">Umanizzazione in corso...</p>
                  <p className="text-sm text-slate-500">
                    Sto riscrivendo il testo nello stile appreso
                  </p>
                  {jobStatus.progress > 0 && (
                    <div className="max-w-xs mx-auto">
                      <div className="w-full bg-slate-200 rounded-full h-2 mt-4">
                        <div
                          className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all"
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
                <Wand2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-600">
                  Il testo umanizzato apparira qui
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
        operationName="Umanizza Testo"
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : (creditEstimate?.current_balance ?? credits)}
        loading={creditLoading}
      />
    </div>
  );
};

export default Humanize;
