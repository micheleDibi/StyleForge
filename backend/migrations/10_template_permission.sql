-- ============================================================================
-- 10: Permesso 'manage_templates' per gestione template esportazione
-- Lo schema usa role_permissions con permission_code (VARCHAR), non una
-- tabella permissions separata.
-- ============================================================================

-- Associa il permesso manage_templates al ruolo admin
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, 'manage_templates'
FROM roles r
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;
