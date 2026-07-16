-- ============================================================================
-- 25: Verifica email + token monouso (verifica / reset password / invito)
-- ============================================================================
-- Aggiunge:
--   * users.email_verified (BOOLEAN, default FALSE per i NUOVI) + email_verified_at
--   * GRANDFATHER: tutti gli utenti ESISTENTI diventano verificati (no lockout);
--     solo le NUOVE registrazioni partono da FALSE.
--   * users.hashed_password reso NULLABLE (gli utenti creati dall'admin non hanno
--     password finché non la impostano via link "set_password").
--   * tabella email_tokens: token monouso (si salva solo lo SHA-256 del token).
--
-- NOTA SUL TIMEOUT (perché questa versione non va più in timeout):
--   * NIENTE "UPDATE users SET ...": il grandfather si fa aggiungendo la colonna
--     con DEFAULT TRUE (riempie le righe esistenti come operazione di soli
--     METADATI, istantanea su Postgres 11+) e poi spostando il default a FALSE
--     per i nuovi inserimenti. Così non si riscrive l'intera tabella.
--   * `SET lock_timeout`: gli ALTER TABLE e la FK verso users richiedono un lock
--     esclusivo su `users` (tabella "calda": l'app la usa ad ogni login). Con un
--     lock_timeout breve, se il lock non è subito disponibile lo statement
--     FALLISCE in fretta invece di restare appeso fino al timeout globale:
--     in tal caso basta rilanciare (meglio in un momento di basso traffico).
--   * email_verified_at resta NULL per gli utenti "grandfathered": l'app legge
--     solo il booleano email_verified, quindi è sicuro (nessuna riscrittura).
--
-- Idempotente. Eseguire su Supabase (SQL Editor). Se uno STEP fallisce per lock,
-- rilanciare solo quello STEP.
-- ============================================================================

-- Se un lock non è subito disponibile, fallisci entro 8s (così è ritentabile)
SET lock_timeout = '8s';

-- ----------------------------------------------------------------------------
-- STEP 1 — Gate verifica email (grandfather senza riscrivere la tabella)
-- ----------------------------------------------------------------------------
-- ADD ... DEFAULT TRUE  -> tutte le righe ESISTENTI risultano verificate
--                          (sola operazione di metadati, niente full rewrite)
-- poi SET DEFAULT FALSE -> i NUOVI utenti partono da non verificato
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP WITH TIME ZONE;

-- ----------------------------------------------------------------------------
-- STEP 2 — La password può essere assente (utente invitato dall'admin)
-- ----------------------------------------------------------------------------
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- ----------------------------------------------------------------------------
-- STEP 3 — Token email monouso (verifica / reset / set_password)
-- ----------------------------------------------------------------------------
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
