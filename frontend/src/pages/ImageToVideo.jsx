import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Film, ArrowLeft, Plus, Trash2, Play, Download, AlertCircle,
  Loader2, CheckCircle2, XCircle, Clock, Settings2, ImagePlus, Info, Zap, Sparkles
} from 'lucide-react';
import { generateVideos, getVideoTasksStatus, getVideoProxyUrl } from '../services/api';

// ── Models ──────────────────────────────────────────────────────────────────
const MODELS = [
  {
    value: 'MiniMax-Hailuo-2.3',
    label: 'Hailuo 2.3',
    desc: 'Ultima generazione. Massima qualita visiva, movimenti fluidi e coerenza temporale.',
    quality: 95,
    speed: 40,
    time: '~3-5 min',
    resolutions: { '768P': [6, 10], '1080P': [6] },
    defaultRes: '768P',
    supportsFastPretreatment: true,
  },
  {
    value: 'MiniMax-Hailuo-2.3-Fast',
    label: 'Hailuo 2.3 Fast',
    desc: 'Versione veloce del 2.3. Qualita leggermente ridotta ma tempi dimezzati.',
    quality: 80,
    speed: 75,
    time: '~1-2 min',
    resolutions: { '768P': [6, 10], '1080P': [6] },
    defaultRes: '768P',
    supportsFastPretreatment: true,
  },
  {
    value: 'MiniMax-Hailuo-02',
    label: 'Hailuo 02',
    desc: 'Generazione precedente. Buon bilanciamento qualita/velocita, stabile e affidabile.',
    quality: 75,
    speed: 60,
    time: '~2-3 min',
    resolutions: { '512P': [6, 10], '768P': [6, 10], '1080P': [6, 10] },
    defaultRes: '768P',
    supportsFastPretreatment: true,
  },
  {
    value: 'I2V-01-Director',
    label: 'I2V-01 Director',
    desc: 'Supporta comandi camera nel prompt: [truck left], [zoom in], [pan right], ecc.',
    quality: 70,
    speed: 55,
    time: '~2-4 min',
    resolutions: { '720P': [6] },
    defaultRes: '720P',
    supportsFastPretreatment: false,
  },
  {
    value: 'I2V-01-live',
    label: 'I2V-01 Live',
    desc: 'Ottimizzato per stile anime e illustrazioni 2D. Ideale per artwork e live2d.',
    quality: 70,
    speed: 60,
    time: '~2-3 min',
    resolutions: { '720P': [6] },
    defaultRes: '720P',
    supportsFastPretreatment: false,
  },
  {
    value: 'I2V-01',
    label: 'I2V-01 Standard',
    desc: 'Modello base image-to-video. Leggero e veloce, adatto per test rapidi.',
    quality: 60,
    speed: 70,
    time: '~1-2 min',
    resolutions: { '720P': [6] },
    defaultRes: '720P',
    supportsFastPretreatment: false,
  },
];

const MAX_PROMPTS = 5;

// ── Quality/Speed Bar ───────────────────────────────────────────────────────
const StatBar = ({ label, value, color }) => (
  <div className="flex items-center gap-2">
    <span className="text-xs text-slate-500 w-16">{label}</span>
    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
    </div>
    <span className="text-xs font-medium text-slate-600 w-8 text-right">{value}%</span>
  </div>
);

// ── Toggle Component ────────────────────────────────────────────────────────
const Toggle = ({ enabled, onChange, label, description }) => (
  <div>
    <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
    <div
      onClick={onChange}
      className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
        enabled ? 'bg-violet-50 border-violet-200' : 'bg-slate-50 border-slate-200'
      }`}
    >
      <div className={`w-10 h-6 rounded-full relative transition-colors flex-shrink-0 ${enabled ? 'bg-violet-500' : 'bg-slate-300'}`}>
        <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${enabled ? 'left-[18px]' : 'left-0.5'}`} />
      </div>
      <div>
        <span className="text-sm text-slate-700">{enabled ? 'Attivo' : 'Disattivo'}</span>
        {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
      </div>
    </div>
  </div>
);

const ImageToVideo = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [prompts, setPrompts] = useState(['']);
  const [model, setModel] = useState('MiniMax-Hailuo-2.3');
  const [promptOptimizer, setPromptOptimizer] = useState(true);
  const [duration, setDuration] = useState(6);
  const [resolution, setResolution] = useState('720P');
  const [fastPretreatment, setFastPretreatment] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [showSettings, setShowSettings] = useState(true);

  const selectedModel = useMemo(() => MODELS.find(m => m.value === model) || MODELS[0], [model]);
  const availableResolutions = useMemo(() => Object.keys(selectedModel.resolutions), [selectedModel]);
  const availableDurations = useMemo(() => selectedModel.resolutions[resolution] || [6], [selectedModel, resolution]);

  // Reset dependent params when model changes
  useEffect(() => {
    const resKeys = Object.keys(selectedModel.resolutions);
    if (!resKeys.includes(resolution)) {
      setResolution(selectedModel.defaultRes);
    }
    if (!selectedModel.supportsFastPretreatment) {
      setFastPretreatment(false);
    }
  }, [model]);

  // Reset duration when resolution changes and current duration is not supported
  useEffect(() => {
    const durations = selectedModel.resolutions[resolution];
    if (durations && !durations.includes(duration)) {
      setDuration(durations[0]);
    }
  }, [resolution, selectedModel]);

  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_SIZE = 10 * 1024 * 1024;

  // Poll pending tasks
  useEffect(() => {
    const pendingIds = tasks
      .filter(t => t.task_id && !['Success', 'Fail'].includes(t.status))
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
      const data = await generateVideos(file, validPrompts, {
        model,
        promptOptimizer,
        duration,
        fastPretreatment: selectedModel.supportsFastPretreatment ? fastPretreatment : undefined,
        resolution,
      });
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
    if (status === 'Success') return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    if (status === 'Fail') return <XCircle className="w-5 h-5 text-red-500" />;
    if (status === 'Queueing') return <Clock className="w-5 h-5 text-blue-500" />;
    return <Loader2 className="w-5 h-5 text-orange-500 animate-spin" />;
  };

  const statusLabel = (status) => {
    const labels = {
      Queueing: 'In coda...',
      Preparing: 'Preparazione...',
      Processing: 'In elaborazione...',
      Success: 'Completato',
      Fail: 'Errore',
    };
    return labels[status] || status;
  };

  const statusColor = (status) => {
    if (status === 'Success') return 'text-green-700';
    if (status === 'Fail') return 'text-red-700';
    if (status === 'Queueing') return 'text-blue-700';
    return 'text-orange-700';
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
                    <p className="text-sm text-slate-500">JPG, PNG, WEBP — max 10MB — lato corto min 300px — aspect ratio da 2:5 a 5:2</p>
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
                      rows={4}
                      maxLength={2000}
                      className="input flex-1 resize-y min-h-[80px]"
                    />
                    {prompts.length > 1 && (
                      <button onClick={() => removePrompt(idx)} className="btn btn-ghost text-red-400 hover:text-red-600 hover:bg-red-50 self-start mt-1">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
                <p className="text-xs text-slate-400">Max 2000 caratteri per prompt. {selectedModel.value === 'I2V-01-Director' && 'Supporta comandi camera: [truck left], [zoom in], [pan right], [tilt up], ecc.'}</p>
              </div>
            </div>

            {/* Settings */}
            <div className="card">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 text-sm font-medium text-slate-500 uppercase tracking-wider w-full"
              >
                <Settings2 className="w-4 h-4" />
                Parametri di generazione
                <span className={`ml-auto transition-transform ${showSettings ? 'rotate-180' : ''}`}>&#9662;</span>
              </button>

              {showSettings && (
                <div className="mt-5 space-y-6">

                  {/* ── Model Selection ── */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Modello</label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {MODELS.map(m => (
                        <div
                          key={m.value}
                          onClick={() => setModel(m.value)}
                          className={`p-3 rounded-xl border-2 cursor-pointer transition-all ${
                            model === m.value
                              ? 'border-violet-400 bg-violet-50 shadow-md shadow-violet-100'
                              : 'border-slate-200 hover:border-slate-300 bg-white'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-bold text-slate-900">{m.label}</span>
                            <span className="text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{m.time}</span>
                          </div>
                          <p className="text-xs text-slate-500 mb-2.5 leading-relaxed">{m.desc}</p>
                          <div className="space-y-1.5">
                            <StatBar label="Qualita" value={m.quality} color="bg-gradient-to-r from-violet-400 to-violet-600" />
                            <StatBar label="Velocita" value={m.speed} color="bg-gradient-to-r from-emerald-400 to-emerald-600" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ── Duration + Resolution row ── */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Resolution */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Risoluzione
                      </label>
                      <div className="flex gap-2">
                        {availableResolutions.map(r => (
                          <button
                            key={r}
                            onClick={() => setResolution(r)}
                            className={`flex-1 py-2.5 px-4 rounded-xl border-2 text-sm font-medium transition-all ${
                              resolution === r
                                ? 'border-violet-400 bg-violet-50 text-violet-700'
                                : 'border-slate-200 text-slate-600 hover:border-slate-300'
                            }`}
                          >
                            {r}
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-slate-400 mt-1.5">
                        Risoluzione output. 1080P offre piu dettaglio ma richiede piu tempo (~30-50% in piu).
                      </p>
                    </div>

                    {/* Duration */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Durata video
                      </label>
                      <div className="flex gap-2">
                        {availableDurations.map(d => (
                          <button
                            key={d}
                            onClick={() => setDuration(d)}
                            className={`flex-1 py-2.5 px-4 rounded-xl border-2 text-sm font-medium transition-all ${
                              duration === d
                                ? 'border-violet-400 bg-violet-50 text-violet-700'
                                : 'border-slate-200 text-slate-600 hover:border-slate-300'
                            }`}
                          >
                            {d} secondi
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-slate-400 mt-1.5">
                        {availableDurations.length > 1
                          ? 'Durata del video. 10s raddoppia circa il tempo di generazione rispetto a 6s.'
                          : 'Questo modello/risoluzione supporta solo 6 secondi.'}
                      </p>
                    </div>
                  </div>

                  {/* ── Toggles row ── */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Toggle
                      enabled={promptOptimizer}
                      onChange={() => setPromptOptimizer(!promptOptimizer)}
                      label="Ottimizzazione Prompt"
                      description="MiniMax riscrive il tuo prompt per migliorare il risultato. Disattiva se vuoi controllo preciso."
                    />

                    {selectedModel.supportsFastPretreatment && (
                      <Toggle
                        enabled={fastPretreatment}
                        onChange={() => setFastPretreatment(!fastPretreatment)}
                        label="Pre-elaborazione veloce"
                        description="Riduce il tempo di ottimizzazione del prompt (~20-30% piu veloce). Solo con Prompt Optimizer attivo."
                      />
                    )}
                  </div>

                  {/* ── Estimated time info ── */}
                  <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <Info className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                    <div className="text-xs text-slate-500 space-y-1">
                      <p><strong>Tempo stimato:</strong> {selectedModel.time} per video ({resolution}, {duration}s)</p>
                      <p><strong>Nota:</strong> 1080P aggiunge ~30-50% al tempo. 10s raddoppia circa rispetto a 6s. Il Fast Pretreatment risparmia ~20-30% sulla fase di preparazione.</p>
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
                      <span className={`text-sm font-medium ${statusColor(task.status)}`}>
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

                  {!['Success', 'Fail'].includes(task.status) && (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-center">
                        <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto mb-2" />
                        <p className="text-xs text-slate-400">{statusLabel(task.status)} ({selectedModel.time})</p>
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
