import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, LogOut, Upload, Sparkles, RefreshCw, Trash2, Wand2,
  Clock, CheckCircle2, AlertCircle, Zap, User, Settings,
  Layers, Brain, BookOpen, Calendar, Download,
  ChevronDown, Eye, Play, Coins, Shield, Pencil, Search,
  ArrowUpRight, ScanSearch, FileDown, BarChart3, ImagePlus
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

  const getAIScoreColor = (p) => p <= 5 ? 'badge-success' : p <= 20 ? 'badge-warning' : 'badge-error';
  const getAIScoreColorInline = (p) => p <= 5 ? 'text-green-700 bg-green-50 border-green-200' : p <= 20 ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-red-700 bg-red-50 border-red-200';
  const getThesisAction = (t) => t.status === 'completed' ? { label: 'Apri', icon: Eye } : t.status === 'generating' ? { label: 'Stato', icon: Clock } : { label: 'Continua', icon: Play };
  const formatDate = (d) => d ? new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
  const getStatusBadge = (status) => {
    const m = { completed: 'badge-success', generating: 'badge-warning', failed: 'badge-error' };
    const icons = { completed: CheckCircle2, generating: Clock, failed: AlertCircle };
    const labels = { completed: 'Completata', generating: 'In corso', failed: 'Errore' };
    const Icon = icons[status] || Clock;
    return <span className={`badge ${m[status] || 'badge-neutral'}`}><Icon className={`w-3 h-3 ${status === 'generating' ? 'animate-spin' : ''}`} />{labels[status] || status}</span>;
  };

  const nonScanJobs = useMemo(() => jobs.filter(j => j.job_type !== 'compilatio_scan'), [jobs]);
  const activeJobs = useMemo(() => nonScanJobs.filter(j => ['pending','training','generating'].includes(j.status)), [nonScanJobs]);
  const completedJobs = useMemo(() => nonScanJobs.filter(j => ['completed','failed'].includes(j.status)), [nonScanJobs]);
  const trainedSessions = useMemo(() => sessions.filter(s => s.is_trained).length, [sessions]);
  const completedTheses = useMemo(() => theses.filter(t => t.status === 'completed').length, [theses]);

  // ─── Loading ───
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="relative inline-block mb-6">
            <div className="w-20 h-20 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-xl shadow-orange-500/25">
              <Sparkles className="w-10 h-10 text-white" />
            </div>
            <div className="absolute inset-0 border-[3px] border-orange-200 border-t-orange-500 rounded-2xl animate-spin"></div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Style<span className="gradient-text">Forge</span></h1>
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
    hasPermission('train') && { key: 'train', icon: Upload, label: 'Addestra', desc: 'Carica PDF e addestra il modello', gradient: 'from-orange-400 to-orange-600', path: '/train' },
    hasPermission('generate') && { key: 'gen', icon: FileText, label: 'Genera', desc: 'Crea contenuti con il tuo stile', gradient: 'from-blue-400 to-blue-600', path: '/generate' },
    hasPermission('humanize') && { key: 'hum', icon: Wand2, label: 'Umanizza', desc: 'Bypassa AI detection', gradient: 'from-purple-400 to-purple-600', path: '/humanize' },
    hasPermission('thesis') && { key: 'thesis', icon: BookOpen, label: 'Tesi / Relazione', desc: 'Genera documenti completi', gradient: 'from-green-400 to-green-600', path: '/thesis' },
    hasPermission('enhance_image') && { key: 'enhance', icon: ImagePlus, label: 'Migliora Immagine', desc: 'Migliora qualita foto con AI', gradient: 'from-cyan-400 to-teal-600', path: '/enhance-image' },
    isAdmin && { key: 'detector', icon: ScanSearch, label: 'Detector AI', desc: 'Scansione AI e plagio', gradient: 'from-pink-400 to-rose-600', path: '/detector-ai' },
  ].filter(Boolean);

  const tabs = [
    { id: 'overview', label: 'Panoramica', icon: Layers },
    ...(theses.length > 0 ? [{ id: 'theses', label: `Tesi (${theses.length})`, icon: BookOpen }] : []),
    ...(sessions.length > 0 ? [{ id: 'sessions', label: `Sessioni (${sessions.length})`, icon: Brain }] : []),
  ];

  return (
    <div className="min-h-screen relative">
      {/* ═══ ANIMATED BACKGROUND ═══ */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-gradient-to-br from-orange-100 to-orange-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob"></div>
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-gradient-to-br from-purple-100 to-pink-100 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-0 left-1/2 w-[400px] h-[400px] bg-gradient-to-br from-blue-100 to-cyan-100 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* ═══ HEADER ═══ */}
      <header className="relative z-10 glass border-b border-white/20">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-xl blur-lg opacity-50"></div>
                  <Logo size="md" className="relative" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">
                    Style<span className="gradient-text">Forge</span>
                  </h1>
                  <p className="text-gray-500 text-sm">Dashboard</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Credits */}
              <div className="hidden sm:flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-50 to-amber-50 rounded-xl border border-orange-200/50">
                <Coins className="w-4 h-4 text-orange-500" />
                <span className="text-sm font-bold text-orange-700">{isAdmin ? '∞' : credits}</span>
                <span className="text-xs text-orange-500">crediti</span>
              </div>
              {/* User */}
              <div className="hidden md:flex items-center gap-2 px-3 py-2 bg-white/70 rounded-xl border border-gray-200/50">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold ${isAdmin ? 'bg-gradient-to-br from-orange-400 to-orange-600' : 'bg-gradient-to-br from-blue-400 to-blue-600'}`}>
                  {(user?.username || 'U')[0].toUpperCase()}
                </div>
                <span className="text-sm font-medium text-gray-700">{user?.username}</span>
                {isAdmin && <span className="badge badge-warning text-[10px]">ADMIN</span>}
              </div>
              {isAdmin && <button onClick={() => navigate('/admin')} className="btn btn-ghost" title="Admin"><Settings className="w-[18px] h-[18px]" /></button>}
              <button onClick={handleRefresh} disabled={refreshing} className="btn btn-ghost"><RefreshCw className={`w-[18px] h-[18px] ${refreshing ? 'animate-spin' : ''}`} /></button>
              <button onClick={handleLogout} className="btn btn-ghost text-red-500 hover:text-red-600 hover:bg-red-50"><LogOut className="w-[18px] h-[18px]" /></button>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* ═══ WELCOME BANNER ═══ */}
        <div className="glass rounded-2xl p-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-orange-200 to-purple-100 rounded-full -translate-y-1/3 translate-x-1/4 blur-2xl opacity-50"></div>
          <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-1">Ciao, {user?.username || 'Utente'} 👋</h2>
              <p className="text-gray-500 text-sm">{activeJobs.length > 0 ? `${activeJobs.length} job in esecuzione` : 'Tutto operativo — pronto a creare'}</p>
            </div>
            <div className="flex gap-3 flex-wrap">
              {[
                { v: sessions.length, l: 'Sessioni', icon: Brain, color: 'from-blue-400 to-blue-600' },
                { v: trainedSessions, l: 'Addestrate', icon: CheckCircle2, color: 'from-green-400 to-green-600' },
                { v: completedTheses, l: 'Tesi', icon: BookOpen, color: 'from-purple-400 to-purple-600' },
                { v: activeJobs.length, l: 'Job attivi', icon: Zap, color: 'from-orange-400 to-orange-600', pulse: activeJobs.length > 0 },
              ].map((s, i) => (
                <div key={i} className="bg-white/70 rounded-xl px-5 py-3 text-center border border-gray-200/50 min-w-[90px]">
                  <div className="flex items-center justify-center gap-1.5">
                    <span className="text-2xl font-bold text-gray-900">{s.v}</span>
                    {s.pulse && <span className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></span>}
                  </div>
                  <span className="text-xs text-gray-500">{s.l}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══ QUICK ACTIONS ═══ */}
        <section>
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">Azioni rapide</h3>
          <div className={`grid gap-4 ${quickActions.length >= 5 ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5' : 'grid-cols-2 lg:grid-cols-4'}`}>
            {quickActions.map(a => (
              <div key={a.key} onClick={() => navigate(a.path)}
                className="glass rounded-2xl p-5 card-interactive group cursor-pointer">
                <div className="flex items-center justify-between mb-4">
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${a.gradient} flex items-center justify-center shadow-lg`}>
                    <a.icon className="w-6 h-6 text-white" />
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-gray-300 group-hover:text-gray-500 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-all" />
                </div>
                <h4 className="font-bold text-gray-900 mb-0.5">{a.label}</h4>
                <p className="text-xs text-gray-500 leading-relaxed">{a.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ═══ TABS ═══ */}
        <div className="flex gap-2 flex-wrap">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 rounded-xl font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/30'
                  : 'bg-white/70 text-gray-600 hover:bg-white hover:shadow-md'
              }`}>
              <tab.icon className="w-4 h-4" />
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
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Job in corso</h3>
                </div>
                <div className="space-y-3">
                  {activeJobs.map(job => <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]} onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))} onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />)}
                </div>
              </section>
            )}
            {completedJobs.length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">Completati di recente</h3>
                <div className="space-y-3">
                  {completedJobs.slice(0, 5).map(job => <JobCard key={job.job_id} job={job} isAdmin={isAdmin} scanResult={scanResults[job.job_id]} onUpdate={u => setJobs(j => j.map(x => x.job_id === u.job_id ? u : x))} onScanComplete={(id, r) => setScanResults(p => ({ ...p, [id]: r }))} />)}
                </div>
              </section>
            )}
            {activeJobs.length === 0 && completedJobs.length === 0 && (
              <div className="glass rounded-2xl p-12 text-center">
                <div className="w-16 h-16 bg-gradient-to-br from-gray-200 to-gray-300 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Zap className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-1">Nessun job ancora</h3>
                <p className="text-sm text-gray-500 mb-6 max-w-xs mx-auto">Addestra un modello o genera contenuti per vederli qui.</p>
                <button onClick={() => navigate('/train')} className="btn btn-primary">
                  Inizia ora
                </button>
              </div>
            )}
          </div>
        )}

        {/* ═══ TAB: TESI ═══ */}
        {activeTab === 'theses' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-gray-500">{theses.length} documenti</span>
              <button onClick={() => navigate('/thesis')} className="btn btn-primary btn-sm">
                + Nuova Tesi
              </button>
            </div>
            {theses.map(thesis => {
              const action = getThesisAction(thesis);
              const ActionIcon = action.icon;
              const scan = scanResults[thesis.id];
              const expanded = expandedThesis === thesis.id;
              return (
                <div key={thesis.id} className="glass rounded-2xl overflow-hidden">
                  <div className="flex items-center gap-4 p-4 cursor-pointer hover:bg-white/50 transition-colors" onClick={() => setExpandedThesis(expanded ? null : thesis.id)}>
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center shadow-lg flex-shrink-0">
                      <BookOpen className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="font-bold text-gray-900 text-sm truncate">{thesis.title}</h4>
                        {getStatusBadge(thesis.status)}
                        {isAdmin && scan && <span className={`badge text-[10px] ${getAIScoreColor(scan.ai_generated_percent)}`}>AI {scan.ai_generated_percent?.toFixed(0)}%</span>}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                        <span>{formatDate(thesis.created_at)}</span>
                        <span>{thesis.num_chapters} capitoli</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button onClick={e => { e.stopPropagation(); handleThesisNavigate(thesis); }}
                        className="btn btn-secondary btn-sm">
                        <ActionIcon className="w-3.5 h-3.5" /> {action.label}
                      </button>
                      <button onClick={e => { e.stopPropagation(); handleDeleteThesis(thesis.id); }} className="btn btn-ghost text-gray-400 hover:text-red-500 hover:bg-red-50">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`} />
                    </div>
                  </div>

                  {expanded && (
                    <div className="border-t border-gray-200/50 p-5 bg-gray-50/50 space-y-4">
                      {thesis.description && <p className="text-sm text-gray-600 bg-white rounded-xl p-3 border border-gray-100">{thesis.description}</p>}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[{ l: 'Capitoli', v: thesis.num_chapters }, { l: 'Sez/Cap', v: thesis.sections_per_chapter }, { l: 'Parole/Sez', v: thesis.words_per_section?.toLocaleString() }, { l: 'Progresso', v: `${thesis.generation_progress || 0}%` }].map((s, i) => (
                          <div key={i} className="bg-white rounded-xl p-3 text-center border border-gray-100">
                            <div className="text-lg font-bold text-gray-900">{s.v}</div>
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider">{s.l}</div>
                          </div>
                        ))}
                      </div>
                      {thesis.key_topics?.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {thesis.key_topics.map((t, i) => <span key={i} className="badge badge-success">{t}</span>)}
                        </div>
                      )}
                      {isAdmin && thesis.status === 'completed' && (
                        scan ? (
                          <div className="bg-white rounded-xl p-4 border border-gray-100">
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-xs font-bold text-purple-700 uppercase tracking-wider flex items-center gap-1"><Shield className="w-3.5 h-3.5" /> Detector AI</span>
                              {scan.has_report && <button onClick={e => { e.stopPropagation(); handleDownloadScanReport(scan.scan_id); }} className="btn btn-ghost btn-sm text-purple-600"><Download className="w-3 h-3" /> Report</button>}
                            </div>
                            <div className="grid grid-cols-4 gap-2">
                              {[
                                { v: scan.ai_generated_percent, l: 'AI', cls: getAIScoreColorInline(scan.ai_generated_percent) },
                                { v: scan.similarity_percent, l: 'Similarita', cls: 'text-blue-700 bg-blue-50 border-blue-200' },
                                { v: scan.global_score_percent, l: 'Globale', cls: 'text-gray-700 bg-gray-50 border-gray-200' },
                                { v: scan.exact_percent, l: 'Esatti', cls: 'text-gray-700 bg-gray-50 border-gray-200' },
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
                            className="btn btn-secondary btn-sm">
                            <Shield className="w-3.5 h-3.5" /> Scansione Detector AI
                          </button>
                        )
                      )}
                      {thesis.status === 'completed' && (
                        <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-gray-100">
                          {templates.length > 0 && (
                            <select value={selectedTemplates[thesis.id] || ''} onChange={e => setSelectedTemplates({ ...selectedTemplates, [thesis.id]: e.target.value || null })} onClick={e => e.stopPropagation()}
                              className="input py-1.5 text-sm w-auto">
                              <option value="">Template default</option>
                              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          )}
                          <div className="flex items-center gap-2">
                            <FileDown className="w-4 h-4 text-gray-400" />
                            {['pdf','docx','txt','md'].map(f => (
                              <button key={f} onClick={e => { e.stopPropagation(); handleExportThesis(thesis.id, f); }} disabled={exportingThesis === thesis.id}
                                className={f === 'pdf' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}>
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
              <span className="text-sm text-gray-500">{sessions.length} sessioni, {trainedSessions} addestrate</span>
              <button onClick={() => navigate('/train')} className="btn btn-primary btn-sm">
                + Nuova Sessione
              </button>
            </div>
            {sessions.length === 0 ? (
              <div className="glass rounded-2xl p-12 text-center">
                <div className="w-16 h-16 bg-gradient-to-br from-gray-200 to-gray-300 rounded-2xl flex items-center justify-center mx-auto mb-4"><FileText className="w-8 h-8 text-white" /></div>
                <h3 className="text-lg font-bold text-gray-900 mb-1">Nessuna sessione</h3>
                <p className="text-sm text-gray-500 mb-6">Crea la tua prima sessione di addestramento.</p>
                <button onClick={() => navigate('/train')} className="btn btn-primary">Crea Sessione</button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {sessions.map(session => (
                  <div key={session.session_id} className="glass rounded-2xl p-5 group">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        {editingSessionName === session.session_id ? (
                          <input ref={editSessionRef} type="text" value={editSessionValue} onChange={e => setEditSessionValue(e.target.value)}
                            onBlur={() => handleSaveSessionName(session.session_id)} onKeyDown={e => handleSessionEditKeyDown(e, session.session_id)}
                            className="input py-1 text-sm w-full"
                            maxLength={255} onClick={e => e.stopPropagation()} />
                        ) : (
                          <div className="flex items-center gap-1 group/name">
                            <h4 className="text-sm font-bold text-gray-900 truncate">{session.name || session.session_id}</h4>
                            <button onClick={() => handleStartSessionEdit(session.session_id, session.name || session.session_id)}
                              className="opacity-0 group-hover/name:opacity-100 transition-opacity p-0.5 hover:bg-gray-100 rounded-lg flex-shrink-0">
                              <Pencil className="w-3 h-3 text-gray-400" />
                            </button>
                          </div>
                        )}
                        {session.name && !editingSessionName && <p className="font-mono text-[10px] text-gray-400 truncate mt-0.5">{session.session_id}</p>}
                      </div>
                      <button onClick={() => handleDeleteSession(session.session_id)}
                        className="btn btn-ghost text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mb-4">
                      {session.is_trained
                        ? <span className="badge badge-success"><CheckCircle2 className="w-3 h-3" /> Addestrata</span>
                        : <span className="badge badge-warning"><Clock className="w-3 h-3" /> Non addestrata</span>
                      }
                      <span className="text-xs text-gray-500">{session.conversation_length} conv. · {session.jobs.length} job</span>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => navigate(`/sessions/${session.session_id}`)}
                        className="btn btn-secondary flex-1 text-sm py-2.5">
                        Dettagli
                      </button>
                      <button onClick={() => navigate(`/generate?session=${session.session_id}`)} disabled={!session.is_trained}
                        className={`flex-1 text-sm py-2.5 ${
                          session.is_trained
                            ? 'btn btn-primary'
                            : 'btn btn-secondary opacity-50 cursor-not-allowed'
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
