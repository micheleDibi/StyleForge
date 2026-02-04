import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Activity, LogOut, Upload,
  Sparkles, RefreshCw, Trash2, ChevronRight, Wand2,
  Clock, CheckCircle2, AlertCircle, Zap, User, Settings,
  TrendingUp, Layers, Brain, BookOpen, Calendar, Download,
  ChevronDown, Eye, List
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getSessions, deleteSession, healthCheck, getJobs, getTheses, deleteThesis, exportThesis } from '../services/api';
import JobCard from '../components/JobCard';
import Logo from '../components/Logo';

const Dashboard = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [theses, setTheses] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedThesis, setExpandedThesis] = useState(null);
  const [exportingThesis, setExportingThesis] = useState(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [sessionsData, healthData, jobsData, thesesData] = await Promise.all([
        getSessions(),
        healthCheck(),
        getJobs(),
        getTheses().catch(() => ({ theses: [] }))
      ]);
      setSessions(sessionsData.sessions);
      setHealth(healthData);
      setJobs(jobsData.jobs || []);
      setTheses(thesesData.theses || []);
    } catch (error) {
      console.error('Errore nel caricamento:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

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
      await exportThesis(thesisId, format);
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
          <span className="badge badge-success">
            <CheckCircle2 className="w-3 h-3" />
            Completata
          </span>
        );
      case 'generating':
        return (
          <span className="badge badge-warning">
            <Clock className="w-3 h-3 animate-spin" />
            In generazione
          </span>
        );
      case 'failed':
        return (
          <span className="badge badge-error">
            <AlertCircle className="w-3 h-3" />
            Errore
          </span>
        );
      default:
        return (
          <span className="badge badge-neutral">
            <Clock className="w-3 h-3" />
            {status}
          </span>
        );
    }
  };

  const activeJobs = jobs.filter(j => j.status === 'pending' || j.status === 'training' || j.status === 'generating');
  const completedJobs = jobs.filter(j => j.status === 'completed' || j.status === 'failed');
  const trainedSessions = sessions.filter(s => s.is_trained).length;
  const completedTheses = theses.filter(t => t.status === 'completed').length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-slate-50 via-orange-50 to-purple-50">
        {/* Animated Background Blobs */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-gradient-to-br from-orange-300 to-orange-400 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
          <div className="absolute top-1/3 right-1/4 w-[400px] h-[400px] bg-gradient-to-br from-purple-300 to-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
          <div className="absolute bottom-1/4 left-1/2 w-[450px] h-[450px] bg-gradient-to-br from-blue-300 to-cyan-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
        </div>

        {/* Loading Content */}
        <div className="text-center relative z-10 animate-fade-in">
          {/* Logo Container with Glow */}
          <div className="relative inline-block mb-8">
            {/* Outer glow ring */}
            <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-3xl blur-2xl opacity-50 scale-110 animate-pulse"></div>

            {/* Logo box */}
            <div className="relative w-28 h-28 bg-gradient-to-br from-orange-500 to-orange-600 rounded-3xl shadow-2xl flex items-center justify-center transform hover:scale-105 transition-transform">
              <Sparkles className="w-14 h-14 text-white animate-pulse" />
            </div>

            {/* Spinning ring */}
            <div className="absolute inset-0 border-4 border-orange-300 border-t-transparent rounded-3xl animate-spin"></div>
          </div>

          {/* Brand Name */}
          <h1 className="text-4xl font-bold text-gray-900 mb-2 animate-slide-up">
            Style<span className="bg-gradient-to-r from-orange-600 to-orange-500 bg-clip-text text-transparent">Forge</span>
          </h1>

          {/* Loading Animation */}
          <div className="flex items-center justify-center gap-2 mb-6 animate-slide-up animation-delay-200">
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce"></div>
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce animation-delay-200"></div>
            <div className="w-3 h-3 bg-orange-500 rounded-full animate-bounce animation-delay-400"></div>
          </div>

          {/* Loading Text */}
          <p className="text-gray-600 font-semibold text-lg mb-2 animate-slide-up animation-delay-400">
            Caricamento dashboard...
          </p>
          <p className="text-gray-500 text-sm animate-slide-up animation-delay-600">
            Preparazione della tua area di lavoro
          </p>

          {/* Progress Bar */}
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
    <div className="min-h-screen relative">
      {/* Background Animation */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-orange-100 to-orange-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-to-br from-purple-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-0 left-1/3 w-[400px] h-[400px] bg-gradient-to-br from-blue-100 to-cyan-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <header className="relative z-10 glass border-b border-white/20">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl blur-lg opacity-50"></div>
                <Logo size="md" className="relative" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Style<span className="gradient-text">Forge</span>
                </h1>
                <p className="text-gray-500 text-sm">Dashboard di controllo</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* User Info */}
              <div className="hidden md:flex items-center gap-3 px-4 py-2 bg-white/50 rounded-xl border border-white/30">
                <div className="w-8 h-8 bg-gradient-to-br from-orange-400 to-orange-600 rounded-lg flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-700">
                  {user?.username || 'Utente'}
                </span>
              </div>

              <button
                onClick={handleRefresh}
                className="btn btn-secondary"
                disabled={refreshing}
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">Aggiorna</span>
              </button>

              <button
                onClick={handleLogout}
                className="btn btn-ghost text-red-600 hover:bg-red-50"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Esci</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8 animate-fade-in">
          {/* System Status */}
          <div className="glass rounded-2xl p-5 hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                health?.status === 'healthy'
                  ? 'bg-gradient-to-br from-green-400 to-emerald-500'
                  : 'bg-gradient-to-br from-red-400 to-red-500'
              }`}>
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Sistema</p>
                <p className="text-xl font-bold text-gray-900">
                  {health?.status === 'healthy' ? 'Online' : 'Offline'}
                </p>
              </div>
            </div>
          </div>

          {/* Sessions */}
          <div className="glass rounded-2xl p-5 hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center">
                <Layers className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Sessioni</p>
                <p className="text-xl font-bold text-gray-900">{sessions.length}</p>
              </div>
            </div>
          </div>

          {/* Trained */}
          <div className="glass rounded-2xl p-5 hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-purple-600 rounded-xl flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Addestrate</p>
                <p className="text-xl font-bold text-gray-900">{trainedSessions}</p>
              </div>
            </div>
          </div>

          {/* Active Jobs */}
          <div className="glass rounded-2xl p-5 hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Job Attivi</p>
                <p className="text-xl font-bold text-gray-900">{activeJobs.length}</p>
              </div>
            </div>
          </div>

          {/* Theses */}
          <div className="glass rounded-2xl p-5 hover:shadow-xl transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-emerald-400 to-teal-600 rounded-xl flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tesi</p>
                <p className="text-xl font-bold text-gray-900">{completedTheses}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8 animate-slide-up">
          {/* Train */}
          <button
            onClick={() => navigate('/train')}
            className="glass rounded-2xl p-6 hover:shadow-xl transition-all group cursor-pointer text-left border-2 border-transparent hover:border-orange-200"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg shadow-orange-500/30">
                <Upload className="w-7 h-7 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-gray-900">Addestra Modello</h3>
                <p className="text-sm text-gray-500">Carica PDF e addestra</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-orange-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div className="flex items-center gap-2">
              <span className="badge badge-neutral">
                <Brain className="w-3 h-3" />
                AI Training
              </span>
            </div>
          </button>

          {/* Generate */}
          <button
            onClick={() => navigate('/generate')}
            className="glass rounded-2xl p-6 hover:shadow-xl transition-all group cursor-pointer text-left border-2 border-transparent hover:border-blue-200"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg shadow-blue-500/30">
                <FileText className="w-7 h-7 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-gray-900">Genera Contenuto</h3>
                <p className="text-sm text-gray-500">Crea con il tuo stile</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div className="flex items-center gap-2">
              <span className="badge badge-info">
                <Sparkles className="w-3 h-3" />
                AI-Powered
              </span>
            </div>
          </button>

          {/* Humanize */}
          <button
            onClick={() => navigate('/humanize')}
            className="glass rounded-2xl p-6 hover:shadow-xl transition-all group cursor-pointer text-left border-2 border-transparent hover:border-purple-200"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg shadow-purple-500/30">
                <Wand2 className="w-7 h-7 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-gray-900">Umanizza Testo</h3>
                <p className="text-sm text-gray-500">Bypassa AI detection</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-purple-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div className="flex items-center gap-2">
              <span className="badge badge-success">
                <CheckCircle2 className="w-3 h-3" />
                Anti-Detection
              </span>
            </div>
          </button>

          {/* Thesis Generator */}
          <button
            onClick={() => navigate('/thesis')}
            className="glass rounded-2xl p-6 hover:shadow-xl transition-all group cursor-pointer text-left border-2 border-transparent hover:border-emerald-200 relative overflow-hidden"
          >
            {/* New Badge */}
            <div className="absolute top-3 right-3">
              <span className="px-2 py-1 bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-bold rounded-full shadow-lg">
                NUOVO
              </span>
            </div>
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg shadow-emerald-500/30">
                <BookOpen className="w-7 h-7 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-gray-900">Tesi / Relazione</h3>
                <p className="text-sm text-gray-500">Genera documenti completi</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div className="flex items-center gap-2">
              <span className="badge" style={{ backgroundColor: '#d1fae5', color: '#065f46' }}>
                <Sparkles className="w-3 h-3" />
                AI Avanzata
              </span>
            </div>
          </button>
        </div>

        {/* Theses Section */}
        {theses.length > 0 && (
          <div className="mb-8 animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-emerald-100 to-teal-200 rounded-xl flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Le tue Tesi / Relazioni</h2>
                  <p className="text-sm text-gray-500">{theses.length} documenti totali</p>
                </div>
              </div>
              <button
                onClick={() => navigate('/thesis')}
                className="btn btn-primary"
              >
                <Sparkles className="w-4 h-4" />
                Nuova Tesi
              </button>
            </div>

            <div className="space-y-3">
              {theses.map((thesis) => (
                <div
                  key={thesis.id}
                  className="glass rounded-2xl overflow-hidden hover:shadow-xl transition-shadow"
                >
                  {/* Thesis Header */}
                  <div
                    className="p-4 cursor-pointer"
                    onClick={() => setExpandedThesis(expandedThesis === thesis.id ? null : thesis.id)}
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
                        <BookOpen className="w-6 h-6 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-lg text-gray-900 break-words">
                          {thesis.title}
                        </h3>
                        {thesis.description && (
                          <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                            {thesis.description}
                          </p>
                        )}
                        <div className="flex flex-wrap items-center gap-3 mt-2">
                          {getStatusBadge(thesis.status)}
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatDate(thesis.created_at)}
                          </span>
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <List className="w-3 h-3" />
                            {thesis.num_chapters} capitoli
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {thesis.status === 'completed' && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExportThesis(thesis.id, 'pdf');
                            }}
                            disabled={exportingThesis === thesis.id}
                            className="btn btn-primary btn-sm"
                          >
                            {exportingThesis === thesis.id ? (
                              <RefreshCw className="w-4 h-4 animate-spin" />
                            ) : (
                              <Download className="w-4 h-4" />
                            )}
                            PDF
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteThesis(thesis.id);
                          }}
                          className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-600" />
                        </button>
                        <ChevronDown
                          className={`w-5 h-5 text-gray-400 transition-transform ${
                            expandedThesis === thesis.id ? 'rotate-180' : ''
                          }`}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedThesis === thesis.id && (
                    <div className="border-t border-gray-200 p-4 bg-gray-50/50">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div className="bg-white rounded-lg p-3 text-center">
                          <p className="text-xs text-gray-500 mb-1">Capitoli</p>
                          <p className="text-lg font-bold text-gray-900">{thesis.num_chapters}</p>
                        </div>
                        <div className="bg-white rounded-lg p-3 text-center">
                          <p className="text-xs text-gray-500 mb-1">Sezioni/Cap</p>
                          <p className="text-lg font-bold text-gray-900">{thesis.sections_per_chapter}</p>
                        </div>
                        <div className="bg-white rounded-lg p-3 text-center">
                          <p className="text-xs text-gray-500 mb-1">Parole/Sez</p>
                          <p className="text-lg font-bold text-gray-900">{thesis.words_per_section?.toLocaleString()}</p>
                        </div>
                        <div className="bg-white rounded-lg p-3 text-center">
                          <p className="text-xs text-gray-500 mb-1">Progresso</p>
                          <p className="text-lg font-bold text-gray-900">{thesis.generation_progress || 0}%</p>
                        </div>
                      </div>

                      {thesis.key_topics && thesis.key_topics.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs text-gray-500 mb-2">Argomenti chiave:</p>
                          <div className="flex flex-wrap gap-2">
                            {thesis.key_topics.map((topic, i) => (
                              <span key={i} className="px-2 py-1 bg-emerald-100 text-emerald-800 text-xs rounded-full">
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex gap-2">
                        {thesis.status === 'completed' && (
                          <>
                            <button
                              onClick={() => handleExportThesis(thesis.id, 'pdf')}
                              disabled={exportingThesis === thesis.id}
                              className="btn btn-primary btn-sm"
                            >
                              <Download className="w-4 h-4" />
                              PDF
                            </button>
                            <button
                              onClick={() => handleExportThesis(thesis.id, 'docx')}
                              disabled={exportingThesis === thesis.id}
                              className="btn btn-secondary btn-sm"
                            >
                              <Download className="w-4 h-4" />
                              DOCX
                            </button>
                            <button
                              onClick={() => handleExportThesis(thesis.id, 'txt')}
                              disabled={exportingThesis === thesis.id}
                              className="btn btn-secondary btn-sm"
                            >
                              <Download className="w-4 h-4" />
                              TXT
                            </button>
                            <button
                              onClick={() => handleExportThesis(thesis.id, 'md')}
                              disabled={exportingThesis === thesis.id}
                              className="btn btn-secondary btn-sm"
                            >
                              <Download className="w-4 h-4" />
                              MD
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Jobs */}
        {activeJobs.length > 0 && (
          <div className="mb-8 animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-orange-100 to-orange-200 rounded-xl flex items-center justify-center">
                  <Clock className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Job Attivi</h2>
                  <p className="text-sm text-gray-500">{activeJobs.length} in esecuzione</p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {activeJobs.map((job) => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  onUpdate={(updatedJob) => {
                    setJobs(jobs.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Recent Jobs */}
        {completedJobs.length > 0 && (
          <div className="mb-8 animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-green-100 to-green-200 rounded-xl flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Job Recenti</h2>
                  <p className="text-sm text-gray-500">Ultimi {Math.min(completedJobs.length, 5)} completati</p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {completedJobs.slice(0, 5).map((job) => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  onUpdate={(updatedJob) => {
                    setJobs(jobs.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Sessions */}
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-100 to-blue-200 rounded-xl flex items-center justify-center">
                <Layers className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Le tue Sessioni</h2>
                <p className="text-sm text-gray-500">{sessions.length} sessioni totali</p>
              </div>
            </div>

            <button
              onClick={() => navigate('/train')}
              className="btn btn-primary"
            >
              <Sparkles className="w-4 h-4" />
              Nuova Sessione
            </button>
          </div>

          {sessions.length === 0 ? (
            <div className="glass rounded-2xl text-center py-16">
              <div className="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <FileText className="w-10 h-10 text-gray-400" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Nessuna sessione</h3>
              <p className="text-gray-500 mb-6 max-w-md mx-auto">
                Inizia creando la tua prima sessione di addestramento per generare contenuti con il tuo stile unico.
              </p>
              <button
                onClick={() => navigate('/train')}
                className="btn btn-primary btn-lg"
              >
                <Upload className="w-5 h-5" />
                Crea Prima Sessione
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  className="glass rounded-2xl p-5 hover:shadow-xl transition-all group border-2 border-transparent hover:border-orange-100"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-lg text-gray-900 mb-1 truncate">
                        {session.name || session.session_id}
                      </h3>
                      {session.name && (
                        <p className="font-mono text-xs text-gray-400 truncate">
                          {session.session_id}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteSession(session.session_id)}
                      className="p-2 hover:bg-red-50 rounded-xl transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="w-4 h-4 text-gray-400 hover:text-red-600" />
                    </button>
                  </div>

                  {/* Status Badge */}
                  <div className="mb-4">
                    {session.is_trained ? (
                      <span className="badge badge-success">
                        <CheckCircle2 className="w-3 h-3" />
                        Addestrata
                      </span>
                    ) : (
                      <span className="badge badge-warning">
                        <Clock className="w-3 h-3" />
                        Non addestrata
                      </span>
                    )}
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-gray-50 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-gray-900">{session.conversation_length}</p>
                      <p className="text-xs text-gray-500">Conversazioni</p>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-gray-900">{session.jobs.length}</p>
                      <p className="text-xs text-gray-500">Job</p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => navigate(`/sessions/${session.session_id}`)}
                      className="flex-1 btn btn-secondary"
                    >
                      Dettagli
                    </button>
                    <button
                      onClick={() => navigate(`/generate?session=${session.session_id}`)}
                      className="flex-1 btn btn-primary"
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
      </main>
    </div>
  );
};

export default Dashboard;
