/**
 * Requisiti password, in un posto solo.
 *
 * SPECCHIA backend/auth.py (validate_password_strength): il backend e' l'unico
 * che decide davvero — questo serve a dirlo all'utente prima di fargli premere
 * invio. Se cambia una regola di la', va cambiata anche qui, altrimenti la form
 * accetta e l'API rifiuta.
 *
 * Prima la regola ("almeno 6") era copiata in tre componenti piu' lo strength
 * meter, e il meter suggeriva requisiti che il backend non imponeva.
 */

export const PASSWORD_MIN_LENGTH = 12;
// bcrypt guarda solo i primi 72 byte e tronca in silenzio.
export const PASSWORD_MAX_BYTES = 72;

const byteLength = (pw) => new TextEncoder().encode(pw).length;

/**
 * @returns {string|null} messaggio d'errore tradotto, o null se la password va bene.
 */
export function validatePassword(pw, t) {
  const password = pw || '';
  if (password.length < PASSWORD_MIN_LENGTH) {
    return t('La password deve essere di almeno {{n}} caratteri', { n: PASSWORD_MIN_LENGTH });
  }
  if (byteLength(password) > PASSWORD_MAX_BYTES) {
    return t('La password non può superare i {{n}} byte', { n: PASSWORD_MAX_BYTES });
  }
  if (!/[A-Z]/.test(password)) {
    return t('La password deve contenere almeno una lettera maiuscola');
  }
  if (!/[0-9]/.test(password)) {
    return t('La password deve contenere almeno un numero');
  }
  return null;
}

/** Punteggio 0-4 per l'indicatore di robustezza (i primi 2 livelli = requisiti minimi). */
export function passwordStrength(pw) {
  const password = pw || '';
  if (!password) return 0;
  let punti = 0;
  if (password.length >= PASSWORD_MIN_LENGTH) punti++;
  if (/[A-Z]/.test(password) && /[0-9]/.test(password)) punti++;
  if (password.length >= 16) punti++;
  if (/[^A-Za-z0-9]/.test(password)) punti++;
  return punti;
}
