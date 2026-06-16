import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Loader, Coins, Store, Plus, UserPlus, X, Check, AlertTriangle, Inbox,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import {
  getMyChildren, createSubUser, assignCreditsToChild,
  getRequestsInbox, approveCreditRequest, rejectCreditRequest,
} from '../services/api';
import RequestsInbox from './RequestsInbox';

const ENTITY_LABELS = {
  distributore: 'Distributore',
  rivenditore: 'Rivenditore',
  privato: 'Privato',
};

// Componente condiviso da distributore e rivenditore per gestire il proprio
// sottoalbero: elenco figli, creazione di sotto-utenti e assegnazione crediti.
const HierarchyManager = ({ title, subtitle, allowedChildTypes }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { credits, refreshUser } = useAuth();

  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [tab, setTab] = useState('utenti');
  const [inboxCount, setInboxCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [childrenRes, inboxRes] = await Promise.all([
        getMyChildren(),
        getRequestsInbox().catch(() => ({ total: 0 })),
      ]);
      setChildren(childrenRes.children || []);
      setInboxCount(inboxRes.total || 0);
    } catch {
      setError(t('Errore nel caricamento degli utenti'));
    } finally {
      setLoading(false);
    }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const flash = (msg) => { setFeedback(msg); setTimeout(() => setFeedback(''), 3500); };

  const afterMutation = async (msg) => {
    await load();
    await refreshUser();   // il saldo del manager può essere cambiato (trasferimenti)
    if (msg) flash(msg);
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto">
        <button onClick={() => navigate('/')} className="btn btn-secondary gap-2 mb-6">
          <ArrowLeft className="w-4 h-4" />
          {t('Torna alla Dashboard')}
        </button>

        <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Users className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900">{title}</h1>
              <p className="text-slate-600">{subtitle}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-orange-50 rounded-xl border border-orange-200">
            <Coins className="w-4 h-4 text-orange-500" />
            <span className="text-sm font-bold text-orange-700">
              {credits === -1 ? '∞' : credits?.toLocaleString('it-IT')}
            </span>
            <span className="text-xs text-orange-500">{t('crediti disponibili')}</span>
          </div>
        </div>

        {feedback && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm flex items-center gap-2">
            <Check className="w-4 h-4 flex-shrink-0" /> {feedback}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setTab('utenti')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium transition-all ${
              tab === 'utenti' ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow' : 'bg-white/70 text-gray-600 hover:bg-white'
            }`}
          >
            <Users className="w-4 h-4" /> {t('Utenti')}
          </button>
          <button
            onClick={() => setTab('richieste')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium transition-all ${
              tab === 'richieste' ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow' : 'bg-white/70 text-gray-600 hover:bg-white'
            }`}
          >
            <Inbox className="w-4 h-4" /> {t('Richieste')}
            {inboxCount > 0 && (
              <span className="ml-1 text-[11px] px-2 py-0.5 rounded-full bg-red-500 text-white font-bold">{inboxCount}</span>
            )}
          </button>
        </div>

        {tab === 'richieste' ? (
          <RequestsInbox
            fetchFn={getRequestsInbox}
            approveFn={approveCreditRequest}
            rejectFn={rejectCreditRequest}
            availableCredits={credits}
            onResolved={() => afterMutation()}
          />
        ) : (
        <>
        <div className="flex justify-end mb-4">
          <button onClick={() => setCreateOpen(true)} className="btn btn-primary gap-2">
            <UserPlus className="w-4 h-4" /> {t('Crea utente')}
          </button>
        </div>

        {loading ? (
          <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
            <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento…')}
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : children.length === 0 ? (
          <div className="glass rounded-2xl p-12 text-center text-slate-500">
            <Store className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>{t('Nessun utente associato. Creane uno con "Crea utente".')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {children.map((u) => (
              <div key={u.id} className="glass rounded-2xl flex items-center gap-4 p-4">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                  <Store className="w-5 h-5 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-slate-900 truncate">{u.full_name || u.username}</p>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-semibold">
                      {t(ENTITY_LABELS[u.entity_type] || u.entity_type)}
                    </span>
                    {!u.email_verified && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-semibold">
                        {t('invito in sospeso')}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 truncate">{u.email}</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-orange-50 rounded-xl border border-orange-200">
                  <Coins className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-bold text-orange-700">{u.credits?.toLocaleString('it-IT')}</span>
                </div>
                <button onClick={() => setAssignTarget(u)} className="btn btn-secondary text-sm gap-1">
                  <Plus className="w-3.5 h-3.5" /> {t('Assegna crediti')}
                </button>
              </div>
            ))}
          </div>
        )}
        </>
        )}
      </div>

      {createOpen && (
        <CreateUserDialog
          allowedChildTypes={allowedChildTypes}
          onClose={() => setCreateOpen(false)}
          onCreated={() => { setCreateOpen(false); afterMutation(t('Utente creato. Invito email inviato.')); }}
        />
      )}
      {assignTarget && (
        <AssignCreditsDialog
          target={assignTarget}
          maxCredits={credits}
          onClose={() => setAssignTarget(null)}
          onAssigned={() => { setAssignTarget(null); afterMutation(t('Crediti assegnati.')); }}
        />
      )}
    </div>
  );
};

const CreateUserDialog = ({ allowedChildTypes, onClose, onCreated }) => {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    email: '', username: '', full_name: '',
    entity_type: allowedChildTypes[0] || 'privato', credits: 0,
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    setErr('');
    if (!form.email.trim() || form.username.trim().length < 3) {
      setErr(t('Email e username (min 3 caratteri) obbligatori.'));
      return;
    }
    setSubmitting(true);
    try {
      await createSubUser({
        email: form.email.trim(),
        username: form.username.trim(),
        full_name: form.full_name.trim() || null,
        entity_type: form.entity_type,
        credits: parseInt(form.credits, 10) || 0,
      });
      onCreated();
    } catch (e) {
      setErr(e?.response?.data?.detail || t('Errore nella creazione'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">{t('Crea utente')}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
        </div>
        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" /> <span>{err}</span>
          </div>
        )}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Email')}</label>
            <input type="email" className="input w-full" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Username')}</label>
            <input className="input w-full" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Nome completo (opzionale)')}</label>
            <input className="input w-full" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            {allowedChildTypes.length > 1 && (
              <div>
                <label className="text-xs text-slate-600 font-medium">{t('Tipo')}</label>
                <select className="input w-full" value={form.entity_type} onChange={(e) => setForm({ ...form, entity_type: e.target.value })}>
                  {allowedChildTypes.map((tp) => (
                    <option key={tp} value={tp}>{t(ENTITY_LABELS[tp] || tp)}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="text-xs text-slate-600 font-medium">{t('Crediti iniziali')}</label>
              <input type="number" min={0} className="input w-full" value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value })} />
            </div>
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">{t('Annulla')}</button>
          <button onClick={submit} disabled={submitting} className="btn btn-primary inline-flex gap-2 disabled:opacity-50">
            {submitting ? <Loader className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {t('Crea')}
          </button>
        </div>
        <p className="text-xs text-slate-400">{t('I crediti iniziali vengono trasferiti dal tuo saldo.')}</p>
      </div>
    </div>
  );
};

const AssignCreditsDialog = ({ target, maxCredits, onClose, onAssigned }) => {
  const { t } = useTranslation();
  const [amount, setAmount] = useState(100);
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    setErr('');
    const amt = parseInt(amount, 10);
    if (!amt || amt <= 0) { setErr(t('Inserisci un importo valido.')); return; }
    setSubmitting(true);
    try {
      await assignCreditsToChild(target.id, amt, description.trim() || null);
      onAssigned();
    } catch (e) {
      setErr(e?.response?.data?.detail || t('Errore nell\'assegnazione'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">{t('Assegna crediti')}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-slate-600">{t('A')}: <span className="font-semibold">{target.full_name || target.username}</span></p>
        {maxCredits !== -1 && (
          <p className="text-xs text-slate-400">{t('Disponibili')}: {maxCredits?.toLocaleString('it-IT')}</p>
        )}
        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" /> <span>{err}</span>
          </div>
        )}
        <div>
          <label className="text-xs text-slate-600 font-medium">{t('Crediti')}</label>
          <input type="number" min={1} className="input w-full" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-slate-600 font-medium">{t('Nota (opzionale)')}</label>
          <input className="input w-full" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">{t('Annulla')}</button>
          <button onClick={submit} disabled={submitting} className="btn btn-primary inline-flex gap-2 disabled:opacity-50">
            {submitting ? <Loader className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {t('Assegna')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default HierarchyManager;
