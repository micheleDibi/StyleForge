import { useEffect, useState, useCallback } from 'react';
import { Loader, Inbox, Check, X, Coins, AlertTriangle, Clock, History } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ENTITY_LABELS = {
  distributore: 'Distributore',
  rivenditore: 'Rivenditore',
  privato: 'Privato',
};

const STATUS_BADGES = {
  pending: { label: 'In attesa', cls: 'bg-amber-100 text-amber-800' },
  approved: { label: 'Approvata', cls: 'bg-emerald-100 text-emerald-800' },
  rejected: { label: 'Rifiutata', cls: 'bg-red-100 text-red-800' },
  canceled: { label: 'Annullata', cls: 'bg-slate-100 text-slate-600' },
  expired: { label: 'Scaduta', cls: 'bg-slate-100 text-slate-600' },
};

const formatDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
  : '—');

// Inbox condivisa delle richieste crediti, con vista "In attesa" e "Storico".
// Props:
//  - fetchFn: () => { requests }   (richieste pending da gestire)
//  - approveFn(id, note), rejectFn(id, note)
//  - availableCredits: saldo dell'approvatore (-1 = infinito/admin)
//  - onResolved: callback dopo approva/rifiuta (aggiorna saldi/elenchi del padre)
//  - historyFn: () => { requests }  (opzionale: storico approvate/rifiutate/annullate)
const RequestsInbox = ({ fetchFn, approveFn, rejectFn, availableCredits = -1, onResolved, historyFn }) => {
  const { t } = useTranslation();
  const [view, setView] = useState('pending');
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const fn = view === 'history' && historyFn ? historyFn : fetchFn;
      const res = await fn();
      setRequests(res.requests || []);
    } catch {
      setError(t('Errore nel caricamento delle richieste'));
    } finally {
      setLoading(false);
    }
  }, [view, fetchFn, historyFn, t]);

  useEffect(() => { load(); }, [load]);

  const handle = async (action, id) => {
    setBusyId(id);
    setError('');
    try {
      if (action === 'approve') await approveFn(id, null);
      else await rejectFn(id, null);
      await load();
      if (onResolved) await onResolved();
    } catch (e) {
      setError(e?.response?.data?.detail || t('Operazione non riuscita'));
    } finally {
      setBusyId(null);
    }
  };

  const isHistory = view === 'history';

  return (
    <div className="space-y-3">
      {historyFn && (
        <div className="flex gap-2">
          <button
            onClick={() => setView('pending')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              !isHistory ? 'bg-orange-500 text-white shadow' : 'bg-white/70 text-gray-600 hover:bg-white'
            }`}
          >
            <Inbox className="w-4 h-4" /> {t('In attesa')}
          </button>
          <button
            onClick={() => setView('history')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              isHistory ? 'bg-orange-500 text-white shadow' : 'bg-white/70 text-gray-600 hover:bg-white'
            }`}
          >
            <History className="w-4 h-4" /> {t('Storico')}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
        </div>
      ) : requests.length === 0 ? (
        <div className="glass rounded-2xl p-10 text-center text-slate-500">
          <Inbox className="w-10 h-10 mx-auto mb-3 text-slate-300" />
          <p>{isHistory ? t('Nessuna richiesta nello storico.') : t('Nessuna richiesta in attesa.')}</p>
        </div>
      ) : (
        requests.map((r) => {
          const insufficient = availableCredits !== -1 && availableCredits < r.package_credits;
          const badge = STATUS_BADGES[r.status] || STATUS_BADGES.pending;
          return (
            <div key={r.id} className="glass rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-semibold text-slate-900 truncate">{r.requester_username}</p>
                  {r.requester_entity_type && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-semibold">
                      {t(ENTITY_LABELS[r.requester_entity_type] || r.requester_entity_type)}
                    </span>
                  )}
                  {isHistory && (
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${badge.cls}`}>
                      {t(badge.label)}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 truncate">{r.requester_email}</p>
                <div className="mt-1 flex items-center gap-2 text-sm flex-wrap">
                  <span className="font-medium text-slate-700">{r.package_name}</span>
                  <span className="inline-flex items-center gap-1 text-orange-600 font-bold">
                    <Coins className="w-3.5 h-3.5" /> {r.package_credits?.toLocaleString('it-IT')}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                    <Clock className="w-3 h-3" /> {formatDateTime(r.created_at)}
                  </span>
                  {isHistory && r.resolved_at && (
                    <span className="text-xs text-slate-400">· {t('gestita il')} {formatDateTime(r.resolved_at)}</span>
                  )}
                </div>
                {!isHistory && insufficient && (
                  <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> {t('Crediti insufficienti per approvare')}
                  </p>
                )}
              </div>
              {!isHistory && (
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => handle('approve', r.id)}
                    disabled={busyId === r.id || insufficient}
                    title={insufficient ? t('Crediti insufficienti') : t('Approva')}
                    className="btn btn-primary text-sm gap-1 disabled:opacity-50"
                  >
                    {busyId === r.id ? <Loader className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} {t('Approva')}
                  </button>
                  <button
                    onClick={() => handle('reject', r.id)}
                    disabled={busyId === r.id}
                    className="btn btn-ghost text-sm text-red-600 hover:bg-red-50 gap-1 disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" /> {t('Rifiuta')}
                  </button>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
};

export default RequestsInbox;
