// Estrae le chiavi da tutti i t('...') in src/ e genera src/i18n/locales/it.json.
// Chiave naturale: il valore italiano coincide con la chiave.
// Eseguire con: npm run i18n:extract
export default {
  locales: ['it'],
  output: 'src/i18n/locales/$LOCALE.json',
  input: ['src/**/*.{js,jsx}'],
  keySeparator: false,
  namespaceSeparator: false,
  defaultValue: (locale, ns, key) => key,
  sort: true,
  keepRemoved: false,
  lexers: {
    js: ['JsxLexer'],
    jsx: ['JsxLexer'],
  },
};
