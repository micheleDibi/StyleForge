import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams, Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Loader, LogIn } from 'lucide-react';
import { verifyEmail } from '../services/api';

const VerifyEmail = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  // Stato iniziale derivato dalla presenza del token (niente setState sincrono nell'effect).
  const [state, setState] = useState(token ? 'loading' : 'error'); // loading | success | error
  const [message, setMessage] = useState(token ? '' : t('Token mancante nel link.'));

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    verifyEmail(token)
      .then((d) => {
        if (!cancelled) { setState('success'); setMessage(d.message || t('Email verificata con successo.')); }
      })
      .catch((err) => {
        if (!cancelled) { setState('error'); setMessage(err.response?.data?.detail || t('Link di verifica non valido o scaduto.')); }
      });
    return () => { cancelled = true; };
  }, [token, t]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="w-full max-w-md glass rounded-3xl p-8 shadow-2xl text-center">
        {state === 'loading' && (
          <>
            <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
            <p className="text-slate-600">{t('Verifica in corso…')}</p>
          </>
        )}
        {state === 'success' && (
          <>
            <div className="w-14 h-14 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Email verificata')}</h1>
            <p className="text-slate-600 mb-6">{message}</p>
            <Link to="/login" className="btn btn-primary btn-lg w-full gap-2">
              <LogIn className="w-4 h-4" /> {t('Vai al login')}
            </Link>
          </>
        )}
        {state === 'error' && (
          <>
            <div className="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Verifica non riuscita')}</h1>
            <p className="text-slate-600 mb-6">{message}</p>
            <Link to="/login" className="btn btn-secondary w-full">{t('Torna al login')}</Link>
          </>
        )}
      </div>
    </div>
  );
};

export default VerifyEmail;
