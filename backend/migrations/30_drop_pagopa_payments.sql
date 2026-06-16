-- Migration 30: rimozione completa dell'integrazione PagoPA.
--
-- Elimina le tabelle del flusso pagamenti PagoPA (ordini + audit eventi).
-- I pacchetti crediti (credit_packages) RESTANO: vengono usati come listino e
-- gestiti dall'admin; l'accredito dei crediti avviene manualmente.
--
-- Idempotente: usa IF EXISTS + CASCADE (pagopa_events ha una FK su payment_orders).

DROP TABLE IF EXISTS pagopa_events CASCADE;
DROP TABLE IF EXISTS payment_orders CASCADE;
