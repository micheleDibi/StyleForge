import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Activity, LogOut, Upload,
  Sparkles, RefreshCw, Trash2, Wand2,
  Clock, CheckCircle2, AlertCircle, Zap, User, Settings,
  Layers, Brain, BookOpen, Calendar, Download,
  ChevronDown, Eye, List, Coins, Shield, Pencil, Play, Search,
  ArrowUpRight, FileDown, ScanSearch
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
  const [templates, setTemplates] = useState([]);
  const [selectedTemplates, setSelectedTemplates] = useState({});
  const [scanResults, setScanResults] = useState({});
  const [thesisScanningId, setThesisScanningId] = useState(null);
  const [thesisScanProgress, setThesisScanProgress] = useState(0);
  const [editingSessionName, setEditingSessionName] = useState(null);
  const [editSessionValue, setEditSessionValue] = useState('');
  const editSessionRef = useRef(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (!editingSessionName) loadData();
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

  useEffect(() => {
    if (!isAdmin || jobs.length === 0) return;
    const completedJobIds = jobs.filter(j => j.status === 'completed' && (j.job_type === 'generation' || j.job_type === 'humanization')).map(j => j.job_id);
    const thesisIds = theses.filter(t => t.status === 'completed').map(t => t.id);
    const allIds = [...completedJobIds, ...thesisIds];
    if (allIds.length === 0) return;
    getCompilatioScansBySource(allIds).then(data => {
      if (data.scans) setScanResults(prev => ({ ...prev, ...data.scans }));
    }).catch(() => {});
  }, [isAdmin, jobs, theses]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const handleDeleteSession = async (sessionId) => {
    if (confirm('Sei sicuro di voler eliminare questa sessione?')) {
      try { await deleteSession(sessionId); setSessions(s => s.filter(x => x.session_id !== sessionId)); }
      catch { alert('Errore nell\'eliminazione della sessione'); }
    }
  };

  const handleDeleteThesis = async (thesisId) => {
    if (confirm('Sei sicuro di voler eliminare questa tesi?')) {
      try { await deleteThesis(thesisId); setTheses(t => t.filter(x => x.id !== thesisId)); }
      catch { alert('Errore nell\'eliminazione della tesi'); }
    }
  };

  const handleExportThesis = async (thesisId, format = 'pdf') => {
    setExportingThesis(thesisId);
    try { await exportThesis(thesisId, format, selectedTemplates[thesisId] || null); }
    catch { alert('Errore nell\'export della tesi'); }
    finally { setExportingThesis(null); }
  };

  const handleLogout = () => { if (confirm('Sei sicuro di voler uscire?')) logout(); };

  const handleStartSessionEdit = (id, name) => { setEditingSessionName(id); setEditSessionValue(name || id); };
  const handleSaveSessionName = async (id) => {
    const trimmed = editSessionValue.trim();
    if (!trimmed) { setEditingSessionName(null); return; }
    try { await renameSession(id, trimmed); setSessions(s => s.map(x => x.session_id === id ? { ...x, name: trimmed } : x)); }
    catch {} finally { setEditingSessionName(null); }
  };
  const handleSessionEditKeyDown = (e, id) => { if (e.key === 'Enter') handleSaveSessionName(id); else if (e.key === 'Escape') setEditingSessionName(null); };

  const handleThesisScan = (thesisId) => navigate(`/thesis?resume=${thesisId}`);
  const handleDownloadScanReport = async (scanId) => { try { await downloadCompilatioReport(scanId); } catch {} };
  const handleThesisNavigate = (thesis) => navigate(`/thesis?resume=${thesis.id}`);

  const getAIScoreColor = (p) => p <= 5 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : p <= 20 ? 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20';

  const getThesisAction = (t) => {
    if (t.status === 'completed') return { label: 'Apri', icon: Eye };
    if (t.status === 'generating') return { label: 'Stato', icon: Clock };
    return { label: 'Continua', icon: Play };
  };

  const formatDate = (d) => {
    if (!d) return '';
    return new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const getStatusBadge = (status) => {
    const map = {
      completed: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: CheckCircle2, text: 'Completata' },
      generating: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', icon: Clock, text: 'In corso' },
      failed: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', icon: AlertCircle, text: 'Errore' },
    };
    const s = map[status] || { cls: 'bg-white/5 text-gray-400 border-white/10', icon: Clock, text: status };
    const Icon = s.icon;
    return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${s.cls}`}><Icon className={`w-3 h-3 ${status === 'generating' ? 'animate-spin' : ''}`} />{s.text}</span>;
  };

  const nonScanJobs = useMemo(() => jobs.filter(j => j.job_type !== 'compilatio_scan'), [jobs]);
  const activeJobs = useMemo(() => nonScanJobs.filter(j => ['pending','training','generating'].includes(j.status)), [nonScanJobs]);
  const completedJobs = useMemo(() => nonScanJobs.filter(j => ['completed','failed'].includes(j.status)), [nonScanJobs]);
  const trainedSessions = useMemo(() => sessions.filter(s => s.is_trained).length, [sessions]);
  const completedTheses = useMemo(() => theses.filter(t => t.status === 'completed').length, [theses]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f]">
        <div className="text-center">
          <div className="relative inline-block mb-6">
            <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-amber-500 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <div className="absolute inset-0 border-2 border-orange-500/30 border-t-orange-400 rounded-2xl animate-spin"></div>
          </div>
          <h1 className="text-xl font-bold text-white mb-1">Style<span className="text-orange-400">Forge</span></h1>
          <p className="text-sm text-gray-500">Caricamento...</p>
          <div className="mt-4 w-48 mx-auto h-1 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-orange-500 to-amber-500 rounded-full animate-loading-bar"></div>
          </div>
        </div>
      </div>
    );
  }

  const quickActions = [
    hasPermission('train') && { key: 'train', icon: Upload, label: 'Addestra', desc: 'Carica PDF e addestra il modello', color: 'orange', path: '/train' },
    hasPermission('generate') && { key: 'gen', icon: FileText, label: 'Genera', desc: 'Crea contenuti con il tuo stile', color: 'blue', path: '/generate' },
    hasPermission('humanize') && { key: 'hum', icon: Wand2, label: 'Umanizza', desc: 'Bypassa i detector AI', color: 'purple', path: '/humanize' },
    hasPermission('thesis') && { key: 'thesis', icon: BookOpen, label: 'Tesi / Relazione', desc: 'Genera documenti accademici completi', color: 'emerald', path: '/thesis' },
    isAdmin && { key: 'detector', icon: ScanSearch, label: 'Detector AI', desc: 'Scansione AI detection e plagio', color: 'indigo', path: '/detector-ai' },
  ].filter(Boolean);

  const colorMap = {
    orange: { bg: 'from-orange-500 to-amber-500', shadow: 'shadow-orange-500/20', hover: 'hover:border-orange-500/30', ring: 'group-hover:ring-orange-500/20' },
    blue: { bg: 'from-blue-500 to-cyan-500', shadow: 'shadow-blue-500/20', hover: 'hover:border-blue-500/30', ring: 'group-hover:ring-blue-500/20' },
    purple: { bg: 'from-purple-500 to-pink-500', shadow: 'shadow-purple-500/20', hover: 'hover:border-purple-500/30', ring: 'group-hover:ring-purple-500/20' },
    emerald: { bg: 'from-emerald-500 to-teal-500', shadow: 'shadow-emerald-500/20', hover: 'hover:border-emerald-500/30', ring: 'group-hover:ring-emerald-500/20' },
    indigo: { bg: 'from-indigo-500 to-violet-500', shadow: 'shadow-indigo-500/20', hover: 'hover:border-indigo-500/30', ring: 'group-hover:ring-indigo-500/20' },
  };

  const tabs = [
    { id: 'overview', label: 'Panoramica' },
    ...(theses.length > 0 ? [{ id: 'theses', label: `Tesi (${theses.length})` }] : []),
    ...(sessions.length > 0 ? [{ id: 'sessions', label: `Sessioni (${sessions.length})` }] : []),
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">

      {/* HEADER */}
      <header className="sticky top-0 z-50 bg-[#0a0a0f]/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
          <div className="flex items-center gap-2.5">
            <Logo size="sm" />
            <span className="text-base font-bold hidden sm:block">Style<span className="text-orange-400">Forge</span></span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-xs">
              <Coins className="w-3 h-3 text-orange-400" />
              <span className="font-bold text-orange-400">{isAdmin ? '∞' : credits}</span>
            </div>
            <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-xs">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${isAdmin ? 'bg-purple-500' : 'bg-orange-500'}`}>
                {(user?.username || 'U')[0].toUpperCase()}
              </div>
              <span className="text-gray-300 font-medium">{user?.username || 'Utente'}</span>
            </div>
            {isAdmin && (
              <button onClick={() => navigate('/admin')} className="p-1.5 rounded-lg text-gray-500 hover:text-purple-400 hover:bg-purple-500/10 transition-colors" title="Admin">
                <Settings className="w-4 h-4" />
              </button>
            )}
            <button onClick={handleRefresh} disabled={refreshing} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-colors">
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={handleLogout} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* MAIN */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-8">

        {/* HERO STATS */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Sessioni', value: sessions.length, icon: Layers, color: 'text-blue-400', bg: 'bg-blue-500/10' },
            { label: 'Addestrate', value: trainedSessions, icon: Brain, color: 'text-purple-400', bg: 'bg-purple-500/10' },
            { label: 'Tesi', value: completedTheses, icon: BookOpen, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
            { label: 'Job attivi', value: activeJobs.length, icon: Zap, color: 'text-orange-400', bg: 'bg-orange-500/10', pulse: activeJobs.length > 0 },
          ].map((s, i) => (
            <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 flex items-center gap-3">
              <div className={`w-10 h-10 ${s.bg} rounded-lg flex items-center justify-center`}>
                <s.icon className={`w-5 h-5 ${s.color}`} />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-2xl font-bold text-white">{s.value}</span>
                  {s.pulse && <span className="w-2 h-2 bg-orange-400 rounded-full animate-pulse"></span>}
                </div>
                <span className="text-[11px] text-gray-500">{s.label}</span>
              </div>
            </div>
          ))}
        </div>

        {/* QUICK ACTIONS */}
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">Azioni rapide</h3>
          <div className={`grid gap-3 ${quickActions.length === 5 ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5' : 'grid-cols-2 lg:grid-cols-4'}`}>
            {quickActions.map(a => {
              const c = colorMap[a.color];
              return (
                <button
                  key={a.key}
                  onClick={() => navigate(a.path)}
                  className={`group bg-white/[0.03] border border-white/[0.06] ${c.hover} rounded-xl p-4 text-left transition-all hover:bg-white/[0.05] relative overflow-hidden`}
                >
                  <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-br ${c.bg} blur-3xl scale-150`} style={{ opacity: 0 }}></div>
                  <div className="relative z-10">
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${c.bg} ${c.shadow} shadow-lg flex items-center justify-center group-hover:scale-110 transition-transform`}>
                        <a.icon className="w-4.5 h-4.5 text-white" />
                      </div>
                      <ArrowUpRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <h4 className="font-semibold text-sm text-gray-200 group-hover:text-white transition-colors">{a.label}</h4>
                    <p className="text-[11px] text-gray-600 mt-0.5 leading-relaxed">{a.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* TABS */}
        <div className="flex items-center gap-0.5 border-b border-white/[0.06] pb-px">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === tab.id
                  ? 'text-orange-400'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-orange-400 rounded-t-full"></div>}
            </button>
          ))}
        </div>

        {/* TAB: PANORAMICA */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {activeJobs.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-1.5 h-1.5 bg-orange-400 rounded-full animate-pulse"></span>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Job in corso</h3>
                </div>
                <div className="space-y-2">
                  {activeJobs.map(job => (
                    <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]}
                      onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))}
                      onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />
                  ))}
                </div>
              </section>
            )}

            {completedJobs.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">Ultimi completati</h3>
                <div className="space-y-2">
                  {completedJobs.slice(0, 5).map(job => (
                    <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]}
                      onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))}
                      onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />
                  ))}
                </div>
              </section>
            )}

            {activeJobs.length === 0 && completedJobs.length === 0 && (
              <div className="text-center py-20">
                <div className="w-14 h-14 bg-white/[0.03] border border-white/[0.06] rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-7 h-7 text-gray-600" />
                </div>
                <h3 className="text-base font-semibold text-gray-300 mb-1">Nessun job</h3>
                <p className="text-sm text-gray-600 mb-5">Inizia addestrando un modello per vedere i risultati qui.</p>
                <button onClick={() => navigate('/train')} className="px-4 py-2 rounded-lg bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/20">
                  Inizia ora
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB: TESI */}
        {activeTab === 'theses' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">{theses.length} documenti</span>
              <button onClick={() => navigate('/thesis')} className="px-3 py-1.5 rounded-lg bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 transition-colors">
                + Nuova Tesi
              </button>
            </div>

            {theses.map(thesis => {
              const action = getThesisAction(thesis);
              const ActionIcon = action.icon;
              const scan = scanResults[thesis.id];
              const expanded = expandedThesis === thesis.id;

              return (
                <div key={thesis.id} className="bg-white/[0.03] border border-white/[0.06] rounded-xl overflow-hidden hover:border-white/[0.1] transition-colors">
                  <div className="flex items-center gap-3 p-3.5 cursor-pointer" onClick={() => setExpandedThesis(expanded ? null : thesis.id)}>
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/10 flex-shrink-0">
                      <BookOpen className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-sm font-semibold text-gray-200 truncate">{thesis.title}</h4>
                        {getStatusBadge(thesis.status)}
                        {isAdmin && scan && (
                          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold border ${getAIScoreColor(scan.ai_generated_percent)}`}>
                            AI {scan.ai_generated_percent?.toFixed(0)}%
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-[11px] text-gray-600">
                        <span>{formatDate(thesis.created_at)}</span>
                        <span>{thesis.num_chapters} capitoli</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button onClick={e => { e.stopPropagation(); handleThesisNavigate(thesis); }}
                        className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white/5 text-gray-300 hover:bg-white/10 border border-white/[0.06] transition-colors flex items-center gap-1">
                        <ActionIcon className="w-3 h-3" /> {action.label}
                      </button>
                      <button onClick={e => { e.stopPropagation(); handleDeleteThesis(thesis.id); }}
                        className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <ChevronDown className={`w-4 h-4 text-gray-600 transition-transform ${expanded ? 'rotate-180' : ''}`} />
                    </div>
                  </div>

                  {expanded && (
                    <div className="border-t border-white/[0.04] p-4 space-y-3 bg-white/[0.01]">
                      {thesis.description && <p className="text-sm text-gray-400 bg-white/[0.02] rounded-lg p-3 border border-white/[0.04]">{thesis.description}</p>}

                      <div className="grid grid-cols-4 gap-2">
                        {[
                          { l: 'Capitoli', v: thesis.num_chapters },
                          { l: 'Sez/Cap', v: thesis.sections_per_chapter },
                          { l: 'Parole/Sez', v: thesis.words_per_section?.toLocaleString() },
                          { l: 'Progresso', v: `${thesis.generation_progress || 0}%` },
                        ].map((s, i) => (
                          <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-2 text-center">
                            <div className="text-base font-bold text-white">{s.v}</div>
                            <div className="text-[9px] text-gray-500 uppercase tracking-wide">{s.l}</div>
                          </div>
                        ))}
                      </div>

                      {thesis.key_topics?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {thesis.key_topics.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[11px] rounded-md border border-emerald-500/20">{t}</span>
                          ))}
                        </div>
                      )}

                      {isAdmin && thesis.status === 'completed' && (
                        scan ? (
                          <div className="bg-white/[0.03] border border-purple-500/20 rounded-lg p-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3 h-3" /> Detector AI</span>
                              {scan.has_report && (
                                <button onClick={e => { e.stopPropagation(); handleDownloadScanReport(scan.scan_id); }}
                                  className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"><Download className="w-3 h-3" /> Report</button>
                              )}
                            </div>
                            <div className="grid grid-cols-4 gap-2">
                              <div className={`rounded-lg p-2 border text-center ${getAIScoreColor(scan.ai_generated_percent)}`}>
                                <div className="text-sm font-bold">{scan.ai_generated_percent?.toFixed(1)}%</div>
                                <div className="text-[9px] opacity-70 uppercase">AI</div>
                              </div>
                              <div className="rounded-lg p-2 border bg-blue-500/10 border-blue-500/20 text-blue-400 text-center">
                                <div className="text-sm font-bold">{scan.similarity_percent?.toFixed(1)}%</div>
                                <div className="text-[9px] opacity-70 uppercase">Simil.</div>
                              </div>
                              <div className="rounded-lg p-2 border bg-white/[0.03] border-white/[0.06] text-gray-300 text-center">
                                <div className="text-sm font-bold">{scan.global_score_percent?.toFixed(1)}%</div>
                                <div className="text-[9px] opacity-70 uppercase">Globale</div>
                              </div>
                              <div className="rounded-lg p-2 border bg-white/[0.03] border-white/[0.06] text-gray-300 text-center">
                                <div className="text-sm font-bold">{scan.exact_percent?.toFixed(1)}%</div>
                                <div className="text-[9px] opacity-70 uppercase">Esatti</div>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <button onClick={e => { e.stopPropagation(); handleThesisScan(thesis.id); }}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/20 transition-colors">
                            <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
                          </button>
                        )
                      )}

                      {thesis.status === 'completed' && (
                        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/[0.04]">
                          {templates.length > 0 && (
                            <select value={selectedTemplates[thesis.id] || ''} onChange={e => setSelectedTemplates({ ...selectedTemplates, [thesis.id]: e.target.value || null })}
                              onClick={e => e.stopPropagation()}
                              className="text-[11px] bg-white/[0.05] border border-white/[0.1] rounded-lg px-2 py-1.5 text-gray-400 focus:outline-none focus:border-orange-500/30">
                              <option value="">Template default</option>
                              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          )}
                          <div className="flex items-center gap-1">
                            {['pdf', 'docx', 'txt', 'md'].map(f => (
                              <button key={f} onClick={e => { e.stopPropagation(); handleExportThesis(thesis.id, f); }}
                                disabled={exportingThesis === thesis.id}
                                className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                                  f === 'pdf' ? 'bg-orange-500 text-white hover:bg-orange-600' : 'bg-white/5 text-gray-400 hover:bg-white/10 border border-white/[0.06]'
                                }`}>
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

        {/* TAB: SESSIONI */}
        {activeTab === 'sessions' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-500">{sessions.length} sessioni, {trainedSessions} addestrate</span>
              <button onClick={() => navigate('/train')} className="px-3 py-1.5 rounded-lg bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 transition-colors">
                + Nuova Sessione
              </button>
            </div>

            {sessions.length === 0 ? (
              <div className="text-center py-20">
                <div className="w-14 h-14 bg-white/[0.03] border border-white/[0.06] rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <FileText className="w-7 h-7 text-gray-600" />
                </div>
                <h3 className="text-base font-semibold text-gray-300 mb-1">Nessuna sessione</h3>
                <p className="text-sm text-gray-600 mb-5">Crea la tua prima sessione di addestramento.</p>
                <button onClick={() => navigate('/train')} className="px-4 py-2 rounded-lg bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 transition-colors">
                  Crea Sessione
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {sessions.map(session => (
                  <div key={session.session_id} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.1] transition-colors group">
                    <div className="flex items-start justify-between mb-2.5">
                      <div className="flex-1 min-w-0">
                        {editingSessionName === session.session_id ? (
                          <input ref={editSessionRef} type="text" value={editSessionValue}
                            onChange={e => setEditSessionValue(e.target.value)}
                            onBlur={() => handleSaveSessionName(session.session_id)}
                            onKeyDown={e => handleSessionEditKeyDown(e, session.session_id)}
                            className="text-sm font-semibold text-white bg-white/5 border border-white/10 rounded-lg px-2 py-1 w-full focus:outline-none focus:border-orange-500/30"
                            maxLength={255} onClick={e => e.stopPropagation()} />
                        ) : (
                          <div className="flex items-center gap-1 group/name">
                            <h4 className="text-sm font-semibold text-gray-200 truncate">{session.name || session.session_id}</h4>
                            <button onClick={() => handleStartSessionEdit(session.session_id, session.name || session.session_id)}
                              className="opacity-0 group-hover/name:opacity-100 transition-opacity p-0.5 hover:bg-white/5 rounded flex-shrink-0">
                              <Pencil className="w-3 h-3 text-gray-600" />
                            </button>
                          </div>
                        )}
                        {session.name && !editingSessionName && <p className="font-mono text-[10px] text-gray-600 truncate mt-0.5">{session.session_id}</p>}
                      </div>
                      <button onClick={() => handleDeleteSession(session.session_id)}
                        className="p-1 rounded-lg text-gray-700 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="flex items-center gap-2 mb-3">
                      {session.is_trained ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" /> Addestrata
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Clock className="w-3 h-3" /> Non addestrata
                        </span>
                      )}
                      <span className="text-[11px] text-gray-600">{session.conversation_length} conv. · {session.jobs.length} job</span>
                    </div>

                    <div className="flex gap-2">
                      <button onClick={() => navigate(`/sessions/${session.session_id}`)}
                        className="flex-1 py-2 rounded-lg text-xs font-medium bg-white/5 text-gray-300 hover:bg-white/10 border border-white/[0.06] transition-colors text-center">
                        Dettagli
                      </button>
                      <button onClick={() => navigate(`/generate?session=${session.session_id}`)} disabled={!session.is_trained}
                        className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors text-center ${
                          session.is_trained ? 'bg-orange-500 text-white hover:bg-orange-600 shadow-lg shadow-orange-500/10' : 'bg-white/[0.03] text-gray-600 cursor-not-allowed'
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
