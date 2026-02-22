import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, LogOut, Upload, Sparkles, RefreshCw, Trash2, Wand2,
  Clock, CheckCircle2, AlertCircle, Zap, User, Settings,
  Layers, Brain, BookOpen, Calendar, Download,
  ChevronDown, Eye, Play, Coins, Shield, Pencil, Search,
  ArrowUpRight, ScanSearch, FileDown
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getSessions, deleteSession, renameSession, healthCheck, getJobs, getTheses, deleteThesis, exportThesis, getExportTemplates, getCompilatioScansBySource, downloadCompilatioReport } from '../services/api';
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
  const [templates, setTemplates] = useState([]);
  const [selectedTemplates, setSelectedTemplates] = useState({});
  const [scanResults, setScanResults] = useState({});
  const [editingSessionName, setEditingSessionName] = useState(null);
  const [editSessionValue, setEditSessionValue] = useState('');
  const editSessionRef = useRef(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadData();
    const interval = setInterval(() => { if (!editingSessionName) loadData(); }, 10000);
    return () => clearInterval(interval);
  }, [editingSessionName]);

  useEffect(() => {
    if (editingSessionName && editSessionRef.current) { editSessionRef.current.focus(); editSessionRef.current.select(); }
  }, [editingSessionName]);

  const loadData = async () => {
    try {
      const [sessionsData, healthData, jobsData, thesesData, templatesData] = await Promise.all([
        getSessions(), healthCheck(), getJobs(),
        getTheses().catch(() => ({ theses: [] })),
        getExportTemplates().catch(() => ({ templates: [] }))
      ]);
      setSessions(sessionsData.sessions); setHealth(healthData);
      setJobs(jobsData.jobs || []); setTheses(thesesData.theses || []);
      setTemplates(templatesData.templates || []);
    } catch (error) { console.error('Errore nel caricamento:', error); }
    finally { setLoading(false); setRefreshing(false); }
  };

  useEffect(() => {
    if (!isAdmin || jobs.length === 0) return;
    const ids = [
      ...jobs.filter(j => j.status === 'completed' && ['generation','humanization'].includes(j.job_type)).map(j => j.job_id),
      ...theses.filter(t => t.status === 'completed').map(t => t.id)
    ];
    if (ids.length === 0) return;
    getCompilatioScansBySource(ids).then(d => { if (d.scans) setScanResults(p => ({ ...p, ...d.scans })); }).catch(() => {});
  }, [isAdmin, jobs, theses]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };
  const handleDeleteSession = async (id) => { if (confirm('Eliminare questa sessione?')) { try { await deleteSession(id); setSessions(s => s.filter(x => x.session_id !== id)); } catch { alert('Errore'); } } };
  const handleDeleteThesis = async (id) => { if (confirm('Eliminare questa tesi?')) { try { await deleteThesis(id); setTheses(t => t.filter(x => x.id !== id)); } catch { alert('Errore'); } } };
  const handleExportThesis = async (id, fmt = 'pdf') => { setExportingThesis(id); try { await exportThesis(id, fmt, selectedTemplates[id] || null); } catch { alert('Errore export'); } finally { setExportingThesis(null); } };
  const handleLogout = () => { if (confirm('Uscire?')) logout(); };
  const handleStartSessionEdit = (id, name) => { setEditingSessionName(id); setEditSessionValue(name || id); };
  const handleSaveSessionName = async (id) => { const t = editSessionValue.trim(); if (!t) { setEditingSessionName(null); return; } try { await renameSession(id, t); setSessions(s => s.map(x => x.session_id === id ? { ...x, name: t } : x)); } catch {} setEditingSessionName(null); };
  const handleSessionEditKeyDown = (e, id) => { if (e.key === 'Enter') handleSaveSessionName(id); else if (e.key === 'Escape') setEditingSessionName(null); };
  const handleThesisScan = (id) => navigate(`/thesis?resume=${id}`);
  const handleDownloadScanReport = async (scanId) => { try { await downloadCompilatioReport(scanId); } catch {} };
  const handleThesisNavigate = (t) => navigate(`/thesis?resume=${t.id}`);

  const getAIScoreColor = (p) => p <= 5 ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : p <= 20 ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-red-600 bg-red-50 border-red-200';
  const getThesisAction = (t) => t.status === 'completed' ? { label: 'Apri', icon: Eye } : t.status === 'generating' ? { label: 'Stato', icon: Clock } : { label: 'Continua', icon: Play };
  const formatDate = (d) => d ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
  const getStatusBadge = (status) => {
    const m = { completed: 'bg-emerald-50 text-emerald-700 border-emerald-200', generating: 'bg-amber-50 text-amber-700 border-amber-200', failed: 'bg-red-50 text-red-700 border-red-200' };
    const icons = { completed: CheckCircle2, generating: Clock, failed: AlertCircle };
    const labels = { completed: 'Completata', generating: 'In corso', failed: 'Errore' };
    const cls = m[status] || 'bg-gray-50 text-gray-600 border-gray-200';
    const Icon = icons[status] || Clock;
    return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${cls}`}><Icon className={`w-3 h-3 ${status === 'generating' ? 'animate-spin' : ''}`} />{labels[status] || status}</span>;
  };

  const nonScanJobs = useMemo(() => jobs.filter(j => j.job_type !== 'compilatio_scan'), [jobs]);
  const activeJobs = useMemo(() => nonScanJobs.filter(j => ['pending','training','generating'].includes(j.status)), [nonScanJobs]);
  const completedJobs = useMemo(() => nonScanJobs.filter(j => ['completed','failed'].includes(j.status)), [nonScanJobs]);
  const trainedSessions = useMemo(() => sessions.filter(s => s.is_trained).length, [sessions]);
  const completedTheses = useMemo(() => theses.filter(t => t.status === 'completed').length, [theses]);

  // ─── Loading ───
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-white to-purple-50">
        <div className="text-center">
          <div className="relative inline-block mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-xl shadow-orange-500/25">
              <Sparkles className="w-10 h-10 text-white" />
            </div>
            <div className="absolute inset-0 border-[3px] border-orange-200 border-t-orange-500 rounded-2xl animate-spin"></div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Style<span className="text-orange-500">Forge</span></h1>
          <p className="text-sm text-gray-400">Caricamento...</p>
          <div className="mt-5 w-48 mx-auto h-1.5 bg-orange-100 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-orange-400 to-orange-600 rounded-full animate-loading-bar"></div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Quick Actions config ───
  const quickActions = [
    hasPermission('train') && { key: 'train', icon: Upload, label: 'Addestra', desc: 'Carica PDF e addestra', gradient: 'from-orange-500 to-amber-500', shadow: 'shadow-orange-500/15', hoverBorder: 'hover:border-orange-300/50', path: '/train' },
    hasPermission('generate') && { key: 'gen', icon: FileText, label: 'Genera', desc: 'Crea con il tuo stile', gradient: 'from-blue-500 to-indigo-500', shadow: 'shadow-blue-500/15', hoverBorder: 'hover:border-blue-300/50', path: '/generate' },
    hasPermission('humanize') && { key: 'hum', icon: Wand2, label: 'Umanizza', desc: 'Bypassa AI detection', gradient: 'from-violet-500 to-purple-600', shadow: 'shadow-violet-500/15', hoverBorder: 'hover:border-violet-300/50', path: '/humanize' },
    hasPermission('thesis') && { key: 'thesis', icon: BookOpen, label: 'Tesi / Relazione', desc: 'Genera documenti completi', gradient: 'from-emerald-500 to-teal-500', shadow: 'shadow-emerald-500/15', hoverBorder: 'hover:border-emerald-300/50', path: '/thesis' },
    isAdmin && { key: 'detector', icon: ScanSearch, label: 'Detector AI', desc: 'Scansione AI e plagio', gradient: 'from-pink-500 to-rose-500', shadow: 'shadow-pink-500/15', hoverBorder: 'hover:border-pink-300/50', path: '/detector-ai' },
  ].filter(Boolean);

  const tabs = [
    { id: 'overview', label: 'Panoramica' },
    ...(theses.length > 0 ? [{ id: 'theses', label: `Tesi (${theses.length})` }] : []),
    ...(sessions.length > 0 ? [{ id: 'sessions', label: `Sessioni (${sessions.length})` }] : []),
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-orange-50/30">

      {/* ═══ HEADER ═══ */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/70 border-b border-gray-200/50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between h-[56px]">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <span className="text-lg font-bold text-gray-900 hidden sm:block">Style<span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-500 to-amber-500">Forge</span></span>
          </div>
          <div className="flex items-center gap-2">
            {/* Credits */}
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200/50">
              <Coins className="w-3.5 h-3.5 text-orange-500" />
              <span className="text-sm font-bold text-orange-600">{isAdmin ? '∞' : credits}</span>
            </div>
            {/* User */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/80 border border-gray-200/50 shadow-sm">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold ${isAdmin ? 'bg-gradient-to-br from-violet-500 to-purple-600' : 'bg-gradient-to-br from-orange-500 to-amber-500'}`}>
                {(user?.username || 'U')[0].toUpperCase()}
              </div>
              <span className="text-sm font-medium text-gray-700">{user?.username}</span>
              {isAdmin && <span className="text-[9px] font-bold text-violet-600 bg-violet-100 px-1.5 py-0.5 rounded-full">ADMIN</span>}
            </div>
            <div className="w-px h-5 bg-gray-200/60 hidden sm:block"></div>
            {isAdmin && <button onClick={() => navigate('/admin')} className="p-2 rounded-xl text-gray-400 hover:text-violet-600 hover:bg-violet-50 transition-all" title="Admin"><Settings className="w-[18px] h-[18px]" /></button>}
            <button onClick={handleRefresh} disabled={refreshing} className="p-2 rounded-xl text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all"><RefreshCw className={`w-[18px] h-[18px] ${refreshing ? 'animate-spin' : ''}`} /></button>
            <button onClick={handleLogout} className="p-2 rounded-xl text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"><LogOut className="w-[18px] h-[18px]" /></button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">

        {/* ═══ WELCOME + STATS ═══ */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-orange-500 via-orange-600 to-amber-500 p-8 text-white shadow-xl shadow-orange-500/15">
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/3 translate-x-1/4 blur-2xl"></div>
          <div className="absolute bottom-0 left-1/4 w-32 h-32 bg-white/5 rounded-full translate-y-1/2 blur-xl"></div>
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <h2 className="text-2xl font-bold mb-1">Ciao, {user?.username || 'Utente'} 👋</h2>
              <p className="text-white/70 text-sm">{activeJobs.length > 0 ? `${activeJobs.length} job in esecuzione` : 'Tutto operativo — pronto a creare'}</p>
            </div>
            <div className="flex gap-3 flex-wrap">
              {[
                { v: sessions.length, l: 'Sessioni' },
                { v: trainedSessions, l: 'Addestrate' },
                { v: completedTheses, l: 'Tesi' },
                { v: activeJobs.length, l: 'Job attivi', pulse: activeJobs.length > 0 },
              ].map((s, i) => (
                <div key={i} className="bg-white/15 backdrop-blur-sm rounded-2xl px-5 py-3 text-center min-w-[85px]">
                  <div className="flex items-center justify-center gap-1.5">
                    <span className="text-2xl font-bold">{s.v}</span>
                    {s.pulse && <span className="w-2 h-2 bg-white rounded-full animate-pulse"></span>}
                  </div>
                  <span className="text-[11px] text-white/60">{s.l}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══ QUICK ACTIONS ═══ */}
        <section>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-[0.15em] mb-4">Azioni rapide</h3>
          <div className={`grid gap-3 ${quickActions.length >= 5 ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5' : 'grid-cols-2 lg:grid-cols-4'}`}>
            {quickActions.map(a => (
              <button key={a.key} onClick={() => navigate(a.path)}
                className={`group relative bg-white/60 backdrop-blur-sm border border-white/80 ${a.hoverBorder} rounded-2xl p-5 text-left transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 shadow-sm`}>
                <div className="flex items-center justify-between mb-4">
                  <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${a.gradient} ${a.shadow} shadow-lg flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
                    <a.icon className="w-5 h-5 text-white" />
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-gray-300 group-hover:text-gray-500 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all duration-300" />
                </div>
                <h4 className="font-semibold text-[15px] text-gray-800 mb-0.5">{a.label}</h4>
                <p className="text-xs text-gray-400 leading-relaxed">{a.desc}</p>
              </button>
            ))}
          </div>
        </section>

        {/* ═══ TABS ═══ */}
        <div className="flex items-center gap-1 p-1 bg-white/60 backdrop-blur-sm border border-white/80 rounded-2xl w-fit shadow-sm">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-400 hover:text-gray-600'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* ═══ TAB: PANORAMICA ═══ */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {activeJobs.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></span>
                  <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-[0.15em]">Job in corso</h3>
                </div>
                <div className="space-y-2.5">
                  {activeJobs.map(job => <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]} onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))} onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />)}
                </div>
              </section>
            )}
            {completedJobs.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-[0.15em] mb-3">Completati di recente</h3>
                <div className="space-y-2.5">
                  {completedJobs.slice(0, 5).map(job => <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]} onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))} onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />)}
                </div>
              </section>
            )}
            {activeJobs.length === 0 && completedJobs.length === 0 && (
              <div className="text-center py-20 bg-white/40 backdrop-blur-sm border border-white/60 rounded-3xl shadow-sm">
                <div className="w-16 h-16 bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-inner">
                  <Zap className="w-8 h-8 text-gray-300" />
                </div>
                <h3 className="text-lg font-semibold text-gray-800 mb-1">Nessun job ancora</h3>
                <p className="text-sm text-gray-400 mb-6 max-w-xs mx-auto">Addestra un modello o genera contenuti per vederli qui.</p>
                <button onClick={() => navigate('/train')} className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-300">
                  Inizia ora
                </button>
              </div>
            )}
          </div>
        )}

        {/* ═══ TAB: TESI ═══ */}
        {activeTab === 'theses' && (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-gray-400">{theses.length} documenti</span>
              <button onClick={() => navigate('/thesis')} className="px-4 py-2 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 text-white text-xs font-semibold hover:shadow-lg hover:shadow-orange-500/15 transition-all duration-300">
                + Nuova Tesi
              </button>
            </div>
            {theses.map(thesis => {
              const action = getThesisAction(thesis);
              const ActionIcon = action.icon;
              const scan = scanResults[thesis.id];
              const expanded = expandedThesis === thesis.id;
              return (
                <div key={thesis.id} className="bg-white/60 backdrop-blur-sm border border-white/80 rounded-2xl overflow-hidden shadow-sm hover:shadow-md hover:-translate-y-px transition-all duration-300">
                  <div className="flex items-center gap-3.5 p-4 cursor-pointer" onClick={() => setExpandedThesis(expanded ? null : thesis.id)}>
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-500/15 flex-shrink-0">
                      <BookOpen className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="font-semibold text-gray-800 text-sm truncate">{thesis.title}</h4>
                        {getStatusBadge(thesis.status)}
                        {isAdmin && scan && <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold border ${getAIScoreColor(scan.ai_generated_percent)}`}>AI {scan.ai_generated_percent?.toFixed(0)}%</span>}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                        <span>{formatDate(thesis.created_at)}</span>
                        <span>{thesis.num_chapters} capitoli</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button onClick={e => { e.stopPropagation(); handleThesisNavigate(thesis); }}
                        className="px-3 py-1.5 rounded-xl text-xs font-medium bg-white/80 text-gray-600 hover:bg-white border border-gray-200/50 shadow-sm transition-all flex items-center gap-1">
                        <ActionIcon className="w-3.5 h-3.5" /> {action.label}
                      </button>
                      <button onClick={e => { e.stopPropagation(); handleDeleteThesis(thesis.id); }} className="p-1.5 rounded-xl text-gray-300 hover:text-red-500 hover:bg-red-50 transition-all">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <ChevronDown className={`w-4 h-4 text-gray-300 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`} />
                    </div>
                  </div>

                  {expanded && (
                    <div className="border-t border-gray-100/50 p-5 space-y-4 bg-gradient-to-b from-white/30 to-transparent">
                      {thesis.description && <p className="text-sm text-gray-500 bg-white/50 rounded-xl p-3 border border-white/60">{thesis.description}</p>}
                      <div className="grid grid-cols-4 gap-2.5">
                        {[{ l: 'Capitoli', v: thesis.num_chapters }, { l: 'Sez/Cap', v: thesis.sections_per_chapter }, { l: 'Parole/Sez', v: thesis.words_per_section?.toLocaleString() }, { l: 'Progresso', v: `${thesis.generation_progress || 0}%` }].map((s, i) => (
                          <div key={i} className="bg-white/50 backdrop-blur-sm border border-white/60 rounded-xl p-3 text-center shadow-sm">
                            <div className="text-lg font-bold text-gray-800">{s.v}</div>
                            <div className="text-[10px] text-gray-400 uppercase tracking-wider">{s.l}</div>
                          </div>
                        ))}
                      </div>
                      {thesis.key_topics?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {thesis.key_topics.map((t, i) => <span key={i} className="px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs rounded-lg border border-emerald-200/50 font-medium">{t}</span>)}
                        </div>
                      )}
                      {isAdmin && thesis.status === 'completed' && (
                        scan ? (
                          <div className="bg-violet-50/50 backdrop-blur-sm border border-violet-200/50 rounded-xl p-4">
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-[11px] font-bold text-violet-600 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3.5 h-3.5" /> Detector AI</span>
                              {scan.has_report && <button onClick={e => { e.stopPropagation(); handleDownloadScanReport(scan.scan_id); }} className="text-xs text-violet-500 hover:text-violet-700 flex items-center gap-1 font-medium"><Download className="w-3 h-3" /> Report</button>}
                            </div>
                            <div className="grid grid-cols-4 gap-2">
                              {[
                                { v: scan.ai_generated_percent, l: 'AI', cls: getAIScoreColor(scan.ai_generated_percent) },
                                { v: scan.similarity_percent, l: 'Similarita', cls: 'text-blue-600 bg-blue-50 border-blue-200' },
                                { v: scan.global_score_percent, l: 'Globale', cls: 'text-gray-600 bg-gray-50 border-gray-200' },
                                { v: scan.exact_percent, l: 'Esatti', cls: 'text-gray-600 bg-gray-50 border-gray-200' },
                              ].map((m, i) => (
                                <div key={i} className={`rounded-xl p-2.5 border text-center ${m.cls}`}>
                                  <div className="text-sm font-bold">{m.v?.toFixed(1)}%</div>
                                  <div className="text-[9px] font-medium opacity-70 uppercase">{m.l}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <button onClick={e => { e.stopPropagation(); handleThesisScan(thesis.id); }}
                            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-violet-50 text-violet-600 hover:bg-violet-100 border border-violet-200/50 transition-all">
                            <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
                          </button>
                        )
                      )}
                      {thesis.status === 'completed' && (
                        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-gray-100/50">
                          {templates.length > 0 && (
                            <select value={selectedTemplates[thesis.id] || ''} onChange={e => setSelectedTemplates({ ...selectedTemplates, [thesis.id]: e.target.value || null })} onClick={e => e.stopPropagation()}
                              className="text-xs bg-white/70 border border-gray-200/50 rounded-xl px-3 py-2 text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-300 backdrop-blur-sm">
                              <option value="">Template default</option>
                              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          )}
                          <div className="flex items-center gap-1.5">
                            <FileDown className="w-3.5 h-3.5 text-gray-300" />
                            {['pdf','docx','txt','md'].map(f => (
                              <button key={f} onClick={e => { e.stopPropagation(); handleExportThesis(thesis.id, f); }} disabled={exportingThesis === thesis.id}
                                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${f === 'pdf' ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-sm hover:shadow-md hover:shadow-orange-500/15' : 'bg-white/70 text-gray-500 hover:bg-white border border-gray-200/50'}`}>
                                {exportingThesis === thesis.id && f === 'pdf' ? <RefreshCw className="w-3 h-3 animate-spin" /> : f.toUpperCase()}
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

        {/* ═══ TAB: SESSIONI ═══ */}
        {activeTab === 'sessions' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-400">{sessions.length} sessioni, {trainedSessions} addestrate</span>
              <button onClick={() => navigate('/train')} className="px-4 py-2 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 text-white text-xs font-semibold hover:shadow-lg hover:shadow-orange-500/15 transition-all duration-300">
                + Nuova Sessione
              </button>
            </div>
            {sessions.length === 0 ? (
              <div className="text-center py-20 bg-white/40 backdrop-blur-sm border border-white/60 rounded-3xl shadow-sm">
                <div className="w-16 h-16 bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4"><FileText className="w-8 h-8 text-gray-300" /></div>
                <h3 className="text-lg font-semibold text-gray-800 mb-1">Nessuna sessione</h3>
                <p className="text-sm text-gray-400 mb-6">Crea la tua prima sessione di addestramento.</p>
                <button onClick={() => navigate('/train')} className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-orange-500/20 transition-all">Crea Sessione</button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {sessions.map(session => (
                  <div key={session.session_id} className="bg-white/60 backdrop-blur-sm border border-white/80 rounded-2xl p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 group shadow-sm">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        {editingSessionName === session.session_id ? (
                          <input ref={editSessionRef} type="text" value={editSessionValue} onChange={e => setEditSessionValue(e.target.value)}
                            onBlur={() => handleSaveSessionName(session.session_id)} onKeyDown={e => handleSessionEditKeyDown(e, session.session_id)}
                            className="text-sm font-semibold text-gray-800 bg-white border border-gray-200 rounded-xl px-2.5 py-1 w-full focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-300"
                            maxLength={255} onClick={e => e.stopPropagation()} />
                        ) : (
                          <div className="flex items-center gap-1 group/name">
                            <h4 className="text-sm font-semibold text-gray-800 truncate">{session.name || session.session_id}</h4>
                            <button onClick={() => handleStartSessionEdit(session.session_id, session.name || session.session_id)}
                              className="opacity-0 group-hover/name:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded-lg flex-shrink-0">
                              <Pencil className="w-3 h-3 text-gray-400" />
                            </button>
                          </div>
                        )}
                        {session.name && !editingSessionName && <p className="font-mono text-[10px] text-gray-400 truncate mt-0.5">{session.session_id}</p>}
                      </div>
                      <button onClick={() => handleDeleteSession(session.session_id)}
                        className="p-1.5 rounded-xl text-gray-300 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mb-4">
                      {session.is_trained
                        ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-200/50"><CheckCircle2 className="w-3 h-3" /> Addestrata</span>
                        : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-200/50"><Clock className="w-3 h-3" /> Non addestrata</span>
                      }
                      <span className="text-[11px] text-gray-400">{session.conversation_length} conv. · {session.jobs.length} job</span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => navigate(`/sessions/${session.session_id}`)}
                        className="flex-1 py-2.5 rounded-xl text-xs font-semibold bg-white/70 text-gray-600 hover:bg-white border border-gray-200/50 shadow-sm transition-all text-center">
                        Dettagli
                      </button>
                      <button onClick={() => navigate(`/generate?session=${session.session_id}`)} disabled={!session.is_trained}
                        className={`flex-1 py-2.5 rounded-xl text-xs font-semibold transition-all text-center ${
                          session.is_trained
                            ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-sm hover:shadow-md hover:shadow-orange-500/15'
                            : 'bg-gray-50 text-gray-300 cursor-not-allowed'
                        }`}>
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
