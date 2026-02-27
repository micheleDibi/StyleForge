import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Loader2, Copy, Check, Download, FileDown, AlertCircle,
  ChevronDown, ChevronUp, Save, X, Eye, Pencil, Link2, Sparkles, Image as ImageIcon
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  processCarouselUrl, getCarouselPrompts, updateCarouselPrompt, exportCarouselPdf
} from '../services/api';

const SECTION_CONFIG = {
  carousel: { label: 'Carosello', desc: '6 slide per Instagram', gradient: 'from-pink-500 to-orange-500' },
  post: { label: 'Post Singolo', desc: 'Titolo + sottotitolo grafica', gradient: 'from-blue-500 to-indigo-500' },
  copertina: { label: 'Copertina Video', desc: 'Testo copertina Instagram', gradient: 'from-purple-500 to-pink-500' },
};

const CarouselCreator = () => {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const [activeTab, setActiveTab] = useState('carousel');
  const [urlInput, setUrlInput] = useState('');
  const [results, setResults] = useState({ carousel: [], post: [], copertina: [] });
  const [processing, setProcessing] = useState(false);
  const [currentUrlIndex, setCurrentUrlIndex] = useState(-1);
  const [totalUrls, setTotalUrls] = useState(0);
  const [error, setError] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [exporting, setExporting] = useState(false);

  // Prompt management
  const [prompts, setPrompts] = useState({});
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [promptSaved, setPromptSaved] = useState(false);

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      const data = await getCarouselPrompts();
      setPrompts(data);
    } catch (e) {
      console.error('Errore caricamento prompt:', e);
    }
  };

  const getValidUrls = () => {
    return urlInput
      .split('\n')
      .map(u => u.trim())
      .filter(u => u && (u.startsWith('http://') || u.startsWith('https://')));
  };

  const handleGenerate = async () => {
    const urls = getValidUrls();
    if (urls.length === 0) {
      setError('Inserisci almeno un URL valido');
      return;
    }

    setError('');
    setProcessing(true);
    setTotalUrls(urls.length);
    const newResults = [];

    for (let i = 0; i < urls.length; i++) {
      setCurrentUrlIndex(i);
      try {
        const result = await processCarouselUrl(urls[i], activeTab);
        newResults.push(result);
      } catch (e) {
        const msg = e.response?.data?.detail || e.message || 'Errore sconosciuto';
        newResults.push({
          url: urls[i],
          error: msg,
          article_title: urls[i],
          article_category: '',
          content: null,
        });
      }
    }

    setResults(prev => ({ ...prev, [activeTab]: newResults }));
    setProcessing(false);
    setCurrentUrlIndex(-1);
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatCarouselForCopy = (content) => {
    if (!content?.slides) return '';
    return content.slides.map(s =>
      `━━━ SLIDE ${s.numero} ━━━\n${s.titolo}\n\n${s.contenuto}`
    ).join('\n\n');
  };

  const formatPostForCopy = (content) => {
    if (!content) return '';
    return `TITOLO:\n${content.titolo || ''}\n\nSOTTOTITOLO:\n${content.sottotitolo || ''}`;
  };

  const formatCopertinaForCopy = (content) => {
    return content?.testo || '';
  };

  const handleExportPdf = async () => {
    const currentResults = results[activeTab];
    if (!currentResults || currentResults.length === 0) return;

    setExporting(true);
    try {
      await exportCarouselPdf(currentResults, activeTab);
    } catch (e) {
      setError('Errore durante l\'esportazione PDF');
    }
    setExporting(false);
  };

  const handleDownloadImage = (base64, format, title) => {
    const link = document.createElement('a');
    link.href = `data:image/${format};base64,${base64}`;
    link.download = `${(title || 'immagine').replace(/[^a-zA-Z0-9]/g, '_')}_enhanced.${format === 'jpeg' ? 'jpg' : format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleSavePrompt = async () => {
    setSavingPrompt(true);
    try {
      await updateCarouselPrompt(activeTab, editingPrompt);
      setPrompts(prev => ({ ...prev, [activeTab]: editingPrompt }));
      setPromptSaved(true);
      setTimeout(() => setPromptSaved(false), 2000);
    } catch (e) {
      setError('Errore nel salvataggio del prompt');
    }
    setSavingPrompt(false);
  };

  const handleOpenPromptEditor = () => {
    setEditingPrompt(prompts[activeTab] || '');
    setShowPromptEditor(true);
  };

  const validUrlCount = getValidUrls().length;
  const currentResults = results[activeTab];

  return (
    <div className="min-h-screen relative">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-pink-100 to-orange-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-gradient-to-br from-purple-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/')} className="btn-ghost p-2 rounded-xl">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Crea <span className="gradient-text">Carosello / Post / Copertina</span>
            </h1>
            <p className="text-sm text-gray-500">Genera contenuti Instagram da articoli EduNews24</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {Object.entries(SECTION_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => { setActiveTab(key); setShowPromptEditor(false); }}
              className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                activeTab === key
                  ? `bg-gradient-to-r ${cfg.gradient} text-white shadow-lg`
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              {cfg.label}
            </button>
          ))}
        </div>

        {/* Section description */}
        <div className="glass rounded-2xl p-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-orange-500" />
              <span className="text-sm font-medium text-gray-700">{SECTION_CONFIG[activeTab].desc}</span>
            </div>
            {/* Admin prompt toggle */}
            {isAdmin && (
              <button
                onClick={() => showPromptEditor ? setShowPromptEditor(false) : handleOpenPromptEditor()}
                className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                {showPromptEditor ? <Eye className="w-3.5 h-3.5" /> : <Pencil className="w-3.5 h-3.5" />}
                {showPromptEditor ? 'Chiudi prompt' : 'Modifica prompt'}
              </button>
            )}
          </div>

          {/* Prompt editor (admin only) */}
          {isAdmin && showPromptEditor && (
            <div className="mt-3 border-t border-gray-200 pt-3">
              <textarea
                value={editingPrompt}
                onChange={e => setEditingPrompt(e.target.value)}
                className="input textarea w-full font-mono text-xs"
                rows={12}
                placeholder="Prompt per questa sezione..."
              />
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={handleSavePrompt}
                  disabled={savingPrompt}
                  className="btn-primary btn-sm flex items-center gap-1.5"
                >
                  {savingPrompt ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  Salva
                </button>
                <button
                  onClick={() => setShowPromptEditor(false)}
                  className="btn-ghost btn-sm flex items-center gap-1.5"
                >
                  <X className="w-3.5 h-3.5" /> Annulla
                </button>
                {promptSaved && (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" /> Prompt aggiornato
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* URL Input */}
        <div className="card p-5 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <Link2 className="w-4 h-4 inline mr-1.5" />
            Link articoli EduNews24
          </label>
          <textarea
            value={urlInput}
            onChange={e => { setUrlInput(e.target.value); setError(''); }}
            className="input textarea w-full"
            rows={4}
            placeholder={"Inserisci uno o piu' link, uno per riga:\nhttps://edunews24.it/tecnologia/articolo-esempio\nhttps://edunews24.it/scuola/altro-articolo"}
            disabled={processing}
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-gray-400">
              {validUrlCount > 0 ? `${validUrlCount} link validi` : 'Nessun link valido'}
            </span>
            <button
              onClick={handleGenerate}
              disabled={processing || validUrlCount === 0}
              className="btn-primary flex items-center gap-2"
            >
              {processing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Elaborazione {currentUrlIndex + 1}/{totalUrls}...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Genera Contenuti
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-center gap-2 mt-3">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <span className="text-red-700 text-sm">{error}</span>
            </div>
          )}
        </div>

        {/* Results */}
        {currentResults && currentResults.length > 0 && (
          <div className="space-y-4">
            {/* Export bar */}
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-800">
                Risultati ({currentResults.filter(r => !r.error).length}/{currentResults.length})
              </h2>
              <button
                onClick={handleExportPdf}
                disabled={exporting}
                className="btn-secondary flex items-center gap-2"
              >
                {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileDown className="w-4 h-4" />}
                Esporta PDF
              </button>
            </div>

            {/* Result cards */}
            {currentResults.map((result, idx) => (
              <ResultCard
                key={idx}
                result={result}
                sectionType={activeTab}
                index={idx}
                copiedId={copiedId}
                onCopy={handleCopy}
                onDownloadImage={handleDownloadImage}
                formatCarouselForCopy={formatCarouselForCopy}
                formatPostForCopy={formatPostForCopy}
                formatCopertinaForCopy={formatCopertinaForCopy}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};


const ResultCard = ({
  result, sectionType, index, copiedId, onCopy,
  onDownloadImage, formatCarouselForCopy, formatPostForCopy, formatCopertinaForCopy
}) => {
  const [showImages, setShowImages] = useState(false);

  if (result.error) {
    return (
      <div className="card p-4 border-l-4 border-red-400">
        <div className="flex items-center gap-2 mb-1">
          <AlertCircle className="w-4 h-4 text-red-500" />
          <span className="text-sm font-medium text-red-700">Errore per: {result.url}</span>
        </div>
        <p className="text-sm text-red-600">{result.error}</p>
      </div>
    );
  }

  const content = result.content;
  const copyAllId = `all-${sectionType}-${index}`;

  return (
    <div className="card p-5">
      {/* Article header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{result.article_title || result.url}</h3>
          <div className="flex items-center gap-2 mt-1">
            {result.article_category && (
              <span className="badge badge-info text-xs">{result.article_category}</span>
            )}
            <a href={result.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline truncate">
              {result.url}
            </a>
          </div>
        </div>
        <button
          onClick={() => {
            let text = '';
            if (sectionType === 'carousel') text = formatCarouselForCopy(content);
            else if (sectionType === 'post') text = formatPostForCopy(content);
            else text = formatCopertinaForCopy(content);
            onCopy(text, copyAllId);
          }}
          className="btn-ghost btn-sm flex items-center gap-1.5 flex-shrink-0 ml-3"
        >
          {copiedId === copyAllId ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
          {copiedId === copyAllId ? 'Copiato!' : 'Copia tutto'}
        </button>
      </div>

      {/* Content based on section type */}
      {sectionType === 'carousel' && content?.slides && (
        <CarouselResult slides={content.slides} index={index} copiedId={copiedId} onCopy={onCopy} />
      )}

      {sectionType === 'post' && content && (
        <PostResult content={content} index={index} copiedId={copiedId} onCopy={onCopy} />
      )}

      {sectionType === 'copertina' && content && (
        <CopertinaResult content={content} index={index} copiedId={copiedId} onCopy={onCopy} />
      )}

      {/* Image section */}
      {(result.image_original_b64 || result.image_enhanced_b64) && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <button
            onClick={() => setShowImages(!showImages)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
          >
            <ImageIcon className="w-4 h-4" />
            Immagine articolo
            {showImages ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showImages && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.image_original_b64 && (
                <div>
                  <p className="text-xs text-gray-500 mb-1.5">Originale</p>
                  <img
                    src={`data:image/${result.image_format || 'jpeg'};base64,${result.image_original_b64}`}
                    alt="Originale"
                    className="w-full rounded-lg border border-gray-200"
                  />
                </div>
              )}
              {result.image_enhanced_b64 && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs text-gray-500">Migliorata con AI</p>
                    <button
                      onClick={() => onDownloadImage(
                        result.image_enhanced_b64,
                        result.image_format || 'jpeg',
                        result.article_title
                      )}
                      className="btn-ghost btn-sm flex items-center gap-1 text-xs"
                    >
                      <Download className="w-3.5 h-3.5" /> Scarica
                    </button>
                  </div>
                  <img
                    src={`data:image/${result.image_format || 'jpeg'};base64,${result.image_enhanced_b64}`}
                    alt="Migliorata"
                    className="w-full rounded-lg border border-gray-200"
                  />
                  {result.image_analysis && (
                    <p className="text-xs text-gray-400 mt-1.5 italic">{result.image_analysis}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};


const CarouselResult = ({ slides, index, copiedId, onCopy }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {slides.map((slide) => {
        const slideId = `slide-${index}-${slide.numero}`;
        // Replace **text** with styled spans for display
        const formattedContent = (slide.contenuto || '').split(/(\*\*.*?\*\*)/).map((part, i) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={i} className="text-gray-900">{part.slice(2, -2)}</strong>;
          }
          return part;
        });

        return (
          <div
            key={slide.numero}
            className={`rounded-xl border p-4 ${
              slide.numero === 1 ? 'border-orange-200 bg-orange-50/50' :
              slide.numero === 6 ? 'border-green-200 bg-green-50/50' :
              'border-gray-200 bg-white'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                slide.numero === 1 ? 'bg-orange-100 text-orange-700' :
                slide.numero === 6 ? 'bg-green-100 text-green-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                SLIDE {slide.numero}
              </span>
              <button
                onClick={() => onCopy(`${slide.titolo}\n\n${slide.contenuto}`, slideId)}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
                title="Copia slide"
              >
                {copiedId === slideId ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-400" />}
              </button>
            </div>
            <h4 className="font-bold text-sm text-gray-900 mb-1.5">{slide.titolo}</h4>
            <p className="text-xs text-gray-600 leading-relaxed">{formattedContent}</p>
          </div>
        );
      })}
    </div>
  );
};


const PostResult = ({ content, index, copiedId, onCopy }) => {
  const titleId = `post-title-${index}`;
  const subId = `post-sub-${index}`;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-blue-600">TITOLO</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{(content.titolo || '').length} caratteri</span>
            <button onClick={() => onCopy(content.titolo || '', titleId)} className="p-1 hover:bg-blue-100 rounded transition-colors">
              {copiedId === titleId ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-400" />}
            </button>
          </div>
        </div>
        <p className="font-bold text-gray-900">{content.titolo}</p>
      </div>

      <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-indigo-600">SOTTOTITOLO</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{(content.sottotitolo || '').length} caratteri</span>
            <button onClick={() => onCopy(content.sottotitolo || '', subId)} className="p-1 hover:bg-indigo-100 rounded transition-colors">
              {copiedId === subId ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-400" />}
            </button>
          </div>
        </div>
        <p className="text-gray-700">{content.sottotitolo}</p>
      </div>
    </div>
  );
};


const CopertinaResult = ({ content, index, copiedId, onCopy }) => {
  const textId = `copertina-${index}`;

  return (
    <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold text-purple-600">COPERTINA VIDEO</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{(content.testo || '').length} caratteri</span>
          <button onClick={() => onCopy(content.testo || '', textId)} className="p-1 hover:bg-purple-100 rounded transition-colors">
            {copiedId === textId ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-400" />}
          </button>
        </div>
      </div>
      <p className="text-lg font-semibold text-gray-900 leading-snug">{content.testo}</p>
    </div>
  );
};

export default CarouselCreator;
