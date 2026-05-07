-- ============================================================================
-- 21: Integrazione "LLM Wiki" (second-brain) nel flusso di generazione tesi
-- ============================================================================
-- Aggiunge:
--   * enum thesis_wiki_status (none → ingesting → ingested → linting → linted → failed)
--   * 6 colonne su theses per tracciare il wiki di ogni tesi
--   * 2 nuovi valori al pre-esistente enum job_type (wiki_ingest, wiki_lint)
--
-- Idempotente: tutte le ALTER usano IF NOT EXISTS / ADD VALUE IF NOT EXISTS.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Enum stato wiki di una tesi
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE thesis_wiki_status AS ENUM (
        'none',         -- wiki mai avviato
        'ingesting',    -- ingest in corso
        'ingested',     -- ingest completato (lint non ancora avviato)
        'linting',      -- lint in corso
        'linted',       -- lint completato (stato "pronto" per generazione)
        'failed'        -- errore irrecuperabile (l'utente puo' rilanciare)
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Colonne su theses
-- ----------------------------------------------------------------------------
ALTER TABLE theses
    ADD COLUMN IF NOT EXISTS restrict_to_sources BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS wiki_status         thesis_wiki_status NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS wiki_path           TEXT,
    ADD COLUMN IF NOT EXISTS wiki_lint_report    JSONB,
    ADD COLUMN IF NOT EXISTS wiki_ingested_at    TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS wiki_linted_at      TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_theses_wiki_status ON theses(wiki_status);

-- ----------------------------------------------------------------------------
-- 3. Estendi enum job_type con i 2 nuovi tipi
--    (job_type e' ENUM in db_models.py:21 -> serve ALTER TYPE)
-- ----------------------------------------------------------------------------
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'wiki_ingest';
ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'wiki_lint';
