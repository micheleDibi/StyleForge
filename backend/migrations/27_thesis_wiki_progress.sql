-- ============================================================================
-- 27: Progresso granulare dell'ingest wiki (per UI: %, fase, documento corrente)
-- ============================================================================
-- Aggiunge theses.wiki_progress (JSONB): payload aggiornato dal task di ingest
--   { phase, percent, message, files[], started_at, updated_at }
-- Letto in polling da GET /thesis/{id}/wiki/status per mostrare barra di
-- avanzamento, tempistiche e cosa sta elaborando il sistema.
-- Idempotente.
-- ============================================================================

ALTER TABLE theses ADD COLUMN IF NOT EXISTS wiki_progress JSONB;
