import axios from 'axios';
import i18n from '../i18n';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// ============================================================================
// TOKEN MANAGEMENT
// ============================================================================

const TOKEN_KEY = 'styleforge_access_token';
const REFRESH_TOKEN_KEY = 'styleforge_refresh_token';
const USER_KEY = 'styleforge_user';

export const getAccessToken = () => localStorage.getItem(TOKEN_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY);
export const getStoredUser = () => {
  const user = localStorage.getItem(USER_KEY);
  return user ? JSON.parse(user) : null;
};

export const setTokens = (accessToken, refreshToken) => {
  localStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
};

export const setUser = (user) => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

// ============================================================================
// AXIOS INTERCEPTORS
// ============================================================================

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh and credit errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 402 - Insufficient Credits
    if (error.response?.status === 402) {
      const detail = error.response?.data?.detail || 'Crediti AI insufficienti. Verifica il tuo piano.';
      // Enrich the error with a specific flag for the frontend
      error.isInsufficientCredits = true;
      error.creditErrorMessage = detail;
      return Promise.reject(error);
    }

    // If error is 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = getRefreshToken();
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_URL}/auth/refresh`, null, {
            params: { refresh_token: refreshToken }
          });

          const { access_token, refresh_token: newRefreshToken } = response.data;
          setTokens(access_token, newRefreshToken);

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed - clear auth and redirect to login
          clearAuth();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      } else {
        // No refresh token - clear auth and redirect
        clearAuth();
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// ============================================================================
// AUTHENTICATION
// ============================================================================

export const register = async (email, username, password, fullName = null) => {
  const response = await api.post('/auth/register', {
    email,
    username,
    password,
    full_name: fullName
  });
  return response.data;
};

export const login = async (username, password) => {
  try {
    console.log('Attempting login for user:', username);
    console.log('API URL:', API_URL);

    const response = await api.post('/auth/login', {
      username,
      password
    });

    console.log('Login response received:', response.status);
    const { access_token, refresh_token } = response.data;

    if (!access_token) {
      throw new Error('No access token received from server');
    }

    setTokens(access_token, refresh_token);

    // Get user profile
    console.log('Fetching user profile...');
    const userResponse = await api.get('/auth/me');
    console.log('User profile received');
    setUser(userResponse.data);

    return { tokens: response.data, user: userResponse.data };
  } catch (error) {
    console.error('Login API error:', error);
    console.error('Error code:', error.code);
    console.error('Error message:', error.message);

    if (error.code === 'ECONNABORTED') {
      throw new Error(i18n.t('Timeout: il server non risponde. Riprova più tardi.'));
    }

    if (error.code === 'ERR_NETWORK' || error.message.includes('Network Error')) {
      throw new Error(i18n.t('Backend non disponibile. Assicurati che il server sia in esecuzione su {{url}}', { url: API_URL }));
    }

    if (error.code === 'ECONNREFUSED') {
      throw new Error(i18n.t('Impossibile connettersi al server. Verifica che il backend sia attivo.'));
    }

    throw error;
  }
};

export const logout = async () => {
  try {
    const refreshToken = getRefreshToken();
    await api.post('/auth/logout', null, {
      params: { refresh_token: refreshToken }
    });
  } catch (error) {
    console.error('Logout error:', error);
  } finally {
    clearAuth();
  }
};

export const logoutAll = async () => {
  try {
    await api.post('/auth/logout/all');
  } catch (error) {
    console.error('Logout all error:', error);
  } finally {
    clearAuth();
  }
};

export const getCurrentUser = async () => {
  const response = await api.get('/auth/me');
  setUser(response.data);
  return response.data;
};

export const updateProfile = async (fullName, email) => {
  const response = await api.put('/auth/me', {
    full_name: fullName,
    email
  });
  setUser(response.data);
  return response.data;
};

export const changePassword = async (currentPassword, newPassword) => {
  const response = await api.post('/auth/me/change-password', {
    current_password: currentPassword,
    new_password: newPassword
  });
  return response.data;
};

export const deleteAccount = async (password) => {
  const response = await api.delete('/auth/me', {
    params: { password }
  });
  clearAuth();
  return response.data;
};

// --- Verifica email / reset password (pubblici, no auth) ---
export const verifyEmail = async (token) => {
  const response = await api.post('/auth/verify-email', { token });
  return response.data;
};

export const resendVerification = async (email) => {
  const response = await api.post('/auth/resend-verification', { email });
  return response.data;
};

export const forgotPassword = async (email) => {
  const response = await api.post('/auth/forgot-password', { email });
  return response.data;
};

export const resetPassword = async (token, newPassword) => {
  const response = await api.post('/auth/reset-password', { token, new_password: newPassword });
  return response.data;
};

export const setPassword = async (token, newPassword) => {
  const response = await api.post('/auth/set-password', { token, new_password: newPassword });
  return response.data;
};

// --- i18n: lingue + traduzioni (pubblici, no auth) ---
export const getActiveLanguages = async () => {
  const response = await api.get('/api/languages');
  return response.data;
};

export const getPublicTranslations = async (code) => {
  const response = await api.get(`/api/translations/${code}`);
  return response.data; // mappa { chiave: valore }
};

// --- i18n admin ---
export const adminListLanguages = async () => {
  const response = await api.get('/admin/languages');
  return response.data;
};

export const adminCreateLanguage = async (payload) => {
  const response = await api.post('/admin/languages', payload);
  return response.data;
};

export const adminUpdateLanguage = async (code, payload) => {
  const response = await api.put(`/admin/languages/${code}`, payload);
  return response.data;
};

export const adminDeleteLanguage = async (code) => {
  const response = await api.delete(`/admin/languages/${code}`);
  return response.data;
};

export const adminGetLanguageDetail = async (code, search = null) => {
  const params = search ? { search } : {};
  const response = await api.get(`/admin/languages/${code}/detail`, { params });
  return response.data;
};

export const adminSaveTranslations = async (code, translations) => {
  const response = await api.put(`/admin/languages/${code}/translations`, { translations });
  return response.data;
};

export const adminSyncBaseLabels = async (catalog) => {
  const response = await api.post('/admin/languages/sync-base', { translations: catalog });
  return response.data;
};

export const adminTranslateEmpty = async (code) => {
  const response = await api.post(`/admin/languages/${code}/translate-empty`);
  return response.data;
};

export const adminGetTranslateStatus = async (jobId) => {
  const response = await api.get(`/admin/languages/translate-status/${jobId}`);
  return response.data;
};

// ============================================================================
// SESSIONS
// ============================================================================

export const createSession = async (sessionId = null) => {
  const params = sessionId ? { session_id: sessionId } : {};
  const response = await api.post('/sessions', null, { params });
  return response.data;
};

export const getSessions = async () => {
  const response = await api.get('/sessions');
  return response.data;
};

export const getSession = async (sessionId) => {
  const response = await api.get(`/sessions/${sessionId}`);
  return response.data;
};

export const deleteSession = async (sessionId) => {
  const response = await api.delete(`/sessions/${sessionId}`);
  return response.data;
};

export const renameSession = async (sessionId, name) => {
  const response = await api.patch(`/sessions/${sessionId}/name`, { name });
  return response.data;
};

// ============================================================================
// TRAINING
// ============================================================================

export const trainSession = async (file, sessionId = null, maxPages = 50) => {
  const formData = new FormData();
  formData.append('file', file);
  if (sessionId) {
    formData.append('session_id', sessionId);
  }
  formData.append('max_pages', maxPages);

  const response = await api.post('/train', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// ============================================================================
// GENERATION
// ============================================================================

export const generateContent = async (sessionId, argomento, numeroParole, destinatario = 'Pubblico Generale') => {
  const response = await api.post('/generate', {
    session_id: sessionId,
    argomento,
    numero_parole: numeroParole,
    destinatario,
  });
  return response.data;
};

export const humanizeContent = async (sessionId, testo, profile = 'informal') => {
  const response = await api.post('/humanize', {
    session_id: sessionId,
    testo,
    profile,
  });
  return response.data;
};

export const antiAICorrection = async (testo, profile = 'informal') => {
  const response = await api.post('/anti-ai-correction', { testo, profile });
  return response.data;
};

// Estrazione testo da file caricato (PDF/DOCX/TXT). Il file NON viene salvato.
export const extractTextFromFile = async (file, onProgress = null) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/extract-text', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 5 minuti: l'estrazione include parsing PDF/DOCX e sanitizzazione,
    // che su file grandi può superare il default di 30s.
    timeout: 300000,
    onUploadProgress: onProgress ? (progressEvent) => {
      const progress = (progressEvent.loaded / progressEvent.total) * 100;
      onProgress(progress);
    } : undefined
  });
  return response.data;
};

// ============================================================================
// JOBS
// ============================================================================

export const getJobStatus = async (jobId) => {
  const response = await api.get(`/jobs/${jobId}`);
  return response.data;
};

export const getJobs = async (sessionId = null) => {
  const params = sessionId ? { session_id: sessionId } : {};
  const response = await api.get('/jobs', { params });
  return response.data;
};

export const deleteJob = async (jobId) => {
  const response = await api.delete(`/jobs/${jobId}`);
  return response.data;
};

export const renameJob = async (jobId, name) => {
  const response = await api.patch(`/jobs/${jobId}/name`, { name });
  return response.data;
};

// ============================================================================
// RESULTS
// ============================================================================

export const downloadResult = async (jobId) => {
  const response = await api.get(`/results/${jobId}`, {
    responseType: 'blob',
  });

  // Crea un URL per il download
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `contenuto_generato_${jobId}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return response.data;
};

export const getResultText = async (jobId) => {
  const response = await api.get(`/results/${jobId}`, {
    responseType: 'text',
  });
  return response.data;
};

// ============================================================================
// HEALTH
// ============================================================================

export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ============================================================================
// CALCIFER HELPER
// ============================================================================

export const chatWithCalcifer = async (message, conversationId = 'default', context = null) => {
  const response = await api.post('/calcifer/chat', {
    message,
    conversation_id: conversationId,
    context
  });
  return response.data;
};

export const getCalciferTip = async (page, context = null) => {
  const response = await api.post('/calcifer/tip', {
    page,
    context
  });
  return response.data;
};

export const clearCalciferConversation = async (conversationId = 'default') => {
  const response = await api.delete(`/calcifer/conversation/${conversationId}`);
  return response.data;
};

// ============================================================================
// THESIS GENERATION
// ============================================================================

// Lookup data
export const getThesisLookupData = async () => {
  const response = await api.get('/api/thesis/lookup');
  return response.data;
};

// Thesis CRUD
export const createThesis = async (thesisData) => {
  const response = await api.post('/api/thesis', thesisData);
  return response.data;
};

export const getTheses = async (status = null) => {
  const params = status ? { status } : {};
  const response = await api.get('/api/thesis', { params });
  return response.data;
};

export const getThesis = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}`);
  return response.data;
};

export const deleteThesis = async (thesisId) => {
  const response = await api.delete(`/api/thesis/${thesisId}`);
  return response.data;
};

// Attachments
export const uploadThesisAttachments = async (thesisId, files, onProgress = null) => {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));

  const response = await api.post(`/api/thesis/${thesisId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 5 minuti: l'upload include estrazione testo (PyMuPDF/docx2txt) e
    // sanitizzazione NUL su PDF anche grandi. Senza override usavamo il
    // default di 30s e Firefox abortiva la fetch (NS_BINDING_ABORTED).
    timeout: 300000,
    onUploadProgress: onProgress ? (progressEvent) => {
      const progress = (progressEvent.loaded / progressEvent.total) * 100;
      onProgress(progress);
    } : undefined
  });
  return response.data;
};

export const getThesisAttachments = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}/attachments`);
  return response.data;
};

export const deleteThesisAttachment = async (thesisId, attachmentId) => {
  const response = await api.delete(`/api/thesis/${thesisId}/attachments/${attachmentId}`);
  return response.data;
};

export const addThesisUrlAttachments = async (thesisId, urls) => {
  const response = await api.post(`/api/thesis/${thesisId}/attachments/urls`, { urls }, {
    timeout: 60000
  });
  return response.data;
};

// Thesis: ricerca paper accademici dentro il wizard (gated dal permesso 'thesis')
export const searchResearchForThesis = async (thesisId, {
  topic,
  sources = null,
  filters = null,
  sortBy = 'composite',
  perProviderLimit = 30,
  finalLimit = 40,
}) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/research/search`,
    {
      topic,
      sources,
      filters,
      sort_by: sortBy,
      per_provider_limit: perProviderLimit,
      final_limit: finalLimit,
    },
    { timeout: 60000 }
  );
  return response.data;
};

export const summarizePaperForThesis = async (thesisId, paper) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/research/summarize`,
    { paper },
    { timeout: 120000 }
  );
  return response.data;
};

// items: [{ paper, summary?: SummaryResult }]
export const addPaperAttachments = async (thesisId, items) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/attachments/papers`,
    { items },
    { timeout: 180000 }
  );
  return response.data;
};

// Estrae 5-8 keyword da usare come termini di ricerca paper, analizzando
// gli allegati testuali (non-paper) gia' caricati per la tesi.
// Costa pochi crediti (paper_keyword_suggest = base + per_attachment).
export const suggestPaperKeywords = async (thesisId) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/suggest-paper-keywords`,
    {},
    { timeout: 60000 }
  );
  return response.data;
};

// ============================================================================
// LLM WIKI (second-brain) — knowledge base per-tesi
// ============================================================================

// Avvia ingest + lint del wiki (in background sul server). Ritorna lo stato
// transitorio (wiki_status='ingesting'); il client deve fare polling con
// getWikiStatus.
export const startWikiIngest = async (thesisId, force = false) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/wiki/ingest`,
    { force: !!force },
    { timeout: 30000 }
  );
  return response.data;
};

// Rilancia il SOLO lint (l'ingest deve gia' essere stato eseguito).
export const startWikiLint = async (thesisId) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/wiki/lint`,
    {},
    { timeout: 30000 }
  );
  return response.data;
};

// Sblocca manualmente un ingest bloccato in ingesting/linting.
export const cancelWikiIngest = async (thesisId) => {
  const response = await api.post(
    `/api/thesis/${thesisId}/wiki/cancel`,
    {},
    { timeout: 15000 }
  );
  return response.data;
};

// Stato del wiki di una tesi (per polling). Ritorna anche sources_count e
// pages_count per la progress bar.
export const getWikiStatus = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}/wiki/status`);
  return response.data;
};

// Report di lint (orphan_pages, broken_wikilinks, contradictions, gaps, ...).
export const getWikiReport = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}/wiki/report`);
  return response.data;
};

// Informazioni estratte dai documenti (vista utente): pagine del wiki
// raggruppate per categoria (fonti/entità/concetti/temi/sintesi/domande).
export const getWikiContent = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}/wiki/content`);
  return response.data;
};

// Generation phases - timeout estesi per operazioni AI
export const generateThesisChapters = async (thesisId) => {
  const response = await api.post(`/api/thesis/${thesisId}/generate-chapters`, {}, {
    timeout: 300000 // 5 minuti: generazione AI sincrona (Claude Opus è più lento)
  });
  return response.data;
};

export const confirmThesisChapters = async (thesisId, chapters) => {
  const response = await api.put(`/api/thesis/${thesisId}/chapters`, { chapters }, {
    timeout: 60000 // 1 minuto
  });
  return response.data;
};

export const generateThesisSections = async (thesisId) => {
  const response = await api.post(`/api/thesis/${thesisId}/generate-sections`, {}, {
    timeout: 300000 // 5 minuti: generazione AI sincrona (Claude Opus è più lento)
  });
  return response.data;
};

export const confirmThesisSections = async (thesisId, chapters) => {
  const response = await api.put(`/api/thesis/${thesisId}/sections`, { chapters }, {
    timeout: 60000 // 1 minuto
  });
  return response.data;
};

export const startThesisContentGeneration = async (thesisId) => {
  const response = await api.post(`/api/thesis/${thesisId}/generate-content`, {}, {
    timeout: 60000 // 1 minuto per avviare
  });
  return response.data;
};

export const getThesisGenerationStatus = async (thesisId) => {
  const response = await api.get(`/api/thesis/${thesisId}/generation-status`);
  return response.data;
};

// Export
export const exportThesis = async (thesisId, format = 'pdf', templateId = null) => {
  const params = { format };
  if (templateId) params.template_id = templateId;

  const response = await api.get(`/api/thesis/${thesisId}/export`, {
    params,
    responseType: 'blob'
  });

  // Determina estensione e tipo MIME
  const mimeTypes = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    txt: 'text/plain',
    md: 'text/markdown'
  };

  const url = window.URL.createObjectURL(new Blob([response.data], { type: mimeTypes[format] }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `tesi_${thesisId}.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);

  return response.data;
};

// Polling per lo stato della generazione tesi
export const pollThesisGenerationStatus = async (thesisId, onUpdate, interval = 3000, timeout = 1800000) => {
  const startTime = Date.now();

  const poll = async () => {
    try {
      const status = await getThesisGenerationStatus(thesisId);
      onUpdate(status);

      if (status.status === 'completed' || status.status === 'failed') {
        return status;
      }

      if (Date.now() - startTime > timeout) {
        throw new Error('Timeout: la generazione non si è completata entro il tempo limite');
      }

      await new Promise(resolve => setTimeout(resolve, interval));
      return poll();
    } catch (error) {
      throw error;
    }
  };

  return poll();
};

// ============================================================================
// POLLING UTILITIES
// ============================================================================

export const pollJobStatus = async (jobId, onUpdate, interval = 3000, timeout = 300000) => {
  const startTime = Date.now();

  const poll = async () => {
    try {
      const status = await getJobStatus(jobId);
      onUpdate(status);

      if (status.status === 'completed' || status.status === 'failed') {
        return status;
      }

      if (Date.now() - startTime > timeout) {
        throw new Error('Timeout: il job non si è completato entro il tempo limite');
      }

      await new Promise(resolve => setTimeout(resolve, interval));
      return poll();
    } catch (error) {
      throw error;
    }
  };

  return poll();
};

// ============================================================================
// CREDITS
// ============================================================================

export const estimateCredits = async (operationType, params = {}) => {
  const response = await api.post('/credits/estimate', {
    operation_type: operationType,
    params
  });
  return response.data;
};

export const estimateApiCost = async (params) => {
  const response = await api.post('/estimate-api-cost', params);
  return response.data;
};

// ============================================================================
// ADMIN - USERS
// ============================================================================

export const getAdminUsers = async (search = null, roleId = null, isActive = null, entityType = null) => {
  const params = {};
  if (search) params.search = search;
  if (roleId !== null) params.role_id = roleId;
  if (isActive !== null) params.is_active = isActive;
  if (entityType) params.entity_type = entityType;
  const response = await api.get('/admin/users', { params });
  return response.data;
};

export const getAdminUser = async (userId) => {
  const response = await api.get(`/admin/users/${userId}`);
  return response.data;
};

export const updateAdminUser = async (userId, data) => {
  const response = await api.put(`/admin/users/${userId}`, data);
  return response.data;
};

export const updateUserRole = async (userId, roleId) => {
  const response = await api.put(`/admin/users/${userId}/role`, { role_id: roleId });
  return response.data;
};

export const getUserPermissions = async (userId) => {
  const response = await api.get(`/admin/users/${userId}/permissions`);
  return response.data;
};

export const updateUserPermissions = async (userId, permissions) => {
  const response = await api.put(`/admin/users/${userId}/permissions`, { permissions });
  return response.data;
};

export const adjustUserCredits = async (userId, amount, description) => {
  const response = await api.post(`/admin/users/${userId}/credits`, { amount, description });
  return response.data;
};

export const getUserTransactions = async (userId, limit = 50, offset = 0) => {
  const response = await api.get(`/admin/users/${userId}/transactions`, {
    params: { limit, offset }
  });
  return response.data;
};

// ============================================================================
// ADMIN - ROLES
// ============================================================================

export const getAdminRoles = async () => {
  const response = await api.get('/admin/roles');
  return response.data;
};

export const updateRolePermissions = async (roleId, permissions) => {
  const response = await api.put(`/admin/roles/${roleId}/permissions`, { permissions });
  return response.data;
};

// ============================================================================
// ADMIN - STATS
// ============================================================================

export const getAdminStats = async () => {
  const response = await api.get('/admin/stats');
  return response.data;
};

// ============================================================================
// ADMIN - CREAZIONE UTENTI
// ============================================================================

export const adminCreateUser = async (userData) => {
  const response = await api.post('/admin/users', userData);
  return response.data;
};

export const adminResendInvite = async (userId) => {
  const response = await api.post(`/admin/users/${userId}/resend-invite`);
  return response.data;
};

// ============================================================================
// ADMIN - CONFIGURAZIONE COSTI CREDITI
// ============================================================================

export const getAdminCreditCosts = async () => {
  const response = await api.get('/admin/settings/credit-costs');
  return response.data;
};

export const updateAdminCreditCosts = async (costs) => {
  const response = await api.put('/admin/settings/credit-costs', { costs });
  return response.data;
};

export const resetAdminCreditCosts = async () => {
  const response = await api.delete('/admin/settings/credit-costs');
  return response.data;
};

export const getAdminEurPerCredit = async () => {
  const response = await api.get('/admin/settings/eur-per-credit');
  return response.data;
};

export const updateAdminEurPerCredit = async (value) => {
  const response = await api.put('/admin/settings/eur-per-credit', { eur_per_credit: value });
  return response.data;
};


// ============================================================================
// ADMIN - TEMPLATE ESPORTAZIONE
// ============================================================================

export const getAdminTemplates = async () => {
  const response = await api.get('/admin/templates');
  return response.data;
};

export const updateAdminTemplates = async (templates) => {
  const response = await api.put('/admin/templates', { templates });
  return response.data;
};

export const deleteAdminTemplate = async (templateId) => {
  const response = await api.delete(`/admin/templates/${templateId}`);
  return response.data;
};

export const getTemplateHelp = async () => {
  const response = await api.get('/admin/templates/help');
  return response.data;
};

export const uploadTemplateBackground = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/admin/templates/background-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const deleteTemplateBackground = async (filename) => {
  const response = await api.delete(`/admin/templates/backgrounds/${filename}`);
  return response.data;
};

// ============================================================================
// TEMPLATE ESPORTAZIONE - PUBBLICO (per selezione utente)
// ============================================================================

export const getExportTemplates = async () => {
  const response = await api.get('/admin/templates');
  return response.data;
};

// ============================================================================
// COMPILATIO SCAN (Admin-only)
// ============================================================================

export const startCompilatioScan = async (text, sourceType = null, sourceJobId = null) => {
  const response = await api.post('/compilatio/scan', {
    text,
    source_type: sourceType,
    source_job_id: sourceJobId
  });
  return response.data;
};

export const getCompilatioScans = async (limit = 20, offset = 0) => {
  const response = await api.get('/compilatio/scans', { params: { limit, offset } });
  return response.data;
};

export const getCompilatioScansBySource = async (sourceJobIds) => {
  const response = await api.get('/compilatio/scans-by-sources', {
    params: { source_job_ids: sourceJobIds.join(',') }
  });
  return response.data;
};

/**
 * Scarica il report Detector AI in PDF.
 * Il PDF viene generato server-side a richiesta (puo' richiedere alcuni secondi
 * per documenti lunghi), quindi abbiamo un timeout esteso e supportiamo un
 * callback di avanzamento.
 *
 * @param {string} scanId
 * @param {(percent: number) => void} [onProgress] - 0..100. Quando il backend
 *   non invia Content-Length (PDF generato in streaming), viene comunque
 *   chiamato con valori "indeterminati" basati sui bytes ricevuti.
 */
export const downloadCompilatioReport = async (scanId, onProgress) => {
  const response = await api.get(`/compilatio/report/${scanId}`, {
    responseType: 'blob',
    timeout: 300000, // 5 minuti: la generazione PDF puo' essere lenta
    onDownloadProgress: (e) => {
      if (typeof onProgress !== 'function') return;
      if (e.total && e.total > 0) {
        const pct = Math.min(99, Math.round((e.loaded / e.total) * 100));
        onProgress(pct);
      } else {
        // Server non invia Content-Length: usiamo i byte ricevuti come hint
        // limitato a 90% per non confondere l'utente.
        const approx = Math.min(90, Math.round((e.loaded / 200000) * 100));
        onProgress(approx);
      }
    },
  });
  if (typeof onProgress === 'function') onProgress(100);

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `styleforge_detector_report_${scanId.substring(0, 8)}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ============================================================================
// IMAGE TO VIDEO (Admin-only)
// ============================================================================

export const generateVideos = async (file, prompts, { model, promptOptimizer, duration, fastPretreatment, resolution } = {}) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('prompts', JSON.stringify(prompts));
  if (model) formData.append('model', model);
  if (promptOptimizer !== undefined) formData.append('prompt_optimizer', promptOptimizer);
  if (duration) formData.append('duration', duration);
  if (fastPretreatment !== undefined && fastPretreatment !== null) formData.append('fast_pretreatment', fastPretreatment);
  if (resolution) formData.append('resolution', resolution);

  const response = await api.post('/api/video/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return response.data;
};

export const getVideoTaskStatus = async (taskId) => {
  const response = await api.get(`/api/video/status/${taskId}`);
  return response.data;
};

export const getVideoTasksStatus = async (taskIds) => {
  const response = await api.get('/api/video/status', {
    params: { task_ids: taskIds.join(',') },
  });
  return response.data;
};

export const getVideoProxyUrl = (videoUrl) => {
  const token = getAccessToken();
  const params = new URLSearchParams({ url: videoUrl, token });
  return `${API_URL}/api/video/proxy?${params.toString()}`;
};

// ============================================================================
// ACADEMIC RESEARCH
// ============================================================================

export const listResearchSources = async () => {
  const response = await api.get('/api/research/sources');
  return response.data;
};

export const searchResearch = async ({
  topic,
  sources = null,
  filters = null,
  sortBy = 'composite',
  perProviderLimit = 30,
  finalLimit = 40,
}) => {
  const response = await api.post(
    '/api/research/search',
    {
      topic,
      sources,
      filters,
      sort_by: sortBy,
      per_provider_limit: perProviderLimit,
      final_limit: finalLimit,
    },
    { timeout: 60000 }
  );
  return response.data;
};

export const summarizePaper = async (paper) => {
  const response = await api.post(
    '/api/research/summarize',
    { paper },
    { timeout: 120000 }
  );
  return response.data;
};

// ============================================================================
// ADMIN - API KEYS
// ============================================================================

export const createApiKey = async (userId, name, expiresInDays = null, rateLimitPerMinute = 30) => {
  const response = await api.post('/admin/api-keys', {
    user_id: userId,
    name,
    expires_in_days: expiresInDays,
    rate_limit_per_minute: rateLimitPerMinute
  });
  return response.data;
};

export const getApiKeys = async (userId = null) => {
  const params = userId ? { user_id: userId } : {};
  const response = await api.get('/admin/api-keys', { params });
  return response.data;
};

export const revokeApiKey = async (keyId) => {
  const response = await api.delete(`/admin/api-keys/${keyId}`);
  return response.data;
};

// ============================================================================
// PACCHETTI CREDITI — listino utente (vetrina)
// ============================================================================

export const listCreditPackages = async () => {
  const response = await api.get('/api/packages');
  return response.data;
};

// ============================================================================
// DISTRIBUTORE - dashboard rivenditori (sola lettura)
// ============================================================================

export const getMyResellers = async () => {
  const response = await api.get('/api/distributor/resellers');
  return response.data;
};

// ============================================================================
// PACCHETTI CREDITI — admin (CRUD listino)
// ============================================================================

export const adminListCreditPackages = async () => {
  const response = await api.get('/admin/credit-packages');
  return response.data;
};

export const adminCreateCreditPackage = async (payload) => {
  const response = await api.post('/admin/credit-packages', payload);
  return response.data;
};

export const adminUpdateCreditPackage = async (packageId, payload) => {
  const response = await api.put(`/admin/credit-packages/${packageId}`, payload);
  return response.data;
};

export const adminDeleteCreditPackage = async (packageId) => {
  const response = await api.delete(`/admin/credit-packages/${packageId}`);
  return response.data;
};

export default api;
