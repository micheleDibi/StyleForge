import { useNavigate } from 'react-router-dom';
import { ArrowLeft, BookMarked } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import PaperSearchPanel from '../components/research/PaperSearchPanel';

const ResearchSearch = () => {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

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

        <PaperSearchPanel onCreditsChanged={refreshUser} />
      </div>
    </div>
  );
};

export default ResearchSearch;
