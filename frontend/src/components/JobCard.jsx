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

  const getAIScoreColor = (p) => p <= 5 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : p <= 20 ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20';

  const formatDate = (d) => new Date(d).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const formatTime = (s) => { if (!s || s <= 0) return null; if (s < 60) return `~${s}s`; if (s < 3600) { const m = Math.floor(s/60); return `~${m}m`; } return `~${Math.floor(s/3600)}h`; };

  const getJobTypeName = () => ({ training: 'Training PDF', generation: 'Generazione', humanization: 'Umanizzazione' }[currentJob.job_type] || currentJob.job_type);
  const getJobTypeIcon = () => ({ training: FileText, generation: Sparkles, humanization: Wand2 }[currentJob.job_type]);
  const getJobTypeGradient = () => ({ training: 'from-blue-500 to-cyan-500', generation: 'from-orange-500 to-amber-500', humanization: 'from-purple-500 to-pink-500' }[currentJob.job_type] || 'from-gray-500 to-gray-600');

  const statusColor = { completed: 'border-l-emerald-500', failed: 'border-l-red-500', pending: 'border-l-gray-600' };
  const statusBadge = {
    completed: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><CheckCircle className="w-3 h-3" />Completato</span>,
    failed: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20"><XCircle className="w-3 h-3" />Fallito</span>,
    pending: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-white/5 text-gray-400 border border-white/10"><Clock className="w-3 h-3" />In coda</span>,
    training: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20"><Loader className="w-3 h-3 animate-spin" />Training</span>,
    generating: <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20"><Loader className="w-3 h-3 animate-spin" />Generazione</span>,
  };

  const TypeIcon = getJobTypeIcon();
  const displayName = currentJob.name || getJobTypeName();

  return (
    <div className={`bg-white/[0.03] border border-white/[0.06] border-l-2 ${statusColor[currentJob.status] || 'border-l-orange-500'} rounded-xl p-3.5 hover:border-white/[0.1] transition-colors`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${getJobTypeGradient()} flex items-center justify-center shadow-lg flex-shrink-0`}>
          {TypeIcon && <TypeIcon className="w-4 h-4 text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 group">
            {editing ? (
              <input ref={editInputRef} type="text" value={editValue} onChange={e => setEditValue(e.target.value)}
                onBlur={handleSaveEdit} onKeyDown={handleEditKeyDown}
                className="text-sm font-semibold text-white bg-white/5 border border-white/10 rounded-lg px-2 py-0.5 focus:outline-none focus:border-orange-500/30" maxLength={255} />
            ) : (
              <>
                <h4 className="text-sm font-semibold text-gray-200 truncate">{displayName}</h4>
                <button onClick={handleStartEdit} className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-white/5 rounded flex-shrink-0">
                  <Pencil className="w-3 h-3 text-gray-600" />
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
            <span className="text-[11px] text-gray-600">{formatDate(currentJob.created_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {currentJob.status === 'completed' && (currentJob.job_type !== 'compilatio_scan') && (
            <button onClick={handleDownload}
              className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-orange-500 text-white hover:bg-orange-600 transition-colors flex items-center gap-1 shadow-lg shadow-orange-500/10">
              <Download className="w-3 h-3" /> Scarica
            </button>
          )}
          <button onClick={handleDelete} className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress */}
      {['pending', 'training', 'generating'].includes(currentJob.status) && (
        <div className="mt-3 bg-white/[0.02] rounded-lg p-2.5 border border-white/[0.04]">
          <div className="flex items-center justify-between text-[11px] mb-1.5">
            <span className="text-gray-500 flex items-center gap-1">
              {['training','generating'].includes(currentJob.status) && <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-pulse"></span>}
              {['training','generating'].includes(currentJob.status) ? 'Elaborazione...' : estimatedTime ? `Stimato: ${formatTime(estimatedTime)}` : 'In attesa...'}
            </span>
            <span className="font-bold text-orange-400">{currentJob.progress || 0}%</span>
          </div>
          <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
            <div className={`h-1.5 rounded-full transition-all duration-500 bg-gradient-to-r from-orange-500 to-amber-500 ${['training','generating'].includes(currentJob.status) ? 'animate-pulse' : ''}`}
              style={{ width: `${currentJob.progress || 0}%` }}></div>
          </div>
        </div>
      )}

      {/* Error */}
      {currentJob.error && (
        <div className="mt-3 flex items-start gap-2 bg-red-500/5 rounded-lg p-2.5 border border-red-500/10">
          <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-[11px] text-red-300">{currentJob.error}</p>
        </div>
      )}

      {/* Result */}
      {showResult && currentJob.result && currentJob.status === 'completed' && (
        <div className="mt-3 bg-emerald-500/5 rounded-lg p-2.5 border border-emerald-500/10">
          <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-wide mb-1">Risultato</p>
          <p className="text-[11px] text-gray-300 whitespace-pre-wrap leading-relaxed">{currentJob.result}</p>
        </div>
      )}

      {/* Scan */}
      {isAdmin && currentJob.status === 'completed' && currentJob.result && ['generation','humanization'].includes(currentJob.job_type) && (
        <div className="mt-3">
          {!scanResult && !scanScanning && !scanError && (
            <button onClick={handleStartScan}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/20 transition-colors">
              <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
            </button>
          )}
          {scanScanning && (
            <div className="bg-purple-500/5 border border-purple-500/10 rounded-lg p-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <Loader className="w-3.5 h-3.5 text-purple-400 animate-spin" />
                <span className="text-purple-400 text-[11px] font-medium">Scansione...</span>
              </div>
              <div className="w-full bg-purple-500/10 rounded-full h-1">
                <div className="bg-purple-500 h-1 rounded-full transition-all" style={{ width: `${scanProgress}%` }}></div>
              </div>
            </div>
          )}
          {scanError && (
            <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-2 flex items-center gap-2 text-[11px]">
              <XCircle className="w-3 h-3 text-red-400 flex-shrink-0" />
              <span className="text-red-300">{scanError}</span>
              <button onClick={handleStartScan} className="ml-auto text-red-400 hover:text-red-300 font-medium">Riprova</button>
            </div>
          )}
          {scanResult && (
            <div className="bg-white/[0.03] border border-purple-500/20 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3 h-3" /> Detector AI</span>
                {scanResult.has_report && (
                  <button onClick={handleDownloadScanReport} className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"><Download className="w-3 h-3" /> Report</button>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div className={`rounded-lg p-2 border text-center ${getAIScoreColor(scanResult.ai_generated_percent)}`}>
                  <div className="text-sm font-bold">{scanResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] opacity-70 uppercase">AI</div>
                </div>
                <div className="rounded-lg p-2 border bg-blue-500/10 border-blue-500/20 text-blue-400 text-center">
                  <div className="text-sm font-bold">{scanResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] opacity-70 uppercase">Simil.</div>
                </div>
                <div className="rounded-lg p-2 border bg-white/[0.03] border-white/[0.06] text-gray-300 text-center">
                  <div className="text-sm font-bold">{scanResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] opacity-70 uppercase">Globale</div>
                </div>
                <div className="rounded-lg p-2 border bg-white/[0.03] border-white/[0.06] text-gray-300 text-center">
                  <div className="text-sm font-bold">{scanResult.exact_percent?.toFixed(1)}%</div>
                  <div className="text-[9px] opacity-70 uppercase">Esatti</div>
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
