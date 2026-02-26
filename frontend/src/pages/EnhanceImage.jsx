import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ImagePlus, ArrowLeft, Download, RefreshCw, AlertCircle, Sparkles, Loader2 } from 'lucide-react';
import { enhanceImage, estimateEnhanceCredits } from '../services/api';
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';

const EnhanceImage = () => {
  const navigate = useNavigate();
  const { isAdmin, credits, refreshUser } = useAuth();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [enhancedUrl, setEnhancedUrl] = useState(null);
  const [enhancedBlob, setEnhancedBlob] = useState(null);
  const [analysis, setAnalysis] = useState('');
  const [params, setParams] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  // Credit dialog
  const [showCreditDialog, setShowCreditDialog] = useState(false);
  const [creditEstimate, setCreditEstimate] = useState(null);
  const [creditLoading, setCreditLoading] = useState(false);

  const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_SIZE = 10 * 1024 * 1024; // 10MB

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
    setEnhancedUrl(null);
    setEnhancedBlob(null);
    setAnalysis('');
    setParams(null);

    const url = URL.createObjectURL(f);
    setPreviewUrl(url);
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) handleFileSelect(selected);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
  };

  const handleEnhance = async () => {
    if (!file) return;

    setCreditLoading(true);
    setShowCreditDialog(true);
    setError('');

    try {
      const estimate = await estimateEnhanceCredits();
      setCreditEstimate(estimate);
    } catch (err) {
      console.error('Errore stima crediti:', err);
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleConfirmedEnhance = async () => {
    setShowCreditDialog(false);
    setLoading(true);
    setError('');

    try {
      const data = await enhanceImage(file);

      // Converti base64 in blob URL
      const byteChars = atob(data.image_base64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const mimeType = data.format === 'jpeg' ? 'image/jpeg' : data.format === 'png' ? 'image/png' : 'image/webp';
      const blob = new Blob([byteArray], { type: mimeType });
      const url = URL.createObjectURL(blob);

      setEnhancedUrl(url);
      setEnhancedBlob(blob);
      setAnalysis(data.analysis);
      setParams(data.params);

      refreshUser();
    } catch (err) {
      if (err.response?.status === 402) {
        setError('Crediti insufficienti per questa operazione.');
      } else {
        setError(err.response?.data?.detail || err.message || 'Errore durante il miglioramento');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!enhancedBlob || !file) return;
    const ext = file.name.split('.').pop();
    const baseName = file.name.replace(/\.[^.]+$/, '');
    const link = document.createElement('a');
    link.href = enhancedUrl;
    link.download = `${baseName}_enhanced.${ext}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleReset = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (enhancedUrl) URL.revokeObjectURL(enhancedUrl);
    setFile(null);
    setPreviewUrl(null);
    setEnhancedUrl(null);
    setEnhancedBlob(null);
    setAnalysis('');
    setParams(null);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const formatParamLabel = (key, value) => {
    const labels = {
      brightness: 'Luminosita',
      contrast: 'Contrasto',
      sharpness: 'Nitidezza',
      color_saturation: 'Saturazione',
      warmth: 'Calore',
      highlights: 'Alte luci',
      shadows: 'Ombre',
      noise_reduction: 'Riduzione rumore',
      auto_levels: 'Auto livelli',
      vibrance: 'Vivacita',
    };
    const label = labels[key] || key;

    if (typeof value === 'boolean') return value ? label : null;
    if (typeof value === 'string') return value !== 'none' ? `${label}: ${value}` : null;
    if (typeof value === 'number') {
      if (key === 'warmth' || key === 'highlights' || key === 'shadows') {
        if (value === 0) return null;
        const sign = value > 0 ? '+' : '';
        return `${label}: ${sign}${value.toFixed(0)}`;
      }
      if (value === 1.0) return null;
      const pct = ((value - 1.0) * 100).toFixed(0);
      const sign = pct > 0 ? '+' : '';
      return `${label}: ${sign}${pct}%`;
    }
    return null;
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
          <h1 className="text-3xl font-bold text-slate-900 mb-2">
            Migliora Immagine
          </h1>
          <p className="text-slate-600">
            Migliora la qualita della tua immagine con l'intelligenza artificiale
          </p>
        </div>

        {/* Upload Area (quando non c'e risultato) */}
        {!enhancedUrl && !loading && (
          <div className="card">
            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                isDragging
                  ? 'border-orange-400 bg-orange-50'
                  : file
                  ? 'border-green-300 bg-green-50/50'
                  : 'border-slate-300 hover:border-orange-400'
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
                onChange={handleFileChange}
                className="hidden"
              />

              {file && previewUrl ? (
                <div className="space-y-4">
                  <img
                    src={previewUrl}
                    alt="Anteprima"
                    className="max-h-72 mx-auto rounded-lg shadow-md"
                  />
                  <div>
                    <p className="font-medium text-slate-900">{file.name}</p>
                    <p className="text-sm text-slate-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
              ) : (
                <>
                  <ImagePlus className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                  <p className="text-slate-600 mb-1">
                    Trascina un'immagine o clicca per selezionare
                  </p>
                  <p className="text-sm text-slate-500">
                    JPG, PNG, WEBP — max 10MB
                  </p>
                </>
              )}
            </div>

            {error && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <button
              onClick={handleEnhance}
              disabled={!file}
              className="w-full btn btn-primary h-12 text-base mt-6 gap-2"
            >
              <Sparkles className="w-5 h-5" />
              Migliora Immagine
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="card text-center py-16">
            <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Loader2 className="w-10 h-10 text-orange-600 animate-spin" />
            </div>
            <h3 className="text-xl font-semibold text-slate-900 mb-2">
              Analisi e miglioramento in corso...
            </h3>
            <p className="text-slate-500 mb-4">
              L'AI sta analizzando la tua immagine e applicando i miglioramenti
            </p>
            <div className="flex items-center justify-center gap-8 text-sm text-slate-400">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-orange-400 rounded-full animate-pulse" />
                Analisi AI
              </span>
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-slate-300 rounded-full" />
                Elaborazione
              </span>
            </div>
          </div>
        )}

        {/* Result */}
        {enhancedUrl && !loading && (
          <div className="space-y-6">
            {/* Confronto side-by-side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="card">
                <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-3">Originale</h3>
                <img
                  src={previewUrl}
                  alt="Originale"
                  className="w-full rounded-lg"
                />
              </div>
              <div className="card">
                <h3 className="text-sm font-medium text-orange-500 uppercase tracking-wider mb-3">Migliorata</h3>
                <img
                  src={enhancedUrl}
                  alt="Migliorata"
                  className="w-full rounded-lg"
                />
              </div>
            </div>

            {/* Analisi AI */}
            {analysis && (
              <div className="card bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-orange-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4 text-orange-600" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-orange-800 mb-1">Analisi AI</h4>
                    <p className="text-sm text-orange-700">{analysis}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Parametri applicati */}
            {params && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(params).map(([key, value]) => {
                  const label = formatParamLabel(key, value);
                  if (!label) return null;
                  return (
                    <span key={key} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                      {label}
                    </span>
                  );
                })}
              </div>
            )}

            {/* Errore */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Azioni */}
            <div className="flex gap-4">
              <button onClick={handleDownload} className="flex-1 btn btn-primary h-12 text-base gap-2">
                <Download className="w-5 h-5" />
                Scarica Immagine
              </button>
              <button onClick={handleReset} className="flex-1 btn btn-secondary h-12 text-base gap-2">
                <RefreshCw className="w-5 h-5" />
                Nuova Immagine
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Credit Confirmation Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleConfirmedEnhance}
        onCancel={() => setShowCreditDialog(false)}
        operationName="Miglioramento Immagine"
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={isAdmin ? -1 : (creditEstimate?.current_balance ?? credits)}
        loading={creditLoading}
      />
    </div>
  );
};

export default EnhanceImage;
