import { useState, useEffect, useRef } from 'react';
import { CheckCircle, XCircle, Loader, Clock, Download, Trash2, FileText, Sparkles, Wand2, Pencil, Shield, RefreshCw } from 'lucide-react';
import { getJobStatus, downloadResult, deleteJob, renameJob, startCompilatioScan, downloadCompilatioReport, pollJobStatus } from '../services/api';

const JobCard = ({ job, onUpdate, onDelete, showResult = false, scanResult: initialScanResult, isAdmin = false, onScanComplete }) => {
  const [currentJob, setCurrentJob] = useState(job);
  const [polling, setPolling] = useState(false);
  const [estimatedTime, setEstimatedTime] = useState(null);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const editInputRef = useRef(null);
  const [scanResult, setScanResult] = useState(initialScanResult || null);
  const [scanScanning, setScanScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanError, setScanError] = useState(null);

  useEffect(() => { if (initialScanResult) setScanResult(initialScanResult); }, [initialScanResult]);

  useEffect(() => {
    setCurrentJob(job);
    if (['pending', 'training', 'generating'].includes(job.status)) {
      setPolling(true);
      let lastProgress = job.progress || 0, lastUpdate = Date.now();
      const interval = setInterval(async () => {
        try {
          const updated = await getJobStatus(job.job_id);
          setCurrentJob(updated);
          if (onUpdate) onUpdate(updated);
          if (updated.progress > 0) {
            const now = Date.now(), delta = updated.progress - lastProgress;
            if (delta > 0) {
              setEstimatedTime(Math.ceil((100 - updated.progress) / (delta / ((now - lastUpdate) / 1000))));
              lastProgress = updated.progress; lastUpdate = now;
            }
          }
          if (['completed', 'failed'].includes(updated.status)) { setPolling(false); setEstimatedTime(null); clearInterval(interval); }
        } catch {}
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [job.job_id]);

  useEffect(() => { if (editing && editInputRef.current) { editInputRef.current.focus(); editInputRef.current.select(); } }, [editing]);

  const handleDownload = async () => { try { await downloadResult(currentJob.job_id); } catch { alert('Errore nel download'); } };
  const handleDelete = async () => {
    if (confirm('Eliminare questo job?')) {
      try { await deleteJob(currentJob.job_id); if (onDelete) onDelete(currentJob.job_id); } catch { alert('Errore nell\'eliminazione'); }
    }
  };

  const handleStartEdit = () => { setEditValue(currentJob.name || getJobTypeName()); setEditing(true); };
  const handleSaveEdit = async () => {
    const trimmed = editValue.trim();
    if (!trimmed) { setEditing(false); return; }
    try { await renameJob(currentJob.job_id, trimmed); const u = { ...currentJob, name: trimmed }; setCurrentJob(u); if (onUpdate) onUpdate(u); } catch {}
    setEditing(false);
  };
  const handleEditKeyDown = (e) => { if (e.key === 'Enter') handleSaveEdit(); else if (e.key === 'Escape') setEditing(false); };

  const handleStartScan = async () => {
    if (scanScanning || !currentJob.result) return;
    setScanScanning(true); setScanError(null); setScanProgress(0);
    try {
      const sourceType = currentJob.job_type === 'generation' ? 'generate' : 'humanize';
      const response = await startCompilatioScan(currentJob.result, sourceType, currentJob.job_id);
      if (response.cached && response.cached_scan) {
        setScanResult(response.cached_scan); setScanScanning(false);
        if (onScanComplete) onScanComplete(currentJob.job_id, response.cached_scan); return;
      }
      const finalStatus = await pollJobStatus(response.job_id, s => setScanProgress(s.progress || 0), 4000);
      if (finalStatus.status === 'completed' && finalStatus.result) {
        try { const parsed = JSON.parse(finalStatus.result); setScanResult(parsed); if (onScanComplete) onScanComplete(currentJob.job_id, parsed); }
        catch { setScanResult(finalStatus.result); }
      } else if (finalStatus.status === 'failed') setScanError(finalStatus.error || 'Scansione fallita');
    } catch (error) { setScanError(error.response?.data?.detail || 'Errore scansione'); }
    finally { setScanScanning(false); }
  };

  const handleDownloadScanReport = async () => { if (scanResult?.scan_id) try { await downloadCompilatioReport(scanResult.scan_id); } catch {} };

  const getAIScoreColor = (p) => p <= 5 ? 'text-green-700 bg-green-50 border-green-200' : p <= 20 ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-red-700 bg-red-50 border-red-200';
  const getAIBadge = (p) => p <= 5 ? 'badge-success' : p <= 20 ? 'badge-warning' : 'badge-error';

  const formatDate = (d) => new Date(d).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const formatTime = (s) => { if (!s || s <= 0) return null; if (s < 60) return `~${s}s`; if (s < 3600) { const m = Math.floor(s/60); return `~${m}m`; } return `~${Math.floor(s/3600)}h`; };

  const getJobTypeName = () => ({ training: 'Training PDF', generation: 'Generazione', humanization: 'Umanizzazione' }[currentJob.job_type] || currentJob.job_type);
  const getJobTypeIcon = () => ({ training: FileText, generation: Sparkles, humanization: Wand2 }[currentJob.job_type]);
  const getJobTypeGradient = () => ({ training: 'from-blue-400 to-blue-600', generation: 'from-orange-400 to-orange-600', humanization: 'from-purple-400 to-purple-600' }[currentJob.job_type] || 'from-gray-400 to-gray-500');
  const getStatusBorder = () => ({ completed: 'border-l-green-500', failed: 'border-l-red-500', pending: 'border-l-gray-300', training: 'border-l-orange-500', generating: 'border-l-orange-500' }[currentJob.status] || 'border-l-orange-500');

  const statusBadge = {
    completed: <span className="badge badge-success"><CheckCircle className="w-3 h-3" />Completato</span>,
    failed: <span className="badge badge-error"><XCircle className="w-3 h-3" />Fallito</span>,
    pending: <span className="badge badge-neutral"><Clock className="w-3 h-3" />In coda</span>,
    training: <span className="badge badge-warning"><Loader className="w-3 h-3 animate-spin" />Training</span>,
    generating: <span className="badge badge-warning"><Loader className="w-3 h-3 animate-spin" />Generazione</span>,
  };

  const TypeIcon = getJobTypeIcon();
  const displayName = currentJob.name || getJobTypeName();

  return (
    <div className={`glass rounded-2xl border-l-[3px] ${getStatusBorder()} p-4 hover:bg-white/50 transition-colors`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${getJobTypeGradient()} flex items-center justify-center shadow-lg flex-shrink-0`}>
          {TypeIcon && <TypeIcon className="w-5 h-5 text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 group">
            {editing ? (
              <input ref={editInputRef} type="text" value={editValue} onChange={e => setEditValue(e.target.value)}
                onBlur={handleSaveEdit} onKeyDown={handleEditKeyDown}
                className="input py-0.5 px-2 text-sm font-semibold" maxLength={255} />
            ) : (
              <>
                <h4 className="text-sm font-bold text-gray-900 truncate">{displayName}</h4>
                <button onClick={handleStartEdit} className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded-lg flex-shrink-0">
                  <Pencil className="w-3 h-3 text-gray-400" />
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {statusBadge[currentJob.status]}
            {scanResult && (
              <span className={`badge text-[10px] ${getAIBadge(scanResult.ai_generated_percent)}`}>
                AI {scanResult.ai_generated_percent?.toFixed(0)}%
              </span>
            )}
            <span className="text-xs text-gray-500">{formatDate(currentJob.created_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {currentJob.status === 'completed' && (currentJob.job_type !== 'compilatio_scan') && (
            <button onClick={handleDownload} className="btn btn-primary btn-sm">
              <Download className="w-3 h-3" /> Scarica
            </button>
          )}
          <button onClick={handleDelete} className="btn btn-ghost text-gray-400 hover:text-red-500 hover:bg-red-50">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress */}
      {['pending', 'training', 'generating'].includes(currentJob.status) && (
        <div className="mt-3 bg-white rounded-xl p-3 border border-gray-100">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-gray-500 flex items-center gap-1.5">
              {['training','generating'].includes(currentJob.status) && <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></span>}
              {['training','generating'].includes(currentJob.status) ? 'Elaborazione...' : estimatedTime ? `Stimato: ${formatTime(estimatedTime)}` : 'In attesa...'}
            </span>
            <span className="font-bold text-orange-600">{currentJob.progress || 0}%</span>
          </div>
          <div className="progress-bar">
            <div className={`progress-bar-fill ${['training','generating'].includes(currentJob.status) ? 'animate-pulse' : ''}`}
              style={{ width: `${currentJob.progress || 0}%` }}></div>
          </div>
        </div>
      )}

      {/* Error */}
      {currentJob.error && (
        <div className="mt-3 flex items-start gap-2 bg-red-50 rounded-xl p-3 border border-red-200">
          <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-red-700">{currentJob.error}</p>
        </div>
      )}

      {/* Result */}
      {showResult && currentJob.result && currentJob.status === 'completed' && (
        <div className="mt-3 bg-green-50 rounded-xl p-3 border border-green-200">
          <p className="text-[10px] text-green-700 font-bold uppercase tracking-wide mb-1">Risultato</p>
          <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{currentJob.result}</p>
        </div>
      )}

      {/* Scan */}
      {isAdmin && currentJob.status === 'completed' && currentJob.result && ['generation','humanization'].includes(currentJob.job_type) && (
        <div className="mt-3">
          {!scanResult && !scanScanning && !scanError && (
            <button onClick={handleStartScan} className="btn btn-secondary btn-sm">
              <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
            </button>
          )}
          {scanScanning && (
            <div className="bg-purple-50 border border-purple-200 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <Loader className="w-3.5 h-3.5 text-purple-600 animate-spin" />
                <span className="text-purple-700 text-xs font-medium">Scansione...</span>
              </div>
              <div className="progress-bar">
                <div className="progress-bar-fill" style={{ width: `${scanProgress}%` }}></div>
              </div>
            </div>
          )}
          {scanError && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-center gap-2 text-xs">
              <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
              <span className="text-red-700">{scanError}</span>
              <button onClick={handleStartScan} className="ml-auto text-red-600 hover:text-red-800 font-bold">Riprova</button>
            </div>
          )}
          {scanResult && (
            <div className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-purple-700 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3.5 h-3.5" /> Detector AI</span>
                {scanResult.has_report && (
                  <button onClick={handleDownloadScanReport} className="btn btn-ghost btn-sm text-purple-600"><Download className="w-3 h-3" /> Report</button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className={`rounded-xl p-2.5 border text-center ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                  <div className="text-sm font-bold">{scanResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">AI</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-blue-50 border-blue-200 text-blue-700 text-center">
                  <div className="text-sm font-bold">{scanResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Simil.</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-gray-50 border-gray-200 text-gray-700 text-center">
                  <div className="text-sm font-bold">{scanResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Globale</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-gray-50 border-gray-200 text-gray-700 text-center">
                  <div className="text-sm font-bold">{scanResult.exact_percent?.toFixed(1)}%</div>
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
