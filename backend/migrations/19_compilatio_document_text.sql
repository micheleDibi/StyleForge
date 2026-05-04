-- Migration 19: aggiunge la colonna document_text alle scansioni Compilatio
--
-- Serve a permettere la generazione del report StyleForge-branded con la sezione
-- "Punti di interesse" (testo originale evidenziato). Le scansioni precedenti a
-- questa migration non avranno il testo salvato e nei loro report la sezione
-- POI verra' omessa (con avviso nel report).
--
-- Idempotente.

BEGIN;

ALTER TABLE compilatio_scans
    ADD COLUMN IF NOT EXISTS document_text TEXT NULL;

COMMIT;
