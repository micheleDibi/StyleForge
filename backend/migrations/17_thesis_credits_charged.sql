-- Migration 17: Add credits_charged flag to theses
-- Flag to mark theses created under the new flat-pricing model.
-- Older rows keep credits_charged=FALSE so the legacy pay-per-step flow remains active for them.

ALTER TABLE theses ADD COLUMN IF NOT EXISTS credits_charged BOOLEAN DEFAULT FALSE;

UPDATE theses SET credits_charged = FALSE WHERE credits_charged IS NULL;
