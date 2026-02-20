-- Migration 12: Rendi session_id nullable su jobs (per Correzione Anti-AI senza sessione)
-- e aggiungi colonna name per nomi descrittivi dei job.

-- session_id nullable: consente job non associati a una sessione
ALTER TABLE jobs ALTER COLUMN session_id DROP NOT NULL;

-- name: nome descrittivo auto-generato o personalizzato dall'utente
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS name VARCHAR(255);
