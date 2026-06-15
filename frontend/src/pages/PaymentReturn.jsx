import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  CheckCircle2, AlertTriangle, Loader, Clock, Coins, ArrowRight, Home, ListChecks,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getPayment } from '../services/api';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_MS = 30000; // dopo 30s smettiamo di pollare

const formatEur = (cents) => (typeof cents === 'number'
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100)
  : '—');

const PaymentReturn = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get('orderId');
  const { refreshUser } = useAuth();

  const [order, setOrder] = useState(null);
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef(Date.now());

  useEffect(() => {
    if (!orderId) {
      setError(t('Order ID mancante.'));
      setPolling(false);
      return undefined;
    }

    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const data = await getPayment(orderId);
        if (cancelled) return;
        setOrder(data);

        const terminal = ['PAID', 'FAILED', 'CANCELED', 'EXPIRED', 'REFUNDED'];
        const elapsedMs = Date.now() - startedAtRef.current;
        setElapsed(elapsedMs);

        if (terminal.includes(data.status)) {
          setPolling(false);
          if (data.status === 'PAID') {
            // Aggiorna saldo crediti utente
            try { await refreshUser(); } catch { /* ignore */ }
          }
          return;
        }
        if (elapsedMs >= MAX_POLL_MS) {
          setPolling(false);
          return;
        }
        timer = setTimeout(tick, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(err?.response?.data?.detail || t('Errore nel recupero dello stato pagamento.'));
        setPolling(false);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">{t('Esito pagamento')}</h1>

      {error && (
        <div className="glass rounded-2xl p-6 flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-red-500 flex-shrink-0" />
          <div>
            <h2 className="font-semibold text-slate-900">{t('Errore')}</h2>
            <p className="text-sm text-slate-600 mt-1">{error}</p>
            <button onClick={() => navigate('/')} className="btn btn-secondary mt-4 inline-flex items-center gap-2">
              <Home className="w-4 h-4" /> {t('Torna alla dashboard')}
            </button>
          </div>
        </div>
      )}

      {!error && polling && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center space-y-3">
          <Loader className="w-10 h-10 text-orange-500 animate-spin" />
          <h2 className="font-semibold text-slate-900">{t('Conferma pagamento in corso…')}</h2>
          <p className="text-sm text-slate-500">
            {t('Stiamo aspettando la notifica di esito da PagoPA. Di solito sono pochi secondi.')}
          </p>
          {elapsed > 0 && (
            <p className="text-xs text-slate-400">{t('{{n}}s', { n: Math.round(elapsed / 1000) })}</p>
          )}
        </div>
      )}

      {!error && !polling && order?.status === 'PAID' && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center space-y-4 border-2 border-emerald-200 bg-emerald-50/50">
          <CheckCircle2 className="w-14 h-14 text-emerald-500" />
          <div>
            <h2 className="text-xl font-bold text-emerald-700">{t('Pagamento riuscito!')}</h2>
            <p className="text-sm text-slate-600 mt-1">{t('Grazie. I crediti sono stati accreditati sul tuo account.')}</p>
          </div>
          <div className="grid grid-cols-2 gap-4 w-full max-w-md">
            <div className="bg-white rounded-xl p-4 border border-slate-200">
              <p className="text-xs text-slate-500 uppercase font-medium">{t('Crediti')}</p>
              <p className="text-2xl font-bold text-orange-600 flex items-center justify-center gap-2">
                <Coins className="w-5 h-5" />
                +{order.credits?.toLocaleString('it-IT')}
              </p>
            </div>
            <div className="bg-white rounded-xl p-4 border border-slate-200">
              <p className="text-xs text-slate-500 uppercase font-medium">{t('Importo')}</p>
              <p className="text-2xl font-bold text-slate-700">{formatEur(order.amount_paid_cents || order.amount_cents)}</p>
            </div>
          </div>
          <div className="flex gap-3 flex-wrap justify-center">
            <button onClick={() => navigate('/')} className="btn btn-primary inline-flex items-center gap-2">
              <Home className="w-4 h-4" /> {t('Vai alla dashboard')}
            </button>
            <button onClick={() => navigate('/payments/history')} className="btn btn-secondary inline-flex items-center gap-2">
              <ListChecks className="w-4 h-4" /> {t('Vedi cronologia')}
            </button>
          </div>
        </div>
      )}

      {!error && !polling && order?.status === 'AWAITING_PAYMENT' && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center space-y-3 border-2 border-amber-200 bg-amber-50/50">
          <Clock className="w-12 h-12 text-amber-500" />
          <h2 className="font-semibold text-slate-900">{t('Pagamento in elaborazione')}</h2>
          <p className="text-sm text-slate-600">
            {t('La conferma da PagoPA non è ancora arrivata. Capita quando il pagamento viene processato in differita. Riceverai un aggiornamento appena disponibile; nel frattempo puoi consultare la cronologia.')}
          </p>
          <div className="flex gap-3 flex-wrap justify-center">
            <button onClick={() => navigate('/payments/history')} className="btn btn-primary inline-flex items-center gap-2">
              <ListChecks className="w-4 h-4" /> {t('Vai alla cronologia')}
            </button>
            <button onClick={() => navigate('/')} className="btn btn-secondary inline-flex items-center gap-2">
              <Home className="w-4 h-4" /> {t('Torna alla dashboard')}
            </button>
          </div>
        </div>
      )}

      {!error && !polling && (order?.status === 'FAILED' || order?.status === 'CANCELED' || order?.status === 'EXPIRED') && (
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center space-y-3 border-2 border-red-200 bg-red-50/50">
          <AlertTriangle className="w-12 h-12 text-red-500" />
          <h2 className="font-semibold text-slate-900">
            {order.status === 'FAILED' && t('Pagamento non riuscito')}
            {order.status === 'CANCELED' && t('Pagamento annullato')}
            {order.status === 'EXPIRED' && t('Posizione scaduta')}
          </h2>
          <p className="text-sm text-slate-600">
            {t('Nessun credito è stato addebitato. Puoi riprovare in qualsiasi momento.')}
          </p>
          <div className="flex gap-3 flex-wrap justify-center">
            <button onClick={() => navigate('/credits/buy')} className="btn btn-primary inline-flex items-center gap-2">
              {t('Riprova')} <ArrowRight className="w-4 h-4" />
            </button>
            <button onClick={() => navigate('/')} className="btn btn-secondary inline-flex items-center gap-2">
              <Home className="w-4 h-4" /> {t('Dashboard')}
            </button>
          </div>
        </div>
      )}

      {order?.iuv && (
        <p className="text-xs text-slate-400 text-center">IUV {order.iuv}</p>
      )}
    </div>
  );
};

export default PaymentReturn;
