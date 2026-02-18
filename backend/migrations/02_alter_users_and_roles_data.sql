-- ============================================
-- PARTE 2: Modifica tabella users + dati iniziali ruoli
-- ============================================

-- Aggiungi colonna role_id
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(id);

-- Aggiungi colonna credits
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 0 NOT NULL;

-- Indice per role_id
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);

-- Inserisci ruoli
INSERT INTO roles (name, description, is_default)
VALUES ('admin', 'Amministratore con accesso completo a tutte le funzionalita e crediti infiniti', FALSE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO roles (name, description, is_default)
VALUES ('user', 'Utente standard con accesso limitato alle funzionalita di base', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Permessi admin: tutti
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
CROSS JOIN (VALUES ('train'), ('generate'), ('humanize'), ('thesis')) AS p(code)
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- Permessi user: solo train e thesis
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
CROSS JOIN (VALUES ('train'), ('thesis')) AS p(code)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_code) DO NOTHING;
