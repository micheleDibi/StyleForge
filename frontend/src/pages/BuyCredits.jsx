import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Coins, Loader, Package, Sparkles, Info, ArrowLeft, Send, Clock, CheckCircle2, XCircle, Ban,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import {
  listCreditPackages, createCreditRequest, getMyCreditRequests, cancelCreditRequest,
} from '../services/api';

const formatEur = (cents) => {
  if (typeof cents !== 'number') return '—';
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100);
};

const STATUS = {
  pending: { label: 'In attesa', cls: 'bg-amber-100 text-amber-800', icon: Clock },
  approved: { label: 'Approvata', cls: 'bg-emerald-100 text-emerald-800', icon: CheckCircle2 },
  rejected: { label: 'Rifiutata', cls: 'bg-red-100 text-red-800', icon: XCircle },
  canceled: { label: 'Annullata', cls: 'bg-slate-100 text-slate-600', icon: Ban },
};

// "Acquista crediti" = richiesta di un pacchetto al proprio referente (o all'admin
// per i distributori). Mostra i pacchetti del proprio profilo + le proprie richieste.
const BuyCredits = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAdmin, credits } = useAuth();

  const [packages, setPackages] = useState([]);
  const [loadingPackages, setLoadingPackages] = useState(true);
  const [errorPackages, setErrorPackages] = useState(null);

  const [requests, setRequests] = useState([]);
  const [submitting, setSubmitting] = useState(null); // package id in volo
  const [toast, setToast] = useState('');
  const [toastErr, setToastErr] = useState('');

  const loadRequests = async () => {
    try {
      const res = await getMyCreditRequests();
      setRequests(res.requests || []);
    } catch { /* ignora */ }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listCreditPackages();
        if (!cancelled) setPackages(res.packages || []);
      } catch {
        if (!cancelled) setErrorPackages(t('Errore caricamento pacchetti.'));
      } finally {
        if (!cancelled) setLoadingPackages(false);
      }
    })();
    loadRequests();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (isAdmin) {
      const timer = setTimeout(() => navigate('/'), 100);
      return () => clearTimeout(timer);
    }
  }, [isAdmin, navigate]);

  const hasPending = requests.some((r) => r.status === 'pending');

  const flash = (msg, isErr = false) => {
    if (isErr) { setToastErr(msg); setTimeout(() => setToastErr(''), 4000); }
    else { setToast(msg); setTimeout(() => setToast(''), 4000); }
  };

  const request = async (pkg) => {
    setSubmitting(pkg.id);
    try {
      await createCreditRequest(pkg.id);
      await loadRequests();
      flash(t('Richiesta inviata al tuo referente.'));
    } catch (e) {
      flash(e?.response?.data?.detail || t('Errore nell\'invio della richiesta'), true);
    } finally {
      setSubmitting(null);
    }
  };

  const cancel = async (id) => {
    try {
      await cancelCreditRequest(id);
      await loadRequests();
      flash(t('Richiesta annullata.'));
    } catch (e) {
      flash(e?.response?.data?.detail || t('Errore'), true);
    }
  };

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
          <h1 className="text-3xl font-bold text-slate-900">{t('Richiedi Crediti')}</h1>
          <p className="text-slate-600 mt-1">
            {t('Scegli un pacchetto e invia la richiesta al tuo referente, che potrà approvarla.')}
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-orange-50 rounded-xl border border-orange-200">
          <Coins className="w-4 h-4 text-orange-500" />
          <span className="text-sm font-bold text-orange-700">{credits}</span>
          <span className="text-xs text-orange-500">{t('crediti attuali')}</span>
        </div>
      </div>

      {toast && (
        <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> {toast}
        </div>
      )}
      {toastErr && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
          <XCircle className="w-4 h-4 flex-shrink-0" /> {toastErr}
        </div>
      )}

      {/* Pacchetti */}
      <div className="space-y-3">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2">
          <Package className="w-5 h-5 text-orange-500" />
          {t('Pacchetti disponibili')}
        </h2>
        {hasPending && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">
            {t('Hai una richiesta in attesa: gestiscila o annullala prima di inviarne un\'altra.')}
          </div>
        )}

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
                  className={`relative text-left p-5 rounded-2xl border-2 flex flex-col ${
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
                  <button
                    onClick={() => request(pkg)}
                    disabled={hasPending || submitting === pkg.id}
                    className="btn btn-primary w-full mt-4 gap-2 disabled:opacity-50"
                  >
                    {submitting === pkg.id ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    {t('Richiedi crediti')}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Le mie richieste */}
      {requests.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold text-slate-900">{t('Le mie richieste')}</h2>
          <div className="space-y-2">
            {requests.map((r) => {
              const st = STATUS[r.status] || STATUS.pending;
              const StIcon = st.icon;
              return (
                <div key={r.id} className="glass rounded-xl p-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-800 truncate">
                      {r.package_name} · <span className="text-orange-600 font-bold">{r.package_credits?.toLocaleString('it-IT')}</span> {t('crediti')}
                    </p>
                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                      <Clock className="w-3 h-3" />
                      {r.created_at ? new Date(r.created_at).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                    </p>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md font-medium ${st.cls}`}>
                    <StIcon className="w-3 h-3" /> {t(st.label)}
                  </span>
                  {r.status === 'pending' && (
                    <button onClick={() => cancel(r.id)} className="btn btn-ghost text-xs text-slate-500 hover:bg-slate-100">
                      {t('Annulla')}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer info */}
      <div className="text-center text-xs text-slate-400 flex items-center justify-center gap-1">
        <Info className="w-3 h-3" />
        {t('I crediti vengono accreditati dal referente al momento dell\'approvazione.')}
      </div>
    </div>
  );
};

export default BuyCredits;
