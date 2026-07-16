-- ============================================================================
-- 28: Copy marketing dei pacchetti crediti (nomi + descrizioni)
-- ============================================================================
-- Rinomina i 9 pacchetti per-ruolo (privato/distributore/rivenditore) con nomi
-- accattivanti e descrizioni professionali, UGUALI per taglio: il ruolo è già
-- implicito (ogni utente vede solo i propri 3 pacchetti), quindi sparisce il
-- vecchio "Pacchetto privato/distributore/rivenditore: N crediti".
--   100  crediti -> PARTENZA   (avvio: struttura + primi capitoli)
--   500  crediti -> SLANCIO    (buona parte della tesi; è il "PIÙ SCELTO")
--   1000 crediti -> TRAGUARDO  (tesi completa)
--
-- Match per NOME ESATTO dei record seminati dalla migrazione 23: NON tocca i
-- vecchi 'Starter'/'Standard'/'Plus' (disattivati, stesso entity_type/credits).
-- Idempotente: una volta rinominati, i match sui vecchi nomi diventano no-op.
-- credit_packages è una tabella piccola e "fredda": nessun rischio di lock.
--
-- Nota: i NOMI sono mostrati in MAIUSCOLO dalla card (CSS), qui restano in
-- forma leggibile per chiarezza lato admin.
-- ============================================================================

-- 100 crediti -> PARTENZA
UPDATE credit_packages
   SET name = 'Partenza',
       description = 'Per impostare la struttura e redigere i primi capitoli con metodo.',
       updated_at = NOW()
 WHERE name IN ('Privato 100', 'Distributore 100', 'Rivenditore 100');

-- 500 crediti -> SLANCIO
UPDATE credit_packages
   SET name = 'Slancio',
       description = 'Copre buona parte della tesi: il taglio scelto da chi cerca equilibrio.',
       updated_at = NOW()
 WHERE name IN ('Privato 500', 'Distributore 500', 'Rivenditore 500');

-- 1000 crediti -> TRAGUARDO
UPDATE credit_packages
   SET name = 'Traguardo',
       description = 'La tesi completa, dall''introduzione alle conclusioni, senza compromessi.',
       updated_at = NOW()
 WHERE name IN ('Privato 1000', 'Distributore 1000', 'Rivenditore 1000');
