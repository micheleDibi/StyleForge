import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams, Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Loader, LogIn, ArrowRightLeft, X } from 'lucide-react';
import { acceptMoveInvite, rejectMoveInvite } from '../services/api';

// Pagina pubblica: il privato accetta o rifiuta un invito di spostamento (token email).
const MoveInvite = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  // prompt | loading | accepted | rejected | error
  const [state, setState] = useState(token ? 'prompt' : 'error');
  const [message, setMessage] = useState(token ? '' : t('Token mancante nel link.'));

  const act = async (kind) => {
    setState('loading');
    try {
      const d = kind === 'accept' ? await acceptMoveInvite(token) : await rejectMoveInvite(token);
      setState(kind === 'accept' ? 'accepted' : 'rejected');
      setMessage(d.message || '');
    } catch (err) {
      setState('error');
      setMessage(err.response?.data?.detail || t('Invito non valido o scaduto.'));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="w-full max-w-md glass rounded-3xl p-8 shadow-2xl text-center">
        {state === 'prompt' && (
          <>
            <div className="w-14 h-14 rounded-2xl bg-orange-100 flex items-center justify-center mx-auto mb-4">
              <ArrowRightLeft className="w-8 h-8 text-orange-500" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Invito di spostamento')}</h1>
            <p className="text-slate-600 mb-6">
              {t('Un referente ti ha invitato ad associare il tuo account sotto la sua gestione. Vuoi accettare?')}
            </p>
            <div className="flex gap-3">
              <button onClick={() => act('accept')} className="btn btn-primary flex-1 gap-2">
                <CheckCircle2 className="w-4 h-4" /> {t('Accetta')}
              </button>
              <button onClick={() => act('reject')} className="btn btn-secondary flex-1 gap-2">
                <X className="w-4 h-4" /> {t('Rifiuta')}
              </button>
            </div>
          </>
        )}
        {state === 'loading' && (
          <>
            <Loader className="w-12 h-12 text-orange-500 animate-spin mx-auto mb-4" />
            <p className="text-slate-600">{t('Elaborazione…')}</p>
          </>
        )}
        {(state === 'accepted' || state === 'rejected') && (
          <>
            <div className="w-14 h-14 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">
              {state === 'accepted' ? t('Spostamento completato') : t('Invito rifiutato')}
            </h1>
            <p className="text-slate-600 mb-6">{message}</p>
            <Link to="/login" className="btn btn-primary w-full gap-2">
              <LogIn className="w-4 h-4" /> {t('Vai al login')}
            </Link>
          </>
        )}
        {state === 'error' && (
          <>
            <div className="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{t('Operazione non riuscita')}</h1>
            <p className="text-slate-600 mb-6">{message}</p>
            <Link to="/login" className="btn btn-secondary w-full">{t('Torna al login')}</Link>
          </>
        )}
      </div>
    </div>
  );
};

export default MoveInvite;
