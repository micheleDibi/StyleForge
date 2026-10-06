import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

const Flag = ({ code }) => (
  <span className={`fi fi-${code}`} style={{ fontSize: '1.05rem', borderRadius: 2, lineHeight: 1 }} />
);

/**
 * Selettore lingua. variant='compact' (solo bandiera, per header) | 'full' (bandiera + nome).
 */
const LanguageSwitcher = ({ variant = 'compact' }) => {
  const { t } = useTranslation();
  const { currentLanguage, setLanguage, availableLanguages } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const current = availableLanguages.find((l) => l.code === currentLanguage) || availableLanguages[0];

  const handleSelect = async (code) => {
    setOpen(false);
    if (code !== currentLanguage) await setLanguage(code);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-2.5 py-2 rounded-xl border border-gray-200/60 bg-white/70 hover:bg-white transition-colors"
        title={t('Lingua')}
      >
        {current && <Flag code={current.flag_country_code} />}
        {variant === 'full' && current && (
          <span className="text-sm font-medium text-gray-700">{current.native_name}</span>
        )}
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-44 bg-white rounded-xl border border-gray-200 shadow-lg z-50 py-1 max-h-72 overflow-y-auto">
          {availableLanguages.map((l) => (
            <button
              key={l.code}
              onClick={() => handleSelect(l.code)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-gray-50 ${
                l.code === currentLanguage ? 'font-semibold text-orange-600' : 'text-gray-700'
              }`}
            >
              <Flag code={l.flag_country_code} />
              <span className="truncate">{l.native_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default LanguageSwitcher;
