import { useState, useMemo, useEffect } from 'react';
import { Download, FileText, Eye, Copy, Check, Loader, FileType, FileCode, BookOpen, List, Calendar, User, Settings, ChevronDown } from 'lucide-react';
import { exportThesis, getExportTemplates } from '../../services/api';

const ThesisPreview = ({ thesis, content }) => {
  const [activeTab, setActiveTab] = useState('preview');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [isExporting, setIsExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // Carica i template disponibili
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const data = await getExportTemplates();
        const tpls = data.templates || [];
        setTemplates(tpls);
        // Imposta il default
        const defaultTpl = tpls.find(t => t.is_default);
        if (defaultTpl) setSelectedTemplate(defaultTpl.id);
        else if (tpls.length > 0) setSelectedTemplate(tpls[0].id);
      } catch (err) {
        console.error('Errore caricamento template:', err);
      }
    };
    loadTemplates();
  }, []);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportThesis(thesis.id, exportFormat, selectedTemplate);
    } catch (err) {
      console.error('Errore export:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(contentWithIndex);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Errore copia:', err);
    }
  };

  const formatExportOptions = [
    { value: 'pdf', label: 'PDF', icon: FileText, description: 'Documento formattato' },
    { value: 'docx', label: 'DOCX', icon: FileType, description: 'Documento Word' },
    { value: 'txt', label: 'TXT', icon: FileType, description: 'Testo semplice' },
    { value: 'md', label: 'Markdown', icon: FileCode, description: 'Con formattazione' }
  ];

  // Estrai la struttura dei capitoli dalla tesi
  const chaptersStructure = useMemo(() => {
    if (!thesis?.chapters_structure?.chapters) return [];
    return thesis.chapters_structure.chapters;
  }, [thesis]);

  // Genera l'indice
  const tableOfContents = useMemo(() => {
    if (!chaptersStructure.length) return '';

    let toc = '═══════════════════════════════════════════════════════════════\n';
    toc += '                           INDICE\n';
    toc += '═══════════════════════════════════════════════════════════════\n\n';

    chaptersStructure.forEach((chapter, chIndex) => {
      if (chapter.is_special) {
        toc += `${chapter.chapter_title || chapter.title}\n\n`;
      } else {
        toc += `Capitolo ${chapter.chapter_index || chIndex + 1}: ${chapter.chapter_title || chapter.title}\n`;
        if (chapter.sections && chapter.sections.length > 0) {
          chapter.sections.forEach((section) => {
            toc += `    ${chapter.chapter_index || chIndex + 1}.${section.index}: ${section.title}\n`;
          });
        }
        toc += '\n';
      }
    });

    toc += '═══════════════════════════════════════════════════════════════\n\n';
    return toc;
  }, [chaptersStructure]);

  // Contenuto con indice
  const contentWithIndex = useMemo(() => {
    if (!content) return '';
    return tableOfContents + content;
  }, [tableOfContents, content]);

  // Calcola statistiche
  const wordCount = contentWithIndex ? contentWithIndex.split(/\s+/).filter(w => w.length > 0).length : 0;
  const charCount = contentWithIndex ? contentWithIndex.length : 0;
  const paragraphCount = contentWithIndex ? contentWithIndex.split(/\n\n+/).filter(p => p.trim().length > 0).length : 0;

  // Formatta la data
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Anteprima e Download</h2>
        <p className="text-slate-600">
          La tua tesi è pronta! Rivedi l'anteprima e scarica nel formato preferito.
        </p>
      </div>

      {/* Thesis Info Card - Titolo completo */}
      <div className="card bg-gradient-to-r from-orange-50 to-red-50 border-orange-200">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-14 h-14 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
            <BookOpen className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-xl font-bold text-slate-900 break-words">{thesis?.title || 'Titolo non disponibile'}</h3>
            {thesis?.description && (
              <p className="text-slate-600 mt-1 break-words">{thesis.description}</p>
            )}
            <div className="flex flex-wrap gap-4 mt-3 text-sm text-slate-500">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {formatDate(thesis?.created_at)}
              </span>
              <span className="flex items-center gap-1">
                <List className="w-4 h-4" />
                {thesis?.num_chapters || chaptersStructure.length} capitoli
              </span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 grid grid-cols-3 gap-4">
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{wordCount.toLocaleString()}</p>
            <p className="text-xs text-slate-600">Parole</p>
          </div>
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{charCount.toLocaleString()}</p>
            <p className="text-xs text-slate-600">Caratteri</p>
          </div>
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{paragraphCount}</p>
            <p className="text-xs text-slate-600">Paragrafi</p>
          </div>
        </div>
      </div>

      {/* Indice interattivo */}
      {chaptersStructure.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <List className="w-5 h-5 text-orange-500" />
            <h3 className="font-semibold text-slate-900">Indice del Documento</h3>
          </div>
          <div className="space-y-3 max-h-60 overflow-y-auto">
            {chaptersStructure.map((chapter, chIndex) => (
              <div key={chIndex} className="border-l-2 border-orange-200 pl-3">
                <p className="font-medium text-slate-800">
                  {chapter.is_special
                    ? (chapter.chapter_title || chapter.title)
                    : `Capitolo ${chapter.chapter_index || chIndex + 1}: ${chapter.chapter_title || chapter.title}`
                  }
                </p>
                {!chapter.is_special && chapter.sections && chapter.sections.length > 0 && (
                  <ul className="mt-1 space-y-1 text-sm text-slate-600">
                    {chapter.sections.map((section, secIndex) => (
                      <li key={secIndex} className="pl-4">
                        {chapter.chapter_index || chIndex + 1}.{section.index}: {section.title}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="card p-0 overflow-hidden">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab('preview')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'preview'
                ? 'bg-white text-orange-600 border-b-2 border-orange-500'
                : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Eye className="w-4 h-4 inline-block mr-2" />
            Anteprima
          </button>
          <button
            onClick={() => setActiveTab('export')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'export'
                ? 'bg-white text-orange-600 border-b-2 border-orange-500'
                : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Download className="w-4 h-4 inline-block mr-2" />
            Esporta
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'preview' ? (
            <div className="space-y-4">
              {/* Copy Button */}
              <div className="flex justify-end">
                <button
                  onClick={handleCopy}
                  className="btn-secondary text-sm py-1.5 px-3"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 mr-1 text-green-500" />
                      Copiato!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 mr-1" />
                      Copia tutto
                    </>
                  )}
                </button>
              </div>

              {/* Content Preview */}
              <div className="bg-slate-50 rounded-lg border border-slate-200 p-6 max-h-[600px] overflow-y-auto">
                <div className="prose prose-slate max-w-none">
                  {contentWithIndex ? (
                    <div className="whitespace-pre-wrap font-serif text-slate-800 leading-relaxed">
                      {contentWithIndex}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                      <p className="text-slate-500">Nessun contenuto disponibile</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Export Format Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  Seleziona il formato di esportazione
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {formatExportOptions.map((format) => {
                    const Icon = format.icon;
                    return (
                      <button
                        key={format.value}
                        onClick={() => setExportFormat(format.value)}
                        className={`p-4 rounded-lg border-2 transition-all ${
                          exportFormat === format.value
                            ? 'border-orange-500 bg-orange-50'
                            : 'border-slate-200 hover:border-orange-300'
                        }`}
                      >
                        <Icon className={`w-8 h-8 mx-auto mb-2 ${
                          exportFormat === format.value ? 'text-orange-500' : 'text-slate-400'
                        }`} />
                        <p className={`font-medium ${
                          exportFormat === format.value ? 'text-orange-600' : 'text-slate-700'
                        }`}>
                          {format.label}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">{format.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Template Selector (only for PDF/DOCX) */}
              {(exportFormat === 'pdf' || exportFormat === 'docx') && templates.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Template di esportazione
                  </label>
                  <div className="relative">
                    <select
                      value={selectedTemplate || ''}
                      onChange={(e) => setSelectedTemplate(e.target.value)}
                      className="w-full p-3 pr-10 rounded-lg border-2 border-slate-200 bg-white text-slate-700 font-medium appearance-none cursor-pointer hover:border-orange-300 focus:border-orange-500 focus:outline-none transition-colors"
                    >
                      {templates.map(tpl => (
                        <option key={tpl.id} value={tpl.id}>
                          {tpl.name} {tpl.is_default ? '(Default)' : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Seleziona il template con le impostazioni di formattazione desiderate.
                  </p>
                </div>
              )}

              {/* Export Button */}
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="btn-primary w-full py-4 text-lg"
              >
                {isExporting ? (
                  <>
                    <Loader className="w-5 h-5 mr-2 animate-spin" />
                    Preparazione download...
                  </>
                ) : (
                  <>
                    <Download className="w-5 h-5 mr-2" />
                    Scarica come {exportFormat.toUpperCase()}
                  </>
                )}
              </button>

              {/* Info */}
              <p className="text-sm text-slate-500 text-center">
                Il file verrà scaricato automaticamente una volta pronto.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-slate-500">
          Tesi generata con StyleForge AI
        </p>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="btn-primary"
        >
          {isExporting ? (
            <>
              <Loader className="w-5 h-5 mr-2 animate-spin" />
              Download...
            </>
          ) : (
            <>
              <Download className="w-5 h-5 mr-2" />
              Download {exportFormat.toUpperCase()}
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default ThesisPreview;
