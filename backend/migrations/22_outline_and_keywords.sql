-- ============================================================================
-- 22: Custom outline (indice fornito dall'utente) + endpoint keyword paper
-- ============================================================================
-- Aggiunge a `theses`:
--   * use_custom_outline BOOL: se TRUE, generate_chapters/sections bypassano
--     l'AI e popolano chapters_structure direttamente da custom_outline.
--   * custom_outline JSONB: struttura {"chapters":[{"title","brief_description",
--     "sections":[{"title","key_points":[]}]}]}.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS + DEFAULT FALSE => metadata-only change
-- in Postgres >= 11, sicuro anche su tabella popolata.
-- ============================================================================

ALTER TABLE theses
    ADD COLUMN IF NOT EXISTS use_custom_outline BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS custom_outline     JSONB;

CREATE INDEX IF NOT EXISTS idx_theses_use_custom_outline
    ON theses(use_custom_outline) WHERE use_custom_outline = TRUE;
