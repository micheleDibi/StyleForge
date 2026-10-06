-- ============================================================================
-- 29: Addebito crediti tesi PER STEP (quote fisse, somma 1000) + idempotenza
-- ============================================================================
-- Si passa dal vecchio addebito flat (1000 alla creazione) a un addebito per
-- step del wizard: Capitoli (150) + Sezioni (150) + Contenuto (700) = 1000.
-- Questi flag evitano doppi addebiti su rigenerazioni/retry e vengono azzerati
-- in caso di rimborso quando uno step fallisce.
--   chapters_charged / sections_charged / content_charged
-- Le tesi esistenti restano com'erano: quelle flat hanno credits_charged=TRUE
-- (già pagate) e questi flag a FALSE non vengono mai usati.
-- Idempotente. Tabella theses: nessun lock pesante (solo ADD COLUMN).
-- ============================================================================

ALTER TABLE theses ADD COLUMN IF NOT EXISTS chapters_charged BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE theses ADD COLUMN IF NOT EXISTS sections_charged BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE theses ADD COLUMN IF NOT EXISTS content_charged  BOOLEAN NOT NULL DEFAULT FALSE;
-- Analisi documenti/paper (ingest Knowledge Base): addebitata una sola volta.
ALTER TABLE theses ADD COLUMN IF NOT EXISTS wiki_charged     BOOLEAN NOT NULL DEFAULT FALSE;
