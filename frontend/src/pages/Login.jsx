import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Lock, Sparkles, User, ArrowRight, Eye, EyeOff, Zap } from 'lucide-react';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isShaking, setIsShaking] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.username || !formData.password) {
      setError('Inserisci username e password');
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 500);
      return;
    }

    setIsLoading(true);

    try {
      const result = await login(formData.username, formData.password);

      setIsLoading(false);

      if (result.success) {
        navigate('/');
      } else {
        setError(result.error);
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 500);
        setFormData(prev => ({ ...prev, password: '' }));
      }
    } catch (err) {
      setIsLoading(false);
      setError('Errore durante il login. Riprova.');
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 500);
      console.error('Login error:', err);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Animation */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-gradient-to-br from-orange-200 to-orange-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-1/3 right-1/4 w-[400px] h-[400px] bg-gradient-to-br from-purple-200 to-pink-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-1/4 left-1/3 w-[450px] h-[450px] bg-gradient-to-br from-blue-200 to-cyan-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      {/* Decorative Elements */}
      <div className="absolute top-10 left-10 w-20 h-20 border-2 border-orange-200 rounded-full opacity-50 animate-float hidden md:block"></div>
      <div className="absolute bottom-20 right-20 w-32 h-32 border-2 border-purple-200 rounded-full opacity-30 animate-float animation-delay-2000 hidden md:block"></div>
      <div className="absolute top-1/2 right-10 w-16 h-16 bg-gradient-to-br from-orange-100 to-orange-200 rounded-2xl opacity-50 rotate-12 animate-float animation-delay-4000 hidden md:block"></div>

      <div className={`w-full max-w-md relative z-10 ${isShaking ? 'animate-shake' : ''}`}>
        {/* Logo/Header */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="inline-block mb-6 relative">
            <div className="absolute inset-0 bg-gradient-to-br from-orange-400 to-orange-600 rounded-3xl blur-2xl opacity-40 scale-110"></div>
            <img
              src="/logo.png"
              alt="StyleForge Logo"
              className="relative h-28 w-auto mx-auto drop-shadow-2xl"
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextElementSibling.style.display = 'flex';
              }}
            />
            <div className="hidden items-center justify-center w-28 h-28 bg-gradient-to-br from-orange-500 to-orange-600 rounded-3xl shadow-2xl relative">
              <Sparkles className="w-14 h-14 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Style<span className="gradient-text">Forge</span>
          </h1>
          <p className="text-gray-600 text-lg">
            Genera contenuti con il tuo stile unico
          </p>
        </div>

        {/* Login Card */}
        <div className="glass rounded-3xl p-8 shadow-2xl animate-slide-up">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-orange-100 to-orange-200 rounded-2xl mb-4">
              <Lock className="w-7 h-7 text-orange-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">
              Bentornato
            </h2>
            <p className="text-gray-500 mt-2">
              Accedi al tuo account per continuare
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username/Email */}
            <div>
              <label htmlFor="username" className="block text-sm font-semibold text-gray-700 mb-2">
                Username o Email
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="w-5 h-5 text-gray-400 group-focus-within:text-orange-500 transition-colors" />
                </div>
                <input
                  id="username"
                  name="username"
                  type="text"
                  value={formData.username}
                  onChange={handleChange}
                  className={`input pl-11 ${error ? 'input-error' : ''}`}
                  placeholder="nome@email.com"
                  autoFocus
                  autoComplete="username"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700 mb-2">
                Password
              </label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="w-5 h-5 text-gray-400 group-focus-within:text-orange-500 transition-colors" />
                </div>
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={handleChange}
                  className={`input pl-11 pr-12 ${error ? 'input-error' : ''}`}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-gray-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-100 rounded-xl animate-scale-in">
                <div className="flex-shrink-0 w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                  <span className="text-red-500 text-lg font-bold">!</span>
                </div>
                <p className="text-sm text-red-600 font-medium">{error}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn btn-primary btn-lg group"
            >
              {isLoading ? (
                <>
                  <div className="spinner"></div>
                  <span>Accesso in corso...</span>
                </>
              ) : (
                <>
                  <span>Accedi</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">oppure</span>
            </div>
          </div>

          {/* Register Link */}
          <div className="text-center">
            <p className="text-gray-600">
              Non hai un account?{' '}
              <Link
                to="/register"
                className="font-semibold text-orange-600 hover:text-orange-700 transition-colors inline-flex items-center gap-1"
              >
                Registrati
                <Zap className="w-4 h-4" />
              </Link>
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Login;
