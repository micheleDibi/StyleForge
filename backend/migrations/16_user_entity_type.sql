-- Migration 16: Add entity_type column to users table
-- Differentiates billing tier: 'private' (default 250 cr/tesi) or 'training' (default 125 cr/tesi).
-- The actual flat cost is configurable from the admin credit cost settings.

ALTER TABLE users ADD COLUMN IF NOT EXISTS entity_type VARCHAR(20) DEFAULT 'private';

-- Backfill existing rows that may have NULL after the ADD (some Postgres editions)
UPDATE users SET entity_type = 'private' WHERE entity_type IS NULL;
