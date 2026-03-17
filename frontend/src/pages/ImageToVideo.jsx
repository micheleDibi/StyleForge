import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Film, ArrowLeft, Plus, Trash2, Play, Download, AlertCircle,
  Loader2, CheckCircle2, XCircle, Clock, Settings2, ImagePlus
} from 'lucide-react';
import { generateVideos, getVideoTasksStatus, getVideoProxyUrl } from '../services/api';

const MODELS = [
  { value: 'I2V-01', label: 'I2V-01 (Standard)' },
  { value: 'I2V-01-live2d', label: 'I2V-01-live2d (Anime/2D)' },
];

const MAX_PROMPTS = 5;

const ImageToVideo = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [prompts, setPrompts] = useState(['']);
  const [model, setModel] = useState('I2V-01');
  const [promptOptimizer, setPromptOptimizer] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [showSettings, setShowSettings] = useState(false);

  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_SIZE = 10 * 1024 * 1024;

  // Poll pending tasks
  useEffect(() => {
    const pendingIds = tasks
      .filter(t => t.task_id && t.status === 'Processing')
      .map(t => t.task_id);

    if (pendingIds.length === 0) return;

    const interval = setInterval(async () => {
      try {
        const data = await getVideoTasksStatus(pendingIds);
        if (data.tasks) {
          setTasks(prev =>
            prev.map(t => {
              const updated = data.tasks.find(u => u.task_id === t.task_id);
              if (!updated) return t;
              return {
                ...t,
                status: updated.status,
                video_url: updated.video_url || t.video_url,
                error: updated.error || t.error,
              };
            })
          );
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [tasks]);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const validateFile = (f) => {
    if (!ALLOWED_TYPES.includes(f.type)) {
      setError('Formato non supportato. Usa JPG, PNG o WEBP.');
      return false;
    }
    if (f.size > MAX_SIZE) {
      setError(`Immagine troppo grande (${formatFileSize(f.size)}). Massimo: 10MB`);
      return false;
    }
    return true;
  };

  const handleFileSelect = (f) => {
    if (!validateFile(f)) return;
    setFile(f);
    setError('');
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
  };

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
  };

  const updatePrompt = (index, value) => {
    setPrompts(prev => prev.map((p, i) => i === index ? value : p));
  };

  const addPrompt = () => {
    if (prompts.length < MAX_PROMPTS) setPrompts(prev => [...prev, '']);
  };

  const removePrompt = (index) => {
    if (prompts.length > 1) setPrompts(prev => prev.filter((_, i) => i !== index));
  };

  const handleGenerate = async () => {
    const validPrompts = prompts.map(p => p.trim()).filter(Boolean);
    if (!file || validPrompts.length === 0) {
      setError('Carica un\'immagine e inserisci almeno un prompt.');
      return;
    }

    setLoading(true);
    setError('');
    setTasks([]);

    try {
      const data = await generateVideos(file, validPrompts, model, promptOptimizer);
      const newTasks = data.tasks.map(t => ({
        task_id: t.task_id,
        prompt: t.prompt,
        status: t.error ? 'Fail' : 'Processing',
        video_url: null,
        error: t.error || null,
      }));
      setTasks(newTasks);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Errore durante la generazione');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (task) => {
    if (!task.video_url) return;
    const proxyUrl = getVideoProxyUrl(task.video_url);
    const link = document.createElement('a');
    link.href = proxyUrl;
    link.download = `video_${task.task_id}.mp4`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleReset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    setPrompts(['']);
    setTasks([]);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const StatusIcon = ({ status }) => {
    if (status === 'Processing') return <Loader2 className="w-5 h-5 text-orange-500 animate-spin" />;
    if (status === 'Success') return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    if (status === 'Fail') return <XCircle className="w-5 h-5 text-red-500" />;
    return <Clock className="w-5 h-5 text-gray-400" />;
  };

  const statusLabel = (status) => {
    if (status === 'Processing') return 'In elaborazione...';
    if (status === 'Success') return 'Completato';
    if (status === 'Fail') return 'Errore';
    return status;
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button onClick={() => navigate('/')} className="btn btn-secondary gap-2 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Torna alla Dashboard
          </button>
          <h1 className="text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <Film className="w-8 h-8 text-violet-600" />
            Image to Video
          </h1>
          <p className="text-slate-600">
            Carica un'immagine e genera video animati con l'AI MiniMax
          </p>
        </div>

        {/* Main content */}
        {tasks.length === 0 && !loading && (
          <div className="space-y-6">
            {/* Upload Area */}
            <div className="card">
              <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">
                Immagine di partenza
              </h3>
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                  isDragging
                    ? 'border-violet-400 bg-violet-50'
                    : file
                    ? 'border-green-300 bg-green-50/50'
                    : 'border-slate-300 hover:border-violet-400'
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp"
                  onChange={(e) => e.target.files[0] && handleFileSelect(e.target.files[0])}
                  className="hidden"
                />
                {file && previewUrl ? (
                  <div className="space-y-3">
                    <img src={previewUrl} alt="Anteprima" className="max-h-64 mx-auto rounded-lg shadow-md" />
                    <p className="font-medium text-slate-900">{file.name}</p>
                    <p className="text-sm text-slate-500">{formatFileSize(file.size)}</p>
                  </div>
                ) : (
                  <>
                    <ImagePlus className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                    <p className="text-slate-600 mb-1">Trascina un'immagine o clicca per selezionare</p>
                    <p className="text-sm text-slate-500">JPG, PNG, WEBP — max 10MB</p>
                  </>
                )}
              </div>
            </div>

            {/* Prompts */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider">
                  Prompt ({prompts.length}/{MAX_PROMPTS})
                </h3>
                {prompts.length < MAX_PROMPTS && (
                  <button onClick={addPrompt} className="btn btn-secondary btn-sm gap-1">
                    <Plus className="w-3.5 h-3.5" /> Aggiungi
                  </button>
                )}
              </div>
              <div className="space-y-3">
                {prompts.map((prompt, idx) => (
                  <div key={idx} className="flex gap-2">
                    <textarea
                      value={prompt}
                      onChange={(e) => updatePrompt(idx, e.target.value)}
                      placeholder={`Descrivi l'animazione desiderata... (es. "La persona sorride e gira la testa lentamente")`}
                      rows={2}
                      className="input flex-1 resize-none"
                    />
                    {prompts.length > 1 && (
                      <button onClick={() => removePrompt(idx)} className="btn btn-ghost text-red-400 hover:text-red-600 hover:bg-red-50 self-start mt-1">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Settings */}
            <div className="card">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 text-sm font-medium text-slate-500 uppercase tracking-wider w-full"
              >
                <Settings2 className="w-4 h-4" />
                Parametri
                <span className={`ml-auto transition-transform ${showSettings ? 'rotate-180' : ''}`}>&#9662;</span>
              </button>
              {showSettings && (
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Modello</label>
                    <select value={model} onChange={(e) => setModel(e.target.value)} className="input w-full">
                      {MODELS.map(m => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Ottimizzazione Prompt</label>
                    <div
                      onClick={() => setPromptOptimizer(!promptOptimizer)}
                      className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        promptOptimizer ? 'bg-violet-50 border-violet-200' : 'bg-slate-50 border-slate-200'
                      }`}
                    >
                      <div className={`w-10 h-6 rounded-full relative transition-colors ${promptOptimizer ? 'bg-violet-500' : 'bg-slate-300'}`}>
                        <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${promptOptimizer ? 'left-[18px]' : 'left-0.5'}`} />
                      </div>
                      <span className="text-sm text-slate-700">{promptOptimizer ? 'Attiva' : 'Disattiva'}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={!file || prompts.every(p => !p.trim())}
              className="w-full btn btn-primary h-12 text-base gap-2"
              style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
            >
              <Play className="w-5 h-5" />
              Genera Video
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="card text-center py-16">
            <div className="w-20 h-20 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Loader2 className="w-10 h-10 text-violet-600 animate-spin" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">Invio in corso...</h3>
            <p className="text-slate-500">Caricamento immagine e creazione task video</p>
          </div>
        )}

        {/* Results */}
        {tasks.length > 0 && !loading && (
          <div className="space-y-6">
            {/* Preview of source image */}
            {previewUrl && (
              <div className="card">
                <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Immagine sorgente</h3>
                <img src={previewUrl} alt="Sorgente" className="max-h-48 rounded-lg shadow-md" />
              </div>
            )}

            {/* Task cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tasks.map((task, idx) => (
                <div key={task.task_id || idx} className="card">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <StatusIcon status={task.status} />
                      <span className={`text-sm font-medium ${
                        task.status === 'Success' ? 'text-green-700' :
                        task.status === 'Fail' ? 'text-red-700' :
                        'text-orange-700'
                      }`}>
                        {statusLabel(task.status)}
                      </span>
                    </div>
                    <span className="text-xs text-slate-400">#{idx + 1}</span>
                  </div>

                  <p className="text-sm text-slate-600 mb-3 line-clamp-2">{task.prompt}</p>

                  {task.status === 'Success' && task.video_url && (
                    <div className="space-y-3">
                      <video
                        controls
                        loop
                        className="w-full rounded-lg bg-black"
                        src={getVideoProxyUrl(task.video_url)}
                      />
                      <button
                        onClick={() => handleDownload(task)}
                        className="btn btn-secondary btn-sm w-full gap-2"
                      >
                        <Download className="w-4 h-4" /> Scarica Video
                      </button>
                    </div>
                  )}

                  {task.status === 'Processing' && (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-center">
                        <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto mb-2" />
                        <p className="text-xs text-slate-400">Generazione in corso...</p>
                      </div>
                    </div>
                  )}

                  {task.status === 'Fail' && task.error && (
                    <div className="p-2 bg-red-50 rounded-lg">
                      <p className="text-xs text-red-600">{task.error}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Actions */}
            <button onClick={handleReset} className="w-full btn btn-secondary h-12 text-base gap-2">
              <ImagePlus className="w-5 h-5" />
              Nuova Generazione
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageToVideo;
