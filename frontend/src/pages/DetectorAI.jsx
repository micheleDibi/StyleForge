import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Shield, AlertTriangle, FileText, Loader, Search } from 'lucide-react';
import { startCompilatioScan, downloadCompilatioReport, pollJobStatus } from '../services/api';
import { useAuth } from '../context/AuthContext';

const DetectorAI = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [text, setText] = useState('');
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);

  const countWords = (t) => t.trim().split(/\s+/).filter(w => w.length > 0).length;

  const getAIScoreColor = (percent) => {
    if (percent <= 5) return 'text-green-600 bg-green-50 border-green-200';
    if (percent <= 20) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const handleScan = async () => {
    if (!text.trim() || text.trim().length < 50 || scanning) return;

    setScanning(true);
    setError(null);
    setResult(null);
    setProgress(0);

    try {
      const response = await startCompilatioScan(text, 'manual', null);

      // Se risultato cached, mostra subito
      if (response.cached && response.cached_scan) {
        setResult(response.cached_scan);
        setScanning(false);
        return;
      }

      // Poll per il risultato
      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => {
          setProgress(status.progress || 0);
        },
        4000
      );

      if (finalStatus.status === 'completed' && finalStatus.result) {
        try {
          const scanResult = JSON.parse(finalStatus.result);
          setResult(scanResult);
        } catch {
          setResult(finalStatus.result);
        }
      } else if (finalStatus.status === 'failed') {
        setError(finalStatus.error || 'Scansione fallita');
      }
    } catch (err) {
      console.error('Errore scansione:', err);
      setError(err.response?.data?.detail || 'Errore durante la scansione');
    } finally {
      setScanning(false);
    }
  };

  const handleDownloadReport = async () => {
    if (result?.scan_id) {
      try {
        await downloadCompilatioReport(result.scan_id);
      } catch (err) {
        console.error('Errore download report:', err);
        alert('Errore nel download del report');
      }
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto">
        <button
          onClick={() => navigate('/')}
          className="btn btn-secondary gap-2 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Torna alla Dashboard
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Search className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Detector AI</h1>
            <p className="text-slate-600">Scansione AI Detection e Plagio</p>
          </div>
          <span className="ml-auto text-xs bg-purple-100 text-purple-600 px-3 py-1 rounded-full font-medium">
            Admin Only
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input */}
          <div>
            <div className="card space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Testo da analizzare
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="input w-full h-80 resize-y min-h-64"
                  placeholder="Incolla qui il testo da analizzare per rilevamento AI e plagio...&#10;&#10;Il testo verra convertito in PDF e inviato per l'analisi completa."
                  disabled={scanning}
                />
                <p className="text-xs text-slate-500 mt-2">
                  {countWords(text)} parole - {text.length} caratteri
                  {text.trim().length > 0 && text.trim().length < 50 && (
                    <span className="text-red-500 ml-2">Minimo 50 caratteri</span>
                  )}
                </p>
              </div>

              <button
                onClick={handleScan}
                disabled={scanning || text.trim().length < 50}
                className="w-full btn gap-2 text-base bg-gradient-to-r from-indigo-500 to-purple-600 text-white hover:from-indigo-600 hover:to-purple-700 h-12 disabled:opacity-50"
              >
                {scanning ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    Scansione in corso...
                  </>
                ) : (
                  <>
                    <Shield className="w-5 h-5" />
                    Avvia Scansione
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results */}
          <div>
            <h2 className="text-xl font-semibold text-slate-900 mb-4">Risultati</h2>

            {scanning && (
              <div className="card">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Loader className="w-5 h-5 text-purple-600 animate-spin" />
                    <span className="text-purple-700 font-medium">Scansione Detector AI in corso...</span>
                  </div>
                  <div className="w-full bg-purple-200 rounded-full h-2.5">
                    <div
                      className="bg-gradient-to-r from-purple-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                  <p className="text-xs text-purple-500 mt-2">L'analisi puo' richiedere alcuni minuti</p>
                </div>
              </div>
            )}

            {error && (
              <div className="card">
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="text-red-700 font-medium">Errore nella scansione</span>
                    <p className="text-red-600 text-sm mt-1">{error}</p>
                    <button onClick={handleScan} className="mt-2 text-red-600 hover:text-red-800 text-sm underline">
                      Riprova
                    </button>
                  </div>
                </div>
              </div>
            )}

            {result && (
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                    <Shield className="w-5 h-5 text-purple-600" />
                    Risultati Detector AI
                  </h3>
                  {result.has_report && (
                    <button
                      onClick={handleDownloadReport}
                      className="btn btn-secondary gap-2 text-sm"
                    >
                      <FileText className="w-4 h-4" />
                      Scarica Report PDF
                    </button>
                  )}
                </div>

                {/* Main Metrics */}
                <div className="grid grid-cols-2 gap-3">
                  <div className={`rounded-xl p-4 border-2 ${getAIScoreColor(result.ai_generated_percent)}`}>
                    <div className="text-3xl font-bold">{result.ai_generated_percent?.toFixed(1)}%</div>
                    <div className="text-sm font-medium opacity-80">AI Generato</div>
                  </div>
                  <div className="rounded-xl p-4 border-2 bg-blue-50 border-blue-200 text-blue-600">
                    <div className="text-3xl font-bold">{result.similarity_percent?.toFixed(1)}%</div>
                    <div className="text-sm font-medium opacity-80">Similarita</div>
                  </div>
                </div>

                {/* Secondary Metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                    <div className="text-lg font-bold">{result.global_score_percent?.toFixed(1)}%</div>
                    <div className="text-xs font-medium opacity-80">Score Globale</div>
                  </div>
                  <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                    <div className="text-lg font-bold">{result.exact_percent?.toFixed(1)}%</div>
                    <div className="text-xs font-medium opacity-80">Match Esatti</div>
                  </div>
                  <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                    <div className="text-lg font-bold">{result.same_meaning_percent?.toFixed(1) || '0.0'}%</div>
                    <div className="text-xs font-medium opacity-80">Stesso Significato</div>
                  </div>
                  <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                    <div className="text-lg font-bold">{result.translation_percent?.toFixed(1) || '0.0'}%</div>
                    <div className="text-xs font-medium opacity-80">Traduzione</div>
                  </div>
                </div>

                {/* Additional Info */}
                <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-600">
                  <div className="flex justify-between">
                    <span>Parole analizzate:</span>
                    <span className="font-medium">{result.word_count?.toLocaleString() || 'N/A'}</span>
                  </div>
                  {result.quotation_percent > 0 && (
                    <div className="flex justify-between mt-1">
                      <span>Citazioni:</span>
                      <span className="font-medium">{result.quotation_percent?.toFixed(1)}%</span>
                    </div>
                  )}
                  {result.suspicious_fingerprint_percent > 0 && (
                    <div className="flex justify-between mt-1">
                      <span>Fingerprint sospetti:</span>
                      <span className="font-medium">{result.suspicious_fingerprint_percent?.toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {!scanning && !error && !result && (
              <div className="card text-center py-12">
                <Search className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-600">
                  Inserisci un testo e avvia la scansione per vedere i risultati
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DetectorAI;
