import { useState, useEffect, useRef } from 'react';
import { CheckCircle, XCircle, Loader, Clock, Download, Trash2, FileText, Sparkles, Wand2, Pencil, Shield } from 'lucide-react';
import { getJobStatus, downloadResult, deleteJob, renameJob, startCompilatioScan, downloadCompilatioReport, pollJobStatus } from '../services/api';

const JobCard = ({ job, onUpdate, onDelete, showResult = false, scanResult: initialScanResult, isAdmin = false, onScanComplete }) => {
  const [currentJob, setCurrentJob] = useState(job);
  const [polling, setPolling] = useState(false);
  const [estimatedTime, setEstimatedTime] = useState(null);

  // Inline rename state
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const editInputRef = useRef(null);

  // Compilatio scan state (admin-only, inline)
  const [scanResult, setScanResult] = useState(initialScanResult || null);
  const [scanScanning, setScanScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanError, setScanError] = useState(null);

  useEffect(() => {
    if (initialScanResult) setScanResult(initialScanResult);
  }, [initialScanResult]);

  useEffect(() => {
    setCurrentJob(job);

    // Avvia polling se il job è in corso
    if (job.status === 'pending' || job.status === 'training' || job.status === 'generating') {
      setPolling(true);
      const startTime = Date.now();
      let lastProgress = job.progress || 0;
      let lastUpdate = startTime;

      const interval = setInterval(async () => {
        try {
          const updated = await getJobStatus(job.job_id);
          setCurrentJob(updated);
          if (onUpdate) onUpdate(updated);

          // Calcola stima tempo rimanente
          if (updated.progress && updated.progress > 0) {
            const now = Date.now();
            const progressDelta = updated.progress - lastProgress;

            if (progressDelta > 0) {
              const timeDelta = (now - lastUpdate) / 1000; // secondi
              const progressRate = progressDelta / timeDelta; // % per secondo
              const remainingProgress = 100 - updated.progress;
              const estimatedSeconds = remainingProgress / progressRate;

              setEstimatedTime(Math.ceil(estimatedSeconds));
              lastProgress = updated.progress;
              lastUpdate = now;
            }
          }

          if (updated.status === 'completed' || updated.status === 'failed') {
            setPolling(false);
            setEstimatedTime(null);
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Errore nel polling:', error);
        }
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [job.job_id]);

  // Focus input on edit start
  useEffect(() => {
    if (editing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editing]);

  const getStatusIcon = () => {
    switch (currentJob.status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-slate-400" />;
      default:
        return <Loader className="w-5 h-5 text-primary-500 animate-spin" />;
    }
  };

  const getStatusColor = () => {
    switch (currentJob.status) {
      case 'completed':
        return 'bg-green-100 text-green-700';
      case 'failed':
        return 'bg-red-100 text-red-700';
      case 'pending':
        return 'bg-slate-100 text-slate-700';
      default:
        return 'bg-primary-100 text-primary-700';
    }
  };

  const getStatusText = () => {
    switch (currentJob.status) {
      case 'completed':
        return 'Completato';
      case 'failed':
        return 'Fallito';
      case 'pending':
        return 'In coda';
      case 'training':
        return 'Training in corso';
      case 'generating':
        return 'Generazione in corso';
      default:
        return currentJob.status;
    }
  };

  const handleDownload = async () => {
    try {
      await downloadResult(currentJob.job_id);
    } catch (error) {
      console.error('Errore nel download:', error);
      alert('Errore nel download del risultato');
    }
  };

  const handleDelete = async () => {
    if (confirm('Sei sicuro di voler eliminare questo job?')) {
      try {
        await deleteJob(currentJob.job_id);
        if (onDelete) onDelete(currentJob.job_id);
      } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        alert('Errore nell\'eliminazione del job');
      }
    }
  };

  const handleStartEdit = () => {
    setEditValue(currentJob.name || getJobTypeName());
    setEditing(true);
  };

  const handleSaveEdit = async () => {
    const trimmed = editValue.trim();
    if (!trimmed) {
      setEditing(false);
      return;
    }
    try {
      await renameJob(currentJob.job_id, trimmed);
      setCurrentJob({ ...currentJob, name: trimmed });
      if (onUpdate) onUpdate({ ...currentJob, name: trimmed });
    } catch (error) {
      console.error('Errore nella rinomina:', error);
    }
    setEditing(false);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      setEditing(false);
    }
  };

  // Compilatio scan handlers
  const handleStartScan = async () => {
    if (scanScanning || !currentJob.result) return;
    setScanScanning(true);
    setScanError(null);
    setScanProgress(0);

    try {
      const sourceType = currentJob.job_type === 'generation' ? 'generate' : 'humanize';
      const response = await startCompilatioScan(currentJob.result, sourceType, currentJob.job_id);

      if (response.cached && response.cached_scan) {
        setScanResult(response.cached_scan);
        setScanScanning(false);
        if (onScanComplete) onScanComplete(currentJob.job_id, response.cached_scan);
        return;
      }

      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => setScanProgress(status.progress || 0),
        4000
      );

      if (finalStatus.status === 'completed' && finalStatus.result) {
        try {
          const parsed = JSON.parse(finalStatus.result);
          setScanResult(parsed);
          if (onScanComplete) onScanComplete(currentJob.job_id, parsed);
        } catch {
          setScanResult(finalStatus.result);
        }
      } else if (finalStatus.status === 'failed') {
        setScanError(finalStatus.error || 'Scansione fallita');
      }
    } catch (error) {
      console.error('Errore scansione:', error);
      setScanError(error.response?.data?.detail || 'Errore durante la scansione');
    } finally {
      setScanScanning(false);
    }
  };

  const handleDownloadScanReport = async () => {
    if (scanResult?.scan_id) {
      try {
        await downloadCompilatioReport(scanResult.scan_id);
      } catch (error) {
        console.error('Errore download report:', error);
      }
    }
  };

  const getAIScoreColor = (percent) => {
    if (percent <= 5) return 'text-green-600 bg-green-50 border-green-200';
    if (percent <= 20) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatEstimatedTime = (seconds) => {
    if (!seconds || seconds <= 0) return null;

    if (seconds < 60) {
      return `~${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs > 0 ? `~${minutes}m ${secs}s` : `~${minutes}m`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return minutes > 0 ? `~${hours}h ${minutes}m` : `~${hours}h`;
    }
  };

  const getJobTypeName = () => {
    switch (currentJob.job_type) {
      case 'training':
        return 'Training PDF';
      case 'generation':
        return 'Generazione Contenuto';
      case 'humanization':
        return 'Umanizzazione Testo';
      default:
        return currentJob.job_type;
    }
  };

  const getJobTypeIcon = () => {
    switch (currentJob.job_type) {
      case 'training':
        return <FileText className="w-5 h-5 text-blue-500" />;
      case 'generation':
        return <Sparkles className="w-5 h-5 text-primary-500" />;
      case 'humanization':
        return <Wand2 className="w-5 h-5 text-purple-500" />;
      default:
        return null;
    }
  };

  const getJobTypeColor = () => {
    switch (currentJob.job_type) {
      case 'training':
        return 'from-blue-500 to-blue-700';
      case 'generation':
        return 'from-primary-500 to-primary-700';
      case 'humanization':
        return 'from-purple-500 to-pink-600';
      default:
        return 'from-slate-500 to-slate-700';
    }
  };

  const displayName = currentJob.name || getJobTypeName();

  return (
    <div className="card hover:shadow-xl transition-all duration-300 hover:scale-[1.02] border-l-4" style={{ borderLeftColor: currentJob.status === 'completed' ? '#10b981' : currentJob.status === 'failed' ? '#ef4444' : '#6366f1' }}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${getJobTypeColor()} flex items-center justify-center shadow-lg transform transition-transform hover:rotate-12`}>
            {getJobTypeIcon() ? (
              <span className="text-white">{getJobTypeIcon()}</span>
            ) : (
              getStatusIcon()
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 group">
              {editing ? (
                <input
                  ref={editInputRef}
                  type="text"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={handleSaveEdit}
                  onKeyDown={handleEditKeyDown}
                  className="font-bold text-slate-900 text-lg bg-white border border-slate-300 rounded-lg px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  maxLength={255}
                />
              ) : (
                <>
                  <p className="font-bold text-slate-900 text-lg">
                    {displayName}
                  </p>
                  <button
                    onClick={handleStartEdit}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-slate-100 rounded"
                    title="Rinomina"
                  >
                    <Pencil className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                  {getStatusIcon()}
                </>
              )}
            </div>
            <p className="font-mono text-xs text-slate-500 mt-1 bg-slate-50 px-2 py-0.5 rounded">
              {currentJob.job_id}
            </p>
            <p className="text-xs text-slate-600 mt-1 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(currentJob.created_at)}
            </p>
          </div>
        </div>
        <span className={`px-3 py-1.5 rounded-full text-xs font-bold ${getStatusColor()} shadow-sm`}>
          {getStatusText()}
        </span>
      </div>

      {/* Progress Bar */}
      {(currentJob.status === 'pending' || currentJob.status === 'training' || currentJob.status === 'generating') && (
        <div className="mb-4 p-4 bg-gradient-to-br from-slate-50 to-blue-50 rounded-xl border border-slate-200">
          <div className="flex items-center justify-between text-sm text-slate-700 mb-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold">Progresso</span>
              {currentJob.status === 'training' || currentJob.status === 'generating' ? (
                <span className="text-xs text-primary-600 font-bold animate-pulse flex items-center gap-1">
                  <span className="w-2 h-2 bg-primary-600 rounded-full"></span>
                  Elaborazione in corso...
                </span>
              ) : estimatedTime && (
                <span className="text-xs text-slate-600 bg-white px-2 py-1 rounded-lg shadow-sm">
                  Tempo stimato: {formatEstimatedTime(estimatedTime)}
                </span>
              )}
            </div>
            <span className="font-bold text-primary-600 text-lg">{currentJob.progress || 0}%</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden shadow-inner">
            <div
              className={`h-3 rounded-full transition-all duration-500 ${
                currentJob.status === 'training' || currentJob.status === 'generating'
                  ? 'bg-gradient-to-r from-primary-500 via-primary-600 to-primary-500 animate-pulse shadow-lg'
                  : 'bg-gradient-to-r from-primary-500 to-primary-700 shadow-md'
              }`}
              style={{ width: `${currentJob.progress || 0}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {currentJob.error && (
        <div className="mb-4 p-4 bg-gradient-to-br from-red-50 to-red-100 border-l-4 border-red-500 rounded-xl shadow-sm">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-900 mb-1">Errore riscontrato</p>
              <p className="text-sm text-red-700">{currentJob.error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Result Preview */}
      {showResult && currentJob.result && currentJob.status === 'completed' && (
        <div className="mb-4 p-4 bg-gradient-to-br from-green-50 to-emerald-50 border-l-4 border-green-500 rounded-xl shadow-sm">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs text-green-800 mb-2 font-bold uppercase tracking-wide">
                Risultato:
              </p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                {currentJob.result}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Detector AI Scan - Admin Only */}
      {isAdmin && currentJob.status === 'completed' && currentJob.result && (currentJob.job_type === 'generation' || currentJob.job_type === 'humanization') && (
        <div className="mb-4">
          {!scanResult && !scanScanning && !scanError && (
            <button
              onClick={handleStartScan}
              className="btn btn-sm gap-2 text-xs bg-gradient-to-r from-purple-500 to-indigo-600 text-white hover:from-purple-600 hover:to-indigo-700"
            >
              <Shield className="w-3.5 h-3.5" />
              Scansione Detector AI
            </button>
          )}

          {scanScanning && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <Loader className="w-4 h-4 text-purple-600 animate-spin" />
                <span className="text-purple-700 font-medium text-xs">Scansione in corso...</span>
              </div>
              <div className="w-full bg-purple-200 rounded-full h-1.5">
                <div
                  className="bg-gradient-to-r from-purple-500 to-indigo-500 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${scanProgress}%` }}
                ></div>
              </div>
            </div>
          )}

          {scanError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-2 flex items-center gap-2 text-xs">
              <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
              <span className="text-red-700">{scanError}</span>
              <button onClick={handleStartScan} className="ml-auto text-red-600 hover:text-red-800 underline">
                Riprova
              </button>
            </div>
          )}

          {scanResult && (
            <div className="bg-purple-50/50 border border-purple-200 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-purple-700 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5" />
                  Detector AI
                </span>
                {scanResult.has_report && (
                  <button
                    onClick={handleDownloadScanReport}
                    className="text-xs text-purple-600 hover:text-purple-800 underline flex items-center gap-1"
                  >
                    <FileText className="w-3 h-3" />
                    Report PDF
                  </button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                <div className={`rounded p-2 border text-center ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                  <div className="text-sm font-bold">{scanResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-[10px] font-medium opacity-80">AI</div>
                </div>
                <div className="rounded p-2 border bg-blue-50 border-blue-200 text-blue-600 text-center">
                  <div className="text-sm font-bold">{scanResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-[10px] font-medium opacity-80">Simil.</div>
                </div>
                <div className="rounded p-2 border bg-slate-50 border-slate-200 text-slate-600 text-center">
                  <div className="text-sm font-bold">{scanResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-[10px] font-medium opacity-80">Globale</div>
                </div>
                <div className="rounded p-2 border bg-slate-50 border-slate-200 text-slate-600 text-center">
                  <div className="text-sm font-bold">{scanResult.exact_percent?.toFixed(1)}%</div>
                  <div className="text-[10px] font-medium opacity-80">Esatti</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {currentJob.status === 'completed' && (currentJob.job_type === 'generation' || currentJob.job_type === 'humanization') && (
          <button
            onClick={handleDownload}
            className={`btn flex-1 gap-2 shadow-md hover:shadow-lg transition-all ${currentJob.job_type === 'humanization' ? 'bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700 text-white' : 'btn-primary'}`}
          >
            <Download className="w-5 h-5" />
            <span className="font-semibold">Scarica</span>
          </button>
        )}
        {currentJob.status === 'completed' && currentJob.job_type === 'training' && (
          <button
            onClick={handleDownload}
            className="btn btn-primary flex-1 gap-2 shadow-md hover:shadow-lg transition-all"
          >
            <Download className="w-5 h-5" />
            <span className="font-semibold">Scarica</span>
          </button>
        )}
        <button
          onClick={handleDelete}
          className="btn btn-secondary gap-2 shadow-md hover:shadow-lg transition-all hover:bg-red-500 hover:text-white hover:border-red-500"
        >
          <Trash2 className="w-5 h-5" />
          <span className="font-semibold">Elimina</span>
        </button>
      </div>
    </div>
  );
};

export default JobCard;
