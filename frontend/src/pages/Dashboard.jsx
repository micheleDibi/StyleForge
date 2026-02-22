import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Activity, LogOut, Upload,
  Sparkles, RefreshCw, Trash2, ChevronRight, Wand2,
  Clock, CheckCircle2, AlertCircle, Zap, User, Settings,
  TrendingUp, Layers, Brain, BookOpen, Calendar, Download,
  ChevronDown, Eye, List, Coins, Shield, Pencil, Play, Search,
  ArrowRight, BarChart3, Hash, FileDown
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getSessions, deleteSession, renameSession, healthCheck, getJobs, getTheses, deleteThesis, exportThesis, getExportTemplates, getCompilatioScansBySource, startCompilatioScan, downloadCompilatioReport, pollJobStatus } from '../services/api';
import JobCard from '../components/JobCard';
import Logo from '../components/Logo';

const Dashboard = () => {
  const navigate = useNavigate();
  const { logout, user, hasPermission, isAdmin, credits } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [theses, setTheses] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedThesis, setExpandedThesis] = useState(null);
  const [exportingThesis, setExportingThesis] = useState(null);

  // Templates state
  const [templates, setTemplates] = useState([]);
  const [selectedTemplates, setSelectedTemplates] = useState({});

  // Compilatio scan results map: { jobId: scanResult }
  const [scanResults, setScanResults] = useState({});
  // Thesis scan state
  const [thesisScanningId, setThesisScanningId] = useState(null);
  const [thesisScanProgress, setThesisScanProgress] = useState(0);

  // Session rename state
  const [editingSessionName, setEditingSessionName] = useState(null);
  const [editSessionValue, setEditSessionValue] = useState('');
  const editSessionRef = useRef(null);

  // Active tab for content sections
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (!editingSessionName) {
        loadData();
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [editingSessionName]);

  useEffect(() => {
    if (editingSessionName && editSessionRef.current) {
      editSessionRef.current.focus();
      editSessionRef.current.select();
    }
  }, [editingSessionName]);

  const loadData = async () => {
    try {
      const [sessionsData, healthData, jobsData, thesesData, templatesData] = await Promise.all([
        getSessions(),
        healthCheck(),
        getJobs(),
        getTheses().catch(() => ({ theses: [] })),
        getExportTemplates().catch(() => ({ templates: [] }))
      ]);
      setSessions(sessionsData.sessions);
      setHealth(healthData);
      setJobs(jobsData.jobs || []);
      setTheses(thesesData.theses || []);
      setTemplates(templatesData.templates || []);
    } catch (error) {
      console.error('Errore nel caricamento:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Fetch scan results for all completed jobs when admin
  useEffect(() => {
    if (!isAdmin || jobs.length === 0) return;

    const completedJobIds = jobs
      .filter(j => (j.status === 'completed') && (j.job_type === 'generation' || j.job_type === 'humanization'))
      .map(j => j.job_id);

    const thesisIds = theses.filter(t => t.status === 'completed').map(t => t.id);
    const allIds = [...completedJobIds, ...thesisIds];

    if (allIds.length === 0) return;

    const fetchScanResults = async () => {
      try {
        const data = await getCompilatioScansBySource(allIds);
        if (data.scans) {
          setScanResults(prev => ({ ...prev, ...data.scans }));
        }
      } catch (err) {
        console.debug('Errore fetch scan results:', err);
      }
    };
    fetchScanResults();
  }, [isAdmin, jobs, theses]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleDeleteSession = async (sessionId) => {
    if (confirm('Sei sicuro di voler eliminare questa sessione?')) {
      try {
        await deleteSession(sessionId);
        setSessions(sessions.filter(s => s.session_id !== sessionId));
      } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        alert('Errore nell\'eliminazione della sessione');
      }
    }
  };

  const handleDeleteThesis = async (thesisId) => {
    if (confirm('Sei sicuro di voler eliminare questa tesi/relazione?')) {
      try {
        await deleteThesis(thesisId);
        setTheses(theses.filter(t => t.id !== thesisId));
      } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        alert('Errore nell\'eliminazione della tesi');
      }
    }
  };

  const handleExportThesis = async (thesisId, format = 'pdf') => {
    setExportingThesis(thesisId);
    try {
      const templateId = selectedTemplates[thesisId] || null;
      await exportThesis(thesisId, format, templateId);
    } catch (error) {
      console.error('Errore nell\'export:', error);
      alert('Errore nell\'export della tesi');
    } finally {
      setExportingThesis(null);
    }
  };

  const handleLogout = () => {
    if (confirm('Sei sicuro di voler uscire?')) {
      logout();
    }
  };

  const handleStartSessionEdit = (sessionId, currentName) => {
    setEditingSessionName(sessionId);
    setEditSessionValue(currentName || sessionId);
  };

  const handleSaveSessionName = async (sessionId) => {
    const trimmed = editSessionValue.trim();
    if (!trimmed) {
      setEditingSessionName(null);
      return;
    }
    try {
      await renameSession(sessionId, trimmed);
      setSessions(sessions.map(s =>
        s.session_id === sessionId ? { ...s, name: trimmed } : s
      ));
    } catch (error) {
      console.error('Errore nella rinomina:', error);
    }
    setEditingSessionName(null);
  };

  const handleSessionEditKeyDown = (e, sessionId) => {
    if (e.key === 'Enter') {
      handleSaveSessionName(sessionId);
    } else if (e.key === 'Escape') {
      setEditingSessionName(null);
    }
  };

  const handleThesisScan = async (thesisId) => {
    navigate(`/thesis?resume=${thesisId}`);
  };

  const handleDownloadScanReport = async (scanId) => {
    try {
      await downloadCompilatioReport(scanId);
    } catch (error) {
      console.error('Errore download report:', error);
    }
  };

  const getAIScoreColor = (percent) => {
    if (percent <= 5) return 'text-green-600 bg-green-50 border-green-200';
    if (percent <= 20) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const getThesisAction = (thesis) => {
    switch (thesis.status) {
      case 'completed':
        return { label: 'Visualizza', icon: Eye };
      case 'generating':
        return { label: 'Progresso', icon: Clock };
      default:
        return { label: 'Continua', icon: Play };
    }
  };

  const handleThesisNavigate = (thesis) => {
    navigate(`/thesis?resume=${thesis.id}`);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-green-100 text-green-700">
            <CheckCircle2 className="w-3 h-3" />
            Completata
          </span>
        );
      case 'generating':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-amber-100 text-amber-700">
            <Clock className="w-3 h-3 animate-spin" />
            In generazione
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-red-100 text-red-700">
            <AlertCircle className="w-3 h-3" />
            Errore
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700">
            <Clock className="w-3 h-3" />
            {status}
          </span>
        );
    }
  };

  // Filter out compilatio_scan jobs
  const nonScanJobs = jobs.filter(j => j.job_type !== 'compilatio_scan');
  const activeJobs = nonScanJobs.filter(j => j.status === 'pending' || j.status === 'training' || j.status === 'generating');
  const completedJobs = nonScanJobs.filter(j => j.status === 'completed' || j.status === 'failed');
  const trainedSessions = sessions.filter(s => s.is_trained).length;
  const completedTheses = theses.filter(t => t.status === 'completed').length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-slate-50 via-orange-50 to-purple-50">
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-gradient-to-br from-orange-300 to-orange-400 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
          <div className="absolute top-1/3 right-1/4 w-[400px] h-[400px] bg-gradient-to-br from-purple-300 to-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
          <div className="absolute bottom-1/4 left-1/2 w-[450px] h-[450px] bg-gradient-to-br from-blue-300 to-cyan-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
        </div>
        <div className="text-center relative z-10 animate-fade-in">
          <div className="relative inline-block mb-8">
            <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-3xl blur-2xl opacity-50 scale-110 animate-pulse"></div>
            <div className="relative w-28 h-28 bg-gradient-to-br from-orange-500 to-orange-600 rounded-3xl shadow-2xl flex items-center justify-center">
              <Sparkles className="w-14 h-14 text-white animate-pulse" />
            </div>
            <div className="absolute inset-0 border-4 border-orange-300 border-t-transparent rounded-3xl animate-spin"></div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2 animate-slide-up">
            Style<span className="bg-gradient-to-r from-orange-600 to-orange-500 bg-clip-text text-transparent">Forge</span>
          </h1>
          <div className="flex items-center justify-center gap-2 mb-6 animate-slide-up animation-delay-200">
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce"></div>
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce animation-delay-200"></div>
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce animation-delay-400"></div>
          </div>
          <p className="text-gray-600 font-semibold text-lg mb-2 animate-slide-up animation-delay-400">
            Caricamento dashboard...
          </p>
          <p className="text-gray-500 text-sm animate-slide-up animation-delay-600">
            Preparazione della tua area di lavoro
          </p>
          <div className="mt-8 w-64 mx-auto animate-slide-up animation-delay-800">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden shadow-inner">
              <div className="h-full bg-gradient-to-r from-orange-500 via-orange-600 to-orange-500 rounded-full animate-loading-bar"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50/80 relative">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] bg-gradient-to-br from-orange-100 to-orange-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-1/2 -left-40 w-[500px] h-[500px] bg-gradient-to-br from-purple-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-40 right-1/3 w-[400px] h-[400px] bg-gradient-to-br from-blue-100 to-cyan-100 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      {/* ═══════════════ HEADER ═══════════════ */}
      <header className="relative z-10 bg-white/80 backdrop-blur-xl border-b border-gray-200/60 sticky top-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left: Logo + Brand */}
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-lg blur-md opacity-40"></div>
                <Logo size="sm" className="relative" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-lg font-bold text-gray-900 leading-tight">
                  Style<span className="gradient-text">Forge</span>
                </h1>
                <p className="text-[11px] text-gray-400 -mt-0.5">Dashboard</p>
              </div>
            </div>

            {/* Right: Controls */}
            <div className="flex items-center gap-2">
              {/* Credits */}
              <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-orange-50 rounded-lg border border-orange-200/60 text-sm">
                <Coins className="w-3.5 h-3.5 text-orange-500" />
                <span className="font-bold text-orange-600">{isAdmin ? '∞' : credits}</span>
                <span className="text-[11px] text-orange-400">crediti</span>
              </div>

              {/* User chip */}
              <div className="hidden lg:flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-200/60">
                <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
                  isAdmin ? 'bg-purple-500' : 'bg-orange-500'
                }`}>
                  {isAdmin ? <Shield className="w-3 h-3 text-white" /> : <User className="w-3 h-3 text-white" />}
                </div>
                <span className="text-sm font-medium text-gray-700">{user?.username || 'Utente'}</span>
                {isAdmin && <span className="text-[10px] font-bold text-purple-600 bg-purple-100 px-1.5 py-0.5 rounded">ADMIN</span>}
              </div>

              {/* Divider */}
              <div className="hidden md:block w-px h-6 bg-gray-200"></div>

              {/* Admin Actions */}
              {isAdmin && (
                <>
                  <button onClick={() => navigate('/detector-ai')} className="p-2 rounded-lg text-indigo-600 hover:bg-indigo-50 transition-colors" title="Detector AI">
                    <Search className="w-4 h-4" />
                  </button>
                  <button onClick={() => navigate('/admin')} className="p-2 rounded-lg text-purple-600 hover:bg-purple-50 transition-colors" title="Pannello Admin">
                    <Settings className="w-4 h-4" />
                  </button>
                </>
              )}

              <button onClick={handleRefresh} disabled={refreshing} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors" title="Aggiorna">
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
              <button onClick={handleLogout} className="p-2 rounded-lg text-red-500 hover:bg-red-50 transition-colors" title="Esci">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ═══════════════ MAIN ═══════════════ */}
      <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* ─── Welcome Banner + Stats ─── */}
        <div className="animate-fade-in">
          <div className="bg-gradient-to-r from-orange-500 via-orange-600 to-amber-500 rounded-2xl p-6 text-white relative overflow-hidden">
            {/* Decorative circles */}
            <div className="absolute top-0 right-0 w-40 h-40 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/4"></div>
            <div className="absolute bottom-0 left-1/3 w-24 h-24 bg-white/5 rounded-full translate-y-1/2"></div>

            <div className="relative z-10">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold mb-1">
                    Bentornato, {user?.username || 'Utente'} 👋
                  </h2>
                  <p className="text-orange-100 text-sm">
                    {activeJobs.length > 0
                      ? `Hai ${activeJobs.length} job in esecuzione`
                      : 'Tutti i sistemi sono operativi'}
                  </p>
                </div>
                {/* Inline mini stats */}
                <div className="flex gap-3">
                  <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2 text-center min-w-[80px]">
                    <div className="text-2xl font-bold">{sessions.length}</div>
                    <div className="text-[11px] text-orange-100">Sessioni</div>
                  </div>
                  <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2 text-center min-w-[80px]">
                    <div className="text-2xl font-bold">{trainedSessions}</div>
                    <div className="text-[11px] text-orange-100">Addestrate</div>
                  </div>
                  <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2 text-center min-w-[80px]">
                    <div className="text-2xl font-bold">{completedTheses}</div>
                    <div className="text-[11px] text-orange-100">Tesi</div>
                  </div>
                  <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2 text-center min-w-[80px]">
                    <div className="flex items-center justify-center gap-1">
                      <div className={`w-2 h-2 rounded-full ${health?.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'}`}></div>
                      <span className="text-2xl font-bold">{activeJobs.length}</span>
                    </div>
                    <div className="text-[11px] text-orange-100">Job Attivi</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ─── Quick Actions Grid ─── */}
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Azioni rapide</h3>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {hasPermission('train') && (
              <button
                onClick={() => navigate('/train')}
                className="group bg-white rounded-xl p-4 border border-gray-200/60 hover:border-orange-300 hover:shadow-lg hover:shadow-orange-100/50 transition-all text-left"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform shadow-md shadow-orange-500/20">
                    <Upload className="w-5 h-5 text-white" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-orange-500 group-hover:translate-x-0.5 transition-all ml-auto" />
                </div>
                <h4 className="font-semibold text-gray-900 text-sm">Addestra Modello</h4>
                <p className="text-xs text-gray-400 mt-0.5">Carica PDF e addestra</p>
              </button>
            )}

            {hasPermission('generate') && (
              <button
                onClick={() => navigate('/generate')}
                className="group bg-white rounded-xl p-4 border border-gray-200/60 hover:border-blue-300 hover:shadow-lg hover:shadow-blue-100/50 transition-all text-left"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform shadow-md shadow-blue-500/20">
                    <FileText className="w-5 h-5 text-white" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all ml-auto" />
                </div>
                <h4 className="font-semibold text-gray-900 text-sm">Genera Contenuto</h4>
                <p className="text-xs text-gray-400 mt-0.5">Crea con il tuo stile</p>
              </button>
            )}

            {hasPermission('humanize') && (
              <button
                onClick={() => navigate('/humanize')}
                className="group bg-white rounded-xl p-4 border border-gray-200/60 hover:border-purple-300 hover:shadow-lg hover:shadow-purple-100/50 transition-all text-left"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform shadow-md shadow-purple-500/20">
                    <Wand2 className="w-5 h-5 text-white" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-purple-500 group-hover:translate-x-0.5 transition-all ml-auto" />
                </div>
                <h4 className="font-semibold text-gray-900 text-sm">Umanizza Testo</h4>
                <p className="text-xs text-gray-400 mt-0.5">Bypassa AI detection</p>
              </button>
            )}

            {hasPermission('thesis') && (
              <button
                onClick={() => navigate('/thesis')}
                className="group bg-white rounded-xl p-4 border border-gray-200/60 hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-100/50 transition-all text-left relative overflow-hidden"
              >
                <div className="absolute top-2 right-2">
                  <span className="px-1.5 py-0.5 bg-emerald-500 text-white text-[9px] font-bold rounded-md">NEW</span>
                </div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform shadow-md shadow-emerald-500/20">
                    <BookOpen className="w-5 h-5 text-white" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-emerald-500 group-hover:translate-x-0.5 transition-all ml-auto" />
                </div>
                <h4 className="font-semibold text-gray-900 text-sm">Tesi / Relazione</h4>
                <p className="text-xs text-gray-400 mt-0.5">Genera documenti completi</p>
              </button>
            )}
          </div>
        </div>

        {/* ─── Content Tabs Navigation ─── */}
        <div className="animate-slide-up">
          <div className="flex items-center gap-1 bg-white rounded-xl p-1 border border-gray-200/60 w-fit">
            {[
              { id: 'overview', label: 'Panoramica', icon: BarChart3 },
              ...(theses.length > 0 ? [{ id: 'theses', label: `Tesi (${theses.length})`, icon: BookOpen }] : []),
              ...(sessions.length > 0 ? [{ id: 'sessions', label: `Sessioni (${sessions.length})`, icon: Layers }] : []),
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-orange-500 text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* ═══════ TAB: PANORAMICA ═══════ */}
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-fade-in">

            {/* Active Jobs */}
            {activeJobs.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Job in corso ({activeJobs.length})</h3>
                </div>
                <div className="space-y-3">
                  {activeJobs.map((job) => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      isAdmin={isAdmin}
                      scanResult={scanResults[job.job_id]}
                      onUpdate={(updatedJob) => {
                        setJobs(jobs.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
                      }}
                      onScanComplete={(jobId, result) => setScanResults(prev => ({ ...prev, [jobId]: result }))}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Completed Jobs */}
            {completedJobs.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Ultimi job completati</h3>
                </div>
                <div className="space-y-3">
                  {completedJobs.slice(0, 5).map((job) => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      isAdmin={isAdmin}
                      scanResult={scanResults[job.job_id]}
                      onUpdate={(updatedJob) => {
                        setJobs(jobs.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
                      }}
                      onScanComplete={(jobId, result) => setScanResults(prev => ({ ...prev, [jobId]: result }))}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Empty state for overview */}
            {activeJobs.length === 0 && completedJobs.length === 0 && (
              <div className="bg-white rounded-2xl border border-gray-200/60 text-center py-16">
                <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-8 h-8 text-gray-300" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">Nessun job</h3>
                <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto">
                  Inizia addestrando un modello o generando contenuti per vederli qui.
                </p>
                <button onClick={() => navigate('/train')} className="btn btn-primary">
                  <Sparkles className="w-4 h-4" />
                  Inizia ora
                </button>
              </div>
            )}
          </div>
        )}

        {/* ═══════ TAB: TESI ═══════ */}
        {activeTab === 'theses' && (
          <div className="space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{theses.length} documenti totali</p>
              <button onClick={() => navigate('/thesis')} className="btn btn-primary btn-sm">
                <Sparkles className="w-3.5 h-3.5" />
                Nuova Tesi
              </button>
            </div>

            {theses.map((thesis) => {
              const action = getThesisAction(thesis);
              const ActionIcon = action.icon;
              const thesisScan = scanResults[thesis.id];
              const isExpanded = expandedThesis === thesis.id;

              return (
                <div key={thesis.id} className="bg-white rounded-xl border border-gray-200/60 overflow-hidden hover:shadow-md transition-all">
                  {/* Thesis Row */}
                  <div
                    className="flex items-center gap-4 p-4 cursor-pointer hover:bg-gray-50/50 transition-colors"
                    onClick={() => setExpandedThesis(isExpanded ? null : thesis.id)}
                  >
                    {/* Icon */}
                    <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center shadow-sm">
                      <BookOpen className="w-5 h-5 text-white" />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="font-semibold text-gray-900 text-sm truncate">{thesis.title}</h4>
                        {getStatusBadge(thesis.status)}
                        {isAdmin && thesisScan && (
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-bold border ${getAIScoreColor(thesisScan.ai_generated_percent)}`}>
                            AI {thesisScan.ai_generated_percent?.toFixed(0)}%
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                        <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(thesis.created_at)}</span>
                        <span>{thesis.num_chapters} cap.</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleThesisNavigate(thesis); }}
                        className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          thesis.status === 'completed'
                            ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                            : thesis.status === 'generating'
                            ? 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                            : 'bg-gray-50 text-gray-700 hover:bg-gray-100'
                        }`}
                      >
                        <ActionIcon className="w-3.5 h-3.5" />
                        {action.label}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteThesis(thesis.id); }}
                        className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <ChevronDown className={`w-4 h-4 text-gray-300 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="border-t border-gray-100 bg-gray-50/30 p-4 space-y-4">
                      {/* Description */}
                      {thesis.description && (
                        <p className="text-sm text-gray-600 bg-white rounded-lg p-3 border border-gray-100">{thesis.description}</p>
                      )}

                      {/* Stats Row */}
                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { label: 'Capitoli', value: thesis.num_chapters },
                          { label: 'Sezioni/Cap', value: thesis.sections_per_chapter },
                          { label: 'Parole/Sez', value: thesis.words_per_section?.toLocaleString() },
                          { label: 'Progresso', value: `${thesis.generation_progress || 0}%` },
                        ].map((stat, i) => (
                          <div key={i} className="bg-white rounded-lg p-2.5 text-center border border-gray-100">
                            <div className="text-lg font-bold text-gray-900">{stat.value}</div>
                            <div className="text-[10px] text-gray-400 uppercase tracking-wide">{stat.label}</div>
                          </div>
                        ))}
                      </div>

                      {/* Key Topics */}
                      {thesis.key_topics && thesis.key_topics.length > 0 && (
                        <div>
                          <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">Argomenti</p>
                          <div className="flex flex-wrap gap-1.5">
                            {thesis.key_topics.map((topic, i) => (
                              <span key={i} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-xs rounded-md border border-emerald-200/50">
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Detector AI Scan */}
                      {isAdmin && thesis.status === 'completed' && (
                        <div>
                          {thesisScan ? (
                            <div className="bg-white rounded-lg border border-purple-200/60 p-3">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-[10px] font-bold text-purple-600 uppercase tracking-wide flex items-center gap-1">
                                  <Shield className="w-3 h-3" /> Detector AI
                                </span>
                                {thesisScan.has_report && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleDownloadScanReport(thesisScan.scan_id); }}
                                    className="text-[11px] text-purple-600 hover:text-purple-800 flex items-center gap-1 font-medium"
                                  >
                                    <Download className="w-3 h-3" /> Report
                                  </button>
                                )}
                              </div>
                              <div className="grid grid-cols-4 gap-2">
                                <div className={`rounded-lg p-2 border text-center ${getAIScoreColor(thesisScan.ai_generated_percent)}`}>
                                  <div className="text-base font-bold">{thesisScan.ai_generated_percent?.toFixed(1)}%</div>
                                  <div className="text-[9px] font-medium opacity-70 uppercase">AI</div>
                                </div>
                                <div className="rounded-lg p-2 border bg-blue-50 border-blue-200/60 text-blue-600 text-center">
                                  <div className="text-base font-bold">{thesisScan.similarity_percent?.toFixed(1)}%</div>
                                  <div className="text-[9px] font-medium opacity-70 uppercase">Similarita</div>
                                </div>
                                <div className="rounded-lg p-2 border bg-gray-50 border-gray-200/60 text-gray-600 text-center">
                                  <div className="text-base font-bold">{thesisScan.global_score_percent?.toFixed(1)}%</div>
                                  <div className="text-[9px] font-medium opacity-70 uppercase">Globale</div>
                                </div>
                                <div className="rounded-lg p-2 border bg-gray-50 border-gray-200/60 text-gray-600 text-center">
                                  <div className="text-base font-bold">{thesisScan.exact_percent?.toFixed(1)}%</div>
                                  <div className="text-[9px] font-medium opacity-70 uppercase">Esatti</div>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleThesisScan(thesis.id); }}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200/60 transition-colors"
                            >
                              <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
                            </button>
                          )}
                        </div>
                      )}

                      {/* Export Row */}
                      {thesis.status === 'completed' && (
                        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-gray-100">
                          {templates.length > 0 && (
                            <select
                              value={selectedTemplates[thesis.id] || ''}
                              onChange={(e) => setSelectedTemplates({ ...selectedTemplates, [thesis.id]: e.target.value || null })}
                              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-orange-300"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <option value="">Template default</option>
                              {templates.map((tpl) => (
                                <option key={tpl.id} value={tpl.id}>{tpl.name}</option>
                              ))}
                            </select>
                          )}
                          <div className="flex items-center gap-1">
                            <FileDown className="w-3.5 h-3.5 text-gray-400" />
                            {['pdf', 'docx', 'txt', 'md'].map((fmt) => (
                              <button
                                key={fmt}
                                onClick={(e) => { e.stopPropagation(); handleExportThesis(thesis.id, fmt); }}
                                disabled={exportingThesis === thesis.id}
                                className={`px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                                  fmt === 'pdf'
                                    ? 'bg-orange-500 text-white hover:bg-orange-600'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                }`}
                              >
                                {exportingThesis === thesis.id && fmt === 'pdf' ? (
                                  <RefreshCw className="w-3 h-3 animate-spin" />
                                ) : (
                                  fmt.toUpperCase()
                                )}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ═══════ TAB: SESSIONI ═══════ */}
        {activeTab === 'sessions' && (
          <div className="animate-fade-in">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-500">{sessions.length} sessioni totali, {trainedSessions} addestrate</p>
              <button onClick={() => navigate('/train')} className="btn btn-primary btn-sm">
                <Sparkles className="w-3.5 h-3.5" />
                Nuova Sessione
              </button>
            </div>

            {sessions.length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-200/60 text-center py-16">
                <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-8 h-8 text-gray-300" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">Nessuna sessione</h3>
                <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto">
                  Inizia creando la tua prima sessione di addestramento.
                </p>
                <button onClick={() => navigate('/train')} className="btn btn-primary">
                  <Upload className="w-4 h-4" />
                  Crea Prima Sessione
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className="bg-white rounded-xl border border-gray-200/60 p-4 hover:shadow-md hover:border-gray-300/60 transition-all group"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        {editingSessionName === session.session_id ? (
                          <input
                            ref={editSessionRef}
                            type="text"
                            value={editSessionValue}
                            onChange={(e) => setEditSessionValue(e.target.value)}
                            onBlur={() => handleSaveSessionName(session.session_id)}
                            onKeyDown={(e) => handleSessionEditKeyDown(e, session.session_id)}
                            className="font-semibold text-sm text-gray-900 bg-white border border-gray-300 rounded-lg px-2 py-1 w-full focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent"
                            maxLength={255}
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <div className="flex items-center gap-1 group/name">
                            <h4 className="font-semibold text-sm text-gray-900 truncate">
                              {session.name || session.session_id}
                            </h4>
                            <button
                              onClick={() => handleStartSessionEdit(session.session_id, session.name || session.session_id)}
                              className="opacity-0 group-hover/name:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded flex-shrink-0"
                              title="Rinomina"
                            >
                              <Pencil className="w-3 h-3 text-gray-400" />
                            </button>
                          </div>
                        )}
                        {session.name && !editingSessionName && (
                          <p className="font-mono text-[10px] text-gray-400 truncate mt-0.5">{session.session_id}</p>
                        )}
                      </div>
                      <button
                        onClick={() => handleDeleteSession(session.session_id)}
                        className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Status + Stats */}
                    <div className="flex items-center gap-2 mb-3">
                      {session.is_trained ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-green-100 text-green-700">
                          <CheckCircle2 className="w-3 h-3" /> Addestrata
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-700">
                          <Clock className="w-3 h-3" /> Non addestrata
                        </span>
                      )}
                      <span className="text-[11px] text-gray-400">{session.conversation_length} conv. &middot; {session.jobs.length} job</span>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/sessions/${session.session_id}`)}
                        className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-xs font-medium bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200/60 transition-colors"
                      >
                        Dettagli
                      </button>
                      <button
                        onClick={() => navigate(`/generate?session=${session.session_id}`)}
                        className={`flex-1 inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                          session.is_trained
                            ? 'bg-orange-500 text-white hover:bg-orange-600 shadow-sm'
                            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        }`}
                        disabled={!session.is_trained}
                      >
                        {session.is_trained ? 'Genera' : 'Non pronta'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
