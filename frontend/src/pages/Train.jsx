import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, ArrowLeft, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { trainSession } from '../services/api';
import { pollJobStatus } from '../services/api';

const Train = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [maxPages, setMaxPages] = useState(50);
  const [uploading, setUploading] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState('');

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError('');

    try {
      // Avvia training
      const response = await trainSession(file, null, maxPages);
      setJobStatus({ ...response, status: 'pending', progress: 0 });

      // Poll status
      await pollJobStatus(
        response.job_id,
        (status) => setJobStatus(status),
        3000
      );

    } catch (err) {
      setError(err.message || 'Errore durante il training');
      setUploading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="btn btn-secondary gap-2 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Torna alla Dashboard
          </button>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">
            Nuovo Training
          </h1>
          <p className="text-slate-600">
            Carica un PDF per addestrare Claude sul tuo stile di scrittura
          </p>
        </div>

        {!jobStatus ? (
          /* Upload Form */
          <form onSubmit={handleSubmit} className="card">
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 mb-3">
                Carica File PDF
              </label>

              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors">
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
                      <FileText className="w-8 h-8 text-blue-600" />
                      <div className="text-left">
                        <p className="font-medium text-slate-900">
                          {file.name}
                        </p>
                        <p className="text-sm text-slate-600">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                      <p className="text-slate-600 mb-1">
                        Clicca per selezionare un file PDF
                      </p>
                      <p className="text-sm text-slate-500">
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
                Numero massimo di pagine da leggere
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
                Più pagine = più tempo di elaborazione
              </p>
            </div>

            <button
              type="submit"
              disabled={!file || uploading}
              className="w-full btn btn-primary h-12 text-base"
            >
              {uploading ? 'Avvio training...' : 'Avvia Training'}
            </button>
          </form>
        ) : (
          /* Job Status */
          <div className="card">
            <div className="text-center mb-6">
              {jobStatus.status === 'completed' ? (
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
              ) : jobStatus.status === 'failed' ? (
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <AlertCircle className="w-8 h-8 text-red-600" />
                </div>
              ) : (
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Upload className="w-8 h-8 text-blue-600 animate-pulse" />
                </div>
              )}

              <h3 className="text-xl font-semibold text-slate-900 mb-2">
                {jobStatus.status === 'completed' ? 'Training Completato!' :
                 jobStatus.status === 'failed' ? 'Training Fallito' :
                 'Training in corso...'}
              </h3>
              <p className="text-slate-600 font-mono text-sm">
                Job ID: {jobStatus.job_id}
              </p>
            </div>

            {jobStatus.progress > 0 && jobStatus.status !== 'completed' && (
              <div className="mb-6">
                <div className="flex items-center justify-between text-sm text-slate-600 mb-2">
                  <span>Progresso</span>
                  <span>{jobStatus.progress}%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-500"
                    style={{ width: `${jobStatus.progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {jobStatus.error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{jobStatus.error}</p>
              </div>
            )}

            <div className="flex gap-3">
              {jobStatus.status === 'completed' && (
                <button
                  onClick={() => navigate(`/generate?session=${jobStatus.session_id}`)}
                  className="flex-1 btn btn-primary"
                >
                  Genera Contenuto
                </button>
              )}
              <button
                onClick={() => navigate('/')}
                className="flex-1 btn btn-secondary"
              >
                Torna alla Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Train;
