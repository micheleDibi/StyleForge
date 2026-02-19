-- ============================================================================
-- 10: Permesso 'manage_templates' per gestione template esportazione
-- ============================================================================

INSERT INTO permissions (code, name, description)
VALUES ('manage_templates', 'Gestione Template', 'Creazione e modifica template esportazione tesi')
ON CONFLICT (code) DO NOTHING;

-- Associa il permesso manage_templates al ruolo admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'admin' AND p.code = 'manage_templates'
ON CONFLICT DO NOTHING;
