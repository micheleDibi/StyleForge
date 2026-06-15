-- ============================================================================
-- 23: Sottotipi utente (distributore/rivenditore/privato) + pacchetti per ruolo
-- ============================================================================
-- Sostituisce il vecchio entity_type a 2 valori ('private'/'training') con tre
-- sottotipi dell'utente normale: 'distributore' | 'rivenditore' | 'privato'.
--   * users.entity_type: nuovo default 'privato'; gli utenti esistenti migrano
--     tutti a 'privato' (l'admin riassegna manualmente distributori/rivenditori).
--   * users.distributor_id: collega un rivenditore al suo distributore (FK self).
--   * credit_packages.entity_type: scoping del pacchetto per sottotipo. Ogni
--     utente vede/acquista solo i pacchetti del proprio sottotipo.
--   * Disattiva i 3 pacchetti generici (Starter/Standard/Plus) e inserisce 9
--     pacchetti nuovi (3 per sottotipo).
--   * Rimuove lo sconto enti di formazione (system_settings).
--
-- Idempotente. La cartella migrations/full_reset/ è uno snapshot legacy
-- pre-billing: NON allineata qui (fuori scope). Il percorso canonico è questa
-- migrazione + db_models.Base.metadata.create_all per i fresh install dev.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. users.entity_type: nuovi sottotipi
-- ----------------------------------------------------------------------------
ALTER TABLE users ALTER COLUMN entity_type SET DEFAULT 'privato';
UPDATE users
   SET entity_type = 'privato'
 WHERE entity_type IS NULL OR entity_type IN ('private', 'training');

-- ----------------------------------------------------------------------------
-- 2. users.distributor_id: collegamento rivenditore -> distributore
-- ----------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS distributor_id UUID
    REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_users_distributor_id ON users(distributor_id);

-- ----------------------------------------------------------------------------
-- 3. credit_packages.entity_type: scoping pacchetto per sottotipo
-- ----------------------------------------------------------------------------
ALTER TABLE credit_packages ADD COLUMN IF NOT EXISTS entity_type VARCHAR(20)
    NOT NULL DEFAULT 'privato';
CREATE INDEX IF NOT EXISTS idx_credit_packages_entity
    ON credit_packages(entity_type, is_active, sort_order);

-- ----------------------------------------------------------------------------
-- 4. Disattiva i 3 pacchetti generici (no delete: preservano FK/snapshot ordini)
-- ----------------------------------------------------------------------------
UPDATE credit_packages
   SET is_active = FALSE, updated_at = NOW()
 WHERE name IN ('Starter', 'Standard', 'Plus');

-- ----------------------------------------------------------------------------
-- 5. Inserisce i 9 pacchetti per sottotipo (idempotente su name+entity_type)
--    sort_order: 100cr->1, 500cr->2, 1000cr->3 (il taglio medio è pre-selezionato).
-- ----------------------------------------------------------------------------
-- Distributore
INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Distributore 100', 100, 3500, TRUE, 1, 'Pacchetto distributore: 100 crediti', 'distributore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Distributore 100' AND entity_type = 'distributore');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Distributore 500', 500, 8000, TRUE, 2, 'Pacchetto distributore: 500 crediti', 'distributore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Distributore 500' AND entity_type = 'distributore');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Distributore 1000', 1000, 15000, TRUE, 3, 'Pacchetto distributore: 1000 crediti', 'distributore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Distributore 1000' AND entity_type = 'distributore');

-- Rivenditore
INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Rivenditore 100', 100, 5000, TRUE, 1, 'Pacchetto rivenditore: 100 crediti', 'rivenditore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Rivenditore 100' AND entity_type = 'rivenditore');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Rivenditore 500', 500, 11000, TRUE, 2, 'Pacchetto rivenditore: 500 crediti', 'rivenditore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Rivenditore 500' AND entity_type = 'rivenditore');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Rivenditore 1000', 1000, 20000, TRUE, 3, 'Pacchetto rivenditore: 1000 crediti', 'rivenditore', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Rivenditore 1000' AND entity_type = 'rivenditore');

-- Privato
INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Privato 100', 100, 15000, TRUE, 1, 'Pacchetto privato: 100 crediti', 'privato', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Privato 100' AND entity_type = 'privato');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Privato 500', 500, 30000, TRUE, 2, 'Pacchetto privato: 500 crediti', 'privato', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Privato 500' AND entity_type = 'privato');

INSERT INTO credit_packages (name, credits, price_cents, is_active, sort_order, description, entity_type, created_at, updated_at)
SELECT 'Privato 1000', 1000, 45000, TRUE, 3, 'Pacchetto privato: 1000 crediti', 'privato', NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Privato 1000' AND entity_type = 'privato');

-- ----------------------------------------------------------------------------
-- 6. Rimuove lo sconto enti di formazione (non più usato)
-- ----------------------------------------------------------------------------
DELETE FROM system_settings WHERE key = 'training_discount_percent';
