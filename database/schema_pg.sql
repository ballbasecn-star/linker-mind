-- Linker Mind v2.0 - PostgreSQL Database Schema
-- This schema is optimized for PostgreSQL with proper data types,
-- indexes, and constraints.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable trgm extension for full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- CONTENTS TABLE - Core content storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS contents (
    id VARCHAR(64) PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    title VARCHAR(1000),
    url TEXT,
    raw_content TEXT,
    summary TEXT,
    main_content TEXT,

    -- AI analysis stored as JSONB
    ai_analysis JSONB,

    -- Metadata stored as JSONB
    metadata JSONB,

    -- Flags and tracking
    favorited BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    reading_progress DECIMAL(5,2) DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    CONSTRAINT contents_source_type_check CHECK (source_type IS NOT NULL),
    CONSTRAINT contents_content_type_check CHECK (content_type IS NOT NULL)
);

-- Content indexes
CREATE INDEX idx_contents_source_type ON contents(source_type);
CREATE INDEX idx_contents_content_type ON contents(content_type);
CREATE INDEX idx_contents_favorited ON contents(favorited) WHERE favorited = TRUE;
CREATE INDEX idx_contents_archived ON contents(archived) WHERE archived = TRUE;
CREATE INDEX idx_contents_created_at ON contents(created_at DESC);
CREATE INDEX idx_contents_updated_at ON contents(updated_at DESC);

-- Full-text search index using GIN (for JSONB search)
CREATE INDEX idx_contents_ai_analysis_gin ON contents USING GIN (ai_analysis);
CREATE INDEX idx_contents_metadata_gin ON contents USING GIN (metadata);

-- ============================================================================
-- FULL-TEXT SEARCH TABLES
-- ============================================================================

-- Contents FTS table
CREATE TABLE IF NOT EXISTS contents_fts (
    id VARCHAR(64) PRIMARY KEY REFERENCES contents(id) ON DELETE CASCADE,
    document TEXT,
    source_tsvector TSV
);

-- Trigger to update FTS table
CREATE OR REPLACE FUNCTION contents_fts_trigger() RETURNS TRIGGER AS $$
BEGIN
    NEW.document := COALESCE(NEW.title, '') || ' ' ||
                     COALESCE(NEW.summary, '') || ' ' ||
                     COALESCE(NEW.main_content, '');

    NEW.source_tsvector = to_tsvector('english', NEW.document);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER contents_fts_update
    BEFORE INSERT OR UPDATE ON contents
    FOR EACH ROW
    EXECUTE FUNCTION contents_fts_trigger();

-- GIN index for FTS
CREATE INDEX idx_contents_fts_source ON contents_fts USING GIN (source_tsvector);

-- ============================================================================
-- NOTES TABLE - Progressive summarization
-- ============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id VARCHAR(64) PRIMARY KEY,
    content_id VARCHAR(64) REFERENCES contents(id) ON DELETE SET NULL,

    note_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,

    -- Progressive summary layers (stored as JSONB)
    highlights JSONB DEFAULT '[]'::jsonb,
    summary_layers JSONB DEFAULT '{}'::jsonb,

    -- Project tags for notes
    project_tags JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT notes_content_id_fkey FOREIGN KEY (content_id) REFERENCES contents(id)
);

CREATE INDEX idx_notes_content_id ON notes(content_id);
CREATE INDEX idx_notes_note_type ON notes(note_type);
CREATE INDEX idx_notes_created_at ON notes(created_at DESC);
CREATE INDEX idx_notes_project_tags ON notes USING GIN (project_tags);

-- Notes FTS table
CREATE TABLE IF NOT EXISTS notes_fts (
    id VARCHAR(64) PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
    document TEXT,
    source_tsvector TSV
);

CREATE OR REPLACE FUNCTION notes_fts_trigger() RETURNS TRIGGER AS $$
BEGIN
    NEW.document := COALESCE(NEW.content, '');

    NEW.source_tsvector = to_tsvector('english', NEW.document);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER notes_fts_update
    BEFORE INSERT OR UPDATE ON notes
    FOR EACH ROW
    EXECUTE FUNCTION notes_fts_trigger();

CREATE INDEX idx_notes_fts_source ON notes_fts USING GIN (source_tsvector);

-- ============================================================================
-- NODES TABLE - PARA organization
-- ============================================================================
CREATE TABLE IF NOT EXISTS nodes (
    id VARCHAR(64) PRIMARY KEY,
    node_type VARCHAR(20) NOT NULL,  -- project, area, resource, archive, custom
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- Hierarchy
    parent_id VARCHAR(64) REFERENCES nodes(id) ON DELETE SET NULL,

    -- Status and properties
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- active, inactive, completed, archived
    icon VARCHAR(10) DEFAULT '📁',

    -- JSON fields
    tags JSONB DEFAULT '[]'::jsonb,
    properties JSONB DEFAULT '{}'::jsonb,

    -- Dates
    target_date DATE,
    completed_at DATE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT nodes_node_type_check CHECK (node_type IN ('project', 'area', 'resource', 'archive', 'custom'))
);

CREATE INDEX idx_nodes_node_type ON nodes(node_type);
CREATE INDEX idx_nodes_parent_id ON nodes(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_nodes_status ON nodes(status);
CREATE INDEX idx_nodes_target_date ON nodes(target_date) WHERE target_date IS NOT NULL;
CREATE INDEX idx_nodes_tags ON nodes USING GIN (tags);

-- ============================================================================
-- NODE CONTENTS RELATIONSHIP
-- ============================================================================
CREATE TABLE IF NOT EXISTS node_contents (
    node_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (node_id, content_id),
    CONSTRAINT fk_node_contents_node FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE INDEX idx_node_contents_node_id ON node_contents(node_id);
CREATE INDEX idx_node_contents_content_id ON node_contents(content_id);

-- ============================================================================
-- LINKS TABLE - Bidirectional linking
-- ============================================================================
CREATE TABLE IF NOT EXISTS links (
    id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    source_type VARCHAR(20) DEFAULT 'content',
    target_id VARCHAR(64) NOT NULL,
    target_type VARCHAR(20) DEFAULT 'content',
    link_type VARCHAR(50) NOT NULL,
    context TEXT,

    -- Calculated properties
    strength DECIMAL(3,2) DEFAULT 1.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT links_link_type_check CHECK (link_type IN (
        'reference', 'related', 'opposes', 'extends',
        'example', 'question', 'application', 'inspired'
    ))
);

CREATE INDEX idx_links_source_id ON links(source_id, source_type);
CREATE INDEX idx_links_target_id ON links(target_id, target_type);
CREATE INDEX idx_links_type ON links(link_type);
CREATE INDEX idx_links_created_at ON links(created_at DESC);

-- ============================================================================
-- INBOX TABLE - Quick capture workflow
-- ============================================================================
CREATE TABLE IF NOT EXISTS inbox (
    id VARCHAR(64) PRIMARY KEY,
    content_id VARCHAR(64) REFERENCES contents(id) ON DELETE SET NULL,

    raw_input TEXT NOT NULL,
    title VARCHAR(500),
    url TEXT,
    source_type VARCHAR(50),

    -- Processing state
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processed, snoozed, archived
    priority INTEGER DEFAULT 0,

    -- Quick tags
    quick_tags JSONB DEFAULT '[]'::jsonb,

    -- Dates
    due_date DATE,

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT inbox_status_check CHECK (status IN ('pending', 'processed', 'snoozed', 'archived'))
);

CREATE INDEX idx_inbox_status ON inbox(status);
CREATE INDEX idxinbox_added_at ON inbox(added_at DESC);
CREATE INDEX idx_inbox_priority ON inbox(priority DESC) WHERE priority > 0;
CREATE INDEX idx_inbox_due_date ON inbox(due_date) WHERE due_date IS NOT NULL;

-- ============================================================================
-- CREATION PROJECTS TABLE - Creative workspace
-- ============================================================================
CREATE TABLE IF NOT EXISTS creation_projects (
    id VARCHAR(64) PRIMARY KEY,
    project_type VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    brief TEXT,

    -- JSON fields for flexible data
    source_materials JSONB DEFAULT '[]'::jsonb,
    quotes JSONB DEFAULT '[]'::jsonb,
    inspirations JSONB DEFAULT '[]'::jsonb,
    outline JSONB DEFAULT '[]'::jsonb,
    sections JSONB DEFAULT '[]'::jsonb,
    images JSONB DEFAULT '[]'::jsonb,

    draft_content TEXT,
    published_url TEXT,

    -- Cover image
    cover_image TEXT,

    -- Status and progress
    status VARCHAR(20) DEFAULT 'research',
    progress DECIMAL(3,2) DEFAULT 0.0,
    word_count_goal INTEGER,
    word_count_actual INTEGER DEFAULT 0,

    -- Dates
    target_date DATE,
    published_at DATE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT creation_projects_status_check CHECK (status IN (
        'research', 'outlining', 'drafting', 'editing',
        'reviewing', 'finalizing', 'published'
    ))
);

CREATE INDEX idx_creation_projects_type ON creation_projects(project_type);
CREATE INDEX idx_creation_projects_status ON creation_projects(status);
CREATE INDEX idx_creation_projects_created_at ON creation_projects(created_at DESC);
CREATE INDEX idx_creation_projects_target_date ON creation_projects(target_date) WHERE target_date IS NOT NULL;

-- ============================================================================
-- LEARNING SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS learning_sessions (
    id VARCHAR(64) PRIMARY KEY,
    content_id VARCHAR(64) NOT NULL REFERENCES contents(id) ON DELETE CASCADE,

    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration INTEGER DEFAULT 0,

    -- Learning behaviors
    highlights_count INTEGER DEFAULT 0,
    notes_added INTEGER DEFAULT 0,
    links_created INTEGER DEFAULT 0,
    summary_layer INTEGER DEFAULT 0,

    -- Self-assessment
    comprehension INTEGER DEFAULT 3 CHECK (comprehension BETWEEN 1 AND 5),
    confidence INTEGER DEFAULT 3 CHECK (confidence BETWEEN 1 AND 5),
    mood VARCHAR(50) DEFAULT 'calm',

    -- Outputs
    key_takeaways JSONB DEFAULT '[]'::jsonb,
    questions JSONB DEFAULT '[]'::jsonb,
    session_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_sessions_content_id ON learning_sessions(content_id);
CREATE INDEX idx_learning_sessions_started_at ON learning_sessions(started_at DESC);

-- ============================================================================
-- REVIEW SCHEDULES TABLE - Spaced repetition
-- ============================================================================
CREATE TABLE IF NOT EXISTS review_schedules (
    content_id VARCHAR(64) PRIMARY KEY REFERENCES contents(id) ON DELETE CASCADE,

    last_reviewed TIMESTAMP WITH TIME ZONE,
    next_review TIMESTAMP WITH TIME ZONE NOT NULL,
    review_count INTEGER DEFAULT 0,
    interval_days INTEGER DEFAULT 1,

    -- SM-2 algorithm parameters
    ease_factor DECIMAL(4,2) DEFAULT 2.5 CHECK (ease_factor >= 1.3),

    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_schedules_next_review ON review_schedules(next_review);
CREATE INDEX idx_review_schedules_last_reviewed ON review_schedules(last_reviewed);

-- ============================================================================
-- SKILLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills (
    id VARCHAR(64) PRIMARY KEY,
    skill_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    level VARCHAR(20) DEFAULT 'beginner',  -- beginner, intermediate, advanced, expert

    parent_ids JSONB DEFAULT '[]'::jsonb,
    description TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_level ON skills(level);
CREATE INDEX idx_skills_name ON skills USING gin (skill_name gin_trgm_ops);

-- ============================================================================
-- SKILL CONTENTS RELATIONSHIP
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_contents (
    skill_id VARCHAR(64) NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    content_id VARCHAR(64) NOT NULL REFERENCES contents(id) ON DELETE CASCADE,

    order_index INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,

    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,

    PRIMARY KEY (skill_id, content_id)
);

CREATE INDEX idx_skill_contents_skill_id ON skill_contents(skill_id);
CREATE INDEX idx_skill_contents_content_id ON skill_contents(content_id);
CREATE INDEX idx_skill_contents_completed ON skill_contents(completed);

-- ============================================================================
-- TAGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    color VARCHAR(20) DEFAULT '#666666',
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT tags_name_check CHECK (name IS NOT NULL AND name <> '')
);

CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_use_count ON tags(use_count DESC);

-- ============================================================================
-- CONTENT TAGS RELATIONSHIP
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_tags (
    content_id VARCHAR(64) NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    tagged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (content_id, tag_id)
);

CREATE INDEX idx_content_tags_content_id ON content_tags(content_id);
CREATE INDEX idx_content_tags_tag_id ON content_tags(tag_id);

-- ============================================================================
-- CITATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS citations (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES creation_projects(id) ON DELETE CASCADE,
    source_content_id VARCHAR(64) NOT NULL REFERENCES contents(id) ON DELETE CASCADE,

    quote_text TEXT NOT NULL,
    context TEXT,

    position VARCHAR(100),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_citations_project FOREIGN KEY (project_id) REFERENCES creation_projects(id),
    CONSTRAINT fk_citations_content FOREIGN KEY (source_content_id) REFERENCES contents(id)
);

-- ============================================================================
-- TASKS TABLE (for async processing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(64) PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    metadata JSONB,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

CREATE INDEX idx_citations_project_id ON citations(project_id);
CREATE INDEX idx_citations_source_content_id ON citations(source_content_id);

-- ============================================================================
-- VIEWS - Common query views
-- ============================================================================

-- Content with tags view
CREATE OR REPLACE VIEW v_content_with_tags AS
SELECT
    c.*,
    COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', t.id,
            'name', t.name,
            'color', t.color
        ) ORDER BY t.use_count DESC
    ), '[]'::jsonb) AS tags
FROM contents c
LEFT JOIN content_tags ct ON c.id = ct.content_id
LEFT JOIN tags t ON ct.tag_id = t.id
GROUP BY c.id
ORDER BY c.created_at DESC;

-- Recent activity view
CREATE OR REPLACE VIEW v_recent_activity AS
SELECT
    'content' as item_type,
    id,
    title,
    created_at,
    source_type,
    platform,
    favorited
FROM contents
UNION ALL
SELECT
    'note' as item_type,
    id,
    content as title,
    created_at,
    'note' as source_type,
    'note' as platform,
    FALSE as favorited
FROM notes
ORDER BY created_at DESC
LIMIT 100;

-- Learning statistics view
CREATE OR REPLACE VIEW v_learning_stats AS
SELECT
    c.id as content_id,
    c.title,
    COUNT(ls.id) as total_sessions,
    SUM(ls.duration) as total_duration,
    AVG(ls.comprehension) as avg_comprehension,
    AVG(ls.confidence) as avg_confidence,
    MAX(ls.started_at) as last_session,
    rs.next_review
FROM contents c
LEFT JOIN learning_sessions ls ON c.id = ls.content_id
LEFT JOIN review_schedules rs ON c.id = rs.content_id
GROUP BY c.id
ORDER BY total_sessions DESC, total_duration DESC;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to generate unique ID
CREATE OR REPLACE FUNCTION generate_id(prefix TEXT = 'content')
RETURNS TEXT AS $$
DECLARE
    timestamp_str TEXT;
    count_val INTEGER;
BEGIN
    timestamp_str := TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24MISS');
    count_val := (SELECT COUNT(*) FROM contents WHERE id LIKE prefix || '%'::TEXT);

    RETURN prefix || '_' || timestamp_str || '_' || LPAD(count_val::TEXT, 3, '0');
END;
$$ LANGUAGE plpgsql;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers to all tables with updated_at
CREATE TRIGGER update_contents_updated_at BEFORE UPDATE ON contents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_notes_updated_at BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_inbox_updated_at BEFORE UPDATE ON inbox
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_creation_projects_updated_at BEFORE UPDATE ON creation_projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_skills_updated_at BEFORE UPDATE ON skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- GRANTS (optional - adjust based on your needs)
-- ============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- ============================================================================
-- VACUUM AND ANALYZE
-- ============================================================================
-- Run after initial data load
-- VACUUM ANALYZE;
