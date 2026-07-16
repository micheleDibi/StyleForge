import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Tag, CreditCard, CheckCircle2, AlertCircle, Plus, Edit2, Trash2, Loader, X, Check,
} from 'lucide-react';
import {
  getAdminEurPerCredit, updateAdminEurPerCredit,
  adminListCreditPackages, adminCreateCreditPackage, adminUpdateCreditPackage, adminDeleteCreditPackage,
} from '../../services/api';

const formatEur = (cents) => (typeof cents === 'number'
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100)
  : '—');

// ============================================================================
// Dialog crea/modifica pacchetto
// ============================================================================
const PackageEditDialog = ({ pkg, onSave, onClose }) => {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    id: pkg.id,
    name: pkg.name || '',
    credits: pkg.credits || 100,
    price_eur: pkg.price_eur != null ? String(pkg.price_eur) : (pkg.price_cents != null ? (pkg.price_cents / 100).toFixed(2) : '10.00'),
    is_active: pkg.is_active !== false,
    sort_order: pkg.sort_order || 0,
    description: pkg.description || '',
    entity_type: pkg.entity_type || 'privato',
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">{form.id ? t('Modifica pacchetto') : t('Nuovo pacchetto')}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">{t('Nome')}</label>
            <input className="input w-full" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Crediti')}</label>
            <input type="number" className="input w-full" value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value })} min={1} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Prezzo (EUR)')}</label>
            <input type="number" step="0.01" className="input w-full" value={form.price_eur} onChange={(e) => setForm({ ...form, price_eur: e.target.value })} min={0.01} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Ordine')}</label>
            <input type="number" className="input w-full" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">{t('Destinatario (sottotipo)')}</label>
            <select
              className="input w-full"
              value={form.entity_type}
              onChange={(e) => setForm({ ...form, entity_type: e.target.value })}
            >
              <option value="distributore">{t('Distributore')}</option>
              <option value="rivenditore">{t('Rivenditore')}</option>
              <option value="privato">{t('Privato')}</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                className="rounded text-orange-500"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              {t('Attivo')}
            </label>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">{t('Descrizione (opzionale)')}</label>
            <textarea className="input w-full min-h-[60px]" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">{t('Annulla')}</button>
          <button onClick={() => onSave(form)} className="btn btn-primary inline-flex gap-2">
            <Check className="w-4 h-4" /> {t('Salva')}
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Gestione pacchetti acquistabili (CRUD)
// ============================================================================
const PackagesManager = () => {
  const { t } = useTranslation();
  const [packages, setPackages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // package being edited (or {} for new)

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminListCreditPackages();
      setPackages(res.packages || []);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const handleSave = async (form) => {
    const payload = {
      name: form.name?.trim(),
      credits: parseInt(form.credits, 10),
      price_cents: Math.round(parseFloat(form.price_eur) * 100),
      is_active: !!form.is_active,
      sort_order: parseInt(form.sort_order, 10) || 0,
      description: form.description?.trim() || null,
      entity_type: form.entity_type || 'privato',
    };
    if (!payload.name || !payload.credits || !payload.price_cents) {
      alert(t('Compila tutti i campi obbligatori.'));
      return;
    }
    try {
      if (form.id) await adminUpdateCreditPackage(form.id, payload);
      else await adminCreateCreditPackage(payload);
      setEditing(null);
      load();
    } catch (err) {
      alert(err?.response?.data?.detail || t('Errore salvataggio pacchetto'));
    }
  };

  const handleDelete = async (pkg) => {
    if (!window.confirm(t('Eliminare il pacchetto "{{name}}"?', { name: pkg.name }))) return;
    try {
      await adminDeleteCreditPackage(pkg.id);
      load();
    } catch (err) {
      alert(err?.response?.data?.detail || t('Errore eliminazione'));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">{t('Pacchetti acquistabili')}</h3>
        <button onClick={() => setEditing({ is_active: true, sort_order: (packages.length + 1) * 10 })} className="btn btn-primary text-sm gap-2">
          <Plus className="w-4 h-4" /> {t('Nuovo pacchetto')}
        </button>
      </div>

      {loading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {packages.map((p) => (
            <div key={p.id} className={`glass rounded-2xl p-5 border-2 ${p.is_active ? 'border-emerald-200' : 'border-slate-200 opacity-60'}`}>
              <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                  <p className="text-xs text-slate-500 uppercase font-medium">{p.name}</p>
                  <p className="text-2xl font-bold text-slate-900">{p.credits.toLocaleString('it-IT')}</p>
                  <p className="text-xs text-slate-400">{t('crediti · ordine {{sort_order}}', { sort_order: p.sort_order })}</p>
                  <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-semibold capitalize">
                    {p.entity_type || 'privato'}
                  </span>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${p.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                  {p.is_active ? t('Attivo') : t('Inattivo')}
                </span>
              </div>
              <p className="text-xl font-bold text-orange-600">{formatEur(p.price_cents)}</p>
              {p.description && <p className="text-xs text-slate-500 mt-2">{p.description}</p>}
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => setEditing({ ...p, price_eur: (p.price_cents / 100).toFixed(2) })}
                  className="btn btn-secondary text-xs gap-1 flex-1"
                >
                  <Edit2 className="w-3 h-3" /> {t('Modifica')}
                </button>
                <button
                  onClick={() => handleDelete(p)}
                  className="btn btn-ghost text-xs text-red-600 hover:bg-red-50"
                  title={t('Elimina')}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <PackageEditDialog
          pkg={editing}
          onSave={handleSave}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
};

// ============================================================================
// Scheda "Listini": prezzi per l'acquisto dei crediti
// - Conversione EUR / credito (prezzo base di un credito)
// - Pacchetti acquistabili (CRUD)
// ============================================================================
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
      <PackagesManager />
    </div>
  );
};

export default AdminListiniSection;
