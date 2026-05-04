-- ============================================================================
-- 20: Integrazione PagoPA / SolutionPA per acquisto crediti
-- ============================================================================
-- Aggiunge:
--   * campi anagrafici (CF, P.IVA, ragione sociale, indirizzo) sull'utente
--     per i dati pagatore richiesti da PagoPA
--   * tabella credit_packages: tagli predefiniti acquistabili (admin-editable)
--   * tabella payment_orders: ordini di pagamento PagoPA con stato
--   * tabella pagopa_events: audit log degli esiti push e file di riconciliazione
--
-- Inserisce 3 pacchetti default (Starter/Standard/Plus) e il permesso
-- 'pagopa_admin' per gli admin StyleForge.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Profilo fatturazione utente
-- ----------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS codice_fiscale VARCHAR(16);
ALTER TABLE users ADD COLUMN IF NOT EXISTS partita_iva VARCHAR(11);
ALTER TABLE users ADD COLUMN IF NOT EXISTS ragione_sociale VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS indirizzo_fatturazione VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_users_codice_fiscale ON users(codice_fiscale);

-- ----------------------------------------------------------------------------
-- 2. Pacchetti crediti acquistabili
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_packages (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    credits     INTEGER NOT NULL CHECK (credits > 0),
    -- Prezzo in centesimi di euro (es. 45.00 EUR = 4500). Evita float per il money.
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_packages_active ON credit_packages(is_active, sort_order);

-- Pacchetti default (idempotente: niente errore se già presenti)
INSERT INTO credit_packages (name, credits, price_cents, sort_order, description)
SELECT 'Starter', 100, 1000, 1, 'Pacchetto piccolo per uso saltuario'
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Starter');

INSERT INTO credit_packages (name, credits, price_cents, sort_order, description)
SELECT 'Standard', 500, 4500, 2, 'Pacchetto medio: 10% di sconto'
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Standard');

INSERT INTO credit_packages (name, credits, price_cents, sort_order, description)
SELECT 'Plus', 1000, 8500, 3, 'Pacchetto grande: 15% di sconto'
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Plus');

-- ----------------------------------------------------------------------------
-- 3. Ordini di pagamento PagoPA
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_orders (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    package_id             INTEGER REFERENCES credit_packages(id) ON DELETE SET NULL,

    -- Snapshot del pacchetto al momento dell'ordine (immutabile anche
    -- se l'admin modifica il pacchetto in seguito)
    credits                INTEGER NOT NULL CHECK (credits > 0),
    amount_cents           INTEGER NOT NULL CHECK (amount_cents > 0),
    causale                VARCHAR(140) NOT NULL,

    -- Identificativi PagoPA
    iuv                    VARCHAR(35) UNIQUE,
    context_id             VARCHAR(35),
    checkout_url           TEXT,

    -- Snapshot dati pagatore al momento dell'ordine
    payer_codice_fiscale   VARCHAR(16) NOT NULL,
    payer_partita_iva      VARCHAR(11),
    payer_ragione_sociale  VARCHAR(255),
    payer_email            VARCHAR(255),

    -- Stato workflow
    -- valori: PENDING | AWAITING_PAYMENT | PAID | FAILED | CANCELED | EXPIRED | REFUNDED
    status                 VARCHAR(30) NOT NULL DEFAULT 'PENDING',

    -- Notifica esito (push)
    notify_received_at     TIMESTAMP WITH TIME ZONE,
    notify_payload         JSONB,
    amount_paid_cents      INTEGER,
    paid_at                TIMESTAMP WITH TIME ZONE,

    -- Riconciliazione
    reconciliation_id      VARCHAR(100),
    identificativo_flusso  VARCHAR(100),

    -- Audit timestamps
    created_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at             TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Tracciamento accredito crediti
    credits_granted_at     TIMESTAMP WITH TIME ZONE,
    credits_transaction_id UUID REFERENCES credit_transactions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user        ON payment_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_status      ON payment_orders(status);
CREATE INDEX IF NOT EXISTS idx_payment_orders_iuv         ON payment_orders(iuv);
CREATE INDEX IF NOT EXISTS idx_payment_orders_context     ON payment_orders(context_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_created_at  ON payment_orders(created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Audit log eventi PagoPA (push esito + riconciliazioni)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pagopa_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id    UUID REFERENCES payment_orders(id) ON DELETE SET NULL,
    iuv         VARCHAR(35),

    -- Tipo evento: ESITO_PUSH | RECONCILIATION_FILE | RPT_ACTIVATED | POSITION_LOADED | POSITION_CANCELED
    event_type  VARCHAR(30) NOT NULL,
    -- Sorgente: soap | rest | sftp | manual | system
    source      VARCHAR(20) NOT NULL,

    payload     JSONB NOT NULL,
    processed   BOOLEAN NOT NULL DEFAULT FALSE,
    error       TEXT,

    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pagopa_events_order ON pagopa_events(order_id);
CREATE INDEX IF NOT EXISTS idx_pagopa_events_iuv   ON pagopa_events(iuv);
CREATE INDEX IF NOT EXISTS idx_pagopa_events_type  ON pagopa_events(event_type);

-- ----------------------------------------------------------------------------
-- 5. Permesso admin per gestione PagoPA
-- ----------------------------------------------------------------------------
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, 'pagopa_admin'
FROM roles r
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_code) DO NOTHING;
