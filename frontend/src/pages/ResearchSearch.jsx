import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Search,
  BookMarked,
  Loader,
  AlertTriangle,
  Inbox,
  SlidersHorizontal,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { searchResearch } from '../services/api';
import FilterPanel from '../components/research/FilterPanel';
import PaperCard from '../components/research/PaperCard';
import CreditEstimatePreview from '../components/CreditEstimatePreview';

const AVAILABLE_SOURCES = [
  { key: 'openalex', label: 'OpenAlex', description: 'Catalogo ampio della ricerca' },
  { key: 'semantic_scholar', label: 'Semantic Scholar', description: 'Paper + citazioni + raccomandazioni' },
  { key: 'crossref', label: 'Crossref', description: 'Metadati bibliografici e DOI' },
];

const SORT_OPTIONS = [
  { value: 'composite', label: 'Rilevanza (punteggio composito)' },
  { value: 'citations', label: 'Numero di citazioni' },
  { value: 'recency', label: 'Più recenti' },
  { value: 'title', label: 'Titolo (A-Z)' },
];

const DEFAULT_FILTERS = {
  year_min: null,
  year_max: null,
  open_access_only: false,
  min_citations: null,
  venue_contains: null,
  author_contains: null,
};

const ResearchSearch = () => {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  const [topic, setTopic] = useState('');
  const [sources, setSources] = useState(AVAILABLE_SOURCES.map((s) => s.key));
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sortBy, setSortBy] = useState('composite');

  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const toggleSource = (key) => {
    setSources((prev) =>
      prev.includes(key) ? prev.filter((s) => s !== key) : [...prev, key]
    );
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    const clean = topic.trim();
    if (!clean || sources.length === 0 || loading) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = await searchResearch({
        topic: clean,
        sources,
        filters,
        sortBy,
      });
      setResults(data);
      if (refreshUser) refreshUser();
    } catch (err) {
      if (err.isInsufficientCredits) {
        setError(err.creditErrorMessage || 'Crediti insufficienti.');
      } else if (err.response?.status === 400) {
        setError(err.response?.data?.detail || 'Parametri non validi.');
      } else {
        setError('Errore nella ricerca. Riprova tra qualche istante.');
      }
    } finally {
      setLoading(false);
    }
  };

  const canSearch = topic.trim().length >= 2 && sources.length > 0 && !loading;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-orange-50">
      <div className="max-w-5xl mx-auto px-4 md:px-6 py-6">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Torna alla dashboard
        </button>

        <header className="mb-6">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white">
              <BookMarked className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-slate-900">Ricerca Accademica</h1>
              <p className="text-sm text-slate-600">
                Aggrega risultati da OpenAlex, Semantic Scholar e Crossref. Riassunti AI on-demand.
              </p>
            </div>
          </div>
        </header>

        <form onSubmit={handleSearch} className="card space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Argomento <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="es. machine learning in agricoltura"
                  className="input w-full pl-9"
                  disabled={loading}
                  minLength={2}
                  maxLength={500}
                  required
                />
              </div>
              <button
                type="submit"
                disabled={!canSearch}
                className="btn-primary inline-flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Cerco...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Cerca
                  </>
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Fonti</label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              {AVAILABLE_SOURCES.map((s) => {
                const active = sources.includes(s.key);
                return (
                  <button
                    type="button"
                    key={s.key}
                    onClick={() => toggleSource(s.key)}
                    disabled={loading}
                    className={`text-left px-3 py-2 rounded-xl border-2 transition-colors ${
                      active
                        ? 'border-orange-500 bg-orange-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-800">{s.label}</span>
                      <input
                        type="checkbox"
                        checked={active}
                        readOnly
                        className="w-4 h-4 pointer-events-none text-orange-500"
                      />
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{s.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <FilterPanel filters={filters} onChange={setFilters} disabled={loading} />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" />
              Ordina per
            </label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="input w-full md:w-80"
              disabled={loading}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <CreditEstimatePreview
            operations={[
              { type: 'research_search', params: { num_sources: sources.length }, label: 'Ricerca' },
            ]}
          />
        </form>

        <div className="mt-6">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {loading && (
            <div className="card text-center py-10 text-slate-600">
              <Loader className="w-6 h-6 animate-spin mx-auto mb-2 text-orange-500" />
              <p className="text-sm">Interrogazione di {sources.length} {sources.length === 1 ? 'fonte' : 'fonti'} in parallelo...</p>
            </div>
          )}

          {!loading && results && (
            <>
              <ResultsHeader results={results} />
              {results.papers.length === 0 ? (
                <div className="card text-center py-10">
                  <Inbox className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                  <p className="text-sm text-slate-600">
                    Nessun risultato con i filtri correnti. Prova ad ampliare la ricerca.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {results.papers.map((p) => (
                    <PaperCard
                      key={p.id}
                      paper={p}
                      onCreditsChanged={refreshUser}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const ResultsHeader = ({ results }) => (
  <div className="mb-4 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600 flex flex-wrap items-center gap-x-4 gap-y-1">
    <span>
      <strong className="text-slate-900">{results.papers.length}</strong> risultati mostrati
    </span>
    <span className="text-slate-400">·</span>
    <span>
      <strong className="text-slate-900">{results.total_unique}</strong> paper unici (da {results.total_raw} risposte)
    </span>
    {results.used_sources?.length > 0 && (
      <>
        <span className="text-slate-400">·</span>
        <span>Fonti: {results.used_sources.join(', ')}</span>
      </>
    )}
    {results.failed_sources?.length > 0 && (
      <span className="flex items-center gap-1 text-amber-700">
        <AlertTriangle className="w-3.5 h-3.5" />
        Fonti non disponibili: {results.failed_sources.map((f) => f.source).join(', ')}
      </span>
    )}
  </div>
);

export default ResearchSearch;
