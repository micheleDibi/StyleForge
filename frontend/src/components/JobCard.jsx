import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Loader, Clock, Download, Trash2, FileText, Sparkles, Wand2 } from 'lucide-react';
import { getJobStatus, downloadResult, deleteJob } from '../services/api';

const JobCard = ({ job, onUpdate, onDelete, showResult = false }) => {
  const [currentJob, setCurrentJob] = useState(job);
  const [polling, setPolling] = useState(false);
  const [estimatedTime, setEstimatedTime] = useState(null);

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
            <div className="flex items-center gap-2">
              <p className="font-bold text-slate-900 text-lg">
                {getJobTypeName()}
              </p>
              {getStatusIcon()}
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
