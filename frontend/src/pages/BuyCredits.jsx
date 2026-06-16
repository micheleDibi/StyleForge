import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Coins, Loader, Package, Sparkles, Info, ArrowLeft, Mail,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import { listCreditPackages } from '../services/api';

const formatEur = (cents) => {
  if (typeof cents !== 'number') return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100);
};

// Listino crediti in sola lettura: mostra i pacchetti disponibili. L'acquisto
// avviene tramite l'amministratore (nessun pagamento online integrato).
const BuyCredits = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAdmin, credits } = useAuth();

  const [packages, setPackages] = useState([]);
  const [loadingPackages, setLoadingPackages] = useState(true);
  const [errorPackages, setErrorPackages] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listCreditPackages();
        if (cancelled) return;
        setPackages(res.packages || []);
      } catch (err) {
        if (!cancelled) setErrorPackages(t('Errore caricamento pacchetti.'));
      } finally {
        if (!cancelled) setLoadingPackages(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Admin escluso: crediti illimitati
  useEffect(() => {
    if (isAdmin) {
      const timer = setTimeout(() => navigate('/'), 100);
      return () => clearTimeout(timer);
    }
  }, [isAdmin, navigate]);

  if (isAdmin) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="glass rounded-2xl p-6 flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-emerald-500" />
          <p className="text-slate-700">{t('Gli admin StyleForge hanno crediti illimitati. Reindirizzamento alla dashboard…')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      <button onClick={() => navigate('/')} className="btn btn-secondary gap-2">
        <ArrowLeft className="w-4 h-4" />
        {t('Torna alla Dashboard')}
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">{t('Acquista Crediti')}</h1>
          <p className="text-slate-600 mt-1">
            {t('Consulta i pacchetti disponibili. Per acquistare crediti contatta l\'amministratore.')}
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-orange-50 rounded-xl border border-orange-200">
          <Coins className="w-4 h-4 text-orange-500" />
          <span className="text-sm font-bold text-orange-700">{credits}</span>
          <span className="text-xs text-orange-500">{t('crediti attuali')}</span>
        </div>
      </div>

      {/* Come acquistare */}
      <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-sm">
        <Mail className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <span>
          {t('L\'acquisto dei crediti è gestito dall\'amministratore: contattalo indicando il pacchetto desiderato e i crediti verranno accreditati sul tuo account.')}
        </span>
      </div>

      {/* Pacchetti */}
      <div className="space-y-3">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2">
          <Package className="w-5 h-5 text-orange-500" />
          {t('Pacchetti disponibili')}
        </h2>

        {loadingPackages ? (
          <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
            <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento pacchetti…')}
          </div>
        ) : errorPackages ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errorPackages}</div>
        ) : packages.length === 0 ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {t("Nessun pacchetto al momento disponibile. Contatta l'amministratore.")}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {packages.map((pkg) => {
              const isFeatured = pkg.sort_order === 2 && packages.length >= 3;
              return (
                <div
                  key={pkg.id}
                  className={`relative text-left p-5 rounded-2xl border-2 ${
                    isFeatured ? 'border-orange-300 bg-orange-50' : 'border-slate-200 bg-white'
                  }`}
                >
                  {isFeatured && (
                    <span className="absolute -top-2 right-4 px-2 py-0.5 rounded-full bg-orange-500 text-white text-[10px] font-bold uppercase">
                      {t('Più scelto')}
                    </span>
                  )}
                  <div className="text-sm font-semibold text-slate-500 uppercase tracking-wide">{pkg.name}</div>
                  <div className="mt-2 text-3xl font-bold text-slate-900">
                    {pkg.credits.toLocaleString('it-IT')}
                  </div>
                  <div className="text-xs text-slate-500 mb-3">{t('crediti')}</div>
                  <div className="text-xl font-bold text-orange-600">{formatEur(pkg.price_cents)}</div>
                  {pkg.description && (
                    <p className="mt-2 text-xs text-slate-500">{pkg.description}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer info */}
      <div className="text-center text-xs text-slate-400 flex items-center justify-center gap-1">
        <Info className="w-3 h-3" />
        {t('I prezzi sono indicativi. L\'accredito dei crediti è effettuato dall\'amministratore.')}
      </div>
    </div>
  );
};

export default BuyCredits;
