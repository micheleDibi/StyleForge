-- Migration 15: Add citation_style column to theses table
-- Supports 'footnotes' (note a piè di pagina) and 'bibliography' (citazioni [x])

ALTER TABLE theses ADD COLUMN IF NOT EXISTS citation_style VARCHAR(20) DEFAULT 'footnotes';
