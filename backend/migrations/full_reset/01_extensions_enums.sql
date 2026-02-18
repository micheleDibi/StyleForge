-- ============================================
-- STEP 1: Extensions e Enum Types
-- ============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE job_status AS ENUM (
    'pending', 'training', 'ready', 'generating', 'completed', 'failed'
);

CREATE TYPE job_type AS ENUM (
    'training', 'generation', 'humanization', 'thesis_generation'
);

CREATE TYPE thesis_status AS ENUM (
    'draft', 'chapters_pending', 'chapters_confirmed',
    'sections_pending', 'sections_confirmed',
    'generating', 'completed', 'failed'
);
