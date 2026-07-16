import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Globe, Plus, RefreshCw, Sparkles, Save, Trash2, ArrowLeft, Search, Loader, X, Check,
} from 'lucide-react';
import {
  adminListLanguages, adminCreateLanguage, adminDeleteLanguage, adminUpdateLanguage,
  adminGetLanguageDetail, adminSaveTranslations, adminSyncBaseLabels,
  adminTranslateEmpty, adminGetTranslateStatus,
} from '../../services/api';
import itBase from '../../i18n/locales/it.json';

const Flag = ({ code }) => <span className={`fi fi-${code}`} style={{ fontSize: '1.1rem', borderRadius: 2 }} />;

// Suggerimenti codici bandiera comuni (qualsiasi codice ISO alpha-2 è valido)
const FLAG_SUGGESTIONS = ['it', 'gb', 'us', 'fr', 'de', 'es', 'pt', 'nl', 'be', 'pl', 'ro', 'gr', 'se', 'dk', 'fi', 'cz', 'hu', 'at', 'ie', 'hr', 'sk', 'si', 'bg', 'lt', 'lv', 'ee', 'ch', 'no', 'ua', 'ru', 'tr', 'sa', 'cn', 'jp', 'kr', 'in', 'br', 'mx', 'ar'];

const AdminLanguagesSection = () => {
  const { t } = useTranslation();
  const [view, setView] = useState('list');     // 'list' | 'detail'
  const [languages, setLanguages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState('');
  const [showAdd, setShowAdd] = useState(false);

  // detail state
  const [editing, setEditing] = useState(null);  // language object
  const [detail, setDetail] = useState(null);
  const [drafts, setDrafts] = useState({});       // key -> value (dirty)
  const [search, setSearch] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [ai, setAi] = useState(null);             // {status,total,done}

  const loadLanguages = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminListLanguages();
      setLanguages(data.languages || []);
    } catch {
      setNotice(t('Errore nel caricamento delle lingue'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { loadLanguages(); }, [loadLanguages]);

  const flash = (msg) => { setNotice(msg); setTimeout(() => setNotice(''), 3000); };

  const handleSyncBase = async () => {
    setSyncing(true);
    try {
      const res = await adminSyncBaseLabels(itBase);
      flash(t('Etichette sincronizzate: {{n}}', { n: res.count }));
    } catch {
      flash(t('Errore nella sincronizzazione delle etichette'));
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = async (code) => {
    if (!confirm(t('Eliminare questa lingua e tutte le sue traduzioni?'))) return;
    try {
      await adminDeleteLanguage(code);
      loadLanguages();
    } catch (e) {
      flash(e.response?.data?.detail || t('Errore'));
    }
  };

  const handleToggleActive = async (lang) => {
    try {
      const updated = await adminUpdateLanguage(lang.code, { is_active: !lang.is_active });
      setLanguages((prev) => prev.map((l) => (l.code === lang.code ? updated : l)));
    } catch (e) {
      flash(e.response?.data?.detail || t('Errore'));
    }
  };

  const openDetail = useCallback(async (lang, q = '') => {
    setEditing(lang);
    setView('detail');
    setDetailLoading(true);
    setDrafts({});
    try {
      const d = await adminGetLanguageDetail(lang.code, q || null);
      setDetail(d);
    } catch {
      flash(t('Errore nel caricamento delle traduzioni'));
    } finally {
      setDetailLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  const handleSave = async () => {
    if (Object.keys(drafts).length === 0) return;
    setSaving(true);
    try {
      await adminSaveTranslations(editing.code, drafts);
      flash(t('Traduzioni salvate'));
      await openDetail(editing, search);
    } catch {
      flash(t('Errore nel salvataggio'));
    } finally {
      setSaving(false);
    }
  };

  const pollAi = async (jobId) => {
    let s = await adminGetTranslateStatus(jobId);
    setAi(s);
    while (s.status === 'running') {
      await new Promise((r) => setTimeout(r, 1500));
      try { s = await adminGetTranslateStatus(jobId); } catch { break; }
      setAi(s);
    }
    setAi(null);
    await openDetail(editing, search);
    flash(t('Traduzione AI completata'));
  };

  const handleAiComplete = async () => {
    try {
      const res = await adminTranslateEmpty(editing.code);
      setAi({ status: 'running', total: 0, done: 0 });
      pollAi(res.job_id);
    } catch {
      flash(t('Errore nell\'avvio della traduzione AI'));
    }
  };

  // ---- LISTA ----
  if (view === 'list') {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Globe className="w-5 h-5 text-orange-500" /> {t('Lingue')}
          </h3>
          <div className="flex gap-2">
            <button onClick={handleSyncBase} disabled={syncing} className="btn btn-secondary text-sm gap-2">
              {syncing ? <Loader className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              {t('Sincronizza etichette')}
            </button>
            <button onClick={() => setShowAdd(true)} className="btn btn-primary text-sm gap-2">
              <Plus className="w-4 h-4" /> {t('Aggiungi lingua')}
            </button>
          </div>
        </div>

        {notice && <div className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700">{notice}</div>}

        {loading ? (
          <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
            <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento...')}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {languages.map((l) => (
              <div key={l.code} className={`glass rounded-2xl p-5 border-2 ${l.is_active ? 'border-emerald-200' : 'border-slate-200 opacity-70'}`}>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <Flag code={l.flag_country_code} />
                    <div className="min-w-0">
                      <p className="font-bold text-slate-900 truncate">{l.native_name}</p>
                      <p className="text-xs text-slate-400 uppercase">{l.code}{l.is_default ? ` · ${t('default')}` : ''}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleActive(l)}
                    disabled={l.is_default}
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${l.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'} disabled:opacity-50`}
                  >
                    {l.is_active ? t('Attiva') : t('Disattivata')}
                  </button>
                </div>
                <div className="flex gap-2 mt-2">
                  <button onClick={() => openDetail(l)} className="btn btn-secondary text-xs gap-1 flex-1">
                    <Globe className="w-3 h-3" /> {t('Traduzioni')}
                  </button>
                  {!l.is_default && (
                    <button onClick={() => handleDelete(l.code)} className="btn btn-ghost text-xs text-red-500 hover:bg-red-50">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {showAdd && (
          <AddLanguageDialog
            onClose={() => setShowAdd(false)}
            onCreated={() => { setShowAdd(false); loadLanguages(); }}
          />
        )}
      </div>
    );
  }

  // ---- DETTAGLIO ----
  const entries = detail?.entries || [];
  const dirtyCount = Object.keys(drafts).length;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <button onClick={() => { setView('list'); setEditing(null); setDetail(null); }} className="btn btn-secondary gap-2 text-sm">
          <ArrowLeft className="w-4 h-4" /> {t('Indietro')}
        </button>
        <div className="flex items-center gap-2">
          {editing && <Flag code={editing.flag_country_code} />}
          <h3 className="text-lg font-bold text-slate-900">{editing?.native_name}</h3>
          {detail && (
            <span className="text-xs text-slate-500">
              {detail.translated}/{detail.total} {t('tradotte')}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={handleAiComplete} disabled={!!ai} className="btn btn-secondary text-sm gap-2">
            {ai ? <Loader className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {ai ? `${ai.done}/${ai.total}` : t('Completa con AI')}
          </button>
          <button onClick={handleSave} disabled={saving || dirtyCount === 0} className="btn btn-primary text-sm gap-2">
            {saving ? <Loader className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {t('Salva')}{dirtyCount > 0 ? ` (${dirtyCount})` : ''}
          </button>
        </div>
      </div>

      {notice && <div className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-700">{notice}</div>}

      <div className="glass rounded-xl p-3 flex items-center gap-2">
        <Search className="w-4 h-4 text-slate-400" />
        <input
          className="input flex-1"
          placeholder={t('Cerca tra le etichette...')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') openDetail(editing, search); }}
        />
        <button onClick={() => openDetail(editing, search)} className="btn btn-secondary text-sm">{t('Cerca')}</button>
      </div>

      {detailLoading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> {t('Caricamento...')}
        </div>
      ) : (
        <div className="glass rounded-2xl divide-y divide-slate-100 max-h-[60vh] overflow-y-auto">
          {entries.length === 0 && (
            <div className="p-6 text-center text-slate-400 text-sm">{t('Nessuna etichetta. Esegui prima "Sincronizza etichette".')}</div>
          )}
          {entries.map((e) => {
            const val = e.key in drafts ? drafts[e.key] : (e.value || '');
            const isEmpty = !val;
            return (
              <div key={e.key} className="p-3 grid grid-cols-1 md:grid-cols-2 gap-2 items-center">
                <div className="text-sm text-slate-600 break-words flex items-start gap-2">
                  {isEmpty
                    ? <X className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-1" />
                    : <Check className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-1" />}
                  <span>{e.key}</span>
                </div>
                <input
                  className={`input w-full ${isEmpty ? 'border-amber-200' : ''}`}
                  value={val}
                  placeholder={t('Traduzione...')}
                  onChange={(ev) => setDrafts((prev) => ({ ...prev, [e.key]: ev.target.value }))}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ----- Dialog "Aggiungi lingua" -----
const AddLanguageDialog = ({ onClose, onCreated }) => {
  const { t } = useTranslation();
  const [form, setForm] = useState({ code: '', name: '', native_name: '', flag_country_code: '', translate_all: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!form.code || !form.name || !form.native_name || !form.flag_country_code) {
      setError(t('Compila tutti i campi'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      await adminCreateLanguage({
        code: form.code.trim().toLowerCase(),
        name: form.name.trim(),
        native_name: form.native_name.trim(),
        flag_country_code: form.flag_country_code.trim().toLowerCase(),
        is_active: true,
        sort_order: 0,
        translate_all: form.translate_all,
      });
      onCreated();
    } catch (e) {
      setError(e.response?.data?.detail || t('Errore nella creazione della lingua'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">{t('Aggiungi lingua')}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Codice')} (ISO)</label>
            <input className="input w-full" placeholder="en" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">{t('Bandiera')}</label>
            <div className="flex items-center gap-2">
              <input className="input w-full" list="flag-suggestions" placeholder="gb" value={form.flag_country_code} onChange={(e) => setForm({ ...form, flag_country_code: e.target.value })} />
              {form.flag_country_code && <Flag code={form.flag_country_code.trim().toLowerCase()} />}
            </div>
            <datalist id="flag-suggestions">
              {FLAG_SUGGESTIONS.map((c) => <option key={c} value={c} />)}
            </datalist>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">{t('Nome')} ({t('in italiano')})</label>
            <input className="input w-full" placeholder="Inglese" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">{t('Nome nativo')}</label>
            <input className="input w-full" placeholder="English" value={form.native_name} onChange={(e) => setForm({ ...form, native_name: e.target.value })} />
          </div>
          <label className="col-span-2 inline-flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={form.translate_all} onChange={(e) => setForm({ ...form, translate_all: e.target.checked })} />
            {t('Traduci tutte le etichette con AI')}
          </label>
        </div>
        {error && <div className="p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{error}</div>}
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">{t('Annulla')}</button>
          <button onClick={submit} disabled={loading} className="btn btn-primary gap-2">
            {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
            {t('Crea')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminLanguagesSection;
