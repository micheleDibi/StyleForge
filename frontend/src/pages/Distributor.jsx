import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Loader, Coins, Store,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getMyResellers } from '../services/api';

// Dashboard distributore (sola lettura): elenco dei propri rivenditori con i
// crediti attuali. Gli aggregati di spesa/storico acquisti non sono più
// disponibili dopo la rimozione dei pagamenti online.
const Distributor = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [resellers, setResellers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMyResellers()
      .then((res) => {
        if (cancelled) return;
        setResellers(res.resellers || []);
      })
      .catch(() => { if (!cancelled) setError(t('Errore nel caricamento dei rivenditori')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto">
        <button onClick={() => navigate('/')} className="btn btn-secondary gap-2 mb-6">
          <ArrowLeft className="w-4 h-4" />
          {t('Torna alla Dashboard')}
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Users className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900">{t('Dashboard Distributore')}</h1>
            <p className="text-slate-600">{t('I tuoi rivenditori e i loro crediti attuali')}</p>
          </div>
        </div>

        {loading ? (
          <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
            <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : resellers.length === 0 ? (
          <div className="glass rounded-2xl p-12 text-center text-slate-500">
            <Store className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>{t('Nessun rivenditore assegnato.')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {resellers.map((r) => (
              <div key={r.id} className="glass rounded-2xl flex items-center gap-4 p-4">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <Store className="w-5 h-5 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">{r.full_name || r.username}</p>
                  <p className="text-xs text-slate-500 truncate">{r.email}</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-orange-50 rounded-xl border border-orange-200">
                  <Coins className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-bold text-orange-700">{r.credits?.toLocaleString('it-IT')}</span>
                  <span className="text-xs text-orange-500">{t('crediti')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Distributor;
