import { useState } from 'react';
import { BookOpen, ExternalLink, Quote, Users, Calendar, Sparkles, ChevronDown, ChevronUp, Loader, Database } from 'lucide-react';
import { summarizePaper as apiSummarizePaper } from '../../services/api';
import PaperSummary from './PaperSummary';

const SOURCE_LABELS = {
  openalex: 'OpenAlex',
  semantic_scholar: 'Semantic Scholar',
  crossref: 'Crossref',
};

const SOURCE_COLORS = {
  openalex: 'bg-blue-50 text-blue-700 border-blue-200',
  semantic_scholar: 'bg-purple-50 text-purple-700 border-purple-200',
  crossref: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

const PaperCard = ({ paper, onCreditsChanged }) => {
  const [abstractOpen, setAbstractOpen] = useState(false);
  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const handleSummarize = async () => {
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const data = await apiSummarizePaper(paper);
      setSummary(data);
      if (onCreditsChanged) onCreditsChanged();
    } catch (e) {
      if (e.isInsufficientCredits) {
        setSummaryError(e.creditErrorMessage || 'Crediti insufficienti.');
      } else {
        setSummaryError('Errore nella generazione del riassunto.');
      }
    } finally {
      setLoadingSummary(false);
    }
  };

  const titleHref = paper.full_text_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
  const authorsDisplay = paper.authors?.length > 5
    ? `${paper.authors.slice(0, 5).join(', ')} et al.`
    : (paper.authors || []).join(', ');

  const scorePct = paper.composite_score != null
    ? Math.round(Math.max(0, Math.min(1, paper.composite_score)) * 100)
    : null;

  return (
    <article className="card space-y-3">
      <header className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-base md:text-lg font-semibold text-slate-900 leading-snug">
            {titleHref ? (
              <a
                href={titleHref}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-orange-600 inline-flex items-baseline gap-1 group"
              >
                <span>{paper.title}</span>
                <ExternalLink className="w-3.5 h-3.5 translate-y-0.5 opacity-0 group-hover:opacity-70 transition-opacity flex-shrink-0" />
              </a>
            ) : paper.title}
          </h3>

          {authorsDisplay && (
            <p className="mt-1 text-sm text-slate-600 flex items-start gap-1.5">
              <Users className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-slate-400" />
              <span>{authorsDisplay}</span>
            </p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600">
            {paper.year && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" />{paper.year}
              </span>
            )}
            {paper.venue && (
              <span className="inline-flex items-center gap-1 truncate max-w-xs">
                <BookOpen className="w-3 h-3 text-slate-400" />{paper.venue}
              </span>
            )}
            {paper.citation_count != null && (
              <span className="inline-flex items-center gap-1">
                <Quote className="w-3 h-3 text-slate-400" />{paper.citation_count.toLocaleString()} citazioni
              </span>
            )}
            {paper.doi && (
              <span className="inline-flex items-center gap-1 font-mono text-slate-500">
                DOI: {paper.doi}
              </span>
            )}
          </div>
        </div>

        {scorePct != null && (
          <div className="flex flex-col items-end gap-1 flex-shrink-0">
            <div className="text-xs text-slate-500">Rilevanza</div>
            <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-orange-400 to-orange-600"
                style={{ width: `${scorePct}%` }}
              />
            </div>
            <div className="text-xs font-semibold text-slate-700">{scorePct}</div>
          </div>
        )}
      </header>

      <div className="flex flex-wrap gap-2">
        {paper.open_access && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
            Open Access
          </span>
        )}
        {(paper.sources || []).map((s) => (
          <span
            key={s}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${SOURCE_COLORS[s] || 'bg-slate-50 text-slate-700 border-slate-200'}`}
          >
            <Database className="w-3 h-3" />
            {SOURCE_LABELS[s] || s}
          </span>
        ))}
      </div>

      {paper.abstract && (
        <div>
          <button
            type="button"
            onClick={() => setAbstractOpen(!abstractOpen)}
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-900"
          >
            {abstractOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            Abstract
          </button>
          {abstractOpen && (
            <p className="mt-2 text-sm text-slate-700 leading-relaxed whitespace-pre-line">
              {paper.abstract}
            </p>
          )}
        </div>
      )}

      <div className="pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleSummarize}
          disabled={loadingSummary}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
        >
          {loadingSummary ? (
            <>
              <Loader className="w-4 h-4 animate-spin" />
              Riassunto in corso...
            </>
          ) : summary ? (
            <>
              <Sparkles className="w-4 h-4" />
              Rigenera riassunto
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Genera riassunto AI
            </>
          )}
        </button>

        {titleHref && (
          <a
            href={titleHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-orange-600"
          >
            <ExternalLink className="w-4 h-4" />
            Apri paper
          </a>
        )}
      </div>

      {summaryError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {summaryError}
        </div>
      )}

      {summary && <PaperSummary summary={summary} />}
    </article>
  );
};

export default PaperCard;
