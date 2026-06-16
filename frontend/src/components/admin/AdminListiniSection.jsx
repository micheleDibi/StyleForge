import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tag, CreditCard, CheckCircle2, AlertCircle } from 'lucide-react';
import { getAdminEurPerCredit, updateAdminEurPerCredit } from '../../services/api';
import { PackagesSubtab } from './AdminPaymentsSection';

// Scheda "Listini": tutto ciò che riguarda i PREZZI per l'acquisto dei crediti.
// - Conversione EUR / credito (prezzo base di un credito)
// - Pacchetti acquistabili (CRUD, riutilizza PackagesSubtab da AdminPaymentsSection)
const AdminListiniSection = () => {
  const { t } = useTranslation();
  const [eurPerCredit, setEurPerCredit] = useState(0.10);
  const [eurPerCreditSaved, setEurPerCreditSaved] = useState(0.10);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let active = true;
    getAdminEurPerCredit()
      .then((data) => {
        if (!active) return;
        const value = data?.eur_per_credit ?? 0.10;
        setEurPerCredit(value);
        setEurPerCreditSaved(value);
      })
      .catch(() => { /* default 0.10 */ });
    return () => { active = false; };
  }, []);

  const saveEur = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await updateAdminEurPerCredit(eurPerCredit);
      setEurPerCreditSaved(eurPerCredit);
      setSuccess(t('Tasso EUR/credito aggiornato.'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (e) {
      setError(t('Errore nel salvataggio del tasso EUR/credito.'));
      setTimeout(() => setError(''), 3000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-2xl p-6">
        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Tag className="w-6 h-6 text-orange-500" />
          {t('Listini')}
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          {t('Gestisci i prezzi e i pacchetti per l\'acquisto dei crediti.')}
        </p>
      </div>

      {/* Feedback */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {success}
        </div>
      )}

      {/* Conversione EUR / credito */}
      <div className="glass rounded-2xl p-5">
        <h3 className="font-bold text-gray-900 mb-1 flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-orange-500" />
          {t('Conversione EUR / Credito')}
        </h3>
        <p className="text-xs text-gray-400 mb-3">
          {t('Prezzo base di un credito, usato per il pricing dell\'acquisto.')}
        </p>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-sm text-gray-600">{t('1 credito =')}</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className="input w-28 text-center text-sm py-1.5"
              value={eurPerCredit}
              onChange={(e) => setEurPerCredit(parseFloat(e.target.value) || 0)}
            />
            <span className="text-sm text-gray-600">EUR</span>
          </div>
          <button
            onClick={saveEur}
            disabled={saving || eurPerCredit === eurPerCreditSaved}
            className="btn btn-primary text-sm disabled:opacity-50"
          >
            {t('Salva')}
          </button>
        </div>
      </div>

      {/* Pacchetti acquistabili */}
      <PackagesSubtab />
    </div>
  );
};

export default AdminListiniSection;
