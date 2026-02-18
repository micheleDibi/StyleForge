-- ============================================
-- STEP 0: Elimina TUTTO
-- ============================================

-- Disabilita RLS su tutte le tabelle prima di droppare
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END $$;

-- Drop tutte le tabelle in ordine (dipendenze)
DROP TABLE IF EXISTS credit_transactions CASCADE;
DROP TABLE IF EXISTS user_permissions CASCADE;
DROP TABLE IF EXISTS role_permissions CASCADE;
DROP TABLE IF EXISTS thesis_generation_jobs CASCADE;
DROP TABLE IF EXISTS thesis_attachments CASCADE;
DROP TABLE IF EXISTS theses CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS refresh_tokens CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS writing_styles CASCADE;
DROP TABLE IF EXISTS content_depth_levels CASCADE;
DROP TABLE IF EXISTS audience_knowledge_levels CASCADE;
DROP TABLE IF EXISTS audience_sizes CASCADE;
DROP TABLE IF EXISTS industries CASCADE;
DROP TABLE IF EXISTS target_audiences CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop enum types
DROP TYPE IF EXISTS thesis_status CASCADE;
DROP TYPE IF EXISTS job_status CASCADE;
DROP TYPE IF EXISTS job_type CASCADE;
