import { useState } from 'react';
import { Sparkles, Loader, AlertTriangle, Lightbulb } from 'lucide-react';
import { suggestPaperKeywords } from '../../services/api';

const PAPER_MIME_TYPE = 'application/x-research-paper';

/**
 * PaperKeywordSuggestions
 *
 * Mostra un bottone che, su click, invoca POST /api/thesis/{id}/suggest-paper-keywords
 * e ottiene una lista di 5-8 termini di ricerca dedotti dai documenti caricati
 * dall'utente nello step "Allegati". I termini sono renderizzati come chip
 * cliccabili: click -> chiama `onSelect(keyword)` (il genitore popola la search bar).
 *
 * Il componente si auto-nasconde se non ci sono allegati testuali non-paper.
 *
 * Props:
 *   thesisId:    ID della tesi corrente
 *   attachments: lista completa degli allegati (dal `data.attachments` del parent)
 *   onSelect:    callback (keyword: string) => void
 *   isThesisPaid: se true la tesi ha gia' pagato il flat: nascondiamo il costo crediti
 */
const PaperKeywordSuggestions = ({ thesisId, attachments, onSelect, isThesisPaid = false }) => {
  const [keywords, setKeywords] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [creditsUsed, setCreditsUsed] = useState(0);

  const eligible = (attachments || []).filter(
    (a) => a.mime_type !== PAPER_MIME_TYPE
  );

  if (!thesisId || eligible.length === 0) return null;

  const handleSuggest = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await suggestPaperKeywords(thesisId);
      setKeywords(res.keywords || []);
      setCreditsUsed(res.credits_consumed || 0);
    } catch (err) {
      if (err.isInsufficientCredits) {
        setError(err.creditErrorMessage || 'Crediti insufficienti per il suggerimento.');
      } else {
        setError(err.response?.data?.detail || 'Errore nel suggerimento delle keyword.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50 p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-white border border-orange-200 text-orange-600 flex items-center justify-center flex-shrink-0">
          <Lightbulb className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900">
            Suggerimenti dalla tua documentazione
          </p>
          <p className="text-xs text-slate-600 mt-0.5">
            Lascia che l'AI analizzi i {eligible.length} documenti che hai caricato e proponga
            termini di ricerca utili per trovare paper accademici correlati.
          </p>
        </div>
        {!keywords && (
          <button
            type="button"
            onClick={handleSuggest}
            disabled={loading}
            className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gradient-to-r from-orange-500 to-red-500 text-white text-sm font-semibold shadow-md hover:shadow-lg hover:from-orange-600 hover:to-red-600 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <>
                <Loader className="w-4 h-4 animate-spin" />
                <span>Analisi...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Suggerisci</span>
              </>
            )}
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {keywords && keywords.length === 0 && !loading && !error && (
        <div className="text-xs text-slate-600">
          Nessun termine specifico estraibile dai documenti. Prova a inserire una keyword a mano.
        </div>
      )}

      {keywords && keywords.length > 0 && (
        <div>
          <p className="text-xs text-slate-600 mb-2">
            Clicca un termine per usarlo come ricerca:
            {!isThesisPaid && creditsUsed > 0 && (
              <span className="ml-1 text-slate-500">({creditsUsed} crediti utilizzati)</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {keywords.map((kw, idx) => (
              <button
                key={`${idx}-${kw}`}
                type="button"
                onClick={() => onSelect && onSelect(kw)}
                className="px-3 py-1.5 rounded-full bg-white border border-orange-200 text-sm text-slate-800 hover:bg-orange-100 hover:border-orange-400 hover:text-orange-800 transition-colors shadow-sm"
              >
                {kw}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={handleSuggest}
            disabled={loading}
            className="mt-3 text-xs text-orange-700 hover:text-orange-800 hover:underline disabled:opacity-50"
          >
            {loading ? 'Rigenero...' : 'Rigenera suggerimenti'}
          </button>
        </div>
      )}
    </div>
  );
};

export default PaperKeywordSuggestions;
