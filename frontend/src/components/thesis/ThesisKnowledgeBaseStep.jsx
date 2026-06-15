import { useEffect, useRef, useState } from 'react';
import {
  Brain, BookMarked, Paperclip, Loader, AlertTriangle, CheckCircle2, Play,
  RefreshCw, FileText, ScrollText, ArrowRight, Clock, Sparkles, Wrench, ChevronDown,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { startWikiIngest, getWikiStatus, getWikiReport, getWikiContent, cancelWikiIngest } from '../../services/api';
import WikiLintReport from './WikiLintReport';
import WikiExtractedInfo from './WikiExtractedInfo';

const STATUS_LABELS = {
  none:      { label: 'Non avviata', cls: 'bg-slate-100 text-slate-700' },
  ingesting: { label: 'Ingest in corso', cls: 'bg-blue-100 text-blue-700' },
  ingested:  { label: 'Ingest completato', cls: 'bg-emerald-50 text-emerald-700' },
  linting:   { label: 'Lint in corso', cls: 'bg-amber-100 text-amber-800' },
  linted:    { label: 'Pronto', cls: 'bg-emerald-100 text-emerald-800' },
  failed:    { label: 'Errore', cls: 'bg-red-100 text-red-700' },
};

// Etichette delle fasi dell'ingest (chiave = `phase` emessa dal backend).
const PHASE_LABELS = {
  starting: 'Avvio…',
  download: 'Scarico i paper selezionati',
  prepare:  'Preparo i documenti caricati',
  ingest:   'Indicizzazione dei documenti',
  lint:     'Controllo qualità del wiki',
};

const POLL_MS = 3000;
const MAX_POLL_MS = 30 * 60 * 1000; // 30 min

// Durata leggibile (es. "2m 13s"). ms -> stringa.
const fmtDuration = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}m ${r}s` : `${r}s`;
};

// Il backend emette timestamp in UTC senza suffisso (datetime.utcnow().isoformat()).
// Forziamo l'interpretazione UTC per non sfasare il cronometro a seconda del fuso.
const parseUtc = (iso) => {
  if (!iso) return null;
  const norm = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const ms = Date.parse(norm);
  return Number.isNaN(ms) ? null : ms;
};

const ThesisKnowledgeBaseStep = ({
  thesisId,
  paperCount = 0,
  attachmentCount = 0,
  restrictToSources = true,
  onComplete,
  onBack,
}) => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [content, setContent] = useState(null);
  const [loadingAction, setLoadingAction] = useState(false);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const pollingRef = useRef(null);
  const startedAtRef = useRef(null);

  const stopPolling = () => {
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const fetchStatus = async () => {
    try {
      const s = await getWikiStatus(thesisId);
      setStatus(s);
      if (s.wiki_status === 'linted') {
        try {
          const r = await getWikiReport(thesisId);
          setReport(r.report || null);
        } catch { /* ignore */ }
      }
      // Informazioni estratte (vista utente): disponibili appena ci sono pagine.
      if (s.wiki_status === 'linted' || s.wiki_status === 'ingested') {
        try {
          const c = await getWikiContent(thesisId);
          setContent(c);
        } catch { /* ignore */ }
      }
      return s;
    } catch (e) {
      setError(e?.response?.data?.detail || t('Errore lettura stato wiki'));
      return null;
    }
  };

  const pollLoop = async () => {
    const s = await fetchStatus();
    const transitional = s && (s.wiki_status === 'ingesting' || s.wiki_status === 'linting');
    const elapsed = Date.now() - (startedAtRef.current || Date.now());
    if (transitional && elapsed < MAX_POLL_MS) {
      pollingRef.current = setTimeout(pollLoop, POLL_MS);
    } else {
      stopPolling();
    }
  };

  // Carica stato all'arrivo nello step (potrebbe essere gia' stato avviato in un'altra finestra)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const s = await fetchStatus();
      if (cancelled) return;
      if (s && (s.wiki_status === 'ingesting' || s.wiki_status === 'linting')) {
        startedAtRef.current = Date.now();
        pollingRef.current = setTimeout(pollLoop, POLL_MS);
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thesisId]);

  // Cronometro: aggiorna "now" ogni secondo solo mentre l'operazione e' in corso,
  // cosi' il tempo trascorso/stima scorre fluido tra un polling e l'altro.
  useEffect(() => {
    const tr = status && (status.wiki_status === 'ingesting' || status.wiki_status === 'linting');
    if (!tr) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [status]);

  const handleStart = async (force = false) => {
    setError(null);
    setLoadingAction(true);
    try {
      const s = await startWikiIngest(thesisId, force);
      setStatus(s);
      setReport(null);
      setContent(null);
      startedAtRef.current = Date.now();
      stopPolling();
      pollingRef.current = setTimeout(pollLoop, POLL_MS);
    } catch (e) {
      setError(e?.response?.data?.detail || t('Errore avvio ingest'));
    } finally {
      setLoadingAction(false);
    }
  };

  const ws = (status?.wiki_status || 'none').toLowerCase();
  const isTransitional = ws === 'ingesting' || ws === 'linting';
  const isReady = ws === 'linted' || ws === 'ingested';
  const isFailed = ws === 'failed';
  const totalSources = paperCount + attachmentCount;

  // Confronto fonti correnti vs. fonti indicizzate: se l'utente ha aggiunto
  // o rimosso documenti/paper dopo l'ultimo ingest, lo segnaliamo cosi'
  // possa rilanciare la KB.
  const indexedSources = status?.sources_count || 0;
  const sourcesDelta = isReady ? totalSources - indexedSources : 0;
  const hasSourcesMismatch = isReady && sourcesDelta !== 0;

  const stLabel = STATUS_LABELS[ws] || STATUS_LABELS.none;

  // --- Avanzamento granulare (barra %, fase, cronometro, documenti) ---
  const progress = status?.progress || null;
  const pct = Math.max(0, Math.min(100, Math.round(
    progress?.percent ?? (ws === 'linting' ? 92 : 0),
  )));
  const phaseKey = progress?.phase || (ws === 'linting' ? 'lint' : 'ingest');
  const progressMsg = progress?.message || '';
  const progressFiles = Array.isArray(progress?.files) ? progress.files : [];
  const startedMs = parseUtc(progress?.started_at) || startedAtRef.current || now;
  const elapsedMs = Math.max(0, now - startedMs);
  // Stima del tempo rimanente: lineare sull'avanzamento, mostrata solo quando
  // c'e' abbastanza segnale (>~8% e qualche secondo trascorso) per non sparare numeri assurdi.
  const etaMs = (pct >= 8 && pct < 100 && elapsedMs > 4000)
    ? (elapsedMs / pct) * (100 - pct)
    : null;

  return (
    <div className="space-y-6">
      {/* Intro */}
      <div className="glass rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center flex-shrink-0">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold text-slate-900 mb-1">{t('Knowledge Base')}</h2>
            <p className="text-sm text-slate-600">
              {t("Costruisci la base di conoscenza che l'AI userà per i capitoli, le sezioni e i contenuti della tesi. I paper selezionati verranno scaricati (quando possibile) e i tuoi documenti saranno indicizzati. Una sessione Claude legge tutto, riconcilia entità e concetti, segnala contraddizioni e produce un wiki navigabile.")}
            </p>
          </div>
        </div>

        {/* Conta fonti */}
        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3">
            <BookMarked className="w-5 h-5 text-orange-500" />
            <div>
              <div className="text-xs text-slate-500">{t('Paper selezionati')}</div>
              <div className="text-lg font-bold text-slate-900">{paperCount}</div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3">
            <Paperclip className="w-5 h-5 text-orange-500" />
            <div>
              <div className="text-xs text-slate-500">{t('Documenti caricati')}</div>
              <div className="text-lg font-bold text-slate-900">{attachmentCount}</div>
            </div>
          </div>
        </div>

        {/* Stato attuale */}
        <div className="mt-5 flex items-center gap-3 flex-wrap">
          <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${stLabel.cls}`}>
            {isTransitional && <Loader className="w-3 h-3 animate-spin" />}
            {isReady && <CheckCircle2 className="w-3 h-3" />}
            {isFailed && <AlertTriangle className="w-3 h-3" />}
            {t(stLabel.label)}
          </span>
          {status?.sources_count > 0 && (
            <span className="text-xs text-slate-500">
              <FileText className="inline w-3 h-3 mr-1" />
              {t('{{count}} fonti in raw/', { count: status.sources_count })}
            </span>
          )}
          {status?.pages_count > 0 && (
            <span className="text-xs text-slate-500">
              <ScrollText className="inline w-3 h-3 mr-1" />
              {t('{{count}} pagine in wiki/', { count: status.pages_count })}
            </span>
          )}
          {restrictToSources && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2 py-0.5">
              {t('Solo fonti selezionate (restrict=ON)')}
            </span>
          )}
        </div>
      </div>

      {/* Azioni */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="inline w-4 h-4 mr-1" /> {error}
        </div>
      )}

      {ws === 'none' && (
        <div className="glass rounded-2xl p-6 text-center">
          <p className="text-sm text-slate-600 mb-4">
            {totalSources === 0
              ? t('Non hai caricato fonti. Puoi procedere comunque (la tesi sarà generata sulla conoscenza generale del modello), oppure tornare agli step precedenti per caricare allegati o paper.')
              : t('Pronto a indicizzare {{count}} font{{suffix}}.', { count: totalSources, suffix: totalSources === 1 ? 'e' : 'i' })}
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <button
              onClick={() => handleStart(false)}
              disabled={loadingAction}
              className="btn btn-primary inline-flex items-center gap-2 disabled:opacity-50"
            >
              {loadingAction ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {t('Avvia ingestione')}
            </button>
            {totalSources === 0 && (
              <button onClick={onComplete} className="btn btn-secondary">
                {t('Salta e procedi')}
              </button>
            )}
          </div>
        </div>
      )}

      {isTransitional && (
        <div className="glass rounded-2xl p-6 space-y-5">
          {/* Intestazione: fase corrente + percentuale */}
          <div className="flex items-start gap-4">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center flex-shrink-0">
              <Loader className="w-5 h-5 text-white animate-spin" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-slate-900">
                {ws === 'ingesting' ? t('Indicizzazione in corso…') : t('Lint del wiki in corso…')}
              </h3>
              <p className="text-sm text-slate-500 mt-0.5">
                {t(PHASE_LABELS[phaseKey] || 'Elaborazione…')}
              </p>
            </div>
            <div className="text-2xl font-bold text-orange-600 tabular-nums flex-shrink-0">
              {pct}%
            </div>
          </div>

          {/* Barra di avanzamento */}
          <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-orange-400 to-orange-600 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(3, pct)}%` }}
            />
          </div>

          {/* Tempistiche */}
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              {t('Trascorso: {{time}}', { time: fmtDuration(elapsedMs) })}
            </span>
            {etaMs != null && (
              <span className="tabular-nums">{t('~{{time}} rimanenti', { time: fmtDuration(etaMs) })}</span>
            )}
          </div>

          {/* Cosa sta facendo ora */}
          {progressMsg && (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <p className="text-sm text-slate-700">{progressMsg}</p>
            </div>
          )}

          {/* Documenti in lavorazione nel batch corrente */}
          {progressFiles.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">{t('Documenti in elaborazione')}</p>
              <div className="flex flex-wrap gap-2">
                {progressFiles.slice(0, 8).map((f, i) => (
                  <span
                    key={`${f}-${i}`}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 max-w-[16rem]"
                  >
                    <FileText className="w-3 h-3 text-orange-500 flex-shrink-0" />
                    <span className="truncate">{f}</span>
                  </span>
                ))}
                {progressFiles.length > 8 && (
                  <span className="self-center text-xs text-slate-400">
                    {t('+{{count}} altri', { count: progressFiles.length - 8 })}
                  </span>
                )}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-400">
            {ws === 'ingesting'
              ? t('Sto leggendo le fonti e popolando il wiki (entità, concetti, temi). Per molte fonti possono volerci alcuni minuti.')
              : t('Sto controllando coerenza, link rotti, contraddizioni e gap.')}
          </p>

          {/* Annulla */}
          <div className="pt-1 border-t border-slate-100 text-center">
            <button
              onClick={async () => {
                if (!confirm(t("Sicuro di voler annullare l'ingest in corso? Lo stato verrà marcato come fallito e potrai ripartire da zero."))) return;
                try {
                  await cancelWikiIngest(thesisId);
                  await fetchStatus();
                  stopPolling();
                } catch (e) {
                  setError(e?.response?.data?.detail || t('Errore annullamento'));
                }
              }}
              className="text-xs text-slate-500 hover:text-red-600 underline mt-3"
            >
              {t('Annulla operazione')}
            </button>
          </div>
        </div>
      )}

      {isFailed && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-2 text-red-700">
            <AlertTriangle className="w-5 h-5" />
            <h3 className="font-semibold">{t('Ingest fallito')}</h3>
          </div>
          <p className="text-sm text-slate-600 mb-4">
            {t("Qualcosa è andato storto durante l'ingestione. Puoi riprovare oppure tornare agli step precedenti (Allegati o Paper) per ridurre il numero di fonti.")}
          </p>
          <div className="flex gap-3">
            <button onClick={() => handleStart(true)} className="btn btn-primary inline-flex items-center gap-2">
              <RefreshCw className="w-4 h-4" /> {t('Riprova')}
            </button>
            {onBack && (
              <button onClick={onBack} className="btn btn-secondary">
                {t('Torna agli allegati')}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Avviso "le fonti sono cambiate dall'ultimo ingest" — mostrato sopra
          il blocco "Knowledge base pronta" cosi' l'utente non puo' non vederlo. */}
      {hasSourcesMismatch && (
        <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold text-amber-900">
              {sourcesDelta > 0
                ? t("Hai aggiunto {{count}} {{noun}} dopo l'ultima indicizzazione", { count: sourcesDelta, noun: sourcesDelta === 1 ? t('fonte') : t('fonti') })
                : t("Hai rimosso {{count}} {{noun}} dopo l'ultima indicizzazione", { count: Math.abs(sourcesDelta), noun: Math.abs(sourcesDelta) === 1 ? t('fonte') : t('fonti') })}
            </p>
            <p className="text-sm text-amber-800 mt-0.5">
              {t('La Knowledge Base attuale non rispecchia le {{total}} fonti che hai ora (indicizzate: {{indexed}}). Rilancia per allinearla, oppure procedi pure con i capitoli usando il wiki precedente.', { total: totalSources, indexed: indexedSources })}
            </p>
            <div className="mt-3 flex gap-2 flex-wrap">
              <button
                onClick={() => handleStart(true)}
                disabled={loadingAction}
                className="btn btn-primary inline-flex items-center gap-2 disabled:opacity-50"
              >
                {loadingAction ? <Loader className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                {t('Rilancia indicizzazione')}
              </button>
            </div>
          </div>
        </div>
      )}

      {isReady && (
        <>
          <div className="glass rounded-2xl p-6">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <div className="flex items-center gap-2 mb-1 text-emerald-700">
                  <CheckCircle2 className="w-5 h-5" />
                  <h3 className="font-semibold">{t('Knowledge base pronta')}</h3>
                </div>
                <p className="text-sm text-slate-600">
                  {t('Il wiki contiene {{pages}} pagine derivate da {{sources}} fonti. Procedi alla generazione capitoli o consulta le informazioni estratte qui sotto.', { pages: status?.pages_count || 0, sources: status?.sources_count || 0 })}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStart(true)}
                  disabled={loadingAction}
                  className="btn btn-secondary inline-flex items-center gap-2 disabled:opacity-50"
                  title={t('Ricostruisce il wiki (utile dopo aver aggiunto fonti)')}
                >
                  <RefreshCw className="w-4 h-4" /> {t('Ricostruisci')}
                </button>
                <button onClick={onComplete} className="btn btn-primary inline-flex items-center gap-2">
                  {t('Procedi ai capitoli')} <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Informazioni estratte dai documenti — vista principale per l'utente */}
          {content && (
            <div className="glass rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-5 h-5 text-orange-500" />
                <h3 className="font-semibold text-slate-900">{t('Informazioni estratte dai documenti')}</h3>
              </div>
              <WikiExtractedInfo content={content} />
            </div>
          )}

          {/* Report tecnico di lint — nascosto in un expander per chi vuole i dettagli */}
          {(ws === 'linted' || report) && (
            <details className="glass rounded-2xl p-6 group">
              <summary className="flex items-center gap-2 cursor-pointer list-none font-semibold text-slate-700">
                <Wrench className="w-4 h-4 text-slate-400" />
                {t('Dettagli tecnici (qualità del wiki)')}
                <ChevronDown className="w-4 h-4 text-slate-400 ml-auto transition-transform group-open:rotate-180" />
              </summary>
              <div className="mt-4">
                <WikiLintReport report={report} summary={report?._raw_summary} />
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
};

export default ThesisKnowledgeBaseStep;
