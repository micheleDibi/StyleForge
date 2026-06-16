import { useEffect, useState, useCallback } from 'react';
import { Loader, Inbox, Check, X, Coins, AlertTriangle, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ENTITY_LABELS = {
  distributore: 'Distributore',
  rivenditore: 'Rivenditore',
  privato: 'Privato',
};

const formatDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
  : '—');

// Inbox condivisa delle richieste crediti.
// Props:
//  - fetchFn: () => { requests, total }
//  - approveFn(id, note), rejectFn(id, note)
//  - availableCredits: saldo dell'approvatore (-1 = infinito/admin) per disabilitare approve
//  - onResolved: callback dopo approva/rifiuta (per aggiornare saldi/elenchi del padre)
const RequestsInbox = ({ fetchFn, approveFn, rejectFn, availableCredits = -1, onResolved }) => {
  const { t } = useTranslation();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchFn();
      setRequests(res.requests || []);
    } catch {
      setError(t('Errore nel caricamento delle richieste'));
    } finally {
      setLoading(false);
    }
  }, [fetchFn, t]);

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

  if (loading) {
    return (
      <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
        <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}
      {requests.length === 0 ? (
        <div className="glass rounded-2xl p-10 text-center text-slate-500">
          <Inbox className="w-10 h-10 mx-auto mb-3 text-slate-300" />
          <p>{t('Nessuna richiesta in attesa.')}</p>
        </div>
      ) : (
        requests.map((r) => {
          const insufficient = availableCredits !== -1 && availableCredits < r.package_credits;
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
                </div>
                {insufficient && (
                  <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> {t('Crediti insufficienti per approvare')}
                  </p>
                )}
              </div>
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
            </div>
          );
        })
      )}
    </div>
  );
};

export default RequestsInbox;
