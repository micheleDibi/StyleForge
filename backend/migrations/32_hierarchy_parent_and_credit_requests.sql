-- ============================================================================
-- 32: Gerarchia di distribuzione (parent_id) + richieste crediti + inviti spostamento
-- ============================================================================
-- Aggiunge:
--   * users.parent_id (FK self): link canonico "appartiene a" dell'albero
--     distributore -> rivenditore -> privato (1:1). Backfill da distributor_id.
--   * tabella credit_requests: richieste di crediti (scelta pacchetto del listino)
--     inoltrate al referente/admin, con snapshot del pacchetto.
--   * tabella parent_move_invitations: inviti di spostamento di un privato (token
--     monouso, accetta/rifiuta via email).
--
-- NOTE:
--   * ADD COLUMN senza default = metadati-only (istantaneo su PG11+).
--   * SET lock_timeout: l'ALTER su `users` (tabella calda) fallisce in fretta se il
--     lock non è subito disponibile, invece di restare appeso.
--   * distributor_id NON viene droppato qui (lo fa la migration 33 dopo il deploy).
--   * Idempotente: IF NOT EXISTS ovunque.

SET lock_timeout = '8s';

-- 1. users.parent_id + indice ------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_users_parent_id ON users(parent_id);

-- Backfill: i rivenditori avevano il riferimento nel vecchio distributor_id.
UPDATE users
   SET parent_id = distributor_id
 WHERE parent_id IS NULL
   AND distributor_id IS NOT NULL;

RESET lock_timeout;

-- 2. credit_requests ---------------------------------------------------------
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

-- 3. parent_move_invitations -------------------------------------------------
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
