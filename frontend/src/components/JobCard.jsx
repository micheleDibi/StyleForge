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

          if (updated.progress && updated.progress > 0) {
            const now = Date.now();
            const progressDelta = updated.progress - lastProgress;

            if (progressDelta > 0) {
              const timeDelta = (now - lastUpdate) / 1000;
              const progressRate = progressDelta / timeDelta;
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

  useEffect(() => {
    if (editing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editing]);

  const getStatusColor = () => {
    switch (currentJob.status) {
      case 'completed': return 'border-green-400';
      case 'failed': return 'border-red-400';
      case 'pending': return 'border-gray-300';
      default: return 'border-orange-400';
    }
  };

  const getStatusBadge = () => {
    switch (currentJob.status) {
      case 'completed':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-green-100 text-green-700"><CheckCircle className="w-3 h-3" />Completato</span>;
      case 'failed':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-red-100 text-red-700"><XCircle className="w-3 h-3" />Fallito</span>;
      case 'pending':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-600"><Clock className="w-3 h-3" />In coda</span>;
      case 'training':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-orange-100 text-orange-700"><Loader className="w-3 h-3 animate-spin" />Training</span>;
      case 'generating':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-orange-100 text-orange-700"><Loader className="w-3 h-3 animate-spin" />Generazione</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-600">{currentJob.status}</span>;
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
    if (seconds < 60) return `~${seconds}s`;
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs > 0 ? `~${minutes}m ${secs}s` : `~${minutes}m`;
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `~${hours}h ${minutes}m` : `~${hours}h`;
  };

  const getJobTypeName = () => {
    switch (currentJob.job_type) {
      case 'training': return 'Training PDF';
      case 'generation': return 'Generazione Contenuto';
      case 'humanization': return 'Umanizzazione Testo';
      default: return currentJob.job_type;
    }
  };

  const getJobTypeIcon = () => {
    switch (currentJob.job_type) {
      case 'training': return <FileText className="w-4 h-4 text-white" />;
      case 'generation': return <Sparkles className="w-4 h-4 text-white" />;
      case 'humanization': return <Wand2 className="w-4 h-4 text-white" />;
      default: return null;
    }
  };

  const getJobTypeGradient = () => {
    switch (currentJob.job_type) {
      case 'training': return 'from-blue-500 to-blue-600';
      case 'generation': return 'from-orange-500 to-orange-600';
      case 'humanization': return 'from-purple-500 to-pink-600';
      default: return 'from-gray-500 to-gray-600';
    }
  };

  const displayName = currentJob.name || getJobTypeName();

  return (
    <div className={`bg-white rounded-xl border-l-4 ${getStatusColor()} border border-gray-200/60 p-4 hover:shadow-md transition-all`}>
      {/* Header Row */}
      <div className="flex items-start gap-3">
        {/* Type Icon */}
        <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${getJobTypeGradient()} flex items-center justify-center shadow-sm flex-shrink-0`}>
          {getJobTypeIcon()}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 group">
            {editing ? (
              <input
                ref={editInputRef}
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={handleSaveEdit}
                onKeyDown={handleEditKeyDown}
                className="font-semibold text-sm text-gray-900 bg-white border border-gray-300 rounded-lg px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent"
                maxLength={255}
              />
            ) : (
              <>
                <h4 className="font-semibold text-sm text-gray-900 truncate">{displayName}</h4>
                <button
                  onClick={handleStartEdit}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded flex-shrink-0"
                  title="Rinomina"
                >
                  <Pencil className="w-3 h-3 text-gray-400" />
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            {getStatusBadge()}
            {/* Inline AI badge for completed scans */}
            {scanResult && (
              <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                AI {scanResult.ai_generated_percent?.toFixed(0)}%
              </span>
            )}
            <span className="text-[11px] text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(currentJob.created_at)}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {currentJob.status === 'completed' && (currentJob.job_type === 'generation' || currentJob.job_type === 'humanization' || currentJob.job_type === 'training') && (
            <button
              onClick={handleDownload}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-orange-500 text-white hover:bg-orange-600 shadow-sm transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Scarica
            </button>
          )}
          <button
            onClick={handleDelete}
            className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      {(currentJob.status === 'pending' || currentJob.status === 'training' || currentJob.status === 'generating') && (
        <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-100">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-gray-500 font-medium">
              {currentJob.status === 'training' || currentJob.status === 'generating' ? (
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></span>
                  Elaborazione...
                </span>
              ) : estimatedTime ? (
                `Tempo stimato: ${formatEstimatedTime(estimatedTime)}`
              ) : (
                'In attesa...'
              )}
            </span>
            <span className="font-bold text-orange-600">{currentJob.progress || 0}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                currentJob.status === 'training' || currentJob.status === 'generating'
                  ? 'bg-gradient-to-r from-orange-400 to-orange-600 animate-pulse'
                  : 'bg-orange-500'
              }`}
              style={{ width: `${currentJob.progress || 0}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Error */}
      {currentJob.error && (
        <div className="mt-3 flex items-start gap-2 bg-red-50 rounded-lg p-3 border border-red-100">
          <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs font-medium text-red-800">Errore</p>
            <p className="text-xs text-red-600 mt-0.5">{currentJob.error}</p>
          </div>
        </div>
      )}

      {/* Result Preview */}
      {showResult && currentJob.result && currentJob.status === 'completed' && (
        <div className="mt-3 bg-green-50 rounded-lg p-3 border border-green-100">
          <p className="text-[10px] text-green-700 font-bold uppercase tracking-wide mb-1">Risultato</p>
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{currentJob.result}</p>
        </div>
      )}

      {/* Detector AI Scan */}
      {isAdmin && currentJob.status === 'completed' && currentJob.result && (currentJob.job_type === 'generation' || currentJob.job_type === 'humanization') && (
        <div className="mt-3">
          {!scanResult && !scanScanning && !scanError && (
            <button
              onClick={handleStartScan}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200/60 transition-colors"
            >
              <Shield className="w-3.5 h-3.5" />
              Scansione Detector AI
            </button>
          )}

          {scanScanning && (
            <div className="bg-purple-50 border border-purple-100 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <Loader className="w-3.5 h-3.5 text-purple-600 animate-spin" />
                <span className="text-purple-700 font-medium text-xs">Scansione in corso...</span>
              </div>
              <div className="w-full bg-purple-200 rounded-full h-1.5">
                <div className="bg-purple-500 h-1.5 rounded-full transition-all duration-500" style={{ width: `${scanProgress}%` }}></div>
              </div>
            </div>
          )}

          {scanError && (
            <div className="bg-red-50 border border-red-100 rounded-lg p-2 flex items-center gap-2 text-xs">
              <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
              <span className="text-red-700">{scanError}</span>
              <button onClick={handleStartScan} className="ml-auto text-red-600 hover:text-red-800 font-medium">Riprova</button>
            </div>
          )}

          {scanResult && (
            <div className="bg-white rounded-lg border border-purple-200/60 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-purple-600 uppercase tracking-wide flex items-center gap-1">
                  <Shield className="w-3 h-3" /> Detector AI
                </span>
                {scanResult.has_report && (
                  <button
                    onClick={handleDownloadScanReport}
                    className="text-[11px] text-purple-600 hover:text-purple-800 flex items-center gap-1 font-medium"
                  >
                    <Download className="w-3 h-3" /> Report
                  </button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className={`rounded-lg p-2 border text-center ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                  <div className="text-base font-bold">{scanResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">AI</div>
                </div>
                <div className="rounded-lg p-2 border bg-blue-50 border-blue-200/60 text-blue-600 text-center">
                  <div className="text-base font-bold">{scanResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Simil.</div>
                </div>
                <div className="rounded-lg p-2 border bg-gray-50 border-gray-200/60 text-gray-600 text-center">
                  <div className="text-base font-bold">{scanResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Globale</div>
                </div>
                <div className="rounded-lg p-2 border bg-gray-50 border-gray-200/60 text-gray-600 text-center">
                  <div className="text-base font-bold">{scanResult.exact_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Esatti</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default JobCard;
