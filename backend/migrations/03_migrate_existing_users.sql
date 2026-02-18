-- ============================================
-- PARTE 3: Migra utenti esistenti ai nuovi ruoli
-- ============================================

-- Admin esistenti -> ruolo admin
UPDATE users
SET role_id = (SELECT id FROM roles WHERE name = 'admin')
WHERE is_admin = TRUE AND role_id IS NULL;

-- Tutti gli altri -> ruolo user
UPDATE users
SET role_id = (SELECT id FROM roles WHERE name = 'user')
WHERE role_id IS NULL;
