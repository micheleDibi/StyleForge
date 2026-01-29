import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Train from './pages/Train';
import Generate from './pages/Generate';
import Humanize from './pages/Humanize';
import SessionDetail from './pages/SessionDetail';
import ThesisGenerator from './pages/ThesisGenerator';
import Helper from './components/Helper';
import Footer from './components/Footer';

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-dots text-blue-600">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

const PublicRoute = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-dots text-blue-600">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <Navigate to="/" replace /> : children;
};

// Helper visibile solo per utenti autenticati
const AuthenticatedHelper = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Helper /> : null;
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <Register />
          </PublicRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/train"
        element={
          <ProtectedRoute>
            <Train />
          </ProtectedRoute>
        }
      />
      <Route
        path="/generate"
        element={
          <ProtectedRoute>
            <Generate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/humanize"
        element={
          <ProtectedRoute>
            <Humanize />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessions/:sessionId"
        element={
          <ProtectedRoute>
            <SessionDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/thesis"
        element={
          <ProtectedRoute>
            <ThesisGenerator />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col">
          <div className="flex-1">
            <AppRoutes />
          </div>
          <Footer />
        </div>
        <AuthenticatedHelper />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
