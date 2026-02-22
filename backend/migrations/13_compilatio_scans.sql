-- ============================================================================
-- 13: Tabella scansioni Compilatio + ENUM job_type aggiornato
-- ============================================================================

-- Aggiungere 'compilatio_scan' al ENUM job_type
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'compilatio_scan';

-- Tabella per salvare le scansioni Compilatio
CREATE TABLE IF NOT EXISTS compilatio_scans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(50) NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Identificativi documento su Compilatio
    compilatio_doc_id VARCHAR(255),
    compilatio_analysis_id VARCHAR(255),
    compilatio_folder_id VARCHAR(255),

    -- Info documento
    document_filename VARCHAR(500) NOT NULL,
    document_text_hash VARCHAR(64),  -- SHA-256 del testo per dedup
    word_count INTEGER DEFAULT 0,

    -- Risultati analisi
    global_score_percent NUMERIC(5,2) DEFAULT 0,
    similarity_percent NUMERIC(5,2) DEFAULT 0,
    exact_percent NUMERIC(5,2) DEFAULT 0,
    ai_generated_percent NUMERIC(5,2) DEFAULT 0,
    same_meaning_percent NUMERIC(5,2) DEFAULT 0,
    translation_percent NUMERIC(5,2) DEFAULT 0,
    quotation_percent NUMERIC(5,2) DEFAULT 0,
    suspicious_fingerprint_percent NUMERIC(5,2) DEFAULT 0,
    points_of_interest INTEGER DEFAULT 0,

    -- Report e dettagli
    report_pdf_path TEXT,
    scan_details JSONB,  -- JSON completo dei risultati e POIs

    -- Sorgente della scansione (da quale pagina e' stata avviata)
    source_type VARCHAR(50),  -- 'generate', 'humanize', 'thesis', 'manual'
    source_job_id VARCHAR(50),  -- job_id del contenuto originale (opzionale)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_compilatio_scans_user_id ON compilatio_scans(user_id);
CREATE INDEX IF NOT EXISTS idx_compilatio_scans_job_id ON compilatio_scans(job_id);
CREATE INDEX IF NOT EXISTS idx_compilatio_scans_text_hash ON compilatio_scans(document_text_hash);
CREATE INDEX IF NOT EXISTS idx_compilatio_scans_created_at ON compilatio_scans(created_at DESC);

-- Permesso compilatio_scan per admin
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, 'compilatio_scan'
FROM roles r
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;
