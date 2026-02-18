-- ============================================
-- StyleForge - Roles, Permissions & Credits System
-- ============================================
-- Migration per aggiungere il sistema di ruoli, permessi e crediti interni.
-- Esegui questo script nel SQL Editor di Supabase DOPO init_supabase.sql
--
-- COSA FA QUESTO SCRIPT:
-- 1. Crea tabelle: roles, role_permissions, user_permissions, credit_transactions
-- 2. Aggiunge colonne role_id e credits alla tabella users
-- 3. Inserisce i ruoli predefiniti (admin, user) con i relativi permessi
-- 4. Migra gli utenti esistenti ai nuovi ruoli
-- ============================================

-- ============================================
-- TABELLA ROLES
-- ============================================
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger per roles.updated_at
CREATE TRIGGER update_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- TABELLA ROLE_PERMISSIONS
-- ============================================
-- Permessi assegnati a ciascun ruolo.
-- permission_code: 'train', 'generate', 'humanize', 'thesis'
CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_code VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(role_id, permission_code)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_code ON role_permissions(permission_code);

-- ============================================
-- TABELLA USER_PERMISSIONS (override per singolo utente)
-- ============================================
-- Permette all'admin di sovrascrivere i permessi del ruolo per un singolo utente.
-- granted = TRUE  -> forza abilitazione (anche se il ruolo non lo ha)
-- granted = FALSE -> forza disabilitazione (anche se il ruolo lo ha)
-- Se non esiste riga -> eredita dal ruolo
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_code VARCHAR(50) NOT NULL,
    granted BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, permission_code)
);

CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_code ON user_permissions(permission_code);

-- ============================================
-- TABELLA CREDIT_TRANSACTIONS
-- ============================================
-- Storico di tutte le transazioni crediti per ogni utente.
-- amount > 0: aggiunta crediti (acquisto, admin_adjustment)
-- amount < 0: consumo crediti (operazione)
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,  -- 'purchase', 'consumption', 'admin_adjustment', 'refund'
    description TEXT,
    related_job_id VARCHAR(50),
    operation_type VARCHAR(50),  -- 'train', 'generate', 'humanize', 'thesis_chapters', 'thesis_sections', 'thesis_content'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_date ON credit_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(transaction_type);

-- ============================================
-- MODIFICHE TABELLA USERS
-- ============================================

-- Aggiungi colonna role_id (FK verso roles)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'role_id') THEN
        ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id);
        RAISE NOTICE 'Colonna role_id aggiunta alla tabella users';
    END IF;
END $$;

-- Aggiungi colonna credits (saldo crediti interni)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'credits') THEN
        ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0 NOT NULL;
        RAISE NOTICE 'Colonna credits aggiunta alla tabella users';
    END IF;
END $$;

-- Indice per role_id
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);

-- ============================================
-- DATI INIZIALI - RUOLI
-- ============================================

-- Inserisci ruolo 'admin'
INSERT INTO roles (name, description, is_default)
VALUES ('admin', 'Amministratore con accesso completo a tutte le funzionalita e crediti infiniti', FALSE)
ON CONFLICT (name) DO NOTHING;

-- Inserisci ruolo 'user'
INSERT INTO roles (name, description, is_default)
VALUES ('user', 'Utente standard con accesso limitato alle funzionalita di base', TRUE)
ON CONFLICT (name) DO NOTHING;

-- ============================================
-- DATI INIZIALI - PERMESSI RUOLI
-- ============================================

-- Permessi per il ruolo 'admin': TUTTI i permessi
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
CROSS JOIN (
    VALUES ('train'), ('generate'), ('humanize'), ('thesis')
) AS p(code)
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- Permessi per il ruolo 'user': solo 'train' e 'thesis'
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
CROSS JOIN (
    VALUES ('train'), ('thesis')
) AS p(code)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- ============================================
-- MIGRAZIONE UTENTI ESISTENTI
-- ============================================

-- Assegna il ruolo 'admin' agli utenti con is_admin = TRUE
UPDATE users
SET role_id = (SELECT id FROM roles WHERE name = 'admin')
WHERE is_admin = TRUE AND role_id IS NULL;

-- Assegna il ruolo 'user' a tutti gli altri utenti
UPDATE users
SET role_id = (SELECT id FROM roles WHERE name = 'user')
WHERE role_id IS NULL;

-- ============================================
-- VERIFICHE
-- ============================================

DO $$
DECLARE
    admin_role_id INTEGER;
    user_role_id INTEGER;
    admin_perms INTEGER;
    user_perms INTEGER;
    migrated_users INTEGER;
BEGIN
    SELECT id INTO admin_role_id FROM roles WHERE name = 'admin';
    SELECT id INTO user_role_id FROM roles WHERE name = 'user';
    SELECT COUNT(*) INTO admin_perms FROM role_permissions WHERE role_id = admin_role_id;
    SELECT COUNT(*) INTO user_perms FROM role_permissions WHERE role_id = user_role_id;
    SELECT COUNT(*) INTO migrated_users FROM users WHERE role_id IS NOT NULL;

    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Migration completata con successo!';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tabelle create: roles, role_permissions, user_permissions, credit_transactions';
    RAISE NOTICE 'Colonne aggiunte a users: role_id, credits';
    RAISE NOTICE '';
    RAISE NOTICE 'Ruolo admin (id=%): % permessi', admin_role_id, admin_perms;
    RAISE NOTICE 'Ruolo user  (id=%): % permessi', user_role_id, user_perms;
    RAISE NOTICE 'Utenti migrati: %', migrated_users;
    RAISE NOTICE '============================================';
END $$;
