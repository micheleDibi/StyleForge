import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Users, Shield, Tag, Search, RefreshCw,
  ChevronDown, ChevronUp, Edit3, Save, X, Plus, Minus,
  Coins, CheckCircle2, AlertCircle, Clock, User as UserIcon,
  Settings, UserPlus, RotateCcw,
  AlertTriangle, FileText, HelpCircle, Copy, Trash2, Key, Check, Loader2, Upload, Image,
  CreditCard, Mail, Calendar, Power, Globe, BookOpen, Brain, Wand2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getAdminUsers, updateAdminUser, updateUserRole,
  updateUserPermissions, adjustUserCredits, getUserTransactions,
  getAdminRoles, updateRolePermissions,
  adminCreateUser, adminResendInvite, getAdminCreditCosts, updateAdminCreditCosts,
  resetAdminCreditCosts,
  getAdminTemplates, updateAdminTemplates,
  deleteAdminTemplate, uploadTemplateBackground, deleteTemplateBackground,
  createApiKey, getApiKeys, revokeApiKey
} from '../services/api';
import Logo from '../components/Logo';
import AdminPaymentsSection from '../components/admin/AdminPaymentsSection';
import AdminLanguagesSection from '../components/admin/AdminLanguagesSection';
import AdminListiniSection from '../components/admin/AdminListiniSection';

const PERMISSION_LABELS = {
  train: 'Addestra Modello',
  generate: 'Genera Contenuto',
  humanize: 'Umanizza Testo',
  thesis: 'Tesi',
  manage_templates: 'Gestione Template',
  compilatio_scan: 'Detector AI (completo)',
  compilatio_scan_thesis: 'Detector AI (solo tesi)'
};

const ALL_PERMISSIONS = ['train', 'generate', 'humanize', 'thesis', 'manage_templates', 'compilatio_scan', 'compilatio_scan_thesis'];

const ENTITY_TYPE_LABELS = {
  distributore: 'Distributore',
  rivenditore: 'Rivenditore',
  privato: 'Privato',
};

// Aree dei costi crediti (per raggruppare le operazioni nella pagina impostazioni).
const COST_GROUPS = [
  { key: 'thesis', label: 'Tesi', icon: BookOpen, hint: 'Costo addebitato a ogni step del wizard tesi.' },
  { key: 'wiki', label: 'Knowledge Base', icon: Brain, hint: 'Analisi dei documenti caricati e dei paper selezionati.' },
  { key: 'research', label: 'Ricerca & Paper', icon: Search, hint: 'Ricerca e riassunto dei paper accademici nel wizard.' },
  { key: 'tools', label: 'Altri strumenti', icon: Wand2, hint: 'Operazioni fuori dal flusso tesi.' },
];

// Operazioni con costo in crediti (niente emoji: icone per gruppo, layout pulito).
const COST_OPERATION_LABELS = {
  // Tesi
  thesis_chapters: { group: 'thesis', label: 'Capitoli (Step 1)', description: 'Quota fissa + scaling sui caratteri degli allegati.', fields: { base: 'Quota fissa', per_1000_attachment_chars: 'Per 1000 caratteri allegati' } },
  thesis_sections: { group: 'thesis', label: 'Sezioni (Step 2)', description: 'Quota fissa + scaling per capitolo.', fields: { base: 'Quota fissa', per_chapter: 'Per capitolo' } },
  thesis_content: { group: 'thesis', label: 'Contenuto (Step 3)', description: 'Quota fissa + scaling per capitolo, sezione e parole.', fields: { base: 'Quota fissa', per_chapter: 'Per capitolo', per_section: 'Per sezione', per_1000_words_target: 'Per 1000 parole target' } },
  // Knowledge Base
  wiki_ingest: { group: 'wiki', label: 'Analisi documenti e paper', description: 'Quota fissa + per fonte analizzata. Copre ingest, controllo qualità e auto-fix.', fields: { base: 'Quota fissa', per_source: 'Per fonte' } },
  wiki_lint: { group: 'wiki', label: 'Ricontrollo qualità', description: 'Rilancio del solo controllo qualità del wiki.', fields: { base: 'Costo base' } },
  // Ricerca & Paper
  research_search: { group: 'research', label: 'Ricerca paper', description: 'Costo base + per fonte interrogata.', fields: { base: 'Costo base', per_source: 'Per fonte' } },
  research_summary: { group: 'research', label: 'Riassunto paper', description: 'Riassunto AI di un singolo paper.', fields: { base: 'Costo base' } },
  paper_keyword_suggest: { group: 'research', label: 'Suggerimento keyword', description: 'Estrazione termini di ricerca dai documenti caricati.', fields: { base: 'Costo base', per_attachment: 'Per documento' } },
  // Altri strumenti
  train: { group: 'tools', label: 'Addestramento stile', description: 'Addestramento del modello sui PDF caricati.', fields: { base: 'Costo base', per_page: 'Per pagina PDF' } },
  generate: { group: 'tools', label: 'Generazione contenuto', description: 'Generazione di testo con lo stile addestrato.', fields: { base: 'Costo base', per_1000_words: 'Per 1000 parole' } },
  humanize: { group: 'tools', label: 'Umanizzazione', description: 'Riscrittura anti-AI del testo.', fields: { base: 'Costo base', per_1000_chars: 'Per 1000 caratteri' } },
  compilatio_scan: { group: 'tools', label: 'Detector AI - Scansione', description: 'Scansione AI/plagio. Costo variabile sulla lunghezza del testo.', fields: { base: 'Costo base', per_1000_chars: 'Per 1000 caratteri' } },
  compilatio_scan_thesis: { group: 'tools', label: 'Detector AI - Scansione tesi', description: 'Tariffa fissa per la scansione AI/plagio dentro il wizard tesi.', fields: { base: 'Costo base (flat)' } },
};

const Admin = () => {
  const { t } = useTranslation();
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
  const [resendingUser, setResendingUser] = useState(null);
  const [newUser, setNewUser] = useState({
    email: '', username: '', full_name: '',
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
  // Elenco distributori (per assegnare il distributore di riferimento ai rivenditori)
  const [distributori, setDistributori] = useState([]);

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

  // API Keys state
  const [apiKeys, setApiKeys] = useState([]);
  const [showCreateKey, setShowCreateKey] = useState(false);
  const [newKeyResult, setNewKeyResult] = useState(null);
  const [keyCopied, setKeyCopied] = useState(false);
  const [keyCreating, setKeyCreating] = useState(false);
  const [newKeyForm, setNewKeyForm] = useState({
    user_id: '', name: '', expires_in_days: '', rate_limit_per_minute: 30
  });

  useEffect(() => {
    loadData();
  }, [activeTab]);

  // Carica i ruoli una volta per il form di creazione utente
  useEffect(() => {
    if (roles.length === 0) {
      getAdminRoles().then(data => setRoles(data.roles)).catch(() => {});
    }
  }, []);

  // Elenco distributori per il selettore "Distributore di riferimento".
  // Va ricaricato ogni volta che un utente viene promosso/declassato a distributore.
  const loadDistributori = async () => {
    try {
      const d = await getAdminUsers(null, null, null, 'distributore');
      setDistributori(d.users || []);
    } catch {
      /* ignora: il selettore mostrerà solo "— nessuno —" */
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'users') {
        const data = await getAdminUsers(searchTerm || null);
        setUsers(data.users);
        loadDistributori();
      } else if (activeTab === 'roles') {
        const data = await getAdminRoles();
        setRoles(data.roles);
      } else if (activeTab === 'settings') {
        const costsData = await getAdminCreditCosts();
        setCreditCosts(costsData.costs);
        setEditedCosts(JSON.parse(JSON.stringify(costsData.costs)));
        setIsDefaultCosts(costsData.is_default);
      } else if (activeTab === 'templates') {
        const data = await getAdminTemplates();
        setTemplates(data.templates || []);
        if (data.help) setTemplateHelp(data.help);
      } else if (activeTab === 'api-keys') {
        const data = await getApiKeys();
        setApiKeys(data.keys || []);
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

  const handleEntityTypeChange = async (userId, entityType) => {
    // Aggiornamento ottimistico: il campo "Distributore di riferimento" compare
    // subito quando si sceglie "rivenditore", senza attendere il round-trip.
    setUsers(prev => prev.map(u => u.id === userId
      ? { ...u, entity_type: entityType, distributor_id: entityType === 'rivenditore' ? u.distributor_id : null }
      : u));
    try {
      const updated = await updateAdminUser(userId, { entity_type: entityType });
      setUsers(prev => prev.map(u => u.id === userId ? updated : u));
      // Promuovere/declassare un distributore cambia l'elenco selezionabile.
      loadDistributori();
    } catch (error) {
      console.error('Errore cambio tipo ente:', error);
      // Rollback dallo stato server in caso di errore.
      const data = await getAdminUsers(searchTerm || null).catch(() => null);
      if (data) setUsers(data.users);
      loadDistributori();
    }
  };

  const handleResendInvite = async (userId) => {
    setResendingUser(userId);
    try {
      await adminResendInvite(userId);
    } catch (error) {
      console.error('Errore reinvio invito:', error);
    } finally {
      setResendingUser(null);
    }
  };

  const handleDistributorChange = async (userId, distributorId) => {
    try {
      // '' = azzera il distributore di riferimento
      const updated = await updateAdminUser(userId, { distributor_id: distributorId });
      setUsers(prev => prev.map(u => u.id === userId ? updated : u));
    } catch (error) {
      console.error('Errore assegnazione distributore:', error);
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
    if (!newUser.email || !newUser.username) {
      setCreateError(t('Email e username sono obbligatori.'));
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
      setNewUser({ email: '', username: '', full_name: '', role_id: '', credits: 0, is_active: true });
      setShowCreateForm(false);
      const data = await getAdminUsers(searchTerm || null);
      setUsers(data.users);
    } catch (error) {
      const detail = error.response?.data?.detail || t('Errore durante la creazione dell\'utente.');
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
      setCostsSuccess(t('Costi aggiornati con successo!'));
      setTimeout(() => setCostsSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || t('Errore nel salvataggio dei costi.');
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
      setCostsSuccess(t('Costi ripristinati ai valori default!'));
      setTimeout(() => setCostsSuccess(''), 3000);
    } catch (error) {
      setCostsError(t('Errore nel ripristino dei costi.'));
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
      setTemplateSuccess(t('Template salvato con successo!'));
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || t('Errore nel salvataggio del template.');
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
        name: t('Nuovo Template {{n}}', { n: templates.length + 1 }),
        is_default: false
      };
      const updatedTemplates = [...templates, newTemplate];
      const data = await updateAdminTemplates(updatedTemplates);
      setTemplates(data.templates || []);
      handleEditTemplate(newTemplate);
      setTemplateSuccess(t('Nuovo template creato!'));
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || t('Errore nella creazione del template.');
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
      setTemplateSuccess(t('Template eliminato!'));
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      const detail = error.response?.data?.detail || t('Errore nell\'eliminazione del template.');
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
      setTemplateSuccess(t('Template impostato come default!'));
      setTimeout(() => setTemplateSuccess(''), 3000);
    } catch (error) {
      setTemplateError(t('Errore nell\'impostazione del template default.'));
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
              title={t('Mostra info')}
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
              {value ? t('Attivo') : t('Disattivo')}
            </button>
          ) : help.type === 'text' ? (
            <input
              type="text"
              className="input w-full text-sm py-1.5"
              value={value ?? help.default ?? ''}
              onChange={(e) => handleTemplateFieldChange(section, fieldKey, e.target.value)}
              placeholder={help.default || ''}
            />
          ) : help.type === 'image' ? (
            <div className="flex flex-col gap-2">
              {value ? (
                <div className="flex items-center gap-2">
                  <img
                    src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/admin/templates/backgrounds/${value}`}
                    alt={t('Sfondo')}
                    className="w-16 h-16 object-cover rounded-lg border border-gray-200"
                  />
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await deleteTemplateBackground(value);
                        handleTemplateFieldChange(section, fieldKey, '');
                      } catch (e) {
                        console.error('Errore rimozione sfondo:', e);
                      }
                    }}
                    className="text-red-500 hover:text-red-700 p-1"
                    title={t('Rimuovi immagine')}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <label className="flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg cursor-pointer transition-colors border border-dashed border-gray-300">
                  <Upload className="w-4 h-4 text-gray-500" />
                  <span className="text-xs text-gray-600">{t('Carica immagine')}</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      try {
                        const data = await uploadTemplateBackground(file);
                        handleTemplateFieldChange(section, fieldKey, data.filename);
                      } catch (err) {
                        const detail = err.response?.data?.detail || t('Errore upload immagine');
                        setTemplateError(detail);
                      }
                      e.target.value = '';
                    }}
                  />
                </label>
              )}
            </div>
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
    if (!dateString) return t('Mai');
    return new Date(dateString).toLocaleDateString('it-IT', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const tabs = [
    { id: 'users', label: t('Utenti'), icon: Users },
    { id: 'roles', label: t('Ruoli'), icon: Shield },
    { id: 'settings', label: t('Parametri'), icon: Settings },
    { id: 'listini', label: t('Listini'), icon: Tag },
    { id: 'templates', label: t('Template Export'), icon: FileText },
    { id: 'api-keys', label: t('API Keys'), icon: Key },
    { id: 'payments', label: t('Pagamenti PagoPA'), icon: CreditCard },
    { id: 'languages', label: t('Lingue'), icon: Globe }
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
                {t('Dashboard')}
              </button>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl blur-lg opacity-50"></div>
                  <Logo size="md" className="relative" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">
                    {t('Pannello')} <span className="gradient-text">{t('Admin')}</span>
                  </h1>
                  <p className="text-gray-500 text-sm">{t('Gestione utenti, ruoli, crediti e impostazioni')}</p>
                </div>
              </div>
            </div>

            <button
              onClick={() => { setRefreshing(true); loadData(); }}
              className="btn btn-secondary"
              disabled={refreshing}
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              {t('Aggiorna')}
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
                        placeholder={t('Cerca per username, email o nome...')}
                        className="input pl-10 w-full"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                      />
                    </div>
                    <button onClick={handleSearch} className="btn btn-secondary">
                      <Search className="w-4 h-4" />
                      {t('Cerca')}
                    </button>
                    <button
                      onClick={() => { setShowCreateForm(!showCreateForm); setCreateError(''); }}
                      className={`btn ${showCreateForm ? 'btn-ghost' : 'btn-primary'}`}
                    >
                      {showCreateForm ? (
                        <><X className="w-4 h-4" /> {t('Chiudi')}</>
                      ) : (
                        <><UserPlus className="w-4 h-4" /> {t('Crea Utente')}</>
                      )}
                    </button>
                  </div>
                </div>

                {/* Create User Form */}
                {showCreateForm && (
                  <div className="glass rounded-2xl p-6 border-2 border-orange-200 bg-orange-50/30">
                    <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                      <UserPlus className="w-5 h-5 text-orange-500" />
                      {t('Crea Nuovo Utente')}
                    </h3>

                    {createError && (
                      <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        {createError}
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">{t('Email *')}</label>
                        <input
                          type="email"
                          className="input w-full"
                          placeholder="email@esempio.com"
                          value={newUser.email}
                          onChange={(e) => setNewUser(prev => ({ ...prev, email: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">{t('Username *')}</label>
                        <input
                          type="text"
                          className="input w-full"
                          placeholder="username"
                          value={newUser.username}
                          onChange={(e) => setNewUser(prev => ({ ...prev, username: e.target.value }))}
                        />
                      </div>
                      <div className="md:col-span-2">
                        <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-100 rounded-xl text-sm text-blue-700">
                          <Mail className="w-4 h-4 flex-shrink-0 mt-0.5" />
                          <span>{t("L'utente riceverà un'email per impostare la propria password e verificare l'indirizzo.")}</span>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">{t('Nome Completo')}</label>
                        <input
                          type="text"
                          className="input w-full"
                          placeholder={t('Nome e cognome')}
                          value={newUser.full_name}
                          onChange={(e) => setNewUser(prev => ({ ...prev, full_name: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">{t('Ruolo')}</label>
                        <select
                          className="input w-full"
                          value={newUser.role_id}
                          onChange={(e) => setNewUser(prev => ({ ...prev, role_id: e.target.value }))}
                        >
                          <option value="">{t('Ruolo Default (user)')}</option>
                          {roles.map(r => (
                            <option key={r.id} value={r.id}>{r.name} {r.is_default ? t('(default)') : ''}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">{t('Crediti Iniziali')}</label>
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
                        <span className="text-sm font-medium text-gray-700">{t('Utente attivo')}</span>
                      </label>
                    </div>

                    <div className="flex justify-end gap-3 mt-6">
                      <button
                        onClick={() => { setShowCreateForm(false); setCreateError(''); }}
                        className="btn btn-ghost"
                      >
                        {t('Annulla')}
                      </button>
                      <button
                        onClick={handleCreateUser}
                        disabled={createLoading}
                        className="btn btn-primary"
                      >
                        {createLoading ? (
                          <><RefreshCw className="w-4 h-4 animate-spin" /> {t('Creazione...')}</>
                        ) : (
                          <><UserPlus className="w-4 h-4" /> {t('Crea Utente')}</>
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
                          const willExpand = expandedUser !== u.id;
                          setExpandedUser(willExpand ? u.id : null);
                          if (willExpand) {
                            if (!transactions[u.id]) handleLoadTransactions(u.id);
                            // Lista distributori sempre fresca quando si apre una card
                            loadDistributori();
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
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-gray-900 truncate">{u.full_name || u.username}</span>
                              <span className={`badge ${u.role_name === 'admin' ? 'badge-warning' : 'badge-info'}`}>
                                {u.role_name || t('Nessun ruolo')}
                              </span>
                              {u.role_name !== 'admin' && u.entity_type && (
                                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                                  {ENTITY_TYPE_LABELS[u.entity_type] ? t(ENTITY_TYPE_LABELS[u.entity_type]) : u.entity_type}
                                </span>
                              )}
                              {!u.is_active && (
                                <span className="badge badge-error">{t('Disabilitato')}</span>
                              )}
                              {!u.email_verified && (
                                <>
                                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">{t('Email non verificata')}</span>
                                  <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); handleResendInvite(u.id); }}
                                    disabled={resendingUser === u.id}
                                    className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 hover:bg-orange-200 disabled:opacity-60"
                                  >
                                    {resendingUser === u.id ? t('Invio…') : t('Reinvia')}
                                  </button>
                                </>
                              )}
                            </div>
                            {u.email !== (u.full_name || u.username) && (
                              <div className="text-sm text-gray-500 truncate">{u.email}</div>
                            )}
                          </div>

                          <div className="hidden md:flex items-center gap-6 text-sm">
                            <div className="text-center">
                              <p className="font-bold text-gray-900">
                                {u.credits === -1 ? '∞' : u.credits}
                              </p>
                              <p className="text-gray-500 text-xs">{t('Crediti')}</p>
                            </div>
                            <div className="text-center">
                              <p className="text-gray-600 text-xs">{formatDate(u.last_login)}</p>
                              <p className="text-gray-500 text-xs">{t('Ultimo login')}</p>
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
                        <div className="border-t border-gray-200 p-4 sm:p-5 bg-gray-50/60 space-y-4">
                          {/* Riga 1: impostazioni account + dettagli */}
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {/* Impostazioni account */}
                            <div className="bg-white rounded-xl border border-gray-100 p-4">
                              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-3 flex items-center gap-2">
                                <Settings className="w-3.5 h-3.5" /> {t('Impostazioni account')}
                              </h4>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
                                <div>
                                  <label className="block text-xs font-medium text-gray-500 mb-1">{t('Ruolo')}</label>
                                  <select
                                    className="input w-full py-1.5 text-sm"
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
                                <div>
                                  <label className="block text-xs font-medium text-gray-500 mb-1">{t('Stato')}</label>
                                  <button
                                    onClick={() => handleToggleActive(u.id, u.is_active)}
                                    className={`w-full inline-flex items-center justify-center gap-2 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                                      u.is_active
                                        ? 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'
                                        : 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100'
                                    }`}
                                  >
                                    <Power className="w-4 h-4" />
                                    {u.is_active ? t('Attivo') : t('Disattivato')}
                                  </button>
                                </div>
                                {u.role_name !== 'admin' && (
                                  <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">{t('Tipo utente')}</label>
                                    <select
                                      className="input w-full py-1.5 text-sm"
                                      value={u.entity_type || 'privato'}
                                      onChange={(e) => handleEntityTypeChange(u.id, e.target.value)}
                                      title={t('Determina i pacchetti crediti acquistabili')}
                                    >
                                      <option value="distributore">{t('Distributore')}</option>
                                      <option value="rivenditore">{t('Rivenditore')}</option>
                                      <option value="privato">{t('Privato')}</option>
                                    </select>
                                  </div>
                                )}
                                {u.role_name !== 'admin' && u.entity_type === 'rivenditore' && (
                                  <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">{t('Distributore di riferimento')}</label>
                                    <select
                                      className="input w-full py-1.5 text-sm"
                                      value={u.distributor_id || ''}
                                      onChange={(e) => handleDistributorChange(u.id, e.target.value)}
                                      title={t('Distributore di riferimento del rivenditore')}
                                    >
                                      <option value="">{t('— nessuno —')}</option>
                                      {distributori.map((d) => (
                                        <option key={d.id} value={d.id}>{d.full_name || d.username}</option>
                                      ))}
                                    </select>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Dettagli */}
                            <div className="bg-white rounded-xl border border-gray-100 p-4">
                              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-3 flex items-center gap-2">
                                <UserIcon className="w-3.5 h-3.5" /> {t('Dettagli')}
                              </h4>
                              <dl className="text-sm divide-y divide-gray-100">
                                <div className="flex items-center justify-between gap-3 py-1.5">
                                  <dt className="text-gray-500">{t('Nome completo')}</dt>
                                  <dd className="font-medium text-gray-900 text-right truncate">{u.full_name || '—'}</dd>
                                </div>
                                <div className="flex items-center justify-between gap-3 py-1.5">
                                  <dt className="text-gray-500 flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> {t('Email')}</dt>
                                  <dd className="font-medium text-gray-900 text-right truncate">{u.email}</dd>
                                </div>
                                <div className="flex items-center justify-between gap-3 py-1.5">
                                  <dt className="text-gray-500 flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> {t('Creato il')}</dt>
                                  <dd className="font-medium text-gray-900 text-right">{formatDate(u.created_at)}</dd>
                                </div>
                                <div className="flex items-center justify-between gap-3 py-1.5">
                                  <dt className="text-gray-500 flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5" /> {t('Aggiornato')}</dt>
                                  <dd className="font-medium text-gray-900 text-right">{formatDate(u.updated_at)}</dd>
                                </div>
                                <div className="flex items-center justify-between gap-3 py-1.5">
                                  <dt className="text-gray-500 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {t('Ultimo login')}</dt>
                                  <dd className="font-medium text-gray-900 text-right">{formatDate(u.last_login)}</dd>
                                </div>
                              </dl>
                            </div>
                          </div>

                          {/* Permessi */}
                          <div className="bg-white rounded-xl border border-gray-100 p-4">
                            <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400 flex items-center gap-2">
                                <Shield className="w-3.5 h-3.5" /> {t('Permessi')}
                              </h4>
                              <p className="text-xs text-gray-400">{t('Click per ciclare: Eredita')} &rarr; {t('Forza Sì')} &rarr; {t('Forza No')}</p>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                              {ALL_PERMISSIONS.map(perm => {
                                const override = u.user_overrides[perm];
                                const hasFromRole = u.permissions.includes(perm);
                                const allowed = override === true || (override == null && hasFromRole);
                                let stateText, stateCls, chipCls, Icon;
                                if (override === true) {
                                  stateText = t('Forza Sì'); stateCls = 'bg-green-200 text-green-900'; chipCls = 'bg-green-50 border-green-300'; Icon = Check;
                                } else if (override === false) {
                                  stateText = t('Forza No'); stateCls = 'bg-red-200 text-red-900'; chipCls = 'bg-red-50 border-red-300'; Icon = X;
                                } else if (hasFromRole) {
                                  stateText = t('Eredita'); stateCls = 'bg-blue-100 text-blue-700'; chipCls = 'bg-white border-blue-200'; Icon = Check;
                                } else {
                                  stateText = t('Eredita'); stateCls = 'bg-gray-100 text-gray-500'; chipCls = 'bg-white border-gray-200'; Icon = Minus;
                                }
                                return (
                                  <button
                                    key={perm}
                                    onClick={() => handlePermissionToggle(u.id, perm, u.user_overrides)}
                                    className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-all hover:shadow-sm ${chipCls}`}
                                  >
                                    <span className="flex items-center gap-2 min-w-0">
                                      <Icon className={`w-4 h-4 flex-shrink-0 ${allowed ? 'text-green-600' : 'text-gray-400'}`} />
                                      <span className="text-gray-700 truncate">{t(PERMISSION_LABELS[perm])}</span>
                                    </span>
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${stateCls}`}>{stateText}</span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>

                          {/* Crediti */}
                          <div className="bg-white rounded-xl border border-gray-100 p-4">
                            <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400 flex items-center gap-2">
                                <Coins className="w-3.5 h-3.5" /> {t('Gestione crediti')}
                              </h4>
                              <span className="text-sm text-gray-500">
                                {t('Saldo attuale:')} <span className="font-bold text-orange-600">{u.credits === -1 ? '∞' : u.credits}</span>
                              </span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-[11rem_1fr_auto] gap-2">
                              <input
                                type="number"
                                placeholder={t('Quantità (es. 100 o -50)')}
                                className="input"
                                value={creditAmount}
                                onChange={(e) => setCreditAmount(e.target.value)}
                              />
                              <input
                                type="text"
                                placeholder={t('Motivazione...')}
                                className="input"
                                value={creditDescription}
                                onChange={(e) => setCreditDescription(e.target.value)}
                              />
                              <button
                                onClick={() => handleAdjustCredits(u.id)}
                                disabled={!creditAmount || !creditDescription || creditLoading}
                                className="btn btn-primary whitespace-nowrap justify-center"
                              >
                                {creditLoading ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Coins className="w-4 h-4" />
                                )}
                                {t('Applica')}
                              </button>
                            </div>
                          </div>

                          {/* Storico transazioni */}
                          {transactions[u.id] && transactions[u.id].length > 0 && (
                            <div className="bg-white rounded-xl border border-gray-100 p-4">
                              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-3 flex items-center gap-2">
                                <Clock className="w-3.5 h-3.5" /> {t('Ultime transazioni')}
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
                      <p className="text-gray-500">{t('Nessun utente trovato')}</p>
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
                            <span className="badge badge-success mt-1">{t('Ruolo Default')}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <h4 className="text-sm font-medium text-gray-600 mb-3">{t('Permessi assegnati:')}</h4>
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
                            {t(PERMISSION_LABELS[perm])}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ===================== TAB PARAMETRI ===================== */}
            {activeTab === 'settings' && editedCosts && (
              <div className="space-y-6">
                {/* Header */}
                <div className="glass rounded-2xl p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <Coins className="w-6 h-6 text-orange-500" />
                        {t('Configurazione Costi Crediti')}
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        {t('Personalizza i costi in crediti per ogni operazione della piattaforma.')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isDefaultCosts ? (
                        <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium">
                          {t('Valori Default')}
                        </span>
                      ) : (
                        <span className="px-3 py-1.5 bg-orange-50 text-orange-700 rounded-lg text-sm font-medium">
                          {t('Personalizzati')}
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

                {/* Costi per area */}
                {COST_GROUPS.map((group) => {
                  const ops = Object.entries(COST_OPERATION_LABELS).filter(([, c]) => c.group === group.key);
                  if (ops.length === 0) return null;
                  const GIcon = group.icon;
                  return (
                    <div key={group.key} className="space-y-3">
                      <div className="flex items-center gap-3 px-1 pt-1">
                        <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center flex-shrink-0">
                          <GIcon className="w-[18px] h-[18px]" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900 leading-tight">{t(group.label)}</h3>
                          <p className="text-xs text-gray-400">{t(group.hint)}</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {ops.map(([opType, opConfig]) => (
                          <div key={opType} className="glass rounded-2xl p-5">
                            <div className="mb-3">
                              <h4 className="font-semibold text-gray-900">{t(opConfig.label)}</h4>
                              {opConfig.description && (
                                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{t(opConfig.description)}</p>
                              )}
                            </div>
                            <div>
                              {Object.entries(opConfig.fields).map(([field, fieldLabel]) => (
                                <div key={field} className="flex items-center justify-between gap-4 py-2 border-t border-slate-100 first:border-t-0 first:pt-0">
                                  <label className="text-sm text-gray-600 flex-1">{t(fieldLabel)}</label>
                                  <div className="flex items-center gap-2">
                                    <input
                                      type="number"
                                      min="0"
                                      step="1"
                                      className="input w-24 text-center text-sm py-1.5"
                                      value={editedCosts[opType]?.[field] ?? 0}
                                      onChange={(e) => handleCostChange(opType, field, e.target.value)}
                                    />
                                    <span className="text-xs text-gray-400 w-12">{t('crediti')}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}

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
                          {t('Ripristina Default')}
                        </button>
                      )}
                      {hasUnsavedCostChanges() && (
                        <span className="text-sm text-amber-600 flex items-center gap-1">
                          <AlertTriangle className="w-4 h-4" />
                          {t('Modifiche non salvate')}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={handleSaveCosts}
                      disabled={costsSaving || !hasUnsavedCostChanges()}
                      className="btn btn-primary"
                    >
                      {costsSaving ? (
                        <><RefreshCw className="w-4 h-4 animate-spin" /> {t('Salvataggio...')}</>
                      ) : (
                        <><Save className="w-4 h-4" /> {t('Salva Modifiche')}</>
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
                          <h3 className="font-bold text-gray-900">{t('Ripristina Valori Default')}</h3>
                          <p className="text-sm text-gray-500">{t("Questa azione non e' reversibile")}</p>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 mb-6">
                        {t('Tutti i costi personalizzati verranno cancellati e ripristinati ai valori predefiniti del sistema. Sei sicuro?')}
                      </p>
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => setShowResetConfirm(false)}
                          className="btn btn-ghost"
                        >
                          {t('Annulla')}
                        </button>
                        <button
                          onClick={handleResetCosts}
                          disabled={costsSaving}
                          className="btn bg-amber-500 hover:bg-amber-600 text-white"
                        >
                          {costsSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> {t('Ripristino...')}</>
                          ) : (
                            <><RotateCcw className="w-4 h-4" /> {t('Ripristina')}</>
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
                        {t('Template di Esportazione')}
                      </h2>
                      <p className="text-sm text-gray-500 mt-1">
                        {t("Crea e personalizza template per l'esportazione delle tesi in PDF e DOCX.")}
                      </p>
                    </div>
                    <button
                      onClick={handleCreateTemplate}
                      disabled={templateSaving}
                      className="btn btn-primary"
                    >
                      <Plus className="w-4 h-4" />
                      {t('Nuovo Template')}
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
                            {t('Default')}
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
                            {t('Modifica')}
                          </button>
                          {!tpl.is_default && (
                            <>
                              <button
                                onClick={() => handleSetDefaultTemplate(tpl.id)}
                                className="btn btn-ghost text-sm py-2"
                                title={t('Imposta come default')}
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setShowDeleteTemplate(tpl.id)}
                                className="btn btn-ghost text-red-500 hover:bg-red-50 text-sm py-2"
                                title={t('Elimina')}
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
                        <p className="text-gray-500">{t('Nessun template trovato. Crea il primo!')}</p>
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
                            placeholder={t('Nome template')}
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleCancelEditTemplate}
                          className="btn btn-ghost"
                        >
                          <X className="w-4 h-4" />
                          {t('Annulla')}
                        </button>
                        <button
                          onClick={handleSaveTemplate}
                          disabled={templateSaving}
                          className="btn btn-primary"
                        >
                          {templateSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> {t('Salvataggio...')}</>
                          ) : (
                            <><Save className="w-4 h-4" /> {t('Salva Template')}</>
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
                        {t('Impostazioni PDF')}
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
                        {t('Impostazioni DOCX')}
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
                          <p>{t('Caricamento parametri...')}</p>
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
                          <h3 className="font-bold text-gray-900">{t('Elimina Template')}</h3>
                          <p className="text-sm text-gray-500">{t("Questa azione non e' reversibile")}</p>
                        </div>
                      </div>
                      <p className="text-sm text-gray-600 mb-6">
                        {t("Il template verra' eliminato definitivamente. Gli utenti che lo utilizzavano passeranno al template default. Sei sicuro?")}
                      </p>
                      <div className="flex justify-end gap-3">
                        <button
                          onClick={() => setShowDeleteTemplate(null)}
                          className="btn btn-ghost"
                        >
                          {t('Annulla')}
                        </button>
                        <button
                          onClick={() => handleDeleteTemplate(showDeleteTemplate)}
                          disabled={templateSaving}
                          className="btn bg-red-500 hover:bg-red-600 text-white"
                        >
                          {templateSaving ? (
                            <><RefreshCw className="w-4 h-4 animate-spin" /> {t('Eliminazione...')}</>
                          ) : (
                            <><Trash2 className="w-4 h-4" /> {t('Elimina')}</>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ═══ API KEYS TAB ═══ */}
            {activeTab === 'api-keys' && (
              <div className="space-y-4">
                {/* Header + Create button */}
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-800">{t('API Keys')}</h2>
                  <button
                    onClick={() => { setShowCreateKey(true); setNewKeyResult(null); setNewKeyForm({ user_id: '', name: '', expires_in_days: '', rate_limit_per_minute: 30 }); }}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" /> {t('Crea API Key')}
                  </button>
                </div>

                {/* Create form */}
                {showCreateKey && (
                  <div className="card p-5 border-l-4 border-orange-400">
                    {newKeyResult ? (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2 text-green-700">
                          <CheckCircle2 className="w-5 h-5" />
                          <span className="font-semibold">{t('API Key creata!')}</span>
                        </div>
                        <div className="bg-gray-900 text-green-400 rounded-xl p-4 font-mono text-sm break-all">
                          {newKeyResult.key}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => { navigator.clipboard.writeText(newKeyResult.key); setKeyCopied(true); setTimeout(() => setKeyCopied(false), 2000); }}
                            className="btn-secondary flex items-center gap-1.5"
                          >
                            {keyCopied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                            {keyCopied ? t('Copiata!') : t('Copia chiave')}
                          </button>
                        </div>
                        <p className="text-xs text-red-600 font-medium">
                          {t("Salva questa chiave ora. Non verra' mai piu' mostrata.")}
                        </p>
                        <button
                          onClick={() => { setShowCreateKey(false); setNewKeyResult(null); loadData(); }}
                          className="btn-ghost text-sm"
                        >
                          {t('Chiudi')}
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <h3 className="font-semibold text-gray-800">{t('Nuova API Key')}</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">{t('Utente')}</label>
                            <select
                              value={newKeyForm.user_id}
                              onChange={e => setNewKeyForm(f => ({ ...f, user_id: e.target.value }))}
                              className="input w-full"
                            >
                              <option value="">{t('Seleziona utente...')}</option>
                              {users.map(u => (
                                <option key={u.id} value={u.id}>{u.email} ({u.username})</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">{t('Nome')}</label>
                            <input
                              type="text"
                              value={newKeyForm.name}
                              onChange={e => setNewKeyForm(f => ({ ...f, name: e.target.value }))}
                              className="input w-full"
                              placeholder={t('Es. Produzione, Test...')}
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">{t('Scadenza (giorni, vuoto = mai)')}</label>
                            <input
                              type="number"
                              value={newKeyForm.expires_in_days}
                              onChange={e => setNewKeyForm(f => ({ ...f, expires_in_days: e.target.value }))}
                              className="input w-full"
                              placeholder="365"
                              min="1"
                              max="365"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-gray-500 mb-1">{t('Rate limit (req/min)')}</label>
                            <input
                              type="number"
                              value={newKeyForm.rate_limit_per_minute}
                              onChange={e => setNewKeyForm(f => ({ ...f, rate_limit_per_minute: parseInt(e.target.value) || 30 }))}
                              className="input w-full"
                              min="1"
                              max="300"
                            />
                          </div>
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={async () => {
                              if (!newKeyForm.user_id || !newKeyForm.name) return;
                              setKeyCreating(true);
                              try {
                                const result = await createApiKey(
                                  newKeyForm.user_id, newKeyForm.name,
                                  newKeyForm.expires_in_days ? parseInt(newKeyForm.expires_in_days) : null,
                                  newKeyForm.rate_limit_per_minute
                                );
                                setNewKeyResult(result);
                              } catch (e) {
                                console.error('Errore creazione API key:', e);
                              }
                              setKeyCreating(false);
                            }}
                            disabled={!newKeyForm.user_id || !newKeyForm.name || keyCreating}
                            className="btn-primary flex items-center gap-1.5"
                          >
                            {keyCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                            {t('Crea')}
                          </button>
                          <button onClick={() => setShowCreateKey(false)} className="btn-ghost">
                            <X className="w-4 h-4" /> {t('Annulla')}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Keys list */}
                {apiKeys.length === 0 ? (
                  <div className="card p-8 text-center text-gray-400">
                    <Key className="w-10 h-10 mx-auto mb-2 opacity-40" />
                    <p>{t('Nessuna API key creata')}</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {apiKeys.map(k => (
                      <div key={k.id} className="card p-4 flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-gray-800">{k.name}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              k.is_active
                                ? (k.expires_at && new Date(k.expires_at) < new Date() ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700')
                                : 'bg-red-100 text-red-700'
                            }`}>
                              {!k.is_active ? t('Revocata') : (k.expires_at && new Date(k.expires_at) < new Date() ? t('Scaduta') : t('Attiva'))}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                            <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{k.key_prefix}...</span>
                            <span>{k.user_email}</span>
                            <span>{t('{{n}} req/min', { n: k.rate_limit_per_minute })}</span>
                            {k.last_used_at && <span>{t('Ultimo uso:')} {new Date(k.last_used_at).toLocaleDateString('it-IT')}</span>}
                            {k.expires_at && <span>{t('Scade:')} {new Date(k.expires_at).toLocaleDateString('it-IT')}</span>}
                          </div>
                        </div>
                        {k.is_active && (
                          <button
                            onClick={async () => {
                              if (!confirm(t('Revocare la key "{{name}}"?', { name: k.name }))) return;
                              try {
                                await revokeApiKey(k.id);
                                loadData();
                              } catch (e) {
                                console.error('Errore revoca:', e);
                              }
                            }}
                            className="btn-ghost text-red-500 hover:text-red-700 flex items-center gap-1 text-sm ml-3"
                          >
                            <Trash2 className="w-4 h-4" /> {t('Revoca')}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ===================== TAB LISTINI ===================== */}
            {activeTab === 'listini' && (
              <AdminListiniSection />
            )}

            {/* ===================== TAB PAGAMENTI PAGOPA ===================== */}
            {activeTab === 'payments' && (
              <AdminPaymentsSection />
            )}
            {activeTab === 'languages' && (
              <AdminLanguagesSection />
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default Admin;
