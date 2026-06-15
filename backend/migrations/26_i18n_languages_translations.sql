-- ============================================================================
-- 26: Multi-lingua (i18n) — tabelle languages + translations
-- ============================================================================
-- Sistema di traduzione gestito dall'admin:
--   * languages: lingue disponibili (codice, nome, bandiera, attiva, default)
--   * translations: coppie (lingua, chiave) -> valore tradotto.
--     La "chiave" È la stringa italiana di partenza (strategia chiave naturale).
--     I valori della lingua 'it' (catalogo base) vengono popolati a runtime
--     dall'azione admin "Sincronizza etichette".
-- Idempotente.
-- ============================================================================

CREATE TABLE IF NOT EXISTS languages (
    code              VARCHAR(10) PRIMARY KEY,
    name              VARCHAR(100) NOT NULL,            -- nome in inglese/italiano (es. 'Inglese')
    native_name       VARCHAR(100) NOT NULL,            -- nome nativo (es. 'English')
    flag_country_code VARCHAR(8) NOT NULL,              -- codice ISO paese per la bandiera (flag-icons)
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    is_default        BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS translations (
    id            BIGSERIAL PRIMARY KEY,
    language_code VARCHAR(10) NOT NULL REFERENCES languages(code) ON DELETE CASCADE,
    key           TEXT NOT NULL,
    value         TEXT,
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_translations_lang_key UNIQUE (language_code, key)
);

CREATE INDEX IF NOT EXISTS idx_translations_lang ON translations(language_code);

-- Lingua di default: italiano
INSERT INTO languages (code, name, native_name, flag_country_code, is_active, is_default, sort_order)
SELECT 'it', 'Italiano', 'Italiano', 'it', TRUE, TRUE, 0
WHERE NOT EXISTS (SELECT 1 FROM languages WHERE code = 'it');
