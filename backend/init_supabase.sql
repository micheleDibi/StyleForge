-- ============================================
-- StyleForge Database Schema for Supabase
-- ============================================
-- Script di inizializzazione database PostgreSQL
-- Esegui questo script nel SQL Editor di Supabase
--
-- ISTRUZIONI SETUP SUPABASE:
-- ============================================
-- 1. Crea un nuovo progetto su https://supabase.com
-- 2. Una volta creato, vai su "SQL Editor" nel menu laterale
-- 3. Clicca "New query"
-- 4. Copia e incolla TUTTO questo script
-- 5. Clicca "Run" (o premi Ctrl/Cmd + Enter)
-- 6. Verifica che non ci siano errori nell'output
--
-- DOPO L'ESECUZIONE:
-- ============================================
-- Vai su Settings -> Database -> Connection string
-- Copia la stringa di connessione "URI" (Session mode, porta 5432)
-- Incollala nel file .env come DATABASE_URL
-- Sostituisci [YOUR-PASSWORD] con la password del database
--
-- ============================================

-- Enable UUID extension (se non già abilitato)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- ENUM TYPES
-- ============================================

-- JobStatus Enum
CREATE TYPE job_status AS ENUM (
    'pending',
    'training',
    'ready',
    'generating',
    'completed',
    'failed'
);

-- JobType Enum
CREATE TYPE job_type AS ENUM (
    'training',
    'generation',
    'humanization'
);

-- ============================================
-- TABLES
-- ============================================

-- Tabella USERS
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Tabella SESSIONS
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(50) NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255),
    is_trained BOOLEAN DEFAULT FALSE,
    conversation_history TEXT,
    pdf_path VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabella JOBS
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(50) NOT NULL UNIQUE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type job_type NOT NULL,
    status job_status DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Tabella REFRESH_TOKENS
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token VARCHAR(500) NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked BOOLEAN DEFAULT FALSE
);

-- ============================================
-- INDEXES
-- ============================================

-- Users indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Sessions indexes
CREATE INDEX idx_sessions_session_id ON sessions(session_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- Jobs indexes
CREATE INDEX idx_jobs_job_id ON jobs(job_id);
CREATE INDEX idx_jobs_session_id ON jobs(session_id);
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);

-- Refresh tokens indexes
CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- ============================================
-- TRIGGER FUNCTIONS per updated_at
-- ============================================

-- Funzione per aggiornare automaticamente updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger per users.updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger per sessions.last_activity
CREATE OR REPLACE FUNCTION update_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_sessions_last_activity
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_session_activity();

-- Trigger per jobs.updated_at
CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================
-- Nota: Abilita RLS solo se vuoi gestire i permessi tramite Supabase Auth
-- Per ora lo lasciamo commentato, gestiamo la sicurezza a livello applicativo

-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- Esempi di policy (decommentare e personalizzare se necessario):
-- CREATE POLICY "Users can view their own data" ON users
--     FOR SELECT USING (auth.uid() = id);
--
-- CREATE POLICY "Users can update their own data" ON users
--     FOR UPDATE USING (auth.uid() = id);

-- ============================================
-- DATI INIZIALI (opzionale)
-- ============================================

-- Puoi aggiungere qui un utente admin di test, ad esempio:
-- INSERT INTO users (email, username, hashed_password, full_name, is_admin)
-- VALUES (
--     'admin@styleforge.com',
--     'admin',
--     '$2b$12$...',  -- Genera l'hash della password con bcrypt
--     'Administrator',
--     TRUE
-- );

-- ============================================
-- THESIS GENERATION TABLES
-- ============================================
-- Tabelle per la funzionalità "Generazione Tesi/Relazione"

-- Estendi job_type enum per includere thesis_generation
-- NOTA: Esegui questo comando separatamente se le tabelle esistono già
-- ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'thesis_generation';

-- ============================================
-- LOOKUP TABLES
-- ============================================

-- Stili di scrittura
CREATE TABLE IF NOT EXISTS writing_styles (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dati iniziali stili di scrittura
INSERT INTO writing_styles (code, name, description, prompt_hint, sort_order) VALUES
('academic', 'Accademico', 'Stile formale con citazioni, terminologia tecnica e struttura rigorosa', 'Usa un registro formale accademico con terminologia specialistica, citazioni e riferimenti bibliografici appropriati', 1),
('professional', 'Professionale', 'Chiaro, conciso e orientato ai risultati', 'Scrivi in modo professionale e orientato agli obiettivi, con focus su chiarezza e concisione', 2),
('journalistic', 'Giornalistico', 'Narrativo, coinvolgente e accessibile al grande pubblico', 'Usa uno stile narrativo coinvolgente e accessibile, con aperture efficaci e struttura a piramide rovesciata', 3),
('technical', 'Tecnico', 'Preciso, dettagliato e procedurale', 'Sii preciso e dettagliato, usa terminologia tecnica appropriata e struttura le informazioni in modo procedurale', 4),
('educational', 'Didattico', 'Chiaro, con esempi pratici e progressione logica', 'Spiega con chiarezza usando esempi concreti, analogie e una progressione logica dal semplice al complesso', 5),
('narrative', 'Narrativo', 'Storytelling con elementi descrittivi e coinvolgenti', 'Usa tecniche narrative per coinvolgere il lettore, con descrizioni vivide e un filo conduttore chiaro', 6)
ON CONFLICT (code) DO NOTHING;

-- Livelli di profondità contenuto
CREATE TABLE IF NOT EXISTS content_depth_levels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    detail_multiplier DECIMAL(3,2) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO content_depth_levels (code, name, description, detail_multiplier, sort_order) VALUES
('overview', 'Panoramica', 'Visione generale senza entrare nei dettagli tecnici, ideale per executive summary', 0.7, 1),
('intermediate', 'Intermedio', 'Bilanciato tra generalità e dettaglio, adatto alla maggior parte dei contesti', 1.0, 2),
('detailed', 'Dettagliato', 'Approfondito con esempi, spiegazioni estese e analisi critica', 1.3, 3),
('expert', 'Esperto', 'Massimo dettaglio per pubblico altamente specializzato, con riferimenti tecnici avanzati', 1.5, 4)
ON CONFLICT (code) DO NOTHING;

-- Livelli di conoscenza del pubblico
CREATE TABLE IF NOT EXISTS audience_knowledge_levels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO audience_knowledge_levels (code, name, description, prompt_hint, sort_order) VALUES
('beginner', 'Principiante', 'Nessuna conoscenza pregressa del tema', 'Spiega ogni concetto dalla base, evita termini tecnici non definiti, usa analogie con la vita quotidiana', 1),
('intermediate', 'Intermedio', 'Conoscenze di base del settore', 'Assumi familiarità con i concetti fondamentali, spiega quelli avanzati e le connessioni tra argomenti', 2),
('advanced', 'Avanzato', 'Buona padronanza del tema e della terminologia', 'Usa terminologia specialistica, focus su aspetti avanzati, approfondimenti critici e confronti', 3),
('expert', 'Esperto', 'Profonda conoscenza del settore e delle sue sfumature', 'Linguaggio tecnico completo, discussione critica delle fonti, analisi delle controversie nel campo', 4)
ON CONFLICT (code) DO NOTHING;

-- Dimensioni del pubblico
CREATE TABLE IF NOT EXISTS audience_sizes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO audience_sizes (code, name, description, sort_order) VALUES
('individual', 'Individuale', 'Singola persona (tesi di laurea, relazione personale, progetto individuale)', 1),
('small_group', 'Piccolo Gruppo', '2-10 persone (team di lavoro, classe ristretta, commissione)', 2),
('medium', 'Medio', '10-50 persone (dipartimento, corso universitario, seminario)', 3),
('large', 'Grande', '50-200 persone (conferenza, workshop, evento aziendale)', 4),
('mass', 'Di Massa', '200+ persone (pubblicazione, evento pubblico, distribuzione online)', 5)
ON CONFLICT (code) DO NOTHING;

-- Industrie/Settori
CREATE TABLE IF NOT EXISTS industries (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    keywords TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO industries (code, name, description, keywords, sort_order) VALUES
('academic', 'Accademico/Universitario', 'Contesto universitario, ricerca scientifica, pubblicazioni', ARRAY['università', 'ricerca', 'tesi', 'pubblicazione', 'paper'], 1),
('healthcare', 'Sanità', 'Settore medico, sanitario e farmaceutico', ARRAY['medicina', 'salute', 'ospedale', 'paziente', 'farmaco'], 2),
('technology', 'Tecnologia', 'IT, software, innovazione digitale', ARRAY['software', 'digitale', 'innovazione', 'tech', 'startup'], 3),
('finance', 'Finanza', 'Banche, investimenti, economia e mercati', ARRAY['banca', 'investimento', 'mercato', 'economia', 'trading'], 4),
('legal', 'Legale', 'Diritto, consulenza legale, normativa', ARRAY['legge', 'diritto', 'contratto', 'normativa', 'giurisprudenza'], 5),
('education', 'Istruzione', 'Scuole, formazione, didattica', ARRAY['scuola', 'formazione', 'didattica', 'apprendimento', 'insegnamento'], 6),
('engineering', 'Ingegneria', 'Progettazione, costruzione, infrastrutture', ARRAY['progetto', 'costruzione', 'sistema', 'infrastruttura', 'impianto'], 7),
('marketing', 'Marketing e Comunicazione', 'Branding, vendite, comunicazione aziendale', ARRAY['brand', 'mercato', 'cliente', 'promozione', 'advertising'], 8),
('science', 'Scienze Naturali', 'Biologia, chimica, fisica, ambiente', ARRAY['scienza', 'ricerca', 'laboratorio', 'esperimento', 'ambiente'], 9),
('humanities', 'Scienze Umane', 'Filosofia, storia, letteratura, arte', ARRAY['filosofia', 'storia', 'letteratura', 'arte', 'cultura'], 10),
('social_sciences', 'Scienze Sociali', 'Sociologia, psicologia, antropologia', ARRAY['società', 'psicologia', 'comportamento', 'comunità', 'ricerca sociale'], 11),
('other', 'Altro', 'Altri settori non specificati', ARRAY[], 99)
ON CONFLICT (code) DO NOTHING;

-- Destinatari
CREATE TABLE IF NOT EXISTS target_audiences (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_hint TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO target_audiences (code, name, description, prompt_hint, sort_order) VALUES
('professor', 'Professore/Relatore', 'Docente universitario o supervisore che valuterà il lavoro', 'Scrivi per un lettore esperto che valuterà criticamente il contenuto, la metodologia e le conclusioni', 1),
('committee', 'Commissione', 'Commissione di valutazione multidisciplinare', 'Scrivi per una commissione di esperti con background diversi, bilancia profondità e accessibilità', 2),
('colleagues', 'Colleghi', 'Pari livello professionale nello stesso settore', 'Scrivi per colleghi che condividono il tuo background, puoi assumere conoscenze di base condivise', 3),
('management', 'Management', 'Dirigenti e decisori aziendali', 'Focus su impatto, risultati e raccomandazioni pratiche, executive summary chiaro', 4),
('clients', 'Clienti', 'Clienti o stakeholder esterni', 'Bilancia tecnicità e accessibilità, enfatizza benefici e valore pratico', 5),
('students', 'Studenti', 'Studenti e apprendenti del settore', 'Spiega chiaramente con esempi pratici, definisci i termini tecnici, struttura didattica', 6),
('general', 'Pubblico Generale', 'Lettori non specializzati', 'Rendi accessibile a chiunque senza background specifico, evita gergo tecnico non spiegato', 7),
('researchers', 'Ricercatori', 'Altri ricercatori nel campo', 'Linguaggio tecnico appropriato, citazioni rigorose, discussione critica della letteratura', 8)
ON CONFLICT (code) DO NOTHING;

-- ============================================
-- TABELLA PRINCIPALE THESES
-- ============================================

-- Stati della tesi
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

-- Tabella principale per le tesi/relazioni
CREATE TABLE IF NOT EXISTS theses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,

    -- Parametri di base
    title VARCHAR(500) NOT NULL,
    description TEXT,
    key_topics TEXT[],

    -- Parametri di generazione
    writing_style_id INTEGER REFERENCES writing_styles(id),
    content_depth_id INTEGER REFERENCES content_depth_levels(id),
    num_chapters INTEGER DEFAULT 5 CHECK (num_chapters >= 1 AND num_chapters <= 20),
    sections_per_chapter INTEGER DEFAULT 3 CHECK (sections_per_chapter >= 1 AND sections_per_chapter <= 10),
    words_per_section INTEGER DEFAULT 5000 CHECK (words_per_section >= 500 AND words_per_section <= 20000),

    -- Caratteristiche pubblico
    knowledge_level_id INTEGER REFERENCES audience_knowledge_levels(id),
    audience_size_id INTEGER REFERENCES audience_sizes(id),
    industry_id INTEGER REFERENCES industries(id),
    target_audience_id INTEGER REFERENCES target_audiences(id),

    -- Provider AI (openai o claude)
    ai_provider VARCHAR(20) DEFAULT 'openai',

    -- Struttura generata (JSON)
    chapters_structure JSONB,

    -- Contenuto generato
    generated_content TEXT,

    -- Stato e metadati
    status thesis_status DEFAULT 'draft',
    current_phase INTEGER DEFAULT 0,
    generation_progress INTEGER DEFAULT 0 CHECK (generation_progress >= 0 AND generation_progress <= 100),
    total_words_generated INTEGER DEFAULT 0,

    -- File allegati
    attachments_path TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Tabella per gli allegati
CREATE TABLE IF NOT EXISTS thesis_attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    extracted_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabella per i job di generazione tesi
CREATE TABLE IF NOT EXISTS thesis_generation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- ============================================
-- INDEXES per Thesis Tables
-- ============================================

CREATE INDEX IF NOT EXISTS idx_theses_user_id ON theses(user_id);
CREATE INDEX IF NOT EXISTS idx_theses_status ON theses(status);
CREATE INDEX IF NOT EXISTS idx_theses_created_at ON theses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_attachments_thesis_id ON thesis_attachments(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_generation_jobs_thesis_id ON thesis_generation_jobs(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_generation_jobs_job_id ON thesis_generation_jobs(job_id);

-- Trigger per theses.updated_at
CREATE TRIGGER update_theses_updated_at
    BEFORE UPDATE ON theses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VERIFICHE
-- ============================================

-- Verifica che tutte le tabelle siano state create
DO $$
BEGIN
    RAISE NOTICE 'Schema creato con successo!';
    RAISE NOTICE 'Tabelle create: users, sessions, jobs, refresh_tokens';
    RAISE NOTICE 'Tabelle thesis: theses, thesis_attachments, thesis_generation_jobs';
    RAISE NOTICE 'Tabelle lookup: writing_styles, content_depth_levels, audience_knowledge_levels, audience_sizes, industries, target_audiences';
    RAISE NOTICE 'Enum types: job_status, job_type, thesis_status';
END $$;


-- ============================================
-- MIGRATIONS (per database esistenti)
-- ============================================
-- Esegui questo blocco se hai un database esistente e devi aggiungere nuove colonne

-- Migration: Aggiungi colonna ai_provider alla tabella theses
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'theses' AND column_name = 'ai_provider') THEN
        ALTER TABLE theses ADD COLUMN ai_provider VARCHAR(20) DEFAULT 'openai';
        RAISE NOTICE 'Colonna ai_provider aggiunta alla tabella theses';
    END IF;
END $$;
