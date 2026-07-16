-- ============================================================================
-- 24: indici compositi per le liste della dashboard (user_id + created_at DESC)
-- ============================================================================
-- Le query della dashboard sono del tipo:
--   SELECT ... FROM jobs   WHERE user_id = ? ORDER BY created_at DESC;
--   SELECT ... FROM theses WHERE user_id = ? ORDER BY created_at DESC;
-- Esistono già gli indici su user_id (idx_jobs_user_id / idx_theses_user_id),
-- ma con l'indice composito (user_id, created_at DESC) il filtro E l'ordinamento
-- sono soddisfatti dall'indice (niente sort separato), utile al crescere dei dati.
-- Idempotente.
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_jobs_user_created   ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_theses_user_created ON theses(user_id, created_at DESC);
