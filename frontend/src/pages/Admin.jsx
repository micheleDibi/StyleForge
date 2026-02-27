import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Shield, BarChart3, Search, RefreshCw,
  ChevronDown, ChevronUp, Edit3, Save, X, Plus, Minus,
  Coins, CheckCircle2, AlertCircle, Clock, User as UserIcon,
  Sparkles, Settings, Eye, EyeOff, UserPlus, RotateCcw,
  AlertTriangle, FileText, HelpCircle, Copy, Trash2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getAdminUsers, updateAdminUser, updateUserRole,
  updateUserPermissions, adjustUserCredits, getUserTransactions,
  getAdminRoles, updateRolePermissions, getAdminStats,
  adminCreateUser, getAdminCreditCosts, updateAdminCreditCosts,
  resetAdminCreditCosts, getAdminTemplates, updateAdminTemplates,
  deleteAdminTemplate
} from '../services/api';
import Logo from '../components/Logo';

const PERMISSION_LABELS = {
  train: 'Addestra Modello',
  generate: 'Genera Contenuto',
  humanize: 'Umanizza Testo',
  thesis: 'Tesi / Relazione',
  manage_templates: 'Gestione Template',
  compilatio_scan: 'Detector AI',
  enhance_image: 'Migliora Immagine',
  carousel_creator: 'Carosello / Post / Copertina'
};

const ALL_PERMISSIONS = ['train', 'generate', 'humanize', 'thesis', 'manage_templates', 'compilatio_scan', 'enhance_image', 'carousel_creator'];

// Labels per le operazioni dei costi crediti
const COST_OPERATION_LABELS = {
  train: { label: 'Training', icon: '🎓', fields: { base: 'Costo base', per_page: 'Per pagina PDF' } },
  generate: { label: 'Generazione Contenuto', icon: '✍️', fields: { base: 'Costo base', per_1000_words: 'Per 1000 parole' } },
  humanize: { label: 'Umanizzazione', icon: '🤖', fields: { base: 'Costo base', per_1000_chars: 'Per 1000 caratteri' } },
  thesis_chapters: { label: 'Tesi - Capitoli', icon: '📚', fields: { base: 'Costo base' } },
  thesis_sections: { label: 'Tesi - Sezioni', icon: '📄', fields: { base: 'Costo base' } },
  thesis_content: { label: 'Tesi - Contenuto', icon: '📝', fields: { base: 'Costo base', per_chapter: 'Per capitolo', per_section: 'Per sezione', per_1000_words_target: 'Per 1000 parole target' } },
  compilatio_scan: { label: 'Detector AI', icon: '🔍', fields: { base: 'Costo base', per_1000_chars: 'Per 1000 caratteri' } },
  enhance_image: { label: 'Migliora Immagine', icon: '🖼️', fields: { base: 'Costo base' } },
  carousel_creator: { label: 'Carosello / Post / Copertina', icon: '📱', fields: { base: 'Costo base', image_enhance: 'Enhancement immagine' } }
};

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

  // Create user state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [newUser, setNewUser] = useState({
    email: '', username: '', password: '', full_name: '',
    role_id: '', credits: 0, is_active: true
  });

  // Settings state
  const [creditCosts, setCreditCosts] = useState(null);
  const [editedCosts, setEditedCosts] = useState(null);
  const [isDefaultCosts, setIsDefaultCosts] = useState(true);
  const [costsSaving, setCostsSaving] = useState(false);
  const [costsError, setCostsError] = useState('');
  const [costsSuccess, setCostsSuccess] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  // Template state
  const [templates, setTemplates] = useState([]);
  const [templateHelp, setTemplateHelp] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editedTemplate, setEditedTemplate] = useState(null);
  const [templateSection, setTemplateSection] = useState('pdf');
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateError, setTemplateError] = useState('');
  const [templateSuccess, setTemplateSuccess] = useState('');
  const [showDeleteTemplate, setShowDeleteTemplate] = useState(null);
  const [activeTooltip, setActiveTooltip] = useState(null);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  // Carica i ruoli una volta per il form di creazione utente
  useEffect(() => {
    if (roles.length === 0) {
      getAdminRoles().then(data => setRoles(data.roles)).catch(() => {});
    }
  }, []);

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
      } else if (activeTab === 'settings') {
        const data = await getAdminCreditCosts();
        setCreditCosts(data.costs);
        setEditedCosts(JSON.parse(JSON.stringify(data.costs)));
        setIsDefaultCosts(data.is_default);
      } else if (activeTab === 'templates') {
        const data = await getAdminTemplates();
        setTemplates(data.templates || []);
        if (data.help) setTemplateHelp(data.help);
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
      const updated = await updateUserRole(userId, parseInt(roleId));
      setUsers(users.map(u => u.id === userId ? updated : u));
    } catch (error) {
      console.error('Errore cambio ruolo:', error);
    }
  };

  const handlePermissionToggle = async (userId, permCode, currentOverrides) => {
    const current = currentOverrides[permCode];
    let newValue;
    if (current === undefined) newValue = true;
    else if (current === true) newValue = false;
    else newValue = null;

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

  // ========== CREATE USER ==========

  const handleCreateUser = async () => {
    setCreateError('');
    if (!newUser.email || !newUser.username || !newUser.password) {
      setCreateError('Email, username e password sono obbligatori.');
      return;
    }

    setCreateLoading(true);
    try {
      const userData = {
        ...newUser,
        role_id: newUser.role_id ? parseInt(newUser.role_id) : null,
        credits: parseInt(newUser.credits) || 0
      };
      await adminCreateUser(userData);

      // Reset form e aggiorna lista
      setNewUser({ email: '', username: '', password: '', full_name: '', role_id: '', credits: 0, is_active: true });
      setShowCreateForm(false);
      const data = await getAdminUsers(searchTerm || null);
      setUsers(data.users);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Errore durante la creazione dell\'utente.';
      setCreateError(detail);
    } finally {
      setCreateLoading(false);
    }
  };

  // ========== CREDIT COSTS SETTINGS ==========

  const handleCostChange = (opType, field, value) => {
    const numValue = parseFloat(value) || 0;
    setEditedCosts(prev => ({
      ...prev,
      [opType]: {
        ...prev[opType],
        [field]: numValue
      }
    }));
  };

  const handleSaveCosts = async () => {
    setCostsSaving(true);
    setCostsError('');
    setCostsSuccess('');
    try {
      const data = await updateAdminCreditCosts(editedCosts);
      setCreditCosts(data.costs);
      setEditedCosts(JSON.parse(JSON.stringify(data.costs)));
      setIsDefaultCosts(data.is_default);
      setCostsSuccess('Costi aggiornati con successo!');
      setTimeout(() => setCostsSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Errore nel salvataggio dei costi.';
      setCostsError(detail);
    } finally {
      setCostsSaving(false);
    }
  };

  const handleResetCosts = async () => {
    setCostsSaving(true);
    setCostsError('');
    setCostsSuccess('');
    try {
      const data = await resetAdminCreditCosts();
      setCreditCosts(data.costs);
      setEditedCosts(JSON.parse(JSON.stringify(data.costs)));
      setIsDefaultCosts(data.is_default);
      setShowResetConfirm(false);
      setCostsSuccess('Costi ripristinati ai valori default!');
      setTimeout(() => setCostsSuccess(''), 3000);
    } catch (error) {
      setCostsError('Errore nel ripristino dei costi.');
    } finally {
      setCostsSaving(false);
    }
  };

  const hasUnsavedCostChanges = () => {
    if (!creditCosts || !editedCosts) return false;
    return JSON.stringify(creditCosts) !== JSON.stringify(editedCosts);
  };

  // ========== TEMPLATE HANDLERS ==========

  const handleEditTemplate = (template) => {
    setEditingTemplate(template.id);
    setEditedTemplate(JSON.parse(JSON.stringify(template)));
    setTemplateSection('pdf');
    setTemplateError('');
    setTemplateSuccess('');
  };

  const handleCancelEditTemplate = () => {
    setEditingTemplate(null);
    setEditedTemplate(null);
    setTemplateError('');
  };

  const handleTemplateFieldChange = (section, field, value) => {
    setEditedTemplate(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));
  };

  const handleSaveTemplate = async () => {
    setTemplateSaving(true);
    setTemplateError('');
    setTemplateSuccess('');
    try {
      const updatedTemplates = templates.map(t =>
        t.id === editedTemplate.id ? editedTemplate : t
      );
      const data = await updateAdminTemplates(updatedTemplates);
      setTemplates(data.templates || []);
      setEditingTemplate(null);
      setEditedTemplate(null);
      setTemplateSuccess('Template salvato con successo!');
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Errore nel salvataggio del template.';
      setTemplateError(detail);
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleCreateTemplate = async () => {
    setTemplateSaving(true);
    setTemplateError('');
    try {
      // Crea una copia del template default
      const defaultTpl = templates.find(t => t.is_default) || templates[0];
      const newTemplate = {
        ...JSON.parse(JSON.stringify(defaultTpl)),
        id: `tpl-${Date.now().toString(36)}`,
        name: `Nuovo Template ${templates.length + 1}`,
        is_default: false
      };
      const updatedTemplates = [...templates, newTemplate];
      const data = await updateAdminTemplates(updatedTemplates);
      setTemplates(data.templates || []);
      handleEditTemplate(newTemplate);
      setTemplateSuccess('Nuovo template creato!');
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Errore nella creazione del template.';
      setTemplateError(detail);
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    setTemplateSaving(true);
    setTemplateError('');
    try {
      const data = await deleteAdminTemplate(templateId);
      setTemplates(data.templates || []);
      setShowDeleteTemplate(null);
      if (editingTemplate === templateId) {
        setEditingTemplate(null);
        setEditedTemplate(null);
      }
      setTemplateSuccess('Template eliminato!');
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Errore nell\'eliminazione del template.';
      setTemplateError(detail);
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleSetDefaultTemplate = async (templateId) => {
    setTemplateSaving(true);
    setTemplateError('');
    try {
      const updatedTemplates = templates.map(t => ({
        ...t,
        is_default: t.id === templateId
      }));
      const data = await updateAdminTemplates(updatedTemplates);
      setTemplates(data.templates || []);
      setTemplateSuccess('Template impostato come default!');
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      setTemplateError('Errore nell\'impostazione del template default.');
    } finally {
      setTemplateSaving(false);
    }
  };

  const renderTemplateField = (section, fieldKey, helpData) => {
    if (!editedTemplate || !helpData) return null;
    const value = editedTemplate[section]?.[fieldKey];
    const help = helpData;
    const tooltipId = `${section}-${fieldKey}`;

    return (
      <div key={fieldKey} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <label className="text-sm font-medium text-gray-700">{help.label}</label>
            <button
              type="button"
              onClick={() => setActiveTooltip(activeTooltip === tooltipId ? null : tooltipId)}
              className="text-gray-400 hover:text-orange-500 transition-colors"
              title="Mostra info"
            >
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          {activeTooltip === tooltipId && (
            <div className="mt-1.5 p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800">
              <p className="font-medium mb-1">{help.description}</p>
              <p className="text-blue-600 italic">{help.example}</p>
            </div>
          )}
        </div>
        <div className="flex-shrink-0 w-40">
          {help.type === 'select' ? (
            <select
              className="input w-full text-sm py-1.5"
              value={value ?? help.default}
              onChange={(e) => handleTemplateFieldChange(section, fieldKey, e.target.value)}
            >
              {help.options?.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : help.type === 'boolean' ? (
            <button
              type="button"
              onClick={() => handleTemplateFieldChange(section, fieldKey, !value)}
              className={`w-full px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                value
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {value ? 'Attivo' : 'Disattivo'}
            </button>
          ) : help.type === 'text' ? (
            <input
              type="text"
              className="input w-full text-sm py-1.5"
              value={value ?? help.default ?? ''}
              onChange={(e) => handleTemplateFieldChange(section, fieldKey, e.target.value)}
              placeholder={help.default || ''}
            />
          ) : (
            <div className="flex items-center gap-1">
              <input
                type="number"
                className="input w-full text-sm py-1.5 text-center"
                min={help.min}
                max={help.max}
                step={help.step || 1}
                value={value ?? help.default ?? 0}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  handleTemplateFieldChange(section, fieldKey, isNaN(v) ? 0 : v);
                }}
              />
              {help.unit && (
                <span className="text-xs text-gray-400 w-8">{help.unit}</span>
              )}
            </div>
          )}
        </div>
      </div>
    );
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
    { id: 'stats', label: 'Statistiche', icon: BarChart3 },
    { id: 'settings', label: 'Impostazioni', icon: Settings },
    { id: 'templates', label: 'Template Export', icon: FileText }
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
                  <p className="text-gray-500 text-sm">Gestione utenti, ruoli, crediti e impostazioni</p>
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
        <div className="flex gap-2 mb-8 flex-wrap">
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
                {/* Search + Create Button */}
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
                    <button onClick={handleSearch} className="btn btn-secondary">
                      <Search className="w-4 h-4" />
                      Cerca
                    </button>
                    <button
                      onClick={() => { setShowCreateForm(!showCreateForm); setCreateError(''); }}
                      className={`btn ${showCreateForm ? 'btn-ghost' : 'btn-primary'}`}
                    >
                      {showCreateForm ? (
                        <><X className="w-4 h-4" /> Chiudi</>
                      ) : (
                        <><UserPlus className="w-4 h-4" /> Crea Utente</>
                      )}
                    </button>
                  </div>
                </div>

                {/* Create User Form */}
                {showCreateForm && (
                  <div className="glass rounded-2xl p-6 border-2 border-orange-200 bg-orange-50/30">
                    <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                      <UserPlus className="w-5 h-5 text-orange-500" />
                      Crea Nuovo Utente
                    </h3>

                    {createError && (
                      <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        {createError}
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                        <input
                          type="email"
                          className="input w-full"
                          placeholder="email@esempio.com"
                          value={newUser.email}
                          onChange={(e) => setNewUser(prev => ({ ...prev, email: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
                        <input
                          type="text"
                          className="input w-full"
                          placeholder="username"
                          value={newUser.username}
                          onChange={(e) => setNewUser(prev => ({ ...prev, username: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Password *</label>
                        <div className="relative">
                          <input
                            type={showPassword ? 'text' : 'password'}
                            className="input w-full pr-10"
                            placeholder="Minimo 6 caratteri"
                            value={newUser.password}
                            onChange={(e) => setNewUser(prev => ({ ...prev, password: e.target.value }))}
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Nome Completo</label>
                        <input
                          type="text"
                          className="input w-full"
                          placeholder="Nome e cognome"
                          value={newUser.full_name}
                          onChange={(e) => setNewUser(prev => ({ ...prev, full_name: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Ruolo</label>
                        <select
                          className="input w-full"
                          value={newUser.role_id}
                          onChange={(e) => setNewUser(prev => ({ ...prev, role_id: e.target.value }))}
                        >
                          <option value="">Ruolo Default (user)</option>
                          {roles.map(r => (
                            <option key={r.id} value={r.id}>{r.name} {r.is_default ? '(default)' : ''}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Crediti Iniziali</label>
                        <input
                          type="number"
                          className="input w-full"
                          min="0"
                          value={newUser.credits}
                          onChange={(e) => setNewUser(prev => ({ ...prev, credits: parseInt(e.target.value) || 0 }))}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-4 mt-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={newUser.is_active}
                          onChange={(e) => setNewUser(prev => ({ ...prev, is_active: e.target.checked }))}
                          className="w-4 h-4 rounded border-gray-300 text-orange-600 focus:ring-orange-500"
                        />
                        <span className="text-sm font-medium text-gray-700">Utente attivo</span>
                      </label>
                    </div>

                    <div className="flex justify-end gap-3 mt-6">
                      <button
                        onClick={() => { setShowCreateForm(false); setCreateError(''); }}
                        className="btn btn-ghost"
                      >
                        Annulla
                      </button>
                      <button
                        onClick={handleCreateUser}
                        disabled={createLoading}
                        className="btn btn-primary"
                      >
                        {createLoading ? (
                          <><RefreshCw className="w-4 h-4 animate-spin" /> Creazione...</>
                        ) : (
                          <><UserPlus className="w-4 h-4" /> Crea Utente</>
                        )}
                      </button>
                    </div>
                  </div>
                )}

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
                                onChange={(e) => handleRoleChange(u.id, e.target.value)}
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

            {/* ===================== TAB IMPOSTAZIONI ===================== */}
            {activeTab === 'settings' && editedCosts && (
              <div className="space-y-6">
                {/* Header */}
                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <Coins className="w-6 h-6 text-orange-500" />
                        Configurazione Costi Crediti
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        Personalizza i costi in crediti per ogni operazione della piattaforma.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isDefaultCosts ? (
                        <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium">
                          Valori Default
                        </span>
                      ) : (
                        <span className="px-3 py-1.5 bg-orange-50 text-orange-700 rounded-lg text-sm font-medium">
                          Personalizzati
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Feedback messages */}
                {costsError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {costsError}
                  </div>
                )}
                {costsSuccess && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                    {costsSuccess}
                  </div>
                )}

                {/* Cost cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(COST_OPERATION_LABELS).map(([opType, opConfig]) => (
                    <div key={opType} className="glass rounded-2xl p-5">
                      <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                        <span className="text-xl">{opConfig.icon}</span>
                        {opConfig.label}
                      </h3>
                      <div className="space-y-3">
                        {Object.entries(opConfig.fields).map(([field, fieldLabel]) => (
                          <div key={field} className="flex items-center justify-between gap-4">
                            <label className="text-sm text-gray-600 flex-1">{fieldLabel}</label>
                            <div className="flex items-center gap-2">
                              <input
                                type="number"
                                min="0"
                                step="1"
                                className="input w-24 text-center text-sm py-1.5"
                                value={editedCosts[opType]?.[field] ?? 0}
                                onChange={(e) => handleCostChange(opType, field, e.target.value)}
                              />
                              <span className="text-xs text-gray-400 w-12">crediti</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Actions */}
                <div className="glass rounded-2xl p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {!isDefaultCosts && (
                        <button
                          onClick={() => setShowResetConfirm(true)}
                          disabled={costsSaving}
                          className="btn btn-ghost text-orange-600 hover:bg-orange-50"
                        >
                          <RotateCcw className="w-4 h-4" />
                          Ripristina Default
                        </button>
                      )}
                      {hasUnsavedCostChanges() && (
                        <span className="text-sm text-amber-600 flex items-center gap-1">
                          <AlertTriangle className="w-4 h-4" />
                          Modifiche non salvate
                        </span>
                      )}
                    </div>
                    <button
                      onClick={handleSaveCosts}
                      disabled={costsSaving || !hasUnsavedCostChanges()}
                      className="btn btn-primary"
                    >
                      {costsSaving ? (
                        <><RefreshCw className="w-4 h-4 animate-spin" /> Salvataggio...</>
                      ) : (
                        <><Save className="w-4 h-4" /> Salva Modifiche</>
                      )}
                    </button>
                  </div>
                </div>

                {/* Reset confirmation modal */}
                {showResetConfirm && (
                  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                          <AlertTriangle className="w-6 h-6 text-amber-600" />
                        </div>
                        <div>
                          <h3 className="font-bold text-gray-900">Ripristina Valori Default</h3>
                          <p className="text-sm text-gray-500">Questa azione non e' reversibile</p>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 mb-6">
                        Tutti i costi personalizzati verranno cancellati e ripristinati ai valori predefiniti del sistema. Sei sicuro?
                      </p>
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => setShowResetConfirm(false)}
                          className="btn btn-ghost"
                        >
                          Annulla
                        </button>
                        <button
                          onClick={handleResetCosts}
                          disabled={costsSaving}
                          className="btn bg-amber-500 hover:bg-amber-600 text-white"
                        >
                          {costsSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> Ripristino...</>
                          ) : (
                            <><RotateCcw className="w-4 h-4" /> Ripristina</>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ===================== TAB TEMPLATE EXPORT ===================== */}
            {activeTab === 'templates' && (
              <div className="space-y-6">
                {/* Header */}
                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <FileText className="w-6 h-6 text-orange-500" />
                        Template di Esportazione
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        Crea e personalizza template per l'esportazione delle tesi in PDF e DOCX.
                      </p>
                    </div>
                    <button
                      onClick={handleCreateTemplate}
                      disabled={templateSaving}
                      className="btn btn-primary"
                    >
                      <Plus className="w-4 h-4" />
                      Nuovo Template
                    </button>
                  </div>
                </div>

                {/* Feedback messages */}
                {templateError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {templateError}
                  </div>
                )}
                {templateSuccess && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                    {templateSuccess}
                  </div>
                )}

                {/* Template List */}
                {!editingTemplate && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {templates.map(tpl => (
                      <div key={tpl.id} className="glass rounded-2xl p-5 relative">
                        {tpl.is_default && (
                          <span className="absolute top-3 right-3 px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full text-xs font-medium">
                            Default
                          </span>
                        )}
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-12 h-12 bg-gradient-to-br from-orange-400 to-red-500 rounded-xl flex items-center justify-center">
                            <FileText className="w-6 h-6 text-white" />
                          </div>
                          <div>
                            <h3 className="font-bold text-gray-900">{tpl.name}</h3>
                            <p className="text-xs text-gray-500">ID: {tpl.id}</p>
                          </div>
                        </div>

                        {/* Mini info */}
                        <div className="grid grid-cols-2 gap-2 mb-4 text-xs text-gray-600">
                          <div className="bg-gray-50 rounded-lg p-2">
                            <p className="font-medium">PDF</p>
                            <p>{tpl.pdf?.page_size || 'A4'} — {tpl.pdf?.font_body || 'helv'} {tpl.pdf?.font_body_size || 11}pt</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2">
                            <p className="font-medium">DOCX</p>
                            <p>{tpl.docx?.font_name || 'Times New Roman'} {tpl.docx?.font_size || 12}pt</p>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleEditTemplate(tpl)}
                            className="btn btn-secondary flex-1 text-sm py-2"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                            Modifica
                          </button>
                          {!tpl.is_default && (
                            <>
                              <button
                                onClick={() => handleSetDefaultTemplate(tpl.id)}
                                className="btn btn-ghost text-sm py-2"
                                title="Imposta come default"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setShowDeleteTemplate(tpl.id)}
                                className="btn btn-ghost text-red-500 hover:bg-red-50 text-sm py-2"
                                title="Elimina"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    ))}

                    {templates.length === 0 && (
                      <div className="col-span-full glass rounded-2xl p-8 text-center">
                        <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                        <p className="text-gray-500">Nessun template trovato. Crea il primo!</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Template Editor */}
                {editingTemplate && editedTemplate && (
                  <div className="glass rounded-2xl p-6 border-2 border-orange-200">
                    {/* Editor header */}
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-red-500 rounded-xl flex items-center justify-center">
                          <Edit3 className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <input
                            type="text"
                            className="input text-lg font-bold py-1"
                            value={editedTemplate.name}
                            onChange={(e) => setEditedTemplate(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="Nome template"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleCancelEditTemplate}
                          className="btn btn-ghost"
                        >
                          <X className="w-4 h-4" />
                          Annulla
                        </button>
                        <button
                          onClick={handleSaveTemplate}
                          disabled={templateSaving}
                          className="btn btn-primary"
                        >
                          {templateSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> Salvataggio...</>
                          ) : (
                            <><Save className="w-4 h-4" /> Salva Template</>
                          )}
                        </button>
                      </div>
                    </div>

                    {/* PDF / DOCX tabs */}
                    <div className="flex gap-2 mb-6">
                      <button
                        onClick={() => setTemplateSection('pdf')}
                        className={`px-5 py-2.5 rounded-xl font-medium text-sm transition-all ${
                          templateSection === 'pdf'
                            ? 'bg-gradient-to-r from-red-500 to-orange-500 text-white shadow-lg'
                            : 'bg-white/70 text-gray-600 hover:bg-white hover:shadow-md'
                        }`}
                      >
                        <FileText className="w-4 h-4 inline-block mr-1.5" />
                        Impostazioni PDF
                      </button>
                      <button
                        onClick={() => setTemplateSection('docx')}
                        className={`px-5 py-2.5 rounded-xl font-medium text-sm transition-all ${
                          templateSection === 'docx'
                            ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg'
                            : 'bg-white/70 text-gray-600 hover:bg-white hover:shadow-md'
                        }`}
                      >
                        <FileText className="w-4 h-4 inline-block mr-1.5" />
                        Impostazioni DOCX
                      </button>
                    </div>

                    {/* Fields */}
                    <div className="bg-white rounded-xl p-4 max-h-[600px] overflow-y-auto">
                      {templateHelp && templateHelp[templateSection] ? (
                        Object.entries(templateHelp[templateSection]).map(([fieldKey, helpData]) =>
                          renderTemplateField(templateSection, fieldKey, helpData)
                        )
                      ) : (
                        <div className="text-center py-8 text-gray-400">
                          <HelpCircle className="w-8 h-8 mx-auto mb-2" />
                          <p>Caricamento parametri...</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Delete confirmation modal */}
                {showDeleteTemplate && (
                  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                    <div className="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
                          <Trash2 className="w-6 h-6 text-red-600" />
                        </div>
                        <div>
                          <h3 className="font-bold text-gray-900">Elimina Template</h3>
                          <p className="text-sm text-gray-500">Questa azione non e' reversibile</p>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 mb-6">
                        Il template verra' eliminato definitivamente. Gli utenti che lo utilizzavano passeranno al template default. Sei sicuro?
                      </p>
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => setShowDeleteTemplate(null)}
                          className="btn btn-ghost"
                        >
                          Annulla
                        </button>
                        <button
                          onClick={() => handleDeleteTemplate(showDeleteTemplate)}
                          disabled={templateSaving}
                          className="btn bg-red-500 hover:bg-red-600 text-white"
                        >
                          {templateSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> Eliminazione...</>
                          ) : (
                            <><Trash2 className="w-4 h-4" /> Elimina</>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default Admin;
