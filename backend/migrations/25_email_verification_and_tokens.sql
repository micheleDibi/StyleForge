-- ============================================================================
-- 25: Verifica email + token monouso (verifica / reset password / invito)
-- ============================================================================
-- Aggiunge:
--   * users.email_verified (BOOLEAN, default FALSE) + users.email_verified_at
--   * GRANDFATHER: tutti gli utenti ESISTENTI diventano verificati (no lockout);
--     solo le NUOVE registrazioni partono da FALSE.
--   * users.hashed_password reso NULLABLE (gli utenti creati dall'admin non hanno
--     password finché non la impostano via link "set_password").
--   * tabella email_tokens: token monouso (si salva solo lo SHA-256 del token).
--
-- Idempotente. Eseguire su Supabase (SQL Editor) prima del deploy del codice.
-- ============================================================================

-- 1. Gate verifica email sugli utenti
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP WITH TIME ZONE;

-- 2. Grandfather: gli utenti già esistenti sono considerati verificati.
--    (Le nuove INSERT dell'app omettono la colonna -> restano FALSE.)
UPDATE users
   SET email_verified = TRUE,
       email_verified_at = COALESCE(email_verified_at, NOW())
 WHERE email_verified = FALSE;

-- 3. La password può essere assente (utente invitato dall'admin che la imposterà)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- 4. Token email monouso (verifica / reset / set_password)
CREATE TABLE IF NOT EXISTS email_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL,          -- SHA-256 (hex) del token grezzo
    purpose     VARCHAR(20) NOT NULL,          -- 'verify' | 'reset' | 'set_password'
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at     TIMESTAMP WITH TIME ZONE,      -- NULL = non usato (monouso)
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_tokens_token_hash ON email_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_email_tokens_user_id    ON email_tokens(user_id);
