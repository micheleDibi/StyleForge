-- Migration 18: Rimuove le feature "Migliora immagine" e "Carosello / Post / Copertina"
--
-- Pulisce le tracce DB dei codici permesso 'enhance_image' e 'carousel_creator'
-- e le impostazioni di sistema dedicate alla feature carousel.
-- Idempotente.

BEGIN;

-- 1) Rimuovi assegnazioni di permesso a livello ruolo
DELETE FROM role_permissions
WHERE permission_code IN ('enhance_image', 'carousel_creator');

-- 2) Rimuovi override di permesso a livello utente
DELETE FROM user_permissions
WHERE permission_code IN ('enhance_image', 'carousel_creator');

-- 3) Rimuovi le impostazioni dedicate (carousel_prompts contiene i prompt AI personalizzati)
DELETE FROM system_settings
WHERE key = 'carousel_prompts';

-- 4) Pulisci i costi crediti dinamici dalla chiave 'credit_costs' (JSONB),
--    rimuovendo le sotto-chiavi 'enhance_image' e 'carousel_creator' se presenti.
--    Se la riga non esiste o non e' un oggetto JSON, l'UPDATE non fa nulla.
UPDATE system_settings
SET value = (value - 'enhance_image' - 'carousel_creator')
WHERE key = 'credit_costs'
  AND jsonb_typeof(value) = 'object';

COMMIT;
