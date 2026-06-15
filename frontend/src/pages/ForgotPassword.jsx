import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Mail, ArrowLeft, Loader, CheckCircle2 } from 'lucide-react';
import { forgotPassword } from '../services/api';

const ForgotPassword = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) { setError(t('Inserisci la tua email')); return; }
    setLoading(true);
    setError('');
    try {
      await forgotPassword(email.trim());
    } catch {
      // La risposta è sempre generica per sicurezza: mostriamo comunque conferma.
    } finally {
      setLoading(false);
      setSent(true);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="w-full max-w-md glass rounded-3xl p-8 shadow-2xl">
        {sent ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Controlla la tua email')}</h1>
            <p className="text-slate-600 mb-6">{t('Se l\'indirizzo è registrato, riceverai un link per reimpostare la password.')}</p>
            <Link to="/login" className="btn btn-secondary w-full">{t('Torna al login')}</Link>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-1">{t('Password dimenticata?')}</h1>
            <p className="text-slate-500 text-sm mb-6">{t('Inserisci la tua email: ti invieremo un link per reimpostarla.')}</p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="email"
                  className="input pl-11"
                  placeholder="nome@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 font-medium">{error}</div>
              )}
              <button type="submit" disabled={loading} className="btn btn-primary btn-lg w-full gap-2">
                {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                {t('Invia link')}
              </button>
            </form>
            <Link to="/login" className="mt-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
              <ArrowLeft className="w-4 h-4" /> {t('Torna al login')}
            </Link>
          </>
        )}
      </div>
    </div>
  );
};

export default ForgotPassword;
