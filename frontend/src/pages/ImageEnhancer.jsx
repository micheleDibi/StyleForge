import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ImagePlus, Sliders, Brain, Maximize2, Palette,
  Download, Sparkles, Loader, CheckCircle2, AlertCircle,
  Upload, ZoomIn, RotateCcw, Info
} from 'lucide-react';
import {
  enhanceImage, analyzeImage, pollJobStatus,
  estimateCredits, downloadEnhancedImage,
  getOriginalImageBlob, getEnhancedImageBlob,
  getEnhancementResult
} from '../services/api';
import { useAuth } from '../context/AuthContext';
import CreditConfirmDialog from '../components/CreditConfirmDialog';

const ENHANCEMENT_TYPES = [
  {
    id: 'basic',
    label: 'Qualit\u00e0 Base',
    desc: 'Sharpen, denoise, contrasto, luminosit\u00e0, saturazione',
    icon: Sliders,
    gradient: 'from-blue-400 to-blue-600',
    creditOp: 'image_enhance_basic'
  },
  {
    id: 'ai_analysis',
    label: 'Analisi AI',
    desc: 'Claude Vision analizza e applica i miglioramenti ottimali',
    icon: Brain,
    gradient: 'from-purple-400 to-purple-600',
    creditOp: 'image_enhance_ai'
  },
  {
    id: 'upscale',
    label: 'Upscaling',
    desc: 'Aumento risoluzione con LANCZOS + sharpening',
    icon: Maximize2,
    gradient: 'from-green-400 to-green-600',
    creditOp: 'image_enhance_upscale'
  },
  {
    id: 'color_correction',
    label: 'Correzione Colore',
    desc: 'White balance, gamma, equalizzazione istogramma',
    icon: Palette,
    gradient: 'from-orange-400 to-orange-600',
    creditOp: 'image_enhance_color'
  }
];

const ImageEnhancer = () => {
  const navigate = useNavigate();
  const { credits, refreshUser } = useAuth();
  const fileInputRef = useRef(null);
  const sliderRef = useRef(null);

  // Upload state
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Enhancement config
  const [enhancementType, setEnhancementType] = useState('basic');
  const [params, setParams] = useState({
    sharpen: 1.0,
    denoise: false,
    contrast: 1.1,
    brightness: 1.0,
    saturation: 1.05
  });

  // Processing state
  const [processing, setProcessing] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);

  // Result state
  const [result, setResult] = useState(null);
  const [originalBlobUrl, setOriginalBlobUrl] = useState(null);
  const [enhancedBlobUrl, setEnhancedBlobUrl] = useState(null);
  const [aiAnalysis, setAiAnalysis] = useState(null);

  // Before/After slider
  const [sliderPosition, setSliderPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);

  // Credit dialog
  const [showCreditDialog, setShowCreditDialog] = useState(false);
  const [creditEstimate, setCreditEstimate] = useState(null);
  const [creditLoading, setCreditLoading] = useState(false);

  // Cleanup blob URLs
  useEffect(() => {
    return () => {
      if (originalBlobUrl) URL.revokeObjectURL(originalBlobUrl);
      if (enhancedBlobUrl) URL.revokeObjectURL(enhancedBlobUrl);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, []);

  // ─── File handling ───
  const handleFileSelect = (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['jpg', 'jpeg', 'png', 'webp'].includes(ext)) {
      setError('Formato non supportato. Usa JPG, PNG o WebP.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError('File troppo grande. Massimo 20MB.');
      return;
    }
    setSelectedFile(file);
    setError(null);
    setResult(null);
    setAiAnalysis(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  // ─── Parameter defaults by type ───
  const getDefaultParams = (type) => {
    switch (type) {
      case 'basic':
        return { sharpen: 1.0, denoise: false, contrast: 1.1, brightness: 1.0, saturation: 1.05 };
      case 'ai_analysis':
        return {};
      case 'upscale':
        return { scale_factor: 2.0, sharpen_after: true };
      case 'color_correction':
        return { auto_white_balance: true, gamma: 1.0, clahe: true, histogram_equalization: false };
      default:
        return {};
    }
  };

  const handleTypeChange = (type) => {
    setEnhancementType(type);
    setParams(getDefaultParams(type));
  };

  // ─── Credit estimation + processing ───
  const handleEnhance = async () => {
    if (!selectedFile) { setError('Seleziona un\'immagine'); return; }
    setError(null);
    setCreditLoading(true);
    setShowCreditDialog(true);

    const typeConfig = ENHANCEMENT_TYPES.find(t => t.id === enhancementType);
    try {
      const estimate = await estimateCredits(typeConfig.creditOp, params);
      setCreditEstimate(estimate);
    } catch (err) {
      setCreditEstimate({ credits_needed: 0, breakdown: {}, current_balance: credits, sufficient: true });
    } finally {
      setCreditLoading(false);
    }
  };

  const handleConfirmedEnhance = async () => {
    setShowCreditDialog(false);
    setProcessing(true);
    setError(null);
    setResult(null);
    setAiAnalysis(null);
    setUploadProgress(0);

    try {
      const response = await enhanceImage(
        selectedFile,
        enhancementType,
        params,
        (progress) => setUploadProgress(progress)
      );

      setJobStatus({ status: 'pending', progress: 0 });

      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => setJobStatus(status),
        2000,
        300000
      );

      if (finalStatus.status === 'completed') {
        // Carica dettagli risultato
        const enhResult = await getEnhancementResult(response.job_id);
        setResult(enhResult);

        if (enhResult.ai_analysis) {
          setAiAnalysis(enhResult.ai_analysis);
        }

        // Carica immagini per confronto
        const [origBlob, enhBlob] = await Promise.all([
          getOriginalImageBlob(response.job_id),
          getEnhancedImageBlob(response.job_id)
        ]);
        if (originalBlobUrl) URL.revokeObjectURL(originalBlobUrl);
        if (enhancedBlobUrl) URL.revokeObjectURL(enhancedBlobUrl);
        setOriginalBlobUrl(URL.createObjectURL(origBlob));
        setEnhancedBlobUrl(URL.createObjectURL(enhBlob));
        setSliderPosition(50);

        refreshUser();
      } else {
        setError(finalStatus.error || 'Enhancement fallito.');
      }
    } catch (err) {
      if (err.isInsufficientCredits) {
        setError(err.creditErrorMessage);
      } else {
        setError(err.response?.data?.detail || err.message || 'Errore durante l\'enhancement.');
      }
    } finally {
      setProcessing(false);
      setJobStatus(null);
    }
  };

  const handleDownload = async () => {
    if (result?.job_id) {
      await downloadEnhancedImage(result.job_id);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (originalBlobUrl) URL.revokeObjectURL(originalBlobUrl);
    if (enhancedBlobUrl) URL.revokeObjectURL(enhancedBlobUrl);
    setPreviewUrl(null);
    setOriginalBlobUrl(null);
    setEnhancedBlobUrl(null);
    setResult(null);
    setAiAnalysis(null);
    setError(null);
    setJobStatus(null);
    setParams(getDefaultParams(enhancementType));
  };

  // ─── Before/After slider handling ───
  const handleSliderMouseDown = () => setIsDragging(true);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !sliderRef.current) return;
      const rect = sliderRef.current.getBoundingClientRect();
      const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
      setSliderPosition((x / rect.width) * 100);
    };
    const handleMouseUp = () => setIsDragging(false);

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const currentType = ENHANCEMENT_TYPES.find(t => t.id === enhancementType);

  return (
    <div className="min-h-screen relative">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-cyan-100 to-teal-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button onClick={() => navigate('/')} className="btn btn-ghost btn-sm">
            <ArrowLeft className="w-4 h-4" /> Dashboard
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-teal-600 rounded-xl flex items-center justify-center shadow-lg">
              <ImagePlus className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Image Enhancer</h1>
              <p className="text-sm text-gray-500">Migliora la qualit&agrave; delle tue immagini con AI</p>
            </div>
          </div>
        </div>

        {/* ═══ UPLOAD ZONE ═══ */}
        {!result && (
          <div className="space-y-6">
            {/* Drop zone */}
            <div
              className={`glass rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer ${
                dragActive
                  ? 'border-cyan-400 bg-cyan-50/50 scale-[1.01]'
                  : selectedFile
                    ? 'border-green-300 bg-green-50/30'
                    : 'border-gray-300 hover:border-cyan-300 hover:bg-cyan-50/20'
              }`}
              onClick={() => !selectedFile && fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp"
                onChange={(e) => handleFileSelect(e.target.files[0])}
                className="hidden"
              />

              {selectedFile ? (
                <div className="p-6">
                  <div className="flex items-start gap-6">
                    {/* Preview */}
                    <div className="relative flex-shrink-0">
                      <img
                        src={previewUrl}
                        alt="Preview"
                        className="w-48 h-48 object-cover rounded-xl shadow-md"
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); handleReset(); }}
                        className="absolute -top-2 -right-2 w-7 h-7 bg-red-500 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-red-600 transition-colors"
                        title="Rimuovi immagine"
                      >
                        &times;
                      </button>
                    </div>
                    {/* File info */}
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-gray-900 truncate">{selectedFile.name}</p>
                      <p className="text-sm text-gray-500 mt-1">
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                      <div className="flex items-center gap-2 mt-3">
                        <CheckCircle2 className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-green-600">Pronta per l'enhancement</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center">
                  <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-lg font-medium text-gray-700">
                    Trascina un'immagine qui
                  </p>
                  <p className="text-sm text-gray-500 mt-2">
                    oppure clicca per selezionare &middot; JPG, PNG, WebP &middot; max 20MB
                  </p>
                </div>
              )}
            </div>

            {/* ═══ ENHANCEMENT TYPE SELECTOR ═══ */}
            {selectedFile && (
              <>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Tipo di Enhancement</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {ENHANCEMENT_TYPES.map((type) => {
                      const Icon = type.icon;
                      const isActive = enhancementType === type.id;
                      return (
                        <button
                          key={type.id}
                          onClick={() => handleTypeChange(type.id)}
                          className={`relative p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                            isActive
                              ? 'border-transparent shadow-lg scale-[1.02]'
                              : 'border-gray-200 hover:border-gray-300 bg-white/50'
                          }`}
                        >
                          {isActive && (
                            <div className={`absolute inset-0 bg-gradient-to-br ${type.gradient} opacity-10 rounded-xl`} />
                          )}
                          <div className="relative">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${
                              isActive
                                ? `bg-gradient-to-br ${type.gradient} text-white shadow-md`
                                : 'bg-gray-100 text-gray-500'
                            }`}>
                              <Icon className="w-5 h-5" />
                            </div>
                            <p className={`font-semibold text-sm ${isActive ? 'text-gray-900' : 'text-gray-700'}`}>
                              {type.label}
                            </p>
                            <p className="text-xs text-gray-500 mt-1 leading-relaxed">{type.desc}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* ═══ PARAMETER CONTROLS ═══ */}
                <div className="glass rounded-2xl p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Sliders className="w-5 h-5 text-gray-400" />
                    Parametri
                  </h3>

                  {enhancementType === 'basic' && (
                    <div className="space-y-5">
                      <SliderControl label="Sharpen" value={params.sharpen} min={0} max={2} step={0.1}
                        onChange={(v) => setParams(p => ({ ...p, sharpen: v }))} />
                      <SliderControl label="Contrasto" value={params.contrast} min={0.5} max={2} step={0.05}
                        onChange={(v) => setParams(p => ({ ...p, contrast: v }))} />
                      <SliderControl label="Luminosit&agrave;" value={params.brightness} min={0.5} max={2} step={0.05}
                        onChange={(v) => setParams(p => ({ ...p, brightness: v }))} />
                      <SliderControl label="Saturazione" value={params.saturation} min={0.5} max={2} step={0.05}
                        onChange={(v) => setParams(p => ({ ...p, saturation: v }))} />
                      <ToggleControl label="Denoise" checked={params.denoise}
                        onChange={(v) => setParams(p => ({ ...p, denoise: v }))} />
                    </div>
                  )}

                  {enhancementType === 'ai_analysis' && (
                    <div className="text-center py-4">
                      <Brain className="w-12 h-12 text-purple-400 mx-auto mb-3" />
                      <p className="text-gray-700 font-medium">Enhancement Intelligente</p>
                      <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
                        Claude Vision analizza l'immagine, identifica i problemi di qualit&agrave;
                        e applica automaticamente i miglioramenti ottimali.
                      </p>
                    </div>
                  )}

                  {enhancementType === 'upscale' && (
                    <div className="space-y-5">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-3">Fattore di Scala</label>
                        <div className="flex gap-3">
                          {[1.5, 2, 3, 4].map((factor) => (
                            <button
                              key={factor}
                              onClick={() => setParams(p => ({ ...p, scale_factor: factor }))}
                              className={`flex-1 py-3 px-4 rounded-xl border-2 font-semibold text-sm transition-all ${
                                params.scale_factor === factor
                                  ? 'border-green-400 bg-green-50 text-green-700 shadow-md'
                                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
                              }`}
                            >
                              {factor}x
                            </button>
                          ))}
                        </div>
                      </div>
                      <ToggleControl label="Sharpen dopo upscale" checked={params.sharpen_after !== false}
                        onChange={(v) => setParams(p => ({ ...p, sharpen_after: v }))} />
                    </div>
                  )}

                  {enhancementType === 'color_correction' && (
                    <div className="space-y-5">
                      <ToggleControl label="Auto White Balance" checked={params.auto_white_balance}
                        onChange={(v) => setParams(p => ({ ...p, auto_white_balance: v }))} />
                      <SliderControl label="Gamma" value={params.gamma} min={0.5} max={2} step={0.05}
                        onChange={(v) => setParams(p => ({ ...p, gamma: v }))} />
                      <ToggleControl label="CLAHE (Contrast Adaptivo)" checked={params.clahe}
                        onChange={(v) => setParams(p => ({ ...p, clahe: v }))} />
                      <ToggleControl label="Equalizzazione Istogramma" checked={params.histogram_equalization}
                        onChange={(v) => setParams(p => ({ ...p, histogram_equalization: v }))} />
                    </div>
                  )}
                </div>

                {/* Error */}
                {error && (
                  <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                {/* ═══ PROCESS BUTTON ═══ */}
                <button
                  onClick={handleEnhance}
                  disabled={processing || !selectedFile}
                  className={`w-full py-4 px-6 rounded-xl font-semibold text-white transition-all duration-200 flex items-center justify-center gap-3 ${
                    processing
                      ? 'bg-gray-400 cursor-not-allowed'
                      : `bg-gradient-to-r ${currentType?.gradient || 'from-cyan-400 to-teal-600'} hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]`
                  }`}
                >
                  {processing ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      {jobStatus ? (
                        <span>
                          {jobStatus.status === 'enhancing' ? 'Elaborazione in corso...' : 'Avvio...'}
                          {jobStatus.progress > 0 && ` (${jobStatus.progress}%)`}
                        </span>
                      ) : (
                        <span>Caricamento... {uploadProgress > 0 ? `(${Math.round(uploadProgress)}%)` : ''}</span>
                      )}
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      Avvia Enhancement
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        )}

        {/* ═══ RESULT: BEFORE/AFTER COMPARISON ═══ */}
        {result && originalBlobUrl && enhancedBlobUrl && (
          <div className="space-y-6">
            {/* AI Analysis (if available) */}
            {aiAnalysis && (
              <div className="glass rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Brain className="w-5 h-5 text-purple-500" />
                  Analisi AI
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">Qualit&agrave; Generale</p>
                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                      aiAnalysis.overall_quality === 'excellent' ? 'bg-green-100 text-green-700' :
                      aiAnalysis.overall_quality === 'good' ? 'bg-blue-100 text-blue-700' :
                      aiAnalysis.overall_quality === 'fair' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {aiAnalysis.overall_quality}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">Problemi Rilevati</p>
                    <div className="flex flex-wrap gap-1">
                      {aiAnalysis.issues_detected?.map((issue, i) => (
                        <span key={i} className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-lg">
                          {issue}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                {aiAnalysis.suggestions?.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-gray-500 mb-2">Suggerimenti Applicati</p>
                    <div className="space-y-1">
                      {aiAnalysis.suggestions.map((s, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm">
                          <span className={`w-2 h-2 rounded-full ${
                            s.priority === 'high' ? 'bg-red-400' :
                            s.priority === 'medium' ? 'bg-yellow-400' : 'bg-green-400'
                          }`} />
                          <span className="text-gray-600">{s.type}: {s.reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Before/After Comparison */}
            <div className="glass rounded-2xl overflow-hidden">
              <div className="p-4 border-b border-gray-200/50 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <ZoomIn className="w-5 h-5 text-gray-400" />
                  Confronto Prima / Dopo
                </h3>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Info className="w-3.5 h-3.5" />
                  Trascina il divisore
                </div>
              </div>

              <div
                ref={sliderRef}
                className="relative select-none cursor-col-resize"
                style={{ aspectRatio: '16/10', maxHeight: '600px' }}
                onMouseDown={handleSliderMouseDown}
              >
                {/* Enhanced (full width, behind) */}
                <img
                  src={enhancedBlobUrl}
                  alt="Enhanced"
                  className="absolute inset-0 w-full h-full object-contain bg-gray-100"
                  draggable={false}
                />

                {/* Original (clipped) */}
                <div
                  className="absolute inset-0 overflow-hidden"
                  style={{ width: `${sliderPosition}%` }}
                >
                  <img
                    src={originalBlobUrl}
                    alt="Original"
                    className="w-full h-full object-contain bg-gray-100"
                    style={{ width: `${sliderRef.current ? sliderRef.current.offsetWidth : 100}px`, maxWidth: 'none' }}
                    draggable={false}
                  />
                </div>

                {/* Slider line */}
                <div
                  className="absolute top-0 bottom-0 w-1 bg-white shadow-lg"
                  style={{ left: `${sliderPosition}%`, transform: 'translateX(-50%)' }}
                >
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 bg-white rounded-full shadow-xl flex items-center justify-center border-2 border-gray-300">
                    <div className="flex gap-0.5">
                      <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                      <div className="w-0.5 h-4 bg-gray-400 rounded-full" />
                    </div>
                  </div>
                </div>

                {/* Labels */}
                <div className="absolute top-3 left-3 px-2 py-1 bg-black/60 rounded-lg text-white text-xs font-medium">
                  Originale
                </div>
                <div className="absolute top-3 right-3 px-2 py-1 bg-black/60 rounded-lg text-white text-xs font-medium">
                  Migliorata
                </div>
              </div>
            </div>

            {/* Result info + Actions */}
            <div className="glass rounded-2xl p-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <p className="font-semibold text-gray-900">{result.original_filename}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {result.original_dimensions?.width}&times;{result.original_dimensions?.height}
                    {' → '}
                    {result.enhanced_dimensions?.width}&times;{result.enhanced_dimensions?.height}
                    {result.enhanced_size_bytes && (
                      <> &middot; {(result.enhanced_size_bytes / (1024 * 1024)).toFixed(2)} MB</>
                    )}
                  </p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={handleReset}
                    className="btn btn-ghost btn-sm flex items-center gap-2"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Nuova Immagine
                  </button>
                  <button
                    onClick={handleDownload}
                    className="btn btn-primary btn-sm flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Scarica
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Credit Dialog */}
      <CreditConfirmDialog
        isOpen={showCreditDialog}
        onConfirm={handleConfirmedEnhance}
        onCancel={() => setShowCreditDialog(false)}
        operationName={`Image Enhancement (${currentType?.label || enhancementType})`}
        estimatedCredits={creditEstimate?.credits_needed || 0}
        breakdown={creditEstimate?.breakdown || {}}
        currentBalance={credits === null ? -1 : credits}
        loading={creditLoading}
      />
    </div>
  );
};

// ─── Reusable Controls ───

const SliderControl = ({ label, value, min, max, step, onChange }) => (
  <div>
    <div className="flex items-center justify-between mb-2">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <span className="text-sm font-mono text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
        {typeof value === 'number' ? value.toFixed(2) : value}
      </span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-cyan-500"
    />
    <div className="flex justify-between text-xs text-gray-400 mt-1">
      <span>{min}</span>
      <span>{max}</span>
    </div>
  </div>
);

const ToggleControl = ({ label, checked, onChange }) => (
  <div className="flex items-center justify-between">
    <label className="text-sm font-medium text-gray-700">{label}</label>
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${
        checked ? 'bg-cyan-500' : 'bg-gray-300'
      }`}
    >
      <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-transform duration-200 ${
        checked ? 'translate-x-6' : 'translate-x-0.5'
      }`} />
    </button>
  </div>
);

export default ImageEnhancer;
