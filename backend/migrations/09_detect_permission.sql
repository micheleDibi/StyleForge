-- ============================================================================
-- 09: Permesso 'detect' per AI Detection
-- Lo schema usa role_permissions con permission_code (VARCHAR), non una
-- tabella permissions separata.
-- ============================================================================

-- Associa il permesso detect al ruolo admin
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, 'detect'
FROM roles r
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;
