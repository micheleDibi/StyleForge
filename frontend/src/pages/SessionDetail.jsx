import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Upload, FileText, Trash2, CheckCircle,
  AlertCircle, RefreshCw, Sparkles
} from 'lucide-react';
import { getSession, getJobs, trainSession, deleteSession, pollJobStatus } from '../services/api';
import JobCard from '../components/JobCard';

const SessionDetail = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Training state
  const [file, setFile] = useState(null);
  const [maxPages, setMaxPages] = useState(50);
  const [uploading, setUploading] = useState(false);
  const [trainingJob, setTrainingJob] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const loadData = async () => {
    try {
      const [sessionData, jobsData] = await Promise.all([
        getSession(sessionId),
        getJobs(sessionId)
      ]);
      setSession(sessionData);
      setJobs(jobsData.jobs || []);
    } catch (error) {
      console.error('Errore nel caricamento:', error);
      alert('Errore nel caricamento della sessione');
      navigate('/');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.pdf')) {
        setError('Solo file PDF sono supportati');
        return;
      }
      if (selectedFile.size > 100 * 1024 * 1024) {
        setError('Il file non può superare i 100MB');
        return;
      }
      setFile(selectedFile);
      setError('');
    }
  };

  const handleTrainSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError('');

    try {
      const response = await trainSession(file, sessionId, maxPages);
      setTrainingJob({ ...response, status: 'pending', progress: 0 });

      await pollJobStatus(
        response.job_id,
        (status) => setTrainingJob(status),
        3000
      );

      // Ricarica i dati dopo il completamento
      await loadData();
      setFile(null);
    } catch (err) {
      setError(err.message || 'Errore durante il training');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteSession = async () => {
    if (confirm('Sei sicuro di voler eliminare questa sessione? Tutti i job associati verranno eliminati.')) {
      try {
        await deleteSession(sessionId);
        navigate('/');
      } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        alert('Errore nell\'eliminazione della sessione');
      }
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-orange-50">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-[3px] border-slate-200"></div>
            <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-orange-500 animate-spin"></div>
          </div>
          <p className="text-sm text-slate-500 font-medium">Caricamento...</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return null;
  }

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="btn btn-secondary gap-2 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Torna alla Dashboard
          </button>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 mb-2">
                {session.name || session.session_id}
              </h1>
              {session.name && (
                <p className="font-mono text-sm text-slate-500 mb-2">
                  {session.session_id}
                </p>
              )}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-2 h-2 rounded-full ${session.is_trained ? 'bg-green-500' : 'bg-slate-300'}`}></span>
                  <span className="text-sm text-slate-600">
                    {session.is_trained ? 'Addestrata' : 'Non addestrata'}
                  </span>
                </div>
                <span className="text-sm text-slate-600">
                  {session.conversation_length} conversazioni
                </span>
                <span className="text-sm text-slate-600">
                  {jobs.length} job
                </span>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleRefresh}
                className="btn btn-secondary gap-2"
                disabled={refreshing}
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                Aggiorna
              </button>
              {session.is_trained && (
                <button
                  onClick={() => navigate(`/generate?session=${sessionId}`)}
                  className="btn btn-primary gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  Genera Contenuto
                </button>
              )}
              <button
                onClick={handleDeleteSession}
                className="btn btn-secondary gap-2 text-red-600 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4" />
                Elimina
              </button>
            </div>
          </div>
        </div>

        <div>
          {/* Jobs List */}
          <div>
            <h2 className="text-xl font-semibold text-slate-900 mb-4">
              Job della Sessione ({jobs.length})
            </h2>

            {jobs.length === 0 ? (
              <div className="card text-center py-12">
                <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-600">
                  Nessun job per questa sessione
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {jobs.map((job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onUpdate={(updatedJob) => {
                      setJobs(jobs.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
                    }}
                    onDelete={(jobId) => {
                      setJobs(jobs.filter(j => j.job_id !== jobId));
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SessionDetail;
