import axios from 'axios';

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
      throw new Error('Timeout: il server non risponde. Riprova più tardi.');
    }

    if (error.code === 'ERR_NETWORK' || error.message.includes('Network Error')) {
      throw new Error('Backend non disponibile. Assicurati che il server sia in esecuzione su ' + API_URL);
    }

    if (error.code === 'ECONNREFUSED') {
      throw new Error('Impossibile connettersi al server. Verifica che il backend sia attivo.');
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

export const humanizeContent = async (sessionId, testo) => {
  const response = await api.post('/humanize', {
    session_id: sessionId,
    testo,
  });
  return response.data;
};

export const antiAICorrection = async (testo) => {
  const response = await api.post('/anti-ai-correction', { testo });
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

// Generation phases - timeout estesi per operazioni AI
export const generateThesisChapters = async (thesisId) => {
  const response = await api.post(`/api/thesis/${thesisId}/generate-chapters`, {}, {
    timeout: 120000 // 2 minuti per generazione AI
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
    timeout: 120000 // 2 minuti per generazione AI
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

// ============================================================================
// ADMIN - USERS
// ============================================================================

export const getAdminUsers = async (search = null, roleId = null, isActive = null) => {
  const params = {};
  if (search) params.search = search;
  if (roleId !== null) params.role_id = roleId;
  if (isActive !== null) params.is_active = isActive;
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

export const downloadCompilatioReport = async (scanId) => {
  const response = await api.get(`/compilatio/report/${scanId}`, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `compilatio_report_${scanId.substring(0, 8)}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ============================================================================
// IMAGE ENHANCEMENT
// ============================================================================

export const enhanceImage = async (file, enhancementType = 'basic', params = {}, onProgress = null) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('enhancement_type', enhancementType);
  formData.append('params', JSON.stringify(params));

  const response = await api.post('/api/image/enhance', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
    onUploadProgress: onProgress ? (progressEvent) => {
      const progress = (progressEvent.loaded / progressEvent.total) * 100;
      onProgress(progress);
    } : undefined
  });
  return response.data;
};

export const analyzeImage = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/api/image/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000
  });
  return response.data;
};

export const downloadEnhancedImage = async (jobId) => {
  const response = await api.get(`/api/image/download/${jobId}`, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `enhanced_image_${jobId.substring(0, 8)}.png`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const getEnhancementResult = async (jobId) => {
  const response = await api.get(`/api/image/result/${jobId}`);
  return response.data;
};

export const getEnhancementHistory = async (limit = 20, offset = 0) => {
  const response = await api.get('/api/image/history', { params: { limit, offset } });
  return response.data;
};

export const getOriginalImageBlob = async (jobId) => {
  const response = await api.get(`/api/image/download-original/${jobId}`, {
    responseType: 'blob'
  });
  return response.data;
};

export const getEnhancedImageBlob = async (jobId) => {
  const response = await api.get(`/api/image/download/${jobId}`, {
    responseType: 'blob'
  });
  return response.data;
};

export default api;
