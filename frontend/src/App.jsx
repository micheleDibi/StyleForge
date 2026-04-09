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
import Admin from './pages/Admin';
import DetectorAI from './pages/DetectorAI';
import EnhanceImage from './pages/EnhanceImage';
import CarouselCreator from './pages/CarouselCreator';
import ImageToVideo from './pages/ImageToVideo';
import Helper from './components/Helper';
import Footer from './components/Footer';

const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-orange-50">
    <div className="flex flex-col items-center gap-4">
      <div className="relative w-12 h-12">
        <div className="absolute inset-0 rounded-full border-[3px] border-slate-200"></div>
        <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-orange-500 animate-spin"></div>
      </div>
      <p className="text-sm text-slate-500 font-medium">Caricamento...</p>
    </div>
  </div>
);

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

const PublicRoute = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  return isAuthenticated ? <Navigate to="/" replace /> : children;
};

const PermissionRoute = ({ children, permission }) => {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return hasPermission(permission) ? children : <Navigate to="/" replace />;
};

const AdminRoute = ({ children }) => {
  const { isAuthenticated, isLoading, isAdmin } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return isAdmin ? children : <Navigate to="/" replace />;
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
          <PermissionRoute permission="train">
            <Train />
          </PermissionRoute>
        }
      />
      <Route
        path="/generate"
        element={
          <PermissionRoute permission="generate">
            <Generate />
          </PermissionRoute>
        }
      />
      <Route
        path="/humanize"
        element={
          <PermissionRoute permission="humanize">
            <Humanize />
          </PermissionRoute>
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
          <PermissionRoute permission="thesis">
            <ThesisGenerator />
          </PermissionRoute>
        }
      />
      <Route
        path="/enhance-image"
        element={
          <PermissionRoute permission="enhance_image">
            <EnhanceImage />
          </PermissionRoute>
        }
      />
      <Route
        path="/carousel"
        element={
          <PermissionRoute permission="carousel_creator">
            <CarouselCreator />
          </PermissionRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <Admin />
          </AdminRoute>
        }
      />
      <Route
        path="/image-to-video"
        element={
          <AdminRoute>
            <ImageToVideo />
          </AdminRoute>
        }
      />
      <Route
        path="/detector-ai"
        element={
          <AdminRoute>
            <DetectorAI />
          </AdminRoute>
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
