-- ============================================================================
-- STYLEFORGE - THESIS GENERATION SCHEMA
-- Eseguire questo script sul database Supabase di produzione
-- Data: 2026-01-27
-- ============================================================================

-- ============================================================================
-- 1. ENUM TYPE per lo stato della tesi
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE thesis_status AS ENUM (
        'draft',
        'chapters_pending',
        'chapters_confirmed',
        'sections_pending',
        'sections_confirmed',
        'generating',
        'completed',
        'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Aggiungi 'thesis_generation' al tipo job_type esistente (se non già presente)
DO $$ BEGIN
    ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'thesis_generation';
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- 2. LOOKUP TABLES
-- ============================================================================

-- Stili di scrittura
CREATE TABLE IF NOT EXISTS writing_styles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Livelli di profondità del contenuto
CREATE TABLE IF NOT EXISTS content_depth_levels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    detail_multiplier DECIMAL(3,2) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Livelli di conoscenza del pubblico
CREATE TABLE IF NOT EXISTS audience_knowledge_levels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dimensioni del pubblico
CREATE TABLE IF NOT EXISTS audience_sizes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settori/industrie
CREATE TABLE IF NOT EXISTS industries (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    keywords TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Destinatari target
CREATE TABLE IF NOT EXISTS target_audiences (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. TABELLA PRINCIPALE TESI
-- ============================================================================

CREATE TABLE IF NOT EXISTS theses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,

    -- Parametri di base
    title VARCHAR(500) NOT NULL,
    description TEXT,
    key_topics TEXT[],

    -- Parametri di generazione
    writing_style_id INTEGER REFERENCES writing_styles(id),
    content_depth_id INTEGER REFERENCES content_depth_levels(id),
    num_chapters INTEGER DEFAULT 5,
    sections_per_chapter INTEGER DEFAULT 3,
    words_per_section INTEGER DEFAULT 5000,

    -- Caratteristiche pubblico
    knowledge_level_id INTEGER REFERENCES audience_knowledge_levels(id),
    audience_size_id INTEGER REFERENCES audience_sizes(id),
    industry_id INTEGER REFERENCES industries(id),
    target_audience_id INTEGER REFERENCES target_audiences(id),

    -- Struttura generata (JSON)
    chapters_structure JSONB,

    -- Contenuto generato
    generated_content TEXT,

    -- Stato e metadati
    status thesis_status DEFAULT 'draft',
    current_phase INTEGER DEFAULT 0,
    generation_progress INTEGER DEFAULT 0,
    total_words_generated INTEGER DEFAULT 0,

    -- File allegati
    attachments_path TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================================
-- 4. TABELLA ALLEGATI
-- ============================================================================

CREATE TABLE IF NOT EXISTS thesis_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    extracted_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. TABELLA JOB DI GENERAZIONE
-- ============================================================================

CREATE TABLE IF NOT EXISTS thesis_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================================
-- 6. INDICI
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_theses_user_id ON theses(user_id);
CREATE INDEX IF NOT EXISTS idx_theses_status ON theses(status);
CREATE INDEX IF NOT EXISTS idx_theses_created_at ON theses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_attachments_thesis_id ON thesis_attachments(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_generation_jobs_thesis_id ON thesis_generation_jobs(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_generation_jobs_status ON thesis_generation_jobs(status);

-- ============================================================================
-- 7. TRIGGER per updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_thesis_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_thesis_updated_at ON theses;
CREATE TRIGGER trigger_thesis_updated_at
    BEFORE UPDATE ON theses
    FOR EACH ROW
    EXECUTE FUNCTION update_thesis_updated_at();

-- ============================================================================
-- 8. DATI INIZIALI - WRITING STYLES
-- ============================================================================

INSERT INTO writing_styles (code, name, description, prompt_hint, sort_order) VALUES
('academic', 'Accademico', 'Stile formale e rigoroso, adatto per tesi universitarie e paper scientifici', 'Usa un linguaggio formale, cita fonti quando appropriato, mantieni oggettività e rigore metodologico', 1),
('professional', 'Professionale', 'Stile chiaro e diretto, adatto per report aziendali e documenti di lavoro', 'Usa un tono professionale ma accessibile, focus su chiarezza e praticità', 2),
('technical', 'Tecnico', 'Stile preciso con terminologia specialistica', 'Usa terminologia tecnica appropriata, includi dettagli implementativi, sii preciso nelle descrizioni', 3),
('journalistic', 'Giornalistico', 'Stile coinvolgente e narrativo', 'Usa uno stile narrativo coinvolgente, includi esempi concreti, mantieni interesse del lettore', 4),
('educational', 'Didattico', 'Stile chiaro e pedagogico, adatto per materiali formativi', 'Spiega concetti in modo progressivo, usa esempi, anticipa domande del lettore', 5),
('creative', 'Creativo', 'Stile espressivo e originale', 'Usa metafore e analogie, sii originale nelle espressioni, mantieni comunque chiarezza', 6)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_hint = EXCLUDED.prompt_hint,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 9. DATI INIZIALI - CONTENT DEPTH LEVELS
-- ============================================================================

INSERT INTO content_depth_levels (code, name, description, detail_multiplier, sort_order) VALUES
('overview', 'Panoramica', 'Trattazione generale degli argomenti, ideale per introduzioni', 0.7, 1),
('intermediate', 'Intermedio', 'Livello di dettaglio bilanciato, adatto alla maggior parte dei casi', 1.0, 2),
('detailed', 'Dettagliato', 'Approfondimento significativo con analisi estese', 1.3, 3),
('expert', 'Esperto', 'Massimo livello di dettaglio e complessità', 1.5, 4)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    detail_multiplier = EXCLUDED.detail_multiplier,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 10. DATI INIZIALI - AUDIENCE KNOWLEDGE LEVELS
-- ============================================================================

INSERT INTO audience_knowledge_levels (code, name, description, prompt_hint, sort_order) VALUES
('beginner', 'Principiante', 'Pubblico senza conoscenze pregresse sull''argomento', 'Spiega tutti i concetti base, evita jargon, usa analogie semplici', 1),
('intermediate', 'Intermedio', 'Pubblico con conoscenze di base', 'Puoi assumere conoscenze fondamentali, spiega concetti avanzati', 2),
('advanced', 'Avanzato', 'Pubblico con buona preparazione', 'Puoi usare terminologia tecnica, focus su aspetti avanzati', 3),
('expert', 'Esperto', 'Pubblico di specialisti del settore', 'Usa linguaggio specialistico, approfondisci aspetti tecnici complessi', 4)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_hint = EXCLUDED.prompt_hint,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 11. DATI INIZIALI - AUDIENCE SIZES
-- ============================================================================

INSERT INTO audience_sizes (code, name, description, sort_order) VALUES
('individual', 'Individuale', 'Documento per uso personale o singolo destinatario', 1),
('small_group', 'Piccolo Gruppo', 'Team di lavoro, commissione esame (5-20 persone)', 2),
('medium', 'Medio', 'Dipartimento, classe, conferenza (20-100 persone)', 3),
('large', 'Ampio', 'Organizzazione, pubblico generale (100+ persone)', 4)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 12. DATI INIZIALI - INDUSTRIES
-- ============================================================================

INSERT INTO industries (code, name, description, keywords, sort_order) VALUES
('technology', 'Tecnologia', 'Informatica, software, hardware, digitale', ARRAY['software', 'IT', 'digitale', 'tech', 'informatica'], 1),
('healthcare', 'Sanità', 'Medicina, farmaceutica, salute pubblica', ARRAY['medicina', 'salute', 'healthcare', 'farmaci'], 2),
('finance', 'Finanza', 'Banche, investimenti, assicurazioni', ARRAY['banca', 'investimenti', 'fintech', 'economia'], 3),
('education', 'Istruzione', 'Scuole, università, formazione', ARRAY['scuola', 'università', 'formazione', 'didattica'], 4),
('engineering', 'Ingegneria', 'Meccanica, civile, elettronica', ARRAY['ingegneria', 'costruzioni', 'meccanica'], 5),
('law', 'Giurisprudenza', 'Legale, normativo, compliance', ARRAY['legge', 'diritto', 'normativa', 'giuridico'], 6),
('marketing', 'Marketing', 'Comunicazione, pubblicità, brand', ARRAY['marketing', 'pubblicità', 'brand', 'comunicazione'], 7),
('science', 'Scienze', 'Ricerca scientifica, laboratorio', ARRAY['ricerca', 'scienza', 'laboratorio', 'sperimentale'], 8),
('humanities', 'Scienze Umane', 'Filosofia, storia, letteratura, arte', ARRAY['filosofia', 'storia', 'letteratura', 'arte'], 9),
('business', 'Business', 'Management, strategia, organizzazione', ARRAY['management', 'strategia', 'azienda', 'business'], 10),
('environment', 'Ambiente', 'Ecologia, sostenibilità, energie rinnovabili', ARRAY['ambiente', 'sostenibilità', 'green', 'ecologia'], 11),
('other', 'Altro', 'Altri settori non specificati', ARRAY[]::TEXT[], 99)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    keywords = EXCLUDED.keywords,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 13. DATI INIZIALI - TARGET AUDIENCES
-- ============================================================================

INSERT INTO target_audiences (code, name, description, prompt_hint, sort_order) VALUES
('thesis_committee', 'Commissione di Laurea', 'Professori e relatori universitari', 'Mantieni rigore accademico, dimostra padronanza metodologica, cita letteratura rilevante', 1),
('professors', 'Docenti', 'Professori e ricercatori', 'Usa linguaggio accademico, approfondisci aspetti teorici', 2),
('students', 'Studenti', 'Studenti universitari o di master', 'Bilancia teoria e pratica, includi esempi concreti', 3),
('executives', 'Dirigenti', 'Manager e C-level', 'Focus su implicazioni strategiche e business value, sii conciso', 4),
('technical_team', 'Team Tecnico', 'Sviluppatori, ingegneri, tecnici', 'Includi dettagli implementativi, usa terminologia tecnica', 5),
('general_public', 'Pubblico Generale', 'Lettori non specializzati', 'Evita jargon, spiega concetti, usa esempi quotidiani', 6),
('investors', 'Investitori', 'Venture capital, business angels', 'Focus su opportunità, mercato, scalabilità', 7),
('clients', 'Clienti', 'Clienti aziendali o consumatori', 'Focus su benefici e valore, linguaggio accessibile', 8)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_hint = EXCLUDED.prompt_hint,
    sort_order = EXCLUDED.sort_order;

-- ============================================================================
-- 14. ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Abilita RLS sulle tabelle principali
ALTER TABLE theses ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis_generation_jobs ENABLE ROW LEVEL SECURITY;

-- Policy per theses: gli utenti possono vedere solo le proprie tesi
DROP POLICY IF EXISTS theses_user_policy ON theses;
CREATE POLICY theses_user_policy ON theses
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Policy per thesis_attachments: accesso tramite thesis ownership
DROP POLICY IF EXISTS thesis_attachments_user_policy ON thesis_attachments;
CREATE POLICY thesis_attachments_user_policy ON thesis_attachments
    FOR ALL
    USING (thesis_id IN (SELECT id FROM theses WHERE user_id = auth.uid()))
    WITH CHECK (thesis_id IN (SELECT id FROM theses WHERE user_id = auth.uid()));

-- Policy per thesis_generation_jobs: accesso tramite thesis ownership
DROP POLICY IF EXISTS thesis_generation_jobs_user_policy ON thesis_generation_jobs;
CREATE POLICY thesis_generation_jobs_user_policy ON thesis_generation_jobs
    FOR ALL
    USING (thesis_id IN (SELECT id FROM theses WHERE user_id = auth.uid()))
    WITH CHECK (thesis_id IN (SELECT id FROM theses WHERE user_id = auth.uid()));

-- Le lookup tables sono pubbliche in lettura
ALTER TABLE writing_styles ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_depth_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE audience_knowledge_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE audience_sizes ENABLE ROW LEVEL SECURITY;
ALTER TABLE industries ENABLE ROW LEVEL SECURITY;
ALTER TABLE target_audiences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS writing_styles_read_policy ON writing_styles;
CREATE POLICY writing_styles_read_policy ON writing_styles FOR SELECT USING (true);

DROP POLICY IF EXISTS content_depth_levels_read_policy ON content_depth_levels;
CREATE POLICY content_depth_levels_read_policy ON content_depth_levels FOR SELECT USING (true);

DROP POLICY IF EXISTS audience_knowledge_levels_read_policy ON audience_knowledge_levels;
CREATE POLICY audience_knowledge_levels_read_policy ON audience_knowledge_levels FOR SELECT USING (true);

DROP POLICY IF EXISTS audience_sizes_read_policy ON audience_sizes;
CREATE POLICY audience_sizes_read_policy ON audience_sizes FOR SELECT USING (true);

DROP POLICY IF EXISTS industries_read_policy ON industries;
CREATE POLICY industries_read_policy ON industries FOR SELECT USING (true);

DROP POLICY IF EXISTS target_audiences_read_policy ON target_audiences;
CREATE POLICY target_audiences_read_policy ON target_audiences FOR SELECT USING (true);

-- ============================================================================
-- FINE SCRIPT
-- ============================================================================

-- Verifica finale
DO $$
BEGIN
    RAISE NOTICE '✅ Schema thesis creato con successo!';
    RAISE NOTICE '📊 Tabelle create: theses, thesis_attachments, thesis_generation_jobs';
    RAISE NOTICE '📚 Lookup tables: writing_styles, content_depth_levels, audience_knowledge_levels, audience_sizes, industries, target_audiences';
    RAISE NOTICE '🔐 Row Level Security configurato';
END $$;
