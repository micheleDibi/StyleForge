-- ============================================================================
-- 11: Garantisce che tutti i permessi siano presenti per i ruoli
-- Questa migration è idempotente e può essere rieseguita senza problemi.
-- ============================================================================

-- ============================================
-- PERMESSI ADMIN: tutti e 6
-- ============================================
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r,
     (VALUES ('train'), ('generate'), ('humanize'), ('thesis'), ('detect'), ('manage_templates')) AS p(code)
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;

-- ============================================
-- PERMESSI USER: train e thesis
-- ============================================
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r,
     (VALUES ('train'), ('thesis')) AS p(code)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_code) DO NOTHING;
