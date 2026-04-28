import { useEffect, useState, useMemo } from 'react';
import {
  BookMarked,
  Sparkles,
  Plus,
  Trash2,
  Info,
  Loader,
  Coins,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  searchResearchForThesis,
  summarizePaperForThesis,
  addPaperAttachments,
  deleteThesisAttachment,
  estimateCredits,
} from '../../services/api';
import PaperSearchPanel from '../research/PaperSearchPanel';

const PAPER_MIME_TYPE = 'application/x-research-paper';

const ThesisPapersForm = ({ data, onChange, thesisId, onCreditsChanged }) => {
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedPapers, setSelectedPapers] = useState(() => new Map());
  const [cachedSummaries, setCachedSummaries] = useState(() => new Map());
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [removingId, setRemovingId] = useState(null);
  const [summaryCost, setSummaryCost] = useState(3);

  // Recupera il costo effettivo di un riassunto AI per la stima
  useEffect(() => {
    let cancelled = false;
    estimateCredits('research_summary', {}).then((res) => {
      if (!cancelled && res?.credits_needed != null) setSummaryCost(res.credits_needed);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const paperAttachments = useMemo(
    () => (data.attachments || []).filter((a) => a.mime_type === PAPER_MIME_TYPE),
    [data.attachments]
  );

  const handleTogglePaper = (paper) => {
    setSelectedPapers((prev) => {
      const next = new Map(prev);
      if (next.has(paper.id)) next.delete(paper.id);
      else next.set(paper.id, paper);
      return next;
    });
  };

  const handleSummaryGenerated = (paperId, summary) => {
    setCachedSummaries((prev) => {
      const next = new Map(prev);
      next.set(paperId, summary);
      return next;
    });
    if (onCreditsChanged) onCreditsChanged();
  };

  const selectedList = Array.from(selectedPapers.values());
  const unsummarizedCount = selectedList.reduce(
    (n, p) => n + (cachedSummaries.has(p.id) ? 0 : 1),
    0
  );
  const estimatedExtraCost = unsummarizedCount * summaryCost;

  const handleAddSelected = async () => {
    if (selectedList.length === 0 || adding) return;
    setAdding(true);
    setError(null);
    setInfo(null);

    const items = selectedList.map((p) => ({
      paper: p,
      summary: cachedSummaries.get(p.id) || null,
    }));

    try {
      const result = await addPaperAttachments(thesisId, items);
      onChange({
        ...data,
        attachments: [...(data.attachments || []), ...(result.attachments || [])],
      });
      setSelectedPapers(new Map());
      const summarized = result.summarized_count || 0;
      const credits = result.credits_consumed || 0;
      setInfo(
        summarized > 0
          ? `Aggiunti ${result.total} paper. Generati ${summarized} riassunti AI (${credits} crediti).`
          : `Aggiunti ${result.total} paper alla tesi.`
      );
      if (onCreditsChanged) onCreditsChanged();
    } catch (err) {
      if (err.isInsufficientCredits) {
        setError(err.creditErrorMessage || 'Crediti insufficienti per generare i riassunti AI.');
      } else {
        setError(err.response?.data?.detail || 'Errore durante l\'aggiunta dei paper.');
      }
    } finally {
      setAdding(false);
    }
  };

  const handleRemovePaper = async (attachmentId) => {
    setRemovingId(attachmentId);
    try {
      await deleteThesisAttachment(thesisId, attachmentId);
      onChange({
        ...data,
        attachments: (data.attachments || []).filter((a) => a.id !== attachmentId),
      });
    } catch {
      setError('Errore durante la rimozione del paper.');
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Paper Scientifici</h2>
        <p className="text-slate-600">
          Cerca paper accademici da OpenAlex, Semantic Scholar e Crossref e selezionane alcuni come fonti per la tesi.
          Per ogni paper aggiunto verrà generato un riassunto AI usato dal modello durante la generazione.
          Questo step è opzionale: puoi anche saltarlo e procedere direttamente agli allegati.
        </p>
      </div>

      {paperAttachments.length > 0 && (
        <div className="card space-y-3">
          <h3 className="font-medium text-slate-900 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-500" />
            Paper già aggiunti alla tesi ({paperAttachments.length})
          </h3>
          <ul className="space-y-2">
            {paperAttachments.map((att) => (
              <li
                key={att.id}
                className="flex items-start justify-between gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-orange-100 text-orange-700 flex items-center justify-center flex-shrink-0">
                    <BookMarked className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{att.original_filename}</p>
                    <p className="text-xs text-slate-500">Paper accademico · contesto attivo per la generazione</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemovePaper(att.id)}
                  disabled={removingId === att.id}
                  className="p-2 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                  title="Rimuovi paper dalla tesi"
                >
                  {removingId === att.id ? (
                    <Loader className="w-4 h-4 text-slate-400 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4 text-red-500" />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!searchOpen ? (
        <div className="card text-center py-10 space-y-3">
          <div className="w-12 h-12 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center mx-auto">
            <BookMarked className="w-6 h-6" />
          </div>
          <p className="text-sm text-slate-700">
            {paperAttachments.length === 0
              ? 'Vuoi cercare paper scientifici da includere come fonti?'
              : 'Aggiungi altri paper o procedi al prossimo step.'}
          </p>
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Cerca paper
          </button>
          <p className="text-xs text-slate-500">
            Step opzionale — puoi saltarlo e procedere direttamente agli allegati.
          </p>
        </div>
      ) : (
        <>
          <PaperSearchPanel
            mode="pick"
            searchFn={(params) => searchResearchForThesis(thesisId, params)}
            summarizeFn={(paper) => summarizePaperForThesis(thesisId, paper)}
            onCreditsChanged={onCreditsChanged}
            selectedIds={new Set(selectedPapers.keys())}
            onTogglePaper={handleTogglePaper}
            summaryByPaperId={Object.fromEntries(cachedSummaries)}
            onSummaryGenerated={handleSummaryGenerated}
          />

          {selectedList.length > 0 && (
            <div className="card space-y-3 sticky bottom-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm">
                  <Sparkles className="w-4 h-4 text-orange-500" />
                  <span className="font-medium text-slate-900">{selectedList.length}</span>
                  <span className="text-slate-600">
                    {selectedList.length === 1 ? 'paper selezionato' : 'paper selezionati'}
                  </span>
                </div>
                {unsummarizedCount > 0 && (
                  <div className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-lg">
                    <Coins className="w-3.5 h-3.5" />
                    ≈ {estimatedExtraCost} crediti per {unsummarizedCount} {unsummarizedCount === 1 ? 'riassunto AI' : 'riassunti AI'} mancanti
                  </div>
                )}
              </div>

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <button
                type="button"
                onClick={handleAddSelected}
                disabled={adding}
                className="btn-primary w-full inline-flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {adding ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Aggiunta paper in corso (genero i riassunti)...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Aggiungi {selectedList.length} paper alla tesi
                  </>
                )}
              </button>
              <p className="text-xs text-slate-500 text-center">
                Per i paper di cui hai già generato il riassunto manualmente, i crediti del riassunto AI non vengono riaddebitati.
              </p>
            </div>
          )}
        </>
      )}

      {info && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{info}</span>
        </div>
      )}

      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800 space-y-1">
            <p className="font-medium">Come vengono usati i paper?</p>
            <ul className="list-disc list-inside space-y-1">
              <li>I metadati (titolo, autori, anno, venue, citazioni) e l'abstract entrano nel contesto della generazione tesi.</li>
              <li>Per ogni paper viene aggiunto anche un riassunto tecnico AI con keywords e limiti dello studio.</li>
              <li>I paper aggiunti compaiono nello step "Allegati" insieme a documenti e link.</li>
              <li>Puoi rimuoverli in qualsiasi momento prima di confermare i capitoli.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThesisPapersForm;
