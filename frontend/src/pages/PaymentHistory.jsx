import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Loader, Receipt, Coins, ArrowRight, Copy, Check, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getUserPaymentHistory } from '../services/api';

const formatEur = (cents) => (typeof cents === 'number'
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

const PAGE_SIZE = 20;

const PaymentHistory = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [copiedIuv, setCopiedIuv] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getUserPaymentHistory(PAGE_SIZE, offset)
      .then((res) => {
        if (cancelled) return;
        setOrders(res.orders || []);
        setTotal(res.total || 0);
      })
      .catch(() => { if (!cancelled) setError(t('Errore caricamento cronologia')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [offset]);

  const handleCopyIuv = async (iuv) => {
    if (!iuv) return;
    try {
      await navigator.clipboard.writeText(iuv);
      setCopiedIuv(iuv);
      setTimeout(() => setCopiedIuv(null), 1500);
    } catch { /* ignore */ }
  };

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Receipt className="w-6 h-6 text-orange-500" />
            {t('Cronologia pagamenti')}
          </h1>
          <p className="text-slate-600 mt-1">{t('Tutti gli acquisti di crediti effettuati tramite PagoPA.')}</p>
        </div>
        <button onClick={() => navigate('/credits/buy')} className="btn btn-primary inline-flex items-center gap-2">
          <Coins className="w-4 h-4" /> {t('Compra crediti')} <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : orders.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center text-slate-500">
          <Receipt className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p>{t('Nessun pagamento ancora effettuato.')}</p>
        </div>
      ) : (
        <div className="glass rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-left text-slate-600">
                <th className="px-4 py-3 font-medium">{t('Data')}</th>
                <th className="px-4 py-3 font-medium">{t('Crediti')}</th>
                <th className="px-4 py-3 font-medium">{t('Importo')}</th>
                <th className="px-4 py-3 font-medium">{t('Stato')}</th>
                <th className="px-4 py-3 font-medium">IUV</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const st = STATUS_LABELS[o.status] || { label: o.status, cls: 'bg-slate-100 text-slate-600' };
                return (
                  <tr key={o.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50">
                    <td className="px-4 py-3 text-slate-700">{formatDate(o.created_at)}</td>
                    <td className="px-4 py-3 font-bold text-orange-600">+{o.credits?.toLocaleString('it-IT')}</td>
                    <td className="px-4 py-3 text-slate-700">{formatEur(o.amount_cents)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-1 rounded-md text-xs font-medium ${st.cls}`}>
                        {STATUS_LABELS[o.status] ? t(st.label) : st.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {o.iuv ? (
                        <button
                          type="button"
                          onClick={() => handleCopyIuv(o.iuv)}
                          className="inline-flex items-center gap-1 text-xs font-mono text-slate-500 hover:text-slate-700"
                          title={t('Copia IUV')}
                        >
                          {copiedIuv === o.iuv ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                          {o.iuv.substring(0, 12)}…
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50">
              <span className="text-xs text-slate-500">{t('Pagina {{page}} di {{totalPages}} · {{total}} ordini', { page, totalPages, total })}</span>
              <div className="flex gap-2">
                <button
                  className="btn btn-secondary p-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  className="btn btn-secondary p-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PaymentHistory;
