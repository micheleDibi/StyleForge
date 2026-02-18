-- ============================================
-- STEP 5: Tabelle thesis
-- ============================================

CREATE TABLE theses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    key_topics TEXT[],
    writing_style_id INTEGER REFERENCES writing_styles(id),
    content_depth_id INTEGER REFERENCES content_depth_levels(id),
    num_chapters INTEGER DEFAULT 5,
    sections_per_chapter INTEGER DEFAULT 3,
    words_per_section INTEGER DEFAULT 5000,
    knowledge_level_id INTEGER REFERENCES audience_knowledge_levels(id),
    audience_size_id INTEGER REFERENCES audience_sizes(id),
    industry_id INTEGER REFERENCES industries(id),
    target_audience_id INTEGER REFERENCES target_audiences(id),
    ai_provider VARCHAR(20) DEFAULT 'openai',
    chapters_structure JSONB,
    generated_content TEXT,
    status thesis_status DEFAULT 'draft',
    current_phase INTEGER DEFAULT 0,
    generation_progress INTEGER DEFAULT 0,
    total_words_generated INTEGER DEFAULT 0,
    attachments_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE thesis_attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    extracted_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE thesis_generation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thesis_id UUID NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
