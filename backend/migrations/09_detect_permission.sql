-- ============================================================================
-- 09: Permesso 'detect' per AI Detection con Copyleaks
-- ============================================================================

INSERT INTO permissions (code, name, description)
VALUES ('detect', 'AI Detection', 'Rilevamento testo AI con Copyleaks')
ON CONFLICT (code) DO NOTHING;

-- Associa il permesso detect al ruolo admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'admin' AND p.code = 'detect'
ON CONFLICT DO NOTHING;
