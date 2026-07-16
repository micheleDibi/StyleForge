import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import itBase from './locales/it.json';

// Strategia "chiave naturale": la stringa italiana È la chiave.
// keySeparator/nsSeparator a false perché le chiavi contengono '.' e ':'.
// fallbackLng 'it' + returnEmptyString:false => chiavi mancanti/vuote tornano in italiano.

const STORED_LANG =
  (typeof localStorage !== 'undefined' && localStorage.getItem('styleforge_language')) || 'it';

i18n.use(initReactI18next).init({
  lng: STORED_LANG,
  fallbackLng: 'it',
  resources: { it: { translation: itBase } },
  keySeparator: false,
  nsSeparator: false,
  returnEmptyString: false,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export default i18n;
