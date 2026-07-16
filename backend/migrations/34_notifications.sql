-- ============================================================================
-- 34: Notifiche in-app (centro notifiche / campanella)
-- ============================================================================
-- Tabella notifications: una riga per notifica destinata a un utente.
-- Idempotente. Non tocca la tabella "users" se non per la FK (lock leggero).

CREATE TABLE IF NOT EXISTS notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(40) NOT NULL,   -- request_received | request_approved | request_rejected | credits_assigned | ...
    title       VARCHAR(160) NOT NULL,
    message     TEXT,
    link        VARCHAR(255),
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at     TIMESTAMP WITH TIME ZONE
);

-- Indice per il conteggio dei non letti e l'elenco recente per utente.
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);
