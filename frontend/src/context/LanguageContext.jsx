import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import i18n from '../i18n';
import { getActiveLanguages, getPublicTranslations } from '../services/api';

const LANG_KEY = 'styleforge_language';

const DEFAULT_LANGUAGES = [
  { code: 'it', name: 'Italiano', native_name: 'Italiano', flag_country_code: 'it', is_default: true },
];

const LanguageContext = createContext();

export const LanguageProvider = ({ children }) => {
  const [currentLanguage, setCurrentLanguage] = useState(
    (typeof localStorage !== 'undefined' && localStorage.getItem(LANG_KEY)) || 'it'
  );
  const [availableLanguages, setAvailableLanguages] = useState(DEFAULT_LANGUAGES);

  // Carica le risorse di una lingua ≠ it e le registra in i18next (una volta).
  const fetchAndRegister = useCallback(async (code) => {
    if (code === 'it' || i18n.hasResourceBundle(code, 'translation')) return;
    try {
      const map = await getPublicTranslations(code);
      i18n.addResourceBundle(code, 'translation', map || {}, true, true);
    } catch {
      // se fallisce, i18next userà il fallback italiano
    }
  }, []);

  // All'avvio: elenco lingue attive + applica la lingua persistita (se ≠ it).
  useEffect(() => {
    getActiveLanguages()
      .then((data) => { if (data?.languages?.length) setAvailableLanguages(data.languages); })
      .catch(() => {});

    if (currentLanguage !== 'it') {
      fetchAndRegister(currentLanguage).then(() => i18n.changeLanguage(currentLanguage));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLanguage = useCallback(async (code) => {
    await fetchAndRegister(code);
    await i18n.changeLanguage(code);
    if (typeof localStorage !== 'undefined') localStorage.setItem(LANG_KEY, code);
    setCurrentLanguage(code);
  }, [fetchAndRegister]);

  return (
    <LanguageContext.Provider value={{ currentLanguage, setLanguage, availableLanguages }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }
  return context;
};
