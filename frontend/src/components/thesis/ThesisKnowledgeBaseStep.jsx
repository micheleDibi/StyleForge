import { useEffect, useRef, useState } from 'react';
import {
  Brain, BookMarked, Paperclip, Loader, AlertTriangle, CheckCircle2, Play,
  RefreshCw, FileText, ScrollText, ArrowRight,
} from 'lucide-react';
import { startWikiIngest, getWikiStatus, getWikiReport, cancelWikiIngest } from '../../services/api';
import WikiLintReport from './WikiLintReport';

const STATUS_LABELS = {
  none:      { label: 'Non avviata', cls: 'bg-slate-100 text-slate-700' },
  ingesting: { label: 'Ingest in corso', cls: 'bg-blue-100 text-blue-700' },
  ingested:  { label: 'Ingest completato', cls: 'bg-emerald-50 text-emerald-700' },
  linting:   { label: 'Lint in corso', cls: 'bg-amber-100 text-amber-800' },
  linted:    { label: 'Pronto', cls: 'bg-emerald-100 text-emerald-800' },
  failed:    { label: 'Errore', cls: 'bg-red-100 text-red-700' },
};

const POLL_MS = 3000;
const MAX_POLL_MS = 30 * 60 * 1000; // 30 min

const ThesisKnowledgeBaseStep = ({
  thesisId,
  paperCount = 0,
  attachmentCount = 0,
  restrictToSources = true,
  onComplete,
  onBack,
}) => {
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [loadingAction, setLoadingAction] = useState(false);
  const [error, setError] = useState(null);
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
        } catch (_) { /* ignore */ }
      }
      return s;
    } catch (e) {
      setError(e?.response?.data?.detail || 'Errore lettura stato wiki');
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

  const handleStart = async (force = false) => {
    setError(null);
    setLoadingAction(true);
    try {
      const s = await startWikiIngest(thesisId, force);
      setStatus(s);
      setReport(null);
      startedAtRef.current = Date.now();
      stopPolling();
      pollingRef.current = setTimeout(pollLoop, POLL_MS);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Errore avvio ingest');
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

  return (
    <div className="space-y-6">
      {/* Intro */}
      <div className="glass rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center flex-shrink-0">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold text-slate-900 mb-1">Knowledge Base</h2>
            <p className="text-sm text-slate-600">
              Costruisci la base di conoscenza che l'AI userà per i capitoli, le sezioni e
              i contenuti della tesi. I paper selezionati verranno scaricati (quando
              possibile) e i tuoi documenti saranno indicizzati. Una sessione Claude legge
              tutto, riconcilia entità e concetti, segnala contraddizioni e produce un wiki
              navigabile.
            </p>
          </div>
        </div>

        {/* Conta fonti */}
        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3">
            <BookMarked className="w-5 h-5 text-orange-500" />
            <div>
              <div className="text-xs text-slate-500">Paper selezionati</div>
              <div className="text-lg font-bold text-slate-900">{paperCount}</div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3">
            <Paperclip className="w-5 h-5 text-orange-500" />
            <div>
              <div className="text-xs text-slate-500">Documenti caricati</div>
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
            {stLabel.label}
          </span>
          {status?.sources_count > 0 && (
            <span className="text-xs text-slate-500">
              <FileText className="inline w-3 h-3 mr-1" />
              {status.sources_count} fonti in raw/
            </span>
          )}
          {status?.pages_count > 0 && (
            <span className="text-xs text-slate-500">
              <ScrollText className="inline w-3 h-3 mr-1" />
              {status.pages_count} pagine in wiki/
            </span>
          )}
          {restrictToSources && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2 py-0.5">
              Solo fonti selezionate (restrict=ON)
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
              ? 'Non hai caricato fonti. Puoi procedere comunque (la tesi sarà generata sulla conoscenza generale del modello), oppure tornare agli step precedenti per caricare allegati o paper.'
              : `Pronto a indicizzare ${totalSources} font${totalSources === 1 ? 'e' : 'i'}.`}
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <button
              onClick={() => handleStart(false)}
              disabled={loadingAction}
              className="btn btn-primary inline-flex items-center gap-2 disabled:opacity-50"
            >
              {loadingAction ? <Loader className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Avvia ingestione
            </button>
            {totalSources === 0 && (
              <button onClick={onComplete} className="btn btn-secondary">
                Salta e procedi
              </button>
            )}
          </div>
        </div>
      )}

      {isTransitional && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center space-y-3">
          <Loader className="w-10 h-10 text-orange-500 animate-spin" />
          <h3 className="font-semibold text-slate-900">
            {ws === 'ingesting' ? 'Indicizzazione in corso…' : 'Lint del wiki in corso…'}
          </h3>
          <p className="text-sm text-slate-500 max-w-md">
            {ws === 'ingesting'
              ? 'Sto leggendo le fonti e popolando il wiki (entità, concetti, temi). Per molte fonti possono volerci alcuni minuti.'
              : 'Sto controllando coerenza, link rotti, contraddizioni e gap.'}
          </p>
          <button
            onClick={async () => {
              if (!confirm('Sicuro di voler annullare l\'ingest in corso? Lo stato verrà marcato come fallito e potrai ripartire da zero.')) return;
              try {
                await cancelWikiIngest(thesisId);
                await fetchStatus();
                stopPolling();
              } catch (e) {
                setError(e?.response?.data?.detail || 'Errore annullamento');
              }
            }}
            className="text-xs text-slate-500 hover:text-red-600 underline mt-2"
          >
            Annulla operazione
          </button>
        </div>
      )}

      {isFailed && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-2 text-red-700">
            <AlertTriangle className="w-5 h-5" />
            <h3 className="font-semibold">Ingest fallito</h3>
          </div>
          <p className="text-sm text-slate-600 mb-4">
            Qualcosa è andato storto durante l'ingestione. Puoi riprovare oppure tornare
            agli step precedenti (Allegati o Paper) per ridurre il numero di fonti.
          </p>
          <div className="flex gap-3">
            <button onClick={() => handleStart(true)} className="btn btn-primary inline-flex items-center gap-2">
              <RefreshCw className="w-4 h-4" /> Riprova
            </button>
            {onBack && (
              <button onClick={onBack} className="btn btn-secondary">
                Torna agli allegati
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
                ? `Hai aggiunto ${sourcesDelta} ${sourcesDelta === 1 ? 'fonte' : 'fonti'} dopo l'ultima indicizzazione`
                : `Hai rimosso ${Math.abs(sourcesDelta)} ${Math.abs(sourcesDelta) === 1 ? 'fonte' : 'fonti'} dopo l'ultima indicizzazione`}
            </p>
            <p className="text-sm text-amber-800 mt-0.5">
              La Knowledge Base attuale non rispecchia le {totalSources} fonti che hai ora
              (indicizzate: {indexedSources}). Rilancia per allinearla, oppure procedi pure
              con i capitoli usando il wiki precedente.
            </p>
            <div className="mt-3 flex gap-2 flex-wrap">
              <button
                onClick={() => handleStart(true)}
                disabled={loadingAction}
                className="btn btn-primary inline-flex items-center gap-2 disabled:opacity-50"
              >
                {loadingAction ? <Loader className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                Rilancia indicizzazione
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
                  <h3 className="font-semibold">Knowledge base pronta</h3>
                </div>
                <p className="text-sm text-slate-600">
                  Il wiki contiene {status?.pages_count || 0} pagine derivate da {status?.sources_count || 0} fonti.
                  Procedi alla generazione capitoli o consulta il report sotto.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleStart(true)}
                  disabled={loadingAction}
                  className="btn btn-secondary inline-flex items-center gap-2 disabled:opacity-50"
                  title="Ricostruisce il wiki (utile dopo aver aggiunto fonti)"
                >
                  <RefreshCw className="w-4 h-4" /> Ricostruisci
                </button>
                <button onClick={onComplete} className="btn btn-primary inline-flex items-center gap-2">
                  Procedi ai capitoli <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {(ws === 'linted' || report) && (
            <div className="glass rounded-2xl p-6">
              <h3 className="font-semibold text-slate-900 mb-3">Report di lint</h3>
              <WikiLintReport
                report={report}
                summary={report?._raw_summary}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ThesisKnowledgeBaseStep;
