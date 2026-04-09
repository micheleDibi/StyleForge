import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ArrowRight, Eye, EyeOff } from 'lucide-react';

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
    <div className="min-h-screen flex relative overflow-hidden">
      {/* Lato sinistro — pannello decorativo */}
      <div className="hidden lg:flex lg:w-1/2 relative items-center justify-center bg-gradient-to-br from-orange-500 via-orange-600 to-red-500">
        {/* Pattern geometrico */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-40 h-40 border-2 border-white rounded-3xl rotate-12"></div>
          <div className="absolute top-40 right-32 w-24 h-24 border-2 border-white rounded-full"></div>
          <div className="absolute bottom-32 left-40 w-32 h-32 border-2 border-white rounded-2xl -rotate-6"></div>
          <div className="absolute bottom-20 right-20 w-20 h-20 border-2 border-white rounded-full"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 border border-white rounded-full"></div>
        </div>
        <div className="relative z-10 text-center px-12">
          <h2 className="text-5xl font-extrabold text-white mb-4 leading-tight">
            Style<span className="text-orange-200">Forge</span>
          </h2>
          <p className="text-xl text-orange-100 font-medium mb-6">
            Genera contenuti con il tuo stile unico
          </p>
          <div className="flex items-center justify-center gap-3 text-orange-200/80 text-sm">
            <span className="w-8 h-px bg-orange-200/40"></span>
            Addestramento AI &middot; Generazione &middot; Umanizzazione &middot; Tesi
            <span className="w-8 h-px bg-orange-200/40"></span>
          </div>
        </div>
      </div>

      {/* Lato destro — form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10 bg-white">
        {/* Sfondo sottile solo mobile */}
        <div className="absolute inset-0 lg:hidden">
          <div className="absolute -top-32 -right-32 w-80 h-80 bg-orange-100 rounded-full opacity-50 blur-3xl"></div>
          <div className="absolute -bottom-32 -left-32 w-80 h-80 bg-orange-50 rounded-full opacity-60 blur-3xl"></div>
        </div>

        <div className={`w-full max-w-sm relative z-10 ${isShaking ? 'animate-shake' : ''}`}>
          {/* Header mobile */}
          <div className="text-center mb-10 lg:mb-8">
            <h1 className="text-3xl font-bold text-slate-900 lg:hidden mb-1">
              Style<span className="gradient-text">Forge</span>
            </h1>
            <h2 className="text-2xl font-bold text-slate-900 hidden lg:block mb-1">
              Bentornato
            </h2>
            <p className="text-slate-500">
              Accedi al tuo account per continuare
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-semibold text-slate-700 mb-2">
                Username o Email
              </label>
              <input
                id="username"
                name="username"
                type="text"
                value={formData.username}
                onChange={handleChange}
                className={`w-full px-4 py-3 rounded-xl border bg-slate-50 text-slate-900 placeholder-slate-400 text-sm transition-all focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:bg-white ${
                  error ? 'border-red-300' : 'border-slate-200 focus:border-orange-400'
                }`}
                placeholder="nome@email.com"
                autoFocus
                autoComplete="username"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-slate-700 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={handleChange}
                  className={`w-full px-4 py-3 pr-12 rounded-xl border bg-slate-50 text-slate-900 placeholder-slate-400 text-sm transition-all focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:bg-white ${
                    error ? 'border-red-300' : 'border-slate-200 focus:border-orange-400'
                  }`}
                  placeholder="La tua password"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 font-medium">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>Accesso in corso...</span>
                </>
              ) : (
                <>
                  <span>Accedi</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Register */}
          <p className="mt-8 text-center text-sm text-slate-500">
            Non hai un account?{' '}
            <Link
              to="/register"
              className="font-semibold text-orange-600 hover:text-orange-700 transition-colors"
            >
              Registrati ora
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
