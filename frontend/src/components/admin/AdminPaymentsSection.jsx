import { useEffect, useMemo, useState } from 'react';
import {
  CreditCard, Package, Settings as SettingsIcon, BarChart3, Loader, Check, X, Plus, Edit2, Trash2,
  Upload, AlertTriangle, RefreshCw, Search, Filter, ChevronDown,
} from 'lucide-react';
import {
  adminListPayments, adminPaymentStats, adminCancelPayment, adminRefundCredits,
  adminListCreditPackages, adminCreateCreditPackage, adminUpdateCreditPackage, adminDeleteCreditPackage,
  adminGetPagopaConfig, adminUpdatePagopaConfig, adminUploadEstrcc,
} from '../../services/api';

const formatEur = (cents) => (typeof cents === 'number'
  ? new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100)
  : '—');

const formatDate = (iso) => (iso
  ? new Date(iso).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
  : '—');

const STATUS_LABELS = {
  PENDING: 'In attesa', AWAITING_PAYMENT: 'Attesa pagamento', PAID: 'Pagato',
  FAILED: 'Fallito', CANCELED: 'Annullato', EXPIRED: 'Scaduto', REFUNDED: 'Rimborsato',
};
const STATUS_COLOR = {
  PENDING: 'bg-slate-100 text-slate-700',
  AWAITING_PAYMENT: 'bg-amber-100 text-amber-800',
  PAID: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELED: 'bg-slate-100 text-slate-600',
  EXPIRED: 'bg-slate-100 text-slate-600',
  REFUNDED: 'bg-blue-100 text-blue-800',
};

const SUB_TABS = [
  { id: 'dashboard', label: 'Cruscotto', icon: BarChart3 },
  { id: 'orders', label: 'Ordini', icon: CreditCard },
  { id: 'packages', label: 'Pacchetti', icon: Package },
  { id: 'config', label: 'Configurazione', icon: SettingsIcon },
];

// ============================================================================
// Sub-tab: Cruscotto
// ============================================================================
const DashboardSubtab = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setStats(await adminPaymentStats()); }
    catch { setError('Errore caricamento statistiche.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const maxRevenue = useMemo(() => {
    if (!stats?.daily?.length) return 0;
    return Math.max(...stats.daily.map((d) => d.revenue_cents || 0));
  }, [stats]);

  if (loading) {
    return <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
      <Loader className="w-4 h-4 animate-spin" /> Caricamento statistiche…
    </div>;
  }
  if (error) {
    return <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }
  if (!stats) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">Panoramica pagamenti</h3>
        <button onClick={load} className="btn btn-ghost text-sm gap-2">
          <RefreshCw className="w-4 h-4" /> Aggiorna
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Ricavi totali" value={formatEur(stats.revenue_cents_total)} accent="orange" />
        <KpiCard label="Ricavi 30gg" value={formatEur(stats.revenue_cents_month)} accent="emerald" />
        <KpiCard label="Ordini totali" value={stats.count_total?.toLocaleString('it-IT') ?? 0} accent="blue" />
        <KpiCard label="Tasso successo" value={`${(stats.success_rate * 100).toFixed(1)}%`} accent="purple" />
      </div>

      {/* Stati */}
      <div className="glass rounded-2xl p-5">
        <h4 className="font-medium text-slate-700 mb-3">Distribuzione per stato</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.count_by_status || {}).map(([s, c]) => (
            <span key={s} className={`px-3 py-1 rounded-lg text-sm ${STATUS_COLOR[s] || 'bg-slate-100 text-slate-600'}`}>
              {STATUS_LABELS[s] || s}: <span className="font-bold">{c}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Daily revenue (SVG bar chart) */}
      <div className="glass rounded-2xl p-5">
        <h4 className="font-medium text-slate-700 mb-3">Ricavi ultimi 30 giorni</h4>
        {(!stats.daily || stats.daily.length === 0) ? (
          <p className="text-sm text-slate-500">Nessun dato disponibile.</p>
        ) : (
          <div className="space-y-1.5">
            {stats.daily.map((d) => {
              const widthPct = maxRevenue > 0 ? Math.max(2, (d.revenue_cents / maxRevenue) * 100) : 0;
              return (
                <div key={d.date} className="flex items-center gap-3 text-xs">
                  <span className="text-slate-500 w-20 flex-shrink-0">{d.date}</span>
                  <div className="flex-1 bg-slate-100 rounded">
                    <div
                      className="bg-gradient-to-r from-orange-400 to-orange-500 h-5 rounded text-white text-[10px] flex items-center px-2"
                      style={{ width: `${widthPct}%` }}
                    >
                      {formatEur(d.revenue_cents)}
                    </div>
                  </div>
                  <span className="text-slate-400 w-12 text-right">{d.count} ord.</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const KpiCard = ({ label, value, accent = 'orange' }) => {
  const colorMap = {
    orange: 'from-orange-500 to-orange-600',
    emerald: 'from-emerald-500 to-emerald-600',
    blue: 'from-blue-500 to-blue-600',
    purple: 'from-purple-500 to-purple-600',
  };
  return (
    <div className="glass rounded-2xl p-4">
      <p className="text-xs text-slate-500 uppercase font-medium">{label}</p>
      <p className={`mt-1 text-2xl font-bold bg-gradient-to-r ${colorMap[accent]} bg-clip-text text-transparent`}>
        {value}
      </p>
    </div>
  );
};

// ============================================================================
// Sub-tab: Ordini
// ============================================================================
const OrdersSubtab = () => {
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ status: '', q: '', limit: 50, offset: 0 });
  const [actionState, setActionState] = useState({ orderId: null, kind: null });
  const [refundDialog, setRefundDialog] = useState(null); // { order, description }

  const load = async () => {
    setLoading(true);
    try {
      const params = { ...filters };
      Object.keys(params).forEach((k) => { if (!params[k]) delete params[k]; });
      const res = await adminListPayments(params);
      setOrders(res.orders || []);
      setTotal(res.total || 0);
    } catch {
      // noop
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filters.offset]);

  const handleSearch = (e) => {
    e.preventDefault();
    setFilters((f) => ({ ...f, offset: 0 }));
    setTimeout(load, 0);
  };

  const handleCancel = async (order) => {
    if (!window.confirm(`Annullare la posizione PagoPA per IUV ${order.iuv}? L'utente non potrà più pagarla.`)) return;
    setActionState({ orderId: order.id, kind: 'cancel' });
    try {
      await adminCancelPayment(order.id);
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore annullamento');
    } finally {
      setActionState({ orderId: null, kind: null });
    }
  };

  const handleRefund = async () => {
    if (!refundDialog) return;
    setActionState({ orderId: refundDialog.order.id, kind: 'refund' });
    try {
      await adminRefundCredits(refundDialog.order.id, refundDialog.description);
      setRefundDialog(null);
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore rimborso');
    } finally {
      setActionState({ orderId: null, kind: null });
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="glass rounded-xl p-3 flex gap-2 items-center flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Cerca per IUV o codice fiscale…"
            className="input flex-1"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            className="input min-w-[160px]"
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}
          >
            <option value="">Tutti gli stati</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <button type="submit" className="btn btn-primary text-sm">Filtra</button>
        <button type="button" onClick={load} className="btn btn-ghost text-sm gap-2">
          <RefreshCw className="w-4 h-4" /> Aggiorna
        </button>
      </form>

      {loading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> Caricamento ordini…
        </div>
      ) : orders.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center text-slate-500">Nessun ordine trovato.</div>
      ) : (
        <div className="glass rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left text-slate-600">
                  <th className="px-3 py-3 font-medium">Data</th>
                  <th className="px-3 py-3 font-medium">Utente</th>
                  <th className="px-3 py-3 font-medium">Crediti</th>
                  <th className="px-3 py-3 font-medium">Importo</th>
                  <th className="px-3 py-3 font-medium">CF / RS</th>
                  <th className="px-3 py-3 font-medium">IUV</th>
                  <th className="px-3 py-3 font-medium">Stato</th>
                  <th className="px-3 py-3 font-medium text-right">Azioni</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50">
                    <td className="px-3 py-3 text-slate-600 whitespace-nowrap">{formatDate(o.created_at)}</td>
                    <td className="px-3 py-3">
                      <div className="font-medium text-slate-700">{o.user_username || '—'}</div>
                      <div className="text-xs text-slate-400">{o.user_email}</div>
                    </td>
                    <td className="px-3 py-3 font-bold text-orange-600">+{o.credits}</td>
                    <td className="px-3 py-3">{formatEur(o.amount_cents)}</td>
                    <td className="px-3 py-3 text-xs text-slate-500">
                      <div className="font-mono">{o.payer_codice_fiscale}</div>
                      {o.payer_ragione_sociale && <div>{o.payer_ragione_sociale}</div>}
                    </td>
                    <td className="px-3 py-3 text-xs font-mono text-slate-500">{o.iuv ? `${o.iuv.substring(0, 12)}…` : '—'}</td>
                    <td className="px-3 py-3">
                      <span className={`inline-block px-2 py-1 rounded-md text-xs font-medium ${STATUS_COLOR[o.status] || ''}`}>
                        {STATUS_LABELS[o.status] || o.status}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        {(o.status === 'PENDING' || o.status === 'AWAITING_PAYMENT') && (
                          <button
                            type="button"
                            disabled={actionState.orderId === o.id}
                            onClick={() => handleCancel(o)}
                            className="btn btn-ghost text-xs"
                            title="Annulla posizione"
                          >
                            {actionState.orderId === o.id && actionState.kind === 'cancel'
                              ? <Loader className="w-3 h-3 animate-spin" />
                              : 'Annulla'}
                          </button>
                        )}
                        {o.status === 'PAID' && (
                          <button
                            type="button"
                            onClick={() => setRefundDialog({ order: o, description: '' })}
                            className="btn btn-ghost text-xs text-red-600 hover:bg-red-50"
                            title="Rimborso interno"
                          >
                            Rimborsa
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 text-xs text-slate-500 border-t border-slate-200 bg-slate-50">
            Totale: {total} ordini
          </div>
        </div>
      )}

      {refundDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-lg text-slate-900">Rimborso interno</h3>
            <p className="text-sm text-slate-600">
              Verranno scalati <b>{refundDialog.order.credits}</b> crediti dall'utente e l'ordine sarà marcato come REFUNDED.
              <strong className="block mt-1 text-amber-700">
                Lo storno bancario su PagoPA va gestito manualmente (questo è solo un rimborso interno crediti).
              </strong>
            </p>
            <textarea
              className="input w-full min-h-[80px]"
              placeholder="Motivo del rimborso (obbligatorio)"
              value={refundDialog.description}
              onChange={(e) => setRefundDialog({ ...refundDialog, description: e.target.value })}
            />
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setRefundDialog(null)} className="btn btn-secondary">Annulla</button>
              <button
                type="button"
                disabled={!refundDialog.description?.trim() || actionState.kind === 'refund'}
                onClick={handleRefund}
                className="btn btn-danger"
              >
                {actionState.kind === 'refund' ? <Loader className="w-4 h-4 animate-spin" /> : 'Conferma rimborso'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Sub-tab: Pacchetti
// ============================================================================
const PackagesSubtab = () => {
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
    };
    if (!payload.name || !payload.credits || !payload.price_cents) {
      alert('Compila tutti i campi obbligatori.');
      return;
    }
    try {
      if (form.id) await adminUpdateCreditPackage(form.id, payload);
      else await adminCreateCreditPackage(payload);
      setEditing(null);
      load();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore salvataggio pacchetto');
    }
  };

  const handleDelete = async (pkg) => {
    if (!window.confirm(`Eliminare il pacchetto "${pkg.name}"? Se ci sono ordini collegati verrà solo disattivato.`)) return;
    try {
      await adminDeleteCreditPackage(pkg.id);
      load();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore eliminazione');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">Pacchetti acquistabili</h3>
        <button onClick={() => setEditing({ is_active: true, sort_order: (packages.length + 1) * 10 })} className="btn btn-primary text-sm gap-2">
          <Plus className="w-4 h-4" /> Nuovo pacchetto
        </button>
      </div>

      {loading ? (
        <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
          <Loader className="w-4 h-4 animate-spin" /> Caricamento…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {packages.map((p) => (
            <div key={p.id} className={`glass rounded-2xl p-5 border-2 ${p.is_active ? 'border-emerald-200' : 'border-slate-200 opacity-60'}`}>
              <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                  <p className="text-xs text-slate-500 uppercase font-medium">{p.name}</p>
                  <p className="text-2xl font-bold text-slate-900">{p.credits.toLocaleString('it-IT')}</p>
                  <p className="text-xs text-slate-400">crediti · ordine {p.sort_order}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${p.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                  {p.is_active ? 'Attivo' : 'Inattivo'}
                </span>
              </div>
              <p className="text-xl font-bold text-orange-600">{formatEur(p.price_cents)}</p>
              {p.description && <p className="text-xs text-slate-500 mt-2">{p.description}</p>}
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => setEditing({ ...p, price_eur: (p.price_cents / 100).toFixed(2) })}
                  className="btn btn-secondary text-xs gap-1 flex-1"
                >
                  <Edit2 className="w-3 h-3" /> Modifica
                </button>
                <button
                  onClick={() => handleDelete(p)}
                  className="btn btn-ghost text-xs text-red-600 hover:bg-red-50"
                  title="Elimina"
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

const PackageEditDialog = ({ pkg, onSave, onClose }) => {
  const [form, setForm] = useState({
    id: pkg.id,
    name: pkg.name || '',
    credits: pkg.credits || 100,
    price_eur: pkg.price_eur != null ? String(pkg.price_eur) : (pkg.price_cents != null ? (pkg.price_cents / 100).toFixed(2) : '10.00'),
    is_active: pkg.is_active !== false,
    sort_order: pkg.sort_order || 0,
    description: pkg.description || '',
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-900">{form.id ? 'Modifica pacchetto' : 'Nuovo pacchetto'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-5 h-5" /></button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">Nome</label>
            <input className="input w-full" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">Crediti</label>
            <input type="number" className="input w-full" value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value })} min={1} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">Prezzo (EUR)</label>
            <input type="number" step="0.01" className="input w-full" value={form.price_eur} onChange={(e) => setForm({ ...form, price_eur: e.target.value })} min={0.01} />
          </div>
          <div>
            <label className="text-xs text-slate-600 font-medium">Ordine</label>
            <input type="number" className="input w-full" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: e.target.value })} />
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                className="rounded text-orange-500"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Attivo
            </label>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-slate-600 font-medium">Descrizione (opzionale)</label>
            <textarea className="input w-full min-h-[60px]" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">Annulla</button>
          <button onClick={() => onSave(form)} className="btn btn-primary inline-flex gap-2">
            <Check className="w-4 h-4" /> Salva
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Sub-tab: Configurazione
// ============================================================================
const ConfigSubtab = () => {
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingTest, setSavingTest] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try { setCfg(await adminGetPagopaConfig()); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const toggleTestMode = async () => {
    if (!cfg) return;
    setSavingTest(true);
    try {
      const updated = await adminUpdatePagopaConfig({ test_mode: !cfg.test_mode });
      setCfg(updated);
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore aggiornamento configurazione');
    } finally {
      setSavingTest(false);
    }
  };

  const handleUploadFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await adminUploadEstrcc(file);
      setUploadResult(res);
    } catch (err) {
      alert(err?.response?.data?.detail || 'Errore upload riconciliazione');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  if (loading) {
    return <div className="glass rounded-2xl p-8 flex items-center justify-center gap-2 text-slate-500">
      <Loader className="w-4 h-4 animate-spin" /> Caricamento configurazione…
    </div>;
  }
  if (!cfg) return null;

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900">Connessione SolutionPA</h3>
          <button
            onClick={toggleTestMode}
            disabled={savingTest}
            className={`btn ${cfg.test_mode ? 'btn-secondary' : 'btn-primary'} text-sm gap-2`}
          >
            {savingTest && <Loader className="w-4 h-4 animate-spin" />}
            {cfg.test_mode ? 'Modalità TEST attiva' : 'Modalità PRODUZIONE'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <ConfigRow label="WSDL URL" value={cfg.wsdl_url} mono />
          <ConfigRow label="Dominio (Codice Ente)" value={cfg.dominio || <em className="text-red-600">non configurato</em>} mono />
          <ConfigRow label="UB (Unità Beneficiaria)" value={cfg.ub || <em className="text-red-600">non configurato</em>} mono />
          <ConfigRow label="Codice Tributo" value={cfg.cod_tributo || <em className="text-red-600">non configurato</em>} mono />
          <ConfigRow label="Username (mascherato)" value={cfg.username_masked || <em className="text-red-600">non configurato</em>} mono />
          <ConfigRow label="Password" value={cfg.password_set ? 'Impostata ✓' : <em className="text-red-600">non configurata</em>} />
          <ConfigRow label="Return URL" value={cfg.return_url_base || <em className="text-red-600">non configurato</em>} mono />
          <ConfigRow
            label="Webhook auth"
            value={(cfg.notify_username_set && cfg.notify_password_set)
              ? 'Configurata ✓'
              : <em className="text-red-600">non configurata</em>}
          />
        </div>
        <p className="text-xs text-slate-500 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          Le credenziali vengono lette dalle variabili d'ambiente al boot del server (PAGOPA_USERNAME, PAGOPA_PASSWORD,
          PAGOPA_DOMINIO, PAGOPA_UB, PAGOPA_COD_TRIBUTO, PAGOPA_NOTIFY_AUTH_USER, PAGOPA_NOTIFY_AUTH_PASS).
          Modificarle richiede un riavvio. Il toggle TEST/PROD si applica al volo (resetta la cache del client SOAP).
        </p>
      </div>

      <div className="glass rounded-2xl p-5 space-y-3">
        <h3 className="font-semibold text-slate-900">Riconciliazione (estrcc XML)</h3>
        <p className="text-sm text-slate-600">
          Carica il file giornaliero di riconciliazione fornito da SolutionPA. Verranno confrontati gli IUV con gli ordini e segnalate eventuali discrepanze sull'importo.
        </p>
        <label className="btn btn-primary inline-flex items-center gap-2 cursor-pointer">
          <Upload className="w-4 h-4" />
          {uploading ? 'Caricamento…' : 'Seleziona file XML'}
          <input type="file" accept=".xml,application/xml,text/xml" className="hidden" onChange={handleUploadFile} disabled={uploading} />
        </label>

        {uploadResult && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KpiCard label="Righe" value={uploadResult.parsed} accent="blue" />
              <KpiCard label="Match" value={uploadResult.matched} accent="emerald" />
              <KpiCard label="Senza match" value={uploadResult.unmatched} accent="orange" />
              <KpiCard label="Discrepanze" value={uploadResult.discrepancies} accent="purple" />
            </div>
            {uploadResult.discrepancies > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-800 text-xs">
                Trovate {uploadResult.discrepancies} righe con importo non corrispondente. Controlla manualmente gli ordini coinvolti.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const ConfigRow = ({ label, value, mono = false }) => (
  <div className="flex flex-col">
    <span className="text-xs uppercase text-slate-500 font-medium">{label}</span>
    <span className={`text-slate-700 ${mono ? 'font-mono text-xs' : ''} break-all`}>{value}</span>
  </div>
);

// ============================================================================
// Componente principale
// ============================================================================
const AdminPaymentsSection = () => {
  const [activeSub, setActiveSub] = useState('dashboard');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1 w-fit flex-wrap">
        {SUB_TABS.map((t) => {
          const Icon = t.icon;
          const active = activeSub === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveSub(t.id)}
              className={`px-3 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2 transition-colors ${
                active ? 'bg-white text-orange-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      <div>
        {activeSub === 'dashboard' && <DashboardSubtab />}
        {activeSub === 'orders' && <OrdersSubtab />}
        {activeSub === 'packages' && <PackagesSubtab />}
        {activeSub === 'config' && <ConfigSubtab />}
      </div>
    </div>
  );
};

export default AdminPaymentsSection;
