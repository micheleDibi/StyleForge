import { useState, useMemo, useEffect } from 'react';
import { Download, FileText, Eye, Copy, Check, Loader, FileType, FileCode, BookOpen, List, Calendar, User, Settings, ChevronDown, Shield, AlertTriangle, BarChart3 } from 'lucide-react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { exportThesis, getExportTemplates, startCompilatioScan, downloadCompilatioReport, pollJobStatus } from '../../services/api';
import { parseThesisContent, buildAssetIndices, formatAssetCaption } from '../../utils/thesisAssets';
import { splitMathSpans } from '../../utils/thesisMath';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';

const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// KaTeX escapa sempre l'input nell'HTML prodotto; trust:false tiene
// disattivati \href e simili. ATTENZIONE: throwOnError:false intercetta solo
// i ParseError — un RangeError (nesting patologico) verrebbe comunque
// rilanciato e farebbe scattare l'ErrorBoundary dell'app: mai senza try/catch.
const katexHtml = (latex, displayMode) => {
  try {
    return katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      trust: false,
      maxExpand: 100,
    });
  } catch {
    return `<span style="color:#b91c1c;font-family:monospace">$${escapeHtml(latex)}$</span>`;
  }
};

/** Singola formula KaTeX con HTML memoizzato (non ricalcolato a ogni re-render). */
const KatexSpan = ({ latex, display = false, className }) => {
  const html = useMemo(() => katexHtml(latex, display), [latex, display]);
  return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />;
};

/** Testo con eventuali formule $...$ renderizzate via KaTeX. */
const MathText = ({ text }) => {
  const spans = useMemo(() => splitMathSpans(text), [text]);
  if (!spans.some((s) => s.kind === 'math')) return text;
  return spans.map((s, i) => (
    s.kind === 'math'
      ? <KatexSpan key={i} latex={s.value} />
      : <span key={i}>{s.value}</span>
  ));
};

const ThesisPreview = ({ thesis, content }) => {
  const { t } = useTranslation();
  const { hasPermission } = useAuth();
  // Detector AI sulla tesi: ammesso a chi ha 'compilatio_scan' (full)
  // OPPURE 'compilatio_scan_thesis' (granulare). hasPermission e' true di default per gli admin.
  const canScanThesis = hasPermission('compilatio_scan') || hasPermission('compilatio_scan_thesis');
  const [activeTab, setActiveTab] = useState('preview');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [isExporting, setIsExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // Compilatio scan state (admin-only)
  const [compilatioScanning, setCompilatioScanning] = useState(false);
  const [compilatioResult, setCompilatioResult] = useState(null);
  const [compilatioError, setCompilatioError] = useState(null);
  const [compilatioJobId, setCompilatioJobId] = useState(null);
  const [compilatioProgress, setCompilatioProgress] = useState(0);

  // Stato per il download del report PDF
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);

  // Carica i template disponibili
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const data = await getExportTemplates();
        const tpls = data.templates || [];
        setTemplates(tpls);
        // Imposta il default
        const defaultTpl = tpls.find(tpl => tpl.is_default);
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

  // Compilatio scan handler (admin-only)
  const handleCompilatioScan = async () => {
    if (!content || compilatioScanning) return;

    setCompilatioScanning(true);
    setCompilatioError(null);
    setCompilatioResult(null);
    setCompilatioProgress(0);

    try {
      const response = await startCompilatioScan(content, 'thesis', thesis?.id);

      // Se risultato cached, mostra subito
      if (response.cached && response.cached_scan) {
        setCompilatioResult(response.cached_scan);
        setCompilatioScanning(false);
        return;
      }

      // Poll per il risultato
      setCompilatioJobId(response.job_id);
      const finalStatus = await pollJobStatus(
        response.job_id,
        (status) => {
          setCompilatioProgress(status.progress || 0);
        },
        4000
      );

      if (finalStatus.status === 'completed' && finalStatus.result) {
        try {
          const scanResult = JSON.parse(finalStatus.result);
          setCompilatioResult(scanResult);
        } catch {
          setCompilatioResult(finalStatus.result);
        }
      } else if (finalStatus.status === 'failed') {
        setCompilatioError(finalStatus.error || t('Scansione fallita'));
      }
    } catch (error) {
      console.error('Errore scansione Compilatio:', error);
      setCompilatioError(error.response?.data?.detail || t('Errore durante la scansione'));
    } finally {
      setCompilatioScanning(false);
    }
  };

  const handleDownloadCompilatioReport = async () => {
    if (!compilatioResult?.scan_id || downloadingReport) return;
    setDownloadingReport(true);
    setDownloadProgress(0);
    try {
      await downloadCompilatioReport(compilatioResult.scan_id, (pct) => {
        setDownloadProgress(pct);
      });
    } catch (error) {
      console.error('Errore download report:', error);
      const msg = error?.code === 'ECONNABORTED'
        ? t('Il download e\' scaduto. Riprova fra qualche istante.')
        : (error?.response?.data?.detail || t('Errore nel download del report'));
      alert(msg);
    } finally {
      setDownloadingReport(false);
      setDownloadProgress(0);
    }
  };

  const getAIScoreColor = (percent) => {
    if (percent <= 5) return 'text-green-600 bg-green-50 border-green-200';
    if (percent <= 20) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const formatExportOptions = [
    { value: 'pdf', label: 'PDF', icon: FileText, description: t('Documento formattato') },
    { value: 'docx', label: 'DOCX', icon: FileType, description: t('Documento Word') },
    { value: 'txt', label: 'TXT', icon: FileType, description: t('Testo semplice') },
    { value: 'md', label: 'Markdown', icon: FileCode, description: t('Con formattazione') }
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

  // Segmenti (testo / tabelle / grafici / HINT) per l'anteprima formattata
  const segments = useMemo(
    () => parseThesisContent(content, thesis?.chapters_structure),
    [content, thesis]
  );
  const assetIndices = useMemo(() => buildAssetIndices(segments), [segments]);

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
        <h2 className="text-2xl font-bold text-slate-900 mb-2">{t('Anteprima e Download')}</h2>
        <p className="text-slate-600">
          {t('La tua tesi è pronta! Rivedi l\'anteprima e scarica nel formato preferito.')}
        </p>
      </div>

      {/* Thesis Info Card - Titolo completo */}
      <div className="card bg-gradient-to-r from-orange-50 to-red-50 border-orange-200">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-14 h-14 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
            <BookOpen className="w-7 h-7 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-xl font-bold text-slate-900 break-words">{thesis?.title || t('Titolo non disponibile')}</h3>
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
                {t('{{count}} capitoli', { count: thesis?.num_chapters || chaptersStructure.length })}
              </span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 grid grid-cols-3 gap-4">
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{wordCount.toLocaleString()}</p>
            <p className="text-xs text-slate-600">{t('Parole')}</p>
          </div>
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{charCount.toLocaleString()}</p>
            <p className="text-xs text-slate-600">{t('Caratteri')}</p>
          </div>
          <div className="bg-white/50 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-orange-600">{paragraphCount}</p>
            <p className="text-xs text-slate-600">{t('Paragrafi')}</p>
          </div>
        </div>
      </div>

      {/* Compilatio Scan - per chi ha permesso 'compilatio_scan' o 'compilatio_scan_thesis' */}
      {canScanThesis && content && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-purple-500" />
            <h3 className="font-semibold text-slate-900">{t('Scansione Detector AI')}</h3>
          </div>

          {!compilatioResult && !compilatioScanning && !compilatioError && (
            <div>
              <p className="text-sm text-slate-600 mb-3">
                {t('Analizza la tesi per rilevamento AI e plagio.')}
              </p>
              <button
                onClick={handleCompilatioScan}
                className="btn gap-2 text-sm bg-gradient-to-r from-purple-500 to-indigo-600 text-white hover:from-purple-600 hover:to-indigo-700 h-10"
              >
                <Shield className="w-4 h-4" />
                {t('Avvia Scansione Detector AI')}
              </button>
            </div>
          )}

          {compilatioScanning && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-2">
                <Loader className="w-5 h-5 text-purple-600 animate-spin" />
                <span className="text-purple-700 font-medium text-sm">{t('Scansione Detector AI in corso...')}</span>
              </div>
              <div className="w-full bg-purple-200 rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-purple-500 to-indigo-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${compilatioProgress}%` }}
                ></div>
              </div>
              <p className="text-xs text-purple-500 mt-1">{t('L\'analisi della tesi puo\' richiedere alcuni minuti')}</p>
            </div>
          )}

          {compilatioError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <span className="text-red-700 text-sm">{compilatioError}</span>
              <button onClick={handleCompilatioScan} className="ml-auto text-red-600 hover:text-red-800 text-sm underline">
                {t('Riprova')}
              </button>
            </div>
          )}

          {compilatioResult && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">{t('Risultati analisi')}</span>
                {compilatioResult.has_report && (
                  <button
                    onClick={handleDownloadCompilatioReport}
                    disabled={downloadingReport}
                    className="btn btn-secondary gap-1 text-xs h-8 disabled:opacity-60 disabled:cursor-not-allowed min-w-[120px]"
                  >
                    {downloadingReport ? (
                      <>
                        <Loader className="w-3 h-3 animate-spin" />
                        {downloadProgress}%
                      </>
                    ) : (
                      <>
                        <FileText className="w-3 h-3" />
                        {t('Report PDF')}
                      </>
                    )}
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className={`rounded-lg p-3 border ${getAIScoreColor(compilatioResult.ai_generated_percent)}`}>
                  <div className="text-2xl font-bold">{compilatioResult.ai_generated_percent?.toFixed(1)}%</div>
                  <div className="text-xs font-medium opacity-80">{t('AI Generato')}</div>
                </div>
                <div className="rounded-lg p-3 border bg-blue-50 border-blue-200 text-blue-600">
                  <div className="text-2xl font-bold">{compilatioResult.similarity_percent?.toFixed(1)}%</div>
                  <div className="text-xs font-medium opacity-80">{t('Similarita')}</div>
                </div>
                <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                  <div className="text-lg font-bold">{compilatioResult.global_score_percent?.toFixed(1)}%</div>
                  <div className="text-xs font-medium opacity-80">{t('Score Globale')}</div>
                </div>
                <div className="rounded-lg p-3 border bg-slate-50 border-slate-200 text-slate-600">
                  <div className="text-lg font-bold">{compilatioResult.exact_percent?.toFixed(1)}%</div>
                  <div className="text-xs font-medium opacity-80">{t('Match Esatti')}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Indice interattivo */}
      {chaptersStructure.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <List className="w-5 h-5 text-orange-500" />
            <h3 className="font-semibold text-slate-900">{t('Indice del Documento')}</h3>
          </div>
          <div className="space-y-3 max-h-60 overflow-y-auto">
            {chaptersStructure.map((chapter, chIndex) => (
              <div key={chIndex} className="border-l-2 border-orange-200 pl-3">
                <p className="font-medium text-slate-800">
                  {chapter.is_special
                    ? (chapter.chapter_title || chapter.title)
                    : t('Capitolo {{index}}: {{title}}', { index: chapter.chapter_index || chIndex + 1, title: chapter.chapter_title || chapter.title })
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
            {t('Anteprima')}
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
            {t('Esporta')}
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
                      {t('Copiato!')}
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 mr-1" />
                      {t('Copia tutto')}
                    </>
                  )}
                </button>
              </div>

              {/* Content Preview */}
              <div className="bg-slate-50 rounded-lg border border-slate-200 p-6 max-h-[600px] overflow-y-auto">
                <div className="prose prose-slate max-w-none">
                  {content ? (
                    <div className="font-serif text-slate-800 leading-relaxed">
                      {tableOfContents && (
                        <div className="whitespace-pre-wrap">{tableOfContents}</div>
                      )}
                      {(assetIndices.tables.length > 0 || assetIndices.figures.length > 0) && (
                        <div className="mb-6 space-y-4">
                          {[
                            [t('Indice delle tabelle'), assetIndices.tables],
                            [t('Indice delle figure'), assetIndices.figures],
                          ].map(([idxTitle, entries]) => entries.length > 0 && (
                            <div key={idxTitle}>
                              <p className="font-semibold text-slate-900">{idxTitle}</p>
                              <ul className="mt-1 space-y-0.5 text-sm text-slate-600">
                                {entries.map((e, i) => (
                                  <li key={i} className="pl-4">{e.label} – {e.caption}</li>
                                ))}
                              </ul>
                            </div>
                          ))}
                        </div>
                      )}
                      {segments.map((seg, idx) => {
                        if (seg.kind === 'text') {
                          return (
                            <div key={idx} className="whitespace-pre-wrap"><MathText text={seg.text} /></div>
                          );
                        }
                        if (seg.kind === 'math') {
                          return (
                            <div key={idx} className="my-4 not-prose flex items-center">
                              <KatexSpan
                                latex={seg.math.latex}
                                display
                                className="flex-1 text-center overflow-x-auto"
                              />
                              {seg.math.label && (
                                <span className="text-sm text-slate-700 pl-3">{seg.math.label}</span>
                              )}
                            </div>
                          );
                        }
                        if (seg.kind === 'table') {
                          return (
                            <div key={idx} className="my-6 not-prose">
                              <p className="text-sm font-semibold text-slate-700 text-center mb-2">
                                {formatAssetCaption(seg.table)}
                              </p>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm border border-slate-300 border-collapse">
                                  <thead>
                                    <tr className="bg-slate-100">
                                      {seg.table.header.map((h, i) => (
                                        <th key={i} className="border border-slate-300 px-3 py-1.5 text-left font-semibold text-slate-800"><MathText text={h} /></th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {seg.table.rows.map((row, r) => (
                                      <tr key={r}>
                                        {row.map((cell, c) => (
                                          <td key={c} className="border border-slate-300 px-3 py-1.5 text-slate-700"><MathText text={cell} /></td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                              {seg.table.source && (
                                <p className="text-xs text-slate-500 italic text-center mt-1">
                                  {t('Fonte:')} {seg.table.source}
                                </p>
                              )}
                            </div>
                          );
                        }
                        if (seg.kind === 'chart') {
                          return (
                            <div key={idx} className="my-6 not-prose border border-slate-300 bg-white rounded-lg p-5 text-center">
                              <BarChart3 className="w-10 h-10 mx-auto mb-2 text-slate-400" />
                              <p className="text-sm font-semibold text-slate-700">
                                {formatAssetCaption(seg.chart)}
                              </p>
                              {seg.chart.spec?.source && (
                                <p className="text-xs text-slate-500 italic mt-1">
                                  {t('Fonte:')} {seg.chart.spec.source}
                                </p>
                              )}
                              <p className="text-xs text-slate-400 mt-2">
                                {seg.chart.error
                                  ? t('Grafico non valido: verrà sostituito da un suggerimento negli export.')
                                  : t('Il grafico renderizzato sarà incluso negli export PDF e DOCX.')}
                              </p>
                            </div>
                          );
                        }
                        // hint
                        return (
                          <div key={idx} className="my-6 not-prose bg-amber-50 border-2 border-amber-400 rounded-lg p-4 flex gap-3">
                            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                            <div>
                              <p className="text-sm font-bold text-amber-800">
                                {t('SUGGERIMENTO — da sostituire')}
                              </p>
                              <p className="text-sm text-amber-800 mt-0.5">{seg.text}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                      <p className="text-slate-500">{t('Nessun contenuto disponibile')}</p>
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
                  {t('Seleziona il formato di esportazione')}
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
                    {t('Template di esportazione')}
                  </label>
                  <div className="relative">
                    <select
                      value={selectedTemplate || ''}
                      onChange={(e) => setSelectedTemplate(e.target.value)}
                      className="w-full p-3 pr-10 rounded-lg border-2 border-slate-200 bg-white text-slate-700 font-medium appearance-none cursor-pointer hover:border-orange-300 focus:border-orange-500 focus:outline-none transition-colors"
                    >
                      {templates.map(tpl => (
                        <option key={tpl.id} value={tpl.id}>
                          {tpl.name} {tpl.is_default ? t('(Default)') : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    {t('Seleziona il template con le impostazioni di formattazione desiderate.')}
                  </p>
                </div>
              )}

              {/* Export Button */}
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed text-base"
              >
                {isExporting ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    {t('Preparazione download...')}
                  </>
                ) : (
                  <>
                    <Download className="w-5 h-5" />
                    {t('Scarica come {{format}}', { format: exportFormat.toUpperCase() })}
                  </>
                )}
              </button>

              {/* Info */}
              <p className="text-sm text-slate-500 text-center">
                {t('Il file verrà scaricato automaticamente una volta pronto.')}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <p className="text-sm text-slate-500 text-center">
        {t('Tesi generata con StyleForge AI')}
      </p>
    </div>
  );
};

export default ThesisPreview;
