import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  Sparkles, Zap, GraduationCap, Wand2, Search, ShieldCheck, ScrollText, ArrowRight,
} from 'lucide-react';

const Footer = () => {
  const { t } = useTranslation();
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
              {t('La piattaforma per generare e umanizzare contenuti accademici e professionali: addestra l\'AI sul tuo stile, crea tesi complete e riduci il rilevamento AI.')}
            </p>
          </div>

          {/* Funzionalità */}
          <div className="space-y-4">
            <h4 className="font-bold text-white text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary-400" />
              {t('Funzionalità')}
            </h4>
            <ul className="space-y-3 text-sm text-slate-300">
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <GraduationCap className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>{t('Generazione di tesi complete')}</span>
              </li>
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <Wand2 className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>{t('Umanizzazione e anti-rilevamento AI')}</span>
              </li>
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <Sparkles className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>{t('Contenuti nel tuo stile di scrittura')}</span>
              </li>
              <li className="flex items-start gap-2 hover:text-white transition-colors">
                <Search className="w-4 h-4 text-primary-400 mt-0.5 flex-shrink-0" />
                <span>{t('Ricerca accademica e knowledge base')}</span>
              </li>
            </ul>
          </div>

          {/* Informazioni legali */}
          <div className="space-y-4">
            <h4 className="font-bold text-white text-lg flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-primary-400" />
              {t('Informazioni legali')}
            </h4>
            <div className="space-y-3">
              <Link
                to="/privacy"
                className="flex items-center gap-3 px-4 py-3 bg-slate-700/50 hover:bg-slate-700 rounded-xl border border-slate-600 hover:border-primary-500 transition-all group"
              >
                <ShieldCheck className="w-5 h-5 text-primary-400 group-hover:scale-110 transition-transform flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white">{t('Privacy Policy')}</p>
                  <p className="text-xs text-slate-400">{t('Come trattiamo i tuoi dati')}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-primary-400 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </Link>
              <Link
                to="/terms"
                className="flex items-center gap-3 px-4 py-3 bg-slate-700/50 hover:bg-slate-700 rounded-xl border border-slate-600 hover:border-primary-500 transition-all group"
              >
                <ScrollText className="w-5 h-5 text-primary-400 group-hover:scale-110 transition-transform flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white">{t('Termini di Servizio')}</p>
                  <p className="text-xs text-slate-400">{t('Condizioni d\'uso del servizio')}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-primary-400 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </Link>
            </div>
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-10 pt-8 border-t border-slate-700">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-slate-400">
              © {new Date().getFullYear()} <span className="font-semibold text-white">StyleForge</span>. {t('Tutti i diritti riservati.')}
            </p>
            <div className="flex gap-5 text-sm">
              <Link to="/privacy" className="text-slate-300 hover:text-primary-400 font-medium transition-colors">{t('Privacy Policy')}</Link>
              <Link to="/terms" className="text-slate-300 hover:text-primary-400 font-medium transition-colors">{t('Termini di Servizio')}</Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
