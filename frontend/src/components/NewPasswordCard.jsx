import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Lock, Eye, EyeOff, Loader, CheckCircle2, AlertTriangle } from 'lucide-react';

/**
 * Card riusabile per impostare una nuova password tramite token nell'URL (?token=).
 * Usata da ResetPassword (password dimenticata) e SetPassword (invito admin).
 * Props: title, subtitle, submitFn(token, password) -> Promise, successText.
 */
const NewPasswordCard = ({ title, subtitle, submitFn, successText }) => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (pw.length < 6) { setError(t('La password deve essere di almeno 6 caratteri')); return; }
    if (pw !== confirm) { setError(t('Le password non coincidono')); return; }
    setLoading(true);
    setError('');
    try {
      await submitFn(token, pw);
      setDone(true);
      setTimeout(() => navigate('/login'), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || t('Link non valido o scaduto.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="w-full max-w-md glass rounded-3xl p-8 shadow-2xl">
        {!token ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Link non valido')}</h1>
            <p className="text-slate-600 mb-6">{t('Token mancante. Richiedi un nuovo link.')}</p>
            <Link to="/login" className="btn btn-secondary w-full">{t('Torna al login')}</Link>
          </div>
        ) : done ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Fatto!')}</h1>
            <p className="text-slate-600 mb-6">{successText}</p>
            <Link to="/login" className="btn btn-primary w-full">{t('Vai al login')}</Link>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-1">{title}</h1>
            <p className="text-slate-500 text-sm mb-6">{subtitle}</p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type={show ? 'text' : 'password'}
                  className="input pl-11 pr-12"
                  placeholder={t('Nuova password')}
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type={show ? 'text' : 'password'}
                  className="input pl-11"
                  placeholder={t('Conferma password')}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </div>
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 font-medium">{error}</div>
              )}
              <button type="submit" disabled={loading} className="btn btn-primary btn-lg w-full gap-2">
                {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                {t('Conferma')}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

export default NewPasswordCard;
