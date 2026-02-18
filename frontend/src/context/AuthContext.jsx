import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  getCurrentUser,
  getAccessToken,
  getStoredUser,
  clearAuth
} from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Controlla se l'utente ha un token valido
    const initAuth = async () => {
      const token = getAccessToken();
      const storedUser = getStoredUser();

      if (token && storedUser) {
        try {
          // Verifica che il token sia ancora valido
          const userData = await getCurrentUser();
          setUser(userData);
          setIsAuthenticated(true);
        } catch (err) {
          // Token non valido o scaduto
          console.error('Token validation error:', err);
          clearAuth();
          setUser(null);
          setIsAuthenticated(false);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = async (username, password) => {
    setError(null);
    try {
      const { user: userData } = await apiLogin(username, password);
      setUser(userData);
      setIsAuthenticated(true);
      return { success: true };
    } catch (err) {
      console.error('AuthContext login error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Errore durante il login';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const register = async (email, username, password, fullName = null) => {
    setError(null);
    try {
      await apiRegister(email, username, password, fullName);
      // Auto-login dopo la registrazione
      return await login(username, password);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 'Errore durante la registrazione';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setError(null);
    }
  };

  const refreshUser = async () => {
    try {
      const userData = await getCurrentUser();
      setUser(userData);
      return userData;
    } catch (err) {
      console.error('Refresh user error:', err);
      return null;
    }
  };

  const clearError = () => setError(null);

  // ============================================================================
  // PERMISSIONS & CREDITS HELPERS
  // ============================================================================

  /**
   * Verifica se l'utente ha un permesso specifico.
   * Admin ha sempre tutti i permessi.
   */
  const hasPermission = useCallback((permissionCode) => {
    if (!user) return false;
    if (user.role === 'admin' || user.is_admin) return true;
    return user.permissions?.includes(permissionCode) || false;
  }, [user]);

  /**
   * Controlla se l'utente e' un amministratore.
   */
  const isAdmin = user?.role === 'admin' || user?.is_admin || false;

  /**
   * Ottieni il saldo crediti. -1 = infiniti (admin).
   */
  const credits = user?.credits ?? 0;

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      isLoading,
      error,
      login,
      register,
      logout,
      refreshUser,
      clearError,
      // Nuovi helper per permessi e crediti
      hasPermission,
      isAdmin,
      credits
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
