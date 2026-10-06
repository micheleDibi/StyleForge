import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Lock, Eye, EyeOff, Loader, CheckCircle2 } from 'lucide-react';
import { changePassword } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { validatePassword } from '../utils/passwordPolicy';

const ChangePassword = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [current, setCurrent] = useState('');
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!current) { setError(t('Inserisci la password attuale')); return; }
    const errorePassword = validatePassword(pw, t);
    if (errorePassword) { setError(errorePassword); return; }
    if (pw !== confirm) { setError(t('Le password non coincidono')); return; }
    setLoading(true);
    setError('');
    try {
      await changePassword(current, pw);
      setDone(true);
      // Il backend revoca tutte le sessioni: forziamo un nuovo login.
      setTimeout(async () => { await logout(); navigate('/login'); }, 2200);
    } catch (err) {
      setError(err.response?.data?.detail || t('Errore nel cambio password'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-md mx-auto">
        <button onClick={() => navigate('/')} className="btn btn-secondary gap-2 mb-6">
          <ArrowLeft className="w-4 h-4" /> {t('Torna alla Dashboard')}
        </button>

        <div className="glass rounded-3xl p-8 shadow-xl">
          {done ? (
            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-green-600" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Password cambiata')}</h1>
              <p className="text-slate-600">{t('Verrai disconnesso: effettua nuovamente l\'accesso con la nuova password.')}</p>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-slate-900 mb-1">{t('Cambia password')}</h1>
              <p className="text-slate-500 text-sm mb-6">{t('Per sicurezza verrai disconnesso da tutti i dispositivi.')}</p>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type={show ? 'text' : 'password'}
                    className="input pl-11 pr-12"
                    placeholder={t('Password attuale')}
                    value={current}
                    onChange={(e) => setCurrent(e.target.value)}
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
                    placeholder={t('Nuova password')}
                    value={pw}
                    onChange={(e) => setPw(e.target.value)}
                  />
                </div>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type={show ? 'text' : 'password'}
                    className="input pl-11"
                    placeholder={t('Conferma nuova password')}
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                  />
                </div>
                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 font-medium">{error}</div>
                )}
                <button type="submit" disabled={loading} className="btn btn-primary btn-lg w-full gap-2">
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                  {t('Cambia password')}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;
