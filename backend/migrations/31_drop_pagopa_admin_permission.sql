-- Migration 31: rimuove il permesso orfano 'pagopa_admin'.
--
-- Era inserito dalla migration 20 in role_permissions per il ruolo admin, ma
-- dopo la rimozione di PagoPA non gate più nulla e non è in PERMISSION_CODES.
-- Pulisce le righe residue da entrambe le tabelle dei permessi.
-- Idempotente: DELETE di righe inesistenti è un no-op.

DELETE FROM role_permissions WHERE permission_code = 'pagopa_admin';
DELETE FROM user_permissions WHERE permission_code = 'pagopa_admin';
