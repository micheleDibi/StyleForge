import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Shield, BarChart3, Search, RefreshCw,
  ChevronDown, ChevronUp, Edit3, Save, X, Plus, Minus,
  Coins, CheckCircle2, AlertCircle, Clock, User as UserIcon,
  Sparkles, Settings
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getAdminUsers, updateAdminUser, updateUserRole,
  updateUserPermissions, adjustUserCredits, getUserTransactions,
  getAdminRoles, updateRolePermissions, getAdminStats
} from '../services/api';
import Logo from '../components/Logo';

const PERMISSION_LABELS = {
  train: 'Addestra Modello',
  generate: 'Genera Contenuto',
  humanize: 'Umanizza Testo',
  thesis: 'Tesi / Relazione'
};

const ALL_PERMISSIONS = ['train', 'generate', 'humanize', 'thesis'];

const Admin = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Users state
  const [users, setUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedUser, setExpandedUser] = useState(null);

  // Roles state
  const [roles, setRoles] = useState([]);

  // Stats state
  const [stats, setStats] = useState(null);

  // Credit adjustment state
  const [creditAmount, setCreditAmount] = useState('');
  const [creditDescription, setCreditDescription] = useState('');
  const [creditLoading, setCreditLoading] = useState(false);

  // Transactions state
  const [transactions, setTransactions] = useState({});

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'users') {
        const data = await getAdminUsers(searchTerm || null);
        setUsers(data.users);
      } else if (activeTab === 'roles') {
        const data = await getAdminRoles();
        setRoles(data.roles);
      } else if (activeTab === 'stats') {
        const data = await getAdminStats();
        setStats(data);
      }
    } catch (error) {
      console.error('Errore caricamento dati:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleSearch = async () => {
    setRefreshing(true);
    try {
      const data = await getAdminUsers(searchTerm || null);
      setUsers(data.users);
    } catch (error) {
      console.error('Errore ricerca:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const handleToggleActive = async (userId, currentActive) => {
    try {
      const updated = await updateAdminUser(userId, { is_active: !currentActive });
      setUsers(users.map(u => u.id === userId ? updated : u));
    } catch (error) {
      console.error('Errore aggiornamento:', error);
    }
  };

  const handleRoleChange = async (userId, roleId) => {
    try {
      const updated = await updateUserRole(userId, roleId);
      setUsers(users.map(u => u.id === userId ? updated : u));
    } catch (error) {
      console.error('Errore cambio ruolo:', error);
    }
  };

  const handlePermissionToggle = async (userId, permCode, currentOverrides) => {
    // Ciclo: undefined (eredita) -> true (forza si) -> false (forza no) -> null (rimuovi) -> ...
    const current = currentOverrides[permCode];
    let newValue;
    if (current === undefined) newValue = true;
    else if (current === true) newValue = false;
    else newValue = null; // rimuovi override

    try {
      const updated = await updateUserPermissions(userId, { [permCode]: newValue });
      setUsers(users.map(u => u.id === userId ? updated : u));
    } catch (error) {
      console.error('Errore aggiornamento permessi:', error);
    }
  };

  const handleAdjustCredits = async (userId) => {
    if (!creditAmount || !creditDescription) return;
    setCreditLoading(true);
    try {
      const updated = await adjustUserCredits(userId, parseInt(creditAmount), creditDescription);
      setUsers(users.map(u => u.id === userId ? updated : u));
      setCreditAmount('');
      setCreditDescription('');
    } catch (error) {
      console.error('Errore crediti:', error);
    } finally {
      setCreditLoading(false);
    }
  };

  const handleLoadTransactions = async (userId) => {
    try {
      const data = await getUserTransactions(userId);
      setTransactions(prev => ({ ...prev, [userId]: data.transactions }));
    } catch (error) {
      console.error('Errore caricamento transazioni:', error);
    }
  };

  const handleUpdateRolePermissions = async (roleId, permissions) => {
    try {
      const updated = await updateRolePermissions(roleId, permissions);
      setRoles(roles.map(r => r.id === roleId ? updated : r));
    } catch (error) {
      console.error('Errore aggiornamento permessi ruolo:', error);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Mai';
    return new Date(dateString).toLocaleDateString('it-IT', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const tabs = [
    { id: 'users', label: 'Utenti', icon: Users },
    { id: 'roles', label: 'Ruoli', icon: Shield },
    { id: 'stats', label: 'Statistiche', icon: BarChart3 }
  ];

  return (
    <div className="min-h-screen relative">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-orange-100 to-orange-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-to-br from-purple-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
      </div>

      {/* Header */}
      <header className="relative z-10 glass border-b border-white/20">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/')} className="btn btn-ghost">
                <ArrowLeft className="w-4 h-4" />
                Dashboard
              </button>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl blur-lg opacity-50"></div>
                  <Logo size="md" className="relative" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">
                    Pannello <span className="gradient-text">Admin</span>
                  </h1>
                  <p className="text-gray-500 text-sm">Gestione utenti, ruoli e crediti</p>
                </div>
              </div>
            </div>

            <button
              onClick={() => { setRefreshing(true); loadData(); }}
              className="btn btn-secondary"
              disabled={refreshing}
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Aggiorna
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-8">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 rounded-xl font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/30'
                  : 'bg-white/70 text-gray-600 hover:bg-white hover:shadow-md'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="loading-dots text-orange-600">
              <span></span><span></span><span></span>
            </div>
          </div>
        ) : (
          <>
            {/* ===================== TAB UTENTI ===================== */}
            {activeTab === 'users' && (
              <div className="space-y-4">
                {/* Search */}
                <div className="glass rounded-2xl p-4">
                  <div className="flex gap-3">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Cerca per username, email o nome..."
                        className="input pl-10 w-full"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      />
                    </div>
                    <button onClick={handleSearch} className="btn btn-primary">
                      <Search className="w-4 h-4" />
                      Cerca
                    </button>
                  </div>
                </div>

                {/* Users list */}
                <div className="space-y-3">
                  {users.map(u => (
                    <div key={u.id} className="glass rounded-2xl overflow-hidden">
                      {/* User row */}
                      <div
                        className="p-4 cursor-pointer hover:bg-white/50 transition-colors"
                        onClick={() => {
                          setExpandedUser(expandedUser === u.id ? null : u.id);
                          if (expandedUser !== u.id && !transactions[u.id]) {
                            handleLoadTransactions(u.id);
                          }
                        }}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                            u.role_name === 'admin'
                              ? 'bg-gradient-to-br from-orange-400 to-orange-600'
                              : 'bg-gradient-to-br from-blue-400 to-blue-600'
                          }`}>
                            {u.role_name === 'admin' ? (
                              <Shield className="w-5 h-5 text-white" />
                            ) : (
                              <UserIcon className="w-5 h-5 text-white" />
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-gray-900">{u.username}</span>
                              <span className={`badge ${u.role_name === 'admin' ? 'badge-warning' : 'badge-info'}`}>
                                {u.role_name || 'Nessun ruolo'}
                              </span>
                              {!u.is_active && (
                                <span className="badge badge-error">Disabilitato</span>
                              )}
                            </div>
                            <div className="text-sm text-gray-500">{u.email}</div>
                          </div>

                          <div className="hidden md:flex items-center gap-6 text-sm">
                            <div className="text-center">
                              <p className="font-bold text-gray-900">
                                {u.credits === -1 ? '∞' : u.credits}
                              </p>
                              <p className="text-gray-500 text-xs">Crediti</p>
                            </div>
                            <div className="text-center">
                              <p className="text-gray-600 text-xs">{formatDate(u.last_login)}</p>
                              <p className="text-gray-500 text-xs">Ultimo login</p>
                            </div>
                          </div>

                          {expandedUser === u.id ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                      </div>

                      {/* Expanded user details */}
                      {expandedUser === u.id && (
                        <div className="border-t border-gray-200 p-4 bg-gray-50/50 space-y-4">
                          {/* Info */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div className="bg-white rounded-xl p-3">
                              <p className="text-xs text-gray-500">Nome completo</p>
                              <p className="font-medium text-gray-900">{u.full_name || '-'}</p>
                            </div>
                            <div className="bg-white rounded-xl p-3">
                              <p className="text-xs text-gray-500">Creato il</p>
                              <p className="font-medium text-gray-900 text-sm">{formatDate(u.created_at)}</p>
                            </div>
                            <div className="bg-white rounded-xl p-3">
                              <p className="text-xs text-gray-500">Ultimo aggiornamento</p>
                              <p className="font-medium text-gray-900 text-sm">{formatDate(u.updated_at)}</p>
                            </div>
                            <div className="bg-white rounded-xl p-3">
                              <p className="text-xs text-gray-500">Ultimo login</p>
                              <p className="font-medium text-gray-900 text-sm">{formatDate(u.last_login)}</p>
                            </div>
                          </div>

                          {/* Ruolo & Stato */}
                          <div className="flex flex-wrap gap-3">
                            <div className="bg-white rounded-xl p-3 flex items-center gap-3">
                              <label className="text-sm font-medium text-gray-600">Ruolo:</label>
                              <select
                                className="input py-1 px-2 text-sm"
                                value={u.role_id || ''}
                                onChange={(e) => handleRoleChange(u.id, parseInt(e.target.value))}
                              >
                                {roles.length > 0 ? roles.map(r => (
                                  <option key={r.id} value={r.id}>{r.name}</option>
                                )) : (
                                  <>
                                    <option value="1">admin</option>
                                    <option value="2">user</option>
                                  </>
                                )}
                              </select>
                            </div>

                            <div className="bg-white rounded-xl p-3 flex items-center gap-3">
                              <label className="text-sm font-medium text-gray-600">Attivo:</label>
                              <button
                                onClick={() => handleToggleActive(u.id, u.is_active)}
                                className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                                  u.is_active
                                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                    : 'bg-red-100 text-red-700 hover:bg-red-200'
                                }`}
                              >
                                {u.is_active ? 'Si' : 'No'}
                              </button>
                            </div>
                          </div>

                          {/* Permessi */}
                          <div className="bg-white rounded-xl p-4">
                            <h4 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
                              <Shield className="w-4 h-4" />
                              Permessi (click per ciclare: Eredita &rarr; Forza Si &rarr; Forza No)
                            </h4>
                            <div className="flex flex-wrap gap-2">
                              {ALL_PERMISSIONS.map(perm => {
                                const override = u.user_overrides[perm];
                                const hasFromRole = u.permissions.includes(perm);
                                let bgClass, label;

                                if (override === true) {
                                  bgClass = 'bg-green-100 text-green-800 border-green-300';
                                  label = `${PERMISSION_LABELS[perm]} [Forzato SI]`;
                                } else if (override === false) {
                                  bgClass = 'bg-red-100 text-red-800 border-red-300';
                                  label = `${PERMISSION_LABELS[perm]} [Forzato NO]`;
                                } else {
                                  bgClass = hasFromRole
                                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                                    : 'bg-gray-100 text-gray-500 border-gray-200';
                                  label = `${PERMISSION_LABELS[perm]} [Ruolo: ${hasFromRole ? 'Si' : 'No'}]`;
                                }

                                return (
                                  <button
                                    key={perm}
                                    onClick={() => handlePermissionToggle(u.id, perm, u.user_overrides)}
                                    className={`px-3 py-2 rounded-lg text-sm font-medium border transition-all hover:shadow-sm ${bgClass}`}
                                  >
                                    {label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>

                          {/* Crediti */}
                          <div className="bg-white rounded-xl p-4">
                            <h4 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
                              <Coins className="w-4 h-4" />
                              Gestione Crediti (Saldo attuale: <span className="text-orange-600">{u.credits === -1 ? 'Infinito' : u.credits}</span>)
                            </h4>
                            <div className="flex gap-2">
                              <input
                                type="number"
                                placeholder="Quantita (es. 100 o -50)"
                                className="input flex-1"
                                value={creditAmount}
                                onChange={(e) => setCreditAmount(e.target.value)}
                              />
                              <input
                                type="text"
                                placeholder="Motivazione..."
                                className="input flex-1"
                                value={creditDescription}
                                onChange={(e) => setCreditDescription(e.target.value)}
                              />
                              <button
                                onClick={() => handleAdjustCredits(u.id)}
                                disabled={!creditAmount || !creditDescription || creditLoading}
                                className="btn btn-primary"
                              >
                                {creditLoading ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Coins className="w-4 h-4" />
                                )}
                                Applica
                              </button>
                            </div>
                          </div>

                          {/* Storico transazioni */}
                          {transactions[u.id] && transactions[u.id].length > 0 && (
                            <div className="bg-white rounded-xl p-4">
                              <h4 className="text-sm font-bold text-gray-700 mb-3">
                                Ultime Transazioni
                              </h4>
                              <div className="space-y-2 max-h-60 overflow-y-auto">
                                {transactions[u.id].slice(0, 10).map((tx, i) => (
                                  <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm text-gray-900 truncate">{tx.description}</p>
                                      <p className="text-xs text-gray-500">{formatDate(tx.created_at)}</p>
                                    </div>
                                    <div className={`font-bold text-sm ${tx.amount > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                      {tx.amount > 0 ? '+' : ''}{tx.amount}
                                    </div>
                                    <div className="text-xs text-gray-400 ml-3 w-16 text-right">
                                      = {tx.balance_after}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}

                  {users.length === 0 && (
                    <div className="glass rounded-2xl p-8 text-center">
                      <UserIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                      <p className="text-gray-500">Nessun utente trovato</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ===================== TAB RUOLI ===================== */}
            {activeTab === 'roles' && (
              <div className="space-y-4">
                {roles.map(role => (
                  <div key={role.id} className="glass rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                          role.name === 'admin'
                            ? 'bg-gradient-to-br from-orange-400 to-orange-600'
                            : 'bg-gradient-to-br from-blue-400 to-blue-600'
                        }`}>
                          <Shield className="w-6 h-6 text-white" />
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-gray-900 capitalize">{role.name}</h3>
                          <p className="text-sm text-gray-500">{role.description}</p>
                          {role.is_default && (
                            <span className="badge badge-success mt-1">Ruolo Default</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <h4 className="text-sm font-medium text-gray-600 mb-3">Permessi assegnati:</h4>
                    <div className="flex flex-wrap gap-2">
                      {ALL_PERMISSIONS.map(perm => {
                        const hasIt = role.permissions.includes(perm);
                        return (
                          <button
                            key={perm}
                            onClick={() => {
                              const newPerms = hasIt
                                ? role.permissions.filter(p => p !== perm)
                                : [...role.permissions, perm];
                              handleUpdateRolePermissions(role.id, newPerms);
                            }}
                            className={`px-4 py-2 rounded-xl text-sm font-medium border-2 transition-all ${
                              hasIt
                                ? 'bg-green-50 text-green-700 border-green-300 hover:bg-green-100'
                                : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'
                            }`}
                          >
                            {hasIt ? <CheckCircle2 className="w-4 h-4 inline mr-1" /> : null}
                            {PERMISSION_LABELS[perm]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ===================== TAB STATISTICHE ===================== */}
            {activeTab === 'stats' && stats && (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center">
                      <Users className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Utenti Totali</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.total_users}</p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-green-400 to-green-600 rounded-xl flex items-center justify-center">
                      <CheckCircle2 className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Utenti Attivi</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.active_users}</p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl flex items-center justify-center">
                      <Coins className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Crediti Distribuiti</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.total_credits_distributed?.toLocaleString()}</p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-red-400 to-red-600 rounded-xl flex items-center justify-center">
                      <Minus className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Crediti Consumati</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.total_credits_consumed?.toLocaleString()}</p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-purple-400 to-purple-600 rounded-xl flex items-center justify-center">
                      <Sparkles className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Operazioni Oggi</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.operations_today}</p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 bg-gradient-to-br from-teal-400 to-teal-600 rounded-xl flex items-center justify-center">
                      <BarChart3 className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase">Operazioni Settimana</p>
                      <p className="text-3xl font-bold text-gray-900">{stats.operations_this_week}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default Admin;
