import { Mail, Sparkles, Github, Heart, Zap, FileText, Sparkle } from 'lucide-react';

const Footer = () => {
  return (
    <footer className="bg-gradient-to-br from-slate-900 via-slate-800 to-primary-900 border-t-4 border-primary-500 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Brand */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center shadow-lg">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white">
                Style<span className="text-primary-400">Forge</span>
              </h3>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Genera contenuti personalizzati addestrati sul tuo stile di scrittura con l'intelligenza artificiale
            </p>
            <div className="flex gap-2 pt-2">
              <div className="px-3 py-1.5 bg-primary-500/20 rounded-lg border border-primary-400/30">
                <span className="text-xs font-semibold text-primary-300">AI-Powered</span>
              </div>
              <div className="px-3 py-1.5 bg-green-500/20 rounded-lg border border-green-400/30">
                <span className="text-xs font-semibold text-green-300">Personalizzato</span>
              </div>
            </div>
          </div>

          {/* Info */}
          <div className="space-y-4">
            <h4 className="font-bold text-white text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary-400" />
              Funzionalità
            </h4>
            <ul className="space-y-3 text-sm text-slate-300">
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <FileText className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>Training personalizzato con PDF</span>
              </li>
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <Sparkle className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>Generazione contenuti automatica</span>
              </li>
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <Zap className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>Gestione sessioni e job in tempo reale</span>
              </li>
            </ul>
          </div>

          {/* Contatti */}
          <div className="space-y-4">
            <h4 className="font-bold text-white text-lg flex items-center gap-2">
              <Mail className="w-5 h-5 text-primary-400" />
              Assistenza
            </h4>
            <div className="space-y-3">
              <a
                href="mailto:m.dibisceglia@ersaf.it"
                className="flex items-center gap-3 px-4 py-3 bg-slate-700/50 hover:bg-slate-700 rounded-xl border border-slate-600 hover:border-primary-500 transition-all group"
              >
                <Mail className="w-5 h-5 text-primary-400 group-hover:scale-110 transition-transform" />
                <div>
                  <p className="text-sm font-semibold text-white">Email</p>
                  <p className="text-xs text-slate-400">m.dibisceglia@ersaf.it</p>
                </div>
              </a>
              <p className="text-xs text-slate-400 px-2">
                Per supporto tecnico e informazioni
              </p>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-10 pt-8 border-t border-slate-700">
          <div className="flex flex-col md:flex-row items-center justify-center gap-4">
            <p className="text-sm text-slate-400">
              © {new Date().getFullYear()} <span className="font-semibold text-white">StyleForge</span>. Tutti i diritti riservati.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
