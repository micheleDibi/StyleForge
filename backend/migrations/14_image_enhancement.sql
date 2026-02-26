-- ============================================================================
-- 14: Image Enhancement - tabella + ENUM aggiornati
-- ============================================================================

-- Aggiungere 'image_enhancement' al ENUM job_type
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'image_enhancement';

-- Aggiungere 'enhancing' al ENUM job_status
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'enhancing';

-- Tabella per salvare i record di image enhancement
CREATE TABLE IF NOT EXISTS image_enhancements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(50) NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Info immagine originale
    original_filename VARCHAR(500) NOT NULL,
    original_path TEXT NOT NULL,
    original_width INTEGER,
    original_height INTEGER,
    original_size_bytes BIGINT,

    -- Info immagine migliorata
    enhanced_path TEXT,
    enhanced_width INTEGER,
    enhanced_height INTEGER,
    enhanced_size_bytes BIGINT,

    -- Parametri enhancement
    enhancement_type VARCHAR(50) NOT NULL,  -- 'basic', 'ai_analysis', 'upscale', 'color_correction'
    enhancement_params JSONB,               -- Parametri dettagliati scelti
    ai_analysis_result JSONB,               -- Risultato analisi Claude Vision (se usato)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_image_enhancements_user_id ON image_enhancements(user_id);
CREATE INDEX IF NOT EXISTS idx_image_enhancements_job_id ON image_enhancements(job_id);
CREATE INDEX IF NOT EXISTS idx_image_enhancements_created_at ON image_enhancements(created_at DESC);

-- Permesso image_enhance per ruoli admin e user
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, 'image_enhance'
FROM roles r
WHERE r.name IN ('admin', 'user')
ON CONFLICT (role_id, permission_code) DO NOTHING;
