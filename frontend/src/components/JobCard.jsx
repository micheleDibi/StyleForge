import { useState, useEffect, useRef } from 'react';
import { CheckCircle, XCircle, Loader, Clock, Download, Trash2, FileText, Sparkles, Wand2, Pencil, Shield } from 'lucide-react';
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

  const getAIScoreColor = (p) => p <= 5 ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : p <= 20 ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-red-600 bg-red-50 border-red-200';

  const formatDate = (d) => new Date(d).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const formatTime = (s) => { if (!s || s <= 0) return null; if (s < 60) return `~${s}s`; if (s < 3600) { const m = Math.floor(s/60); return `~${m}m`; } return `~${Math.floor(s/3600)}h`; };

  const getJobTypeName = () => ({ training: 'Training PDF', generation: 'Generazione', humanization: 'Umanizzazione' }[currentJob.job_type] || currentJob.job_type);
  const getJobTypeIcon = () => ({ training: FileText, generation: Sparkles, humanization: Wand2 }[currentJob.job_type]);
  const getJobTypeGradient = () => ({ training: 'from-blue-500 to-indigo-500', generation: 'from-orange-500 to-amber-500', humanization: 'from-violet-500 to-purple-600' }[currentJob.job_type] || 'from-gray-400 to-gray-500');
  const getJobTypeShadow = () => ({ training: 'shadow-blue-500/15', generation: 'shadow-orange-500/15', humanization: 'shadow-violet-500/15' }[currentJob.job_type] || 'shadow-gray-500/15');
  const getStatusBorder = () => ({ completed: 'border-l-emerald-400', failed: 'border-l-red-400', pending: 'border-l-gray-300', training: 'border-l-orange-400', generating: 'border-l-orange-400' }[currentJob.status] || 'border-l-orange-400');

  const statusBadge = {
    completed: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-200/50"><CheckCircle className="w-3 h-3" />Completato</span>,
    failed: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-50 text-red-600 border border-red-200/50"><XCircle className="w-3 h-3" />Fallito</span>,
    pending: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-50 text-gray-500 border border-gray-200/50"><Clock className="w-3 h-3" />In coda</span>,
    training: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-200/50"><Loader className="w-3 h-3 animate-spin" />Training</span>,
    generating: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-200/50"><Loader className="w-3 h-3 animate-spin" />Generazione</span>,
  };

  const TypeIcon = getJobTypeIcon();
  const displayName = currentJob.name || getJobTypeName();

  return (
    <div className={`bg-white/60 backdrop-blur-sm border border-white/80 border-l-[3px] ${getStatusBorder()} rounded-2xl p-4 hover:shadow-md hover:-translate-y-px transition-all duration-300 shadow-sm`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${getJobTypeGradient()} ${getJobTypeShadow()} shadow-lg flex items-center justify-center flex-shrink-0`}>
          {TypeIcon && <TypeIcon className="w-4 h-4 text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 group">
            {editing ? (
              <input ref={editInputRef} type="text" value={editValue} onChange={e => setEditValue(e.target.value)}
                onBlur={handleSaveEdit} onKeyDown={handleEditKeyDown}
                className="text-sm font-semibold text-gray-800 bg-white border border-gray-200 rounded-xl px-2.5 py-0.5 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-300" maxLength={255} />
            ) : (
              <>
                <h4 className="text-sm font-semibold text-gray-800 truncate">{displayName}</h4>
                <button onClick={handleStartEdit} className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded-lg flex-shrink-0">
                  <Pencil className="w-3 h-3 text-gray-400" />
                </button>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            {statusBadge[currentJob.status]}
            {scanResult && (
              <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold border ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                AI {scanResult.ai_generated_percent?.toFixed(0)}%
              </span>
            )}
            <span className="text-[11px] text-gray-400">{formatDate(currentJob.created_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {currentJob.status === 'completed' && (currentJob.job_type !== 'compilatio_scan') && (
            <button onClick={handleDownload}
              className="px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-gradient-to-r from-orange-500 to-amber-500 text-white hover:shadow-md hover:shadow-orange-500/15 transition-all flex items-center gap-1 shadow-sm">
              <Download className="w-3 h-3" /> Scarica
            </button>
          )}
          <button onClick={handleDelete} className="p-1.5 rounded-xl text-gray-300 hover:text-red-500 hover:bg-red-50 transition-all">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress */}
      {['pending', 'training', 'generating'].includes(currentJob.status) && (
        <div className="mt-3 bg-white/50 backdrop-blur-sm rounded-xl p-3 border border-white/60 shadow-sm">
          <div className="flex items-center justify-between text-[11px] mb-1.5">
            <span className="text-gray-400 flex items-center gap-1.5">
              {['training','generating'].includes(currentJob.status) && <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></span>}
              {['training','generating'].includes(currentJob.status) ? 'Elaborazione...' : estimatedTime ? `Stimato: ${formatTime(estimatedTime)}` : 'In attesa...'}
            </span>
            <span className="font-bold text-orange-600">{currentJob.progress || 0}%</span>
          </div>
          <div className="w-full bg-orange-100/50 rounded-full h-1.5 overflow-hidden">
            <div className={`h-1.5 rounded-full transition-all duration-500 bg-gradient-to-r from-orange-500 to-amber-500 ${['training','generating'].includes(currentJob.status) ? 'animate-pulse' : ''}`}
              style={{ width: `${currentJob.progress || 0}%` }}></div>
          </div>
        </div>
      )}

      {/* Error */}
      {currentJob.error && (
        <div className="mt-3 flex items-start gap-2 bg-red-50/80 rounded-xl p-3 border border-red-200/50">
          <XCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />
          <p className="text-[11px] text-red-600">{currentJob.error}</p>
        </div>
      )}

      {/* Result */}
      {showResult && currentJob.result && currentJob.status === 'completed' && (
        <div className="mt-3 bg-emerald-50/60 backdrop-blur-sm rounded-xl p-3 border border-emerald-200/50">
          <p className="text-[10px] text-emerald-600 font-bold uppercase tracking-wide mb-1">Risultato</p>
          <p className="text-[11px] text-gray-600 whitespace-pre-wrap leading-relaxed">{currentJob.result}</p>
        </div>
      )}

      {/* Scan */}
      {isAdmin && currentJob.status === 'completed' && currentJob.result && ['generation','humanization'].includes(currentJob.job_type) && (
        <div className="mt-3">
          {!scanResult && !scanScanning && !scanError && (
            <button onClick={handleStartScan}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-violet-50 text-violet-600 hover:bg-violet-100 border border-violet-200/50 transition-all">
              <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
            </button>
          )}
          {scanScanning && (
            <div className="bg-violet-50/60 backdrop-blur-sm border border-violet-200/50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <Loader className="w-3.5 h-3.5 text-violet-500 animate-spin" />
                <span className="text-violet-600 text-[11px] font-medium">Scansione...</span>
              </div>
              <div className="w-full bg-violet-100/50 rounded-full h-1">
                <div className="bg-violet-500 h-1 rounded-full transition-all" style={{ width: `${scanProgress}%` }}></div>
              </div>
            </div>
          )}
          {scanError && (
            <div className="bg-red-50/60 border border-red-200/50 rounded-xl p-2.5 flex items-center gap-2 text-[11px]">
              <XCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
              <span className="text-red-600">{scanError}</span>
              <button onClick={handleStartScan} className="ml-auto text-red-500 hover:text-red-700 font-semibold">Riprova</button>
            </div>
          )}
          {scanResult && (
            <div className="bg-violet-50/50 backdrop-blur-sm border border-violet-200/50 rounded-xl p-3.5">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[10px] font-bold text-violet-600 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3 h-3" /> Detector AI</span>
                {scanResult.has_report && (
                  <button onClick={handleDownloadScanReport} className="text-[11px] text-violet-500 hover:text-violet-700 flex items-center gap-1 font-medium"><Download className="w-3 h-3" /> Report</button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className={`rounded-xl p-2.5 border text-center ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                  <div className="text-sm font-bold">{scanResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">AI</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-blue-50 border-blue-200 text-blue-600 text-center">
                  <div className="text-sm font-bold">{scanResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Simil.</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-gray-50 border-gray-200 text-gray-600 text-center">
                  <div className="text-sm font-bold">{scanResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] font-medium opacity-70 uppercase">Globale</div>
                </div>
                <div className="rounded-xl p-2.5 border bg-gray-50 border-gray-200 text-gray-600 text-center">
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
