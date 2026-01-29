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
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Sparkles className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Caricamento...</p>
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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Training Section */}
          <div className="lg:col-span-1">
            <h2 className="text-xl font-semibold text-slate-900 mb-4">
              Training
            </h2>

            {!trainingJob ? (
              <form onSubmit={handleTrainSubmit} className="card">
                <div className="mb-6">
                  <label className="block text-sm font-medium text-slate-700 mb-3">
                    Carica File PDF
                  </label>

                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:border-blue-400 transition-colors">
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={handleFileChange}
                      className="hidden"
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      className="cursor-pointer block"
                    >
                      {file ? (
                        <div className="flex items-center justify-center gap-3">
                          <FileText className="w-6 h-6 text-blue-600" />
                          <div className="text-left">
                            <p className="font-medium text-slate-900 text-sm">
                              {file.name}
                            </p>
                            <p className="text-xs text-slate-600">
                              {formatFileSize(file.size)}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <>
                          <Upload className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                          <p className="text-slate-600 text-sm mb-1">
                            Clicca per selezionare
                          </p>
                          <p className="text-xs text-slate-500">
                            Max 100MB
                          </p>
                        </>
                      )}
                    </label>
                  </div>

                  {error && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                      <AlertCircle className="w-5 h-5 text-red-600" />
                      <p className="text-sm text-red-700">{error}</p>
                    </div>
                  )}
                </div>

                <div className="mb-6">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Numero massimo di pagine
                  </label>
                  <input
                    type="number"
                    value={maxPages}
                    onChange={(e) => setMaxPages(parseInt(e.target.value))}
                    min="1"
                    max="500"
                    className="input w-full"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Più pagine = più tempo
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={!file || uploading}
                  className="w-full btn btn-primary gap-2"
                >
                  {uploading ? (
                    <>
                      <div className="loading-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      Avvio training...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      Avvia Training
                    </>
                  )}
                </button>
              </form>
            ) : (
              <div className="card">
                <div className="text-center mb-4">
                  {trainingJob.status === 'completed' ? (
                    <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <CheckCircle className="w-6 h-6 text-green-600" />
                    </div>
                  ) : trainingJob.status === 'failed' ? (
                    <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <AlertCircle className="w-6 h-6 text-red-600" />
                    </div>
                  ) : (
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <Upload className="w-6 h-6 text-blue-600 animate-pulse" />
                    </div>
                  )}

                  <h3 className="font-semibold text-slate-900 mb-1">
                    {trainingJob.status === 'completed' ? 'Completato!' :
                     trainingJob.status === 'failed' ? 'Fallito' :
                     'Training in corso...'}
                  </h3>
                  <p className="font-mono text-xs text-slate-500">
                    {trainingJob.job_id}
                  </p>
                </div>

                {trainingJob.progress > 0 && trainingJob.status !== 'completed' && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-sm text-slate-600 mb-2">
                      <span>Progresso</span>
                      <span>{trainingJob.progress}%</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${trainingJob.progress}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {trainingJob.error && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{trainingJob.error}</p>
                  </div>
                )}

                {trainingJob.status === 'completed' && (
                  <button
                    onClick={() => setTrainingJob(null)}
                    className="w-full btn btn-primary"
                  >
                    Nuovo Training
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Jobs List */}
          <div className="lg:col-span-2">
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
