import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Loader, Coins, ChevronDown, ChevronUp, Receipt, Store,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getMyResellers, getResellerPayments } from '../services/api';

const formatEur = (val) => (typeof val === 'number'
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(val)
  : '—');

const formatEurCents = (cents) => (typeof cents === 'number'
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100)
  : '—');

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' });
};

const STATUS_LABELS = {
  PENDING: { label: 'In attesa', cls: 'bg-slate-100 text-slate-700' },
  AWAITING_PAYMENT: { label: 'Attesa pagamento', cls: 'bg-amber-100 text-amber-800' },
  PAID: { label: 'Pagato', cls: 'bg-emerald-100 text-emerald-800' },
  FAILED: { label: 'Fallito', cls: 'bg-red-100 text-red-800' },
  CANCELED: { label: 'Annullato', cls: 'bg-slate-100 text-slate-600' },
  EXPIRED: { label: 'Scaduto', cls: 'bg-slate-100 text-slate-600' },
  REFUNDED: { label: 'Rimborsato', cls: 'bg-blue-100 text-blue-800' },
};

const Distributor = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [resellers, setResellers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [payments, setPayments] = useState({});      // { resellerId: [orders] }
  const [loadingPayments, setLoadingPayments] = useState(null);

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

  const toggleExpand = async (resellerId) => {
    if (expanded === resellerId) {
      setExpanded(null);
      return;
    }
    setExpanded(resellerId);
    // Lazy-load dello storico solo alla prima apertura
    if (!payments[resellerId]) {
      setLoadingPayments(resellerId);
      try {
        const res = await getResellerPayments(resellerId);
        setPayments((prev) => ({ ...prev, [resellerId]: res.orders || [] }));
      } catch {
        setPayments((prev) => ({ ...prev, [resellerId]: [] }));
      } finally {
        setLoadingPayments(null);
      }
    }
  };

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
            <p className="text-slate-600">{t('I tuoi rivenditori: crediti, spesa e storico acquisti')}</p>
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
            {resellers.map((r) => {
              const isOpen = expanded === r.id;
              return (
                <div key={r.id} className="glass rounded-2xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleExpand(r.id)}
                    className="w-full flex items-center gap-4 p-4 text-left hover:bg-slate-50/60"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                      <Store className="w-5 h-5 text-slate-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-900 truncate">{r.full_name || r.username}</p>
                      <p className="text-xs text-slate-500 truncate">{r.email}</p>
                    </div>
                    <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-orange-50 rounded-xl border border-orange-200">
                      <Coins className="w-4 h-4 text-orange-500" />
                      <span className="text-sm font-bold text-orange-700">{r.credits?.toLocaleString('it-IT')}</span>
                      <span className="text-xs text-orange-500">{t('crediti')}</span>
                    </div>
                    <div className="text-right hidden md:block">
                      <p className="text-sm font-bold text-slate-900">{formatEur(r.total_spent_eur)}</p>
                      <p className="text-xs text-slate-500">{t('{{count}} acquisti', { count: r.purchase_count })}</p>
                    </div>
                    {isOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
                  </button>

                  {isOpen && (
                    <div className="border-t border-slate-100 p-4 bg-slate-50/40">
                      {/* Riepilogo mobile (crediti/spesa nascosti nella riga su schermi piccoli) */}
                      <div className="flex sm:hidden gap-3 mb-3">
                        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-50 rounded-xl border border-orange-200">
                          <Coins className="w-4 h-4 text-orange-500" />
                          <span className="text-sm font-bold text-orange-700">{r.credits?.toLocaleString('it-IT')}</span>
                        </div>
                        <div className="px-3 py-1.5 bg-white rounded-xl border border-slate-200">
                          <span className="text-sm font-bold text-slate-900">{formatEur(r.total_spent_eur)}</span>
                          <span className="text-xs text-slate-500 ml-1">· {t('{{count}} acquisti', { count: r.purchase_count })}</span>
                        </div>
                      </div>

                      <h4 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-2">
                        <Receipt className="w-4 h-4 text-slate-400" /> {t('Storico acquisti')}
                      </h4>

                      {loadingPayments === r.id ? (
                        <div className="flex items-center gap-2 text-slate-500 text-sm py-4">
                          <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
                        </div>
                      ) : (payments[r.id] || []).length === 0 ? (
                        <p className="text-sm text-slate-400 py-3">{t('Nessun acquisto registrato.')}</p>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead className="text-left text-slate-500 border-b border-slate-200">
                              <tr>
                                <th className="px-3 py-2 font-medium">{t('Data')}</th>
                                <th className="px-3 py-2 font-medium">{t('Crediti')}</th>
                                <th className="px-3 py-2 font-medium">{t('Importo')}</th>
                                <th className="px-3 py-2 font-medium">{t('Stato')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(payments[r.id] || []).map((o) => {
                                const st = STATUS_LABELS[o.status] || { label: o.status, cls: 'bg-slate-100 text-slate-600' };
                                return (
                                  <tr key={o.id} className="border-b border-slate-100 last:border-0">
                                    <td className="px-3 py-2 text-slate-700">{formatDate(o.created_at)}</td>
                                    <td className="px-3 py-2 font-bold text-orange-600">+{o.credits?.toLocaleString('it-IT')}</td>
                                    <td className="px-3 py-2 text-slate-700">{formatEurCents(o.amount_cents)}</td>
                                    <td className="px-3 py-2">
                                      <span className={`inline-block px-2 py-1 rounded-md text-xs font-medium ${st.cls}`}>
                                        {st.label === o.status ? st.label : t(st.label)}
                                      </span>
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Distributor;
