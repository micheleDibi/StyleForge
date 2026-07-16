-- ============================================================================
-- 32: Gerarchia di distribuzione (parent_id) + richieste crediti + inviti spostamento
-- ============================================================================
-- Aggiunge:
--   * users.parent_id (FK self): link canonico dell'albero distributore ->
--     rivenditore -> privato (1:1). Backfill da distributor_id.
--   * tabella credit_requests: richieste di crediti (scelta pacchetto).
--   * tabella parent_move_invitations: inviti di spostamento di un privato (token).
--
-- ⚠️ SE VA IN TIMEOUT: è contesa di lock sulla tabella "users" (di solito una
--    connessione "idle in transaction" che tiene un lock). NON è la migration in
--    sé. Rimedio (eseguilo PRIMA, poi rilancia il BLOCCO 3):
--
--    -- a) Trova i bloccanti:
--    --   SELECT pid, state, wait_event_type,
--    --          age(clock_timestamp(), xact_start) AS tx_age, left(query,80) AS q
--    --   FROM pg_stat_activity
--    --   WHERE datname = current_database() AND pid <> pg_backend_pid()
--    --     AND (state = 'idle in transaction' OR wait_event_type = 'Lock')
--    --   ORDER BY xact_start;
--    --
--    -- b) Termina le transazioni orfane (idle in transaction da oltre 1 minuto):
--    --   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
--    --   WHERE datname = current_database() AND pid <> pg_backend_pid()
--    --     AND state = 'idle in transaction' AND xact_start < now() - interval '1 minute';
--
-- I blocchi sono INDIPENDENTI e idempotenti: puoi eseguirli uno alla volta.
-- Il lock_timeout breve fa FALLIRE in fretta (invece di restare appeso): se un
-- blocco va in timeout, libera i lock (sopra) e rilancia solo quel blocco.

-- ----------------------------------------------------------------------------
-- BLOCCO 1: tabella credit_requests (non tocca pesantemente users)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_requests (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requester_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approver_id          UUID REFERENCES users(id) ON DELETE CASCADE,   -- NULL = pool admin
    approver_is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    package_id           INTEGER REFERENCES credit_packages(id) ON DELETE SET NULL,
    package_name         VARCHAR(100) NOT NULL,
    package_credits      INTEGER NOT NULL,
    package_price_cents  INTEGER NOT NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|canceled
    note                 TEXT,
    resolver_id          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at          TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_credit_requests_requester ON credit_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_credit_requests_approver  ON credit_requests(approver_id, status);
CREATE INDEX IF NOT EXISTS idx_credit_requests_admin     ON credit_requests(approver_is_admin, status);

-- ----------------------------------------------------------------------------
-- BLOCCO 2: tabella parent_move_invitations
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parent_move_invitations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    privato_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_parent_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    to_parent_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- l'invitante
    token_hash      VARCHAR(64) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|accepted|rejected|expired|canceled
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at     TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_move_inv_token   ON parent_move_invitations(token_hash);
CREATE INDEX IF NOT EXISTS idx_move_inv_privato ON parent_move_invitations(privato_id, status);

-- ----------------------------------------------------------------------------
-- BLOCCO 3: users.parent_id (richiede ACCESS EXCLUSIVE su users → sensibile ai lock)
--   ADD COLUMN senza default = metadati-only (istantaneo su PG11+); il costo è
--   SOLO acquisire il lock. Se va in timeout, libera i lock (header) e rilancia.
-- ----------------------------------------------------------------------------
SET lock_timeout = '5s';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_users_parent_id ON users(parent_id);

RESET lock_timeout;

-- ----------------------------------------------------------------------------
-- BLOCCO 4: backfill (i rivenditori avevano il riferimento nel vecchio distributor_id)
-- ----------------------------------------------------------------------------
UPDATE users
   SET parent_id = distributor_id
 WHERE parent_id IS NULL
   AND distributor_id IS NOT NULL;
