-- Linker Mind Database Schema
-- SQLite Database for Linker Mind Refactored System
-- Version: 2.0

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CONTENT TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS contents (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,                 -- webpage, twitter, youtube, etc.
    content_type TEXT NOT NULL,                -- article, video, book, podcast, etc.
    title TEXT,
    url TEXT,
    raw_content TEXT,                          -- Original extracted content
    summary TEXT,                              -- AI-generated summary
    main_content TEXT,                         -- Main content body
    html_content TEXT,                         -- Raw HTML if available

    -- AI Analysis fields (stored as JSON)
    ai_analysis TEXT,                          -- JSON: {key_points, topics, sentiment, etc.}

    -- Metadata (stored as JSON)
    metadata TEXT,                             -- JSON: {author, publish_date, tags, etc.}

    -- Media information (stored as JSON)
    media TEXT,                                -- JSON: {type, images[], videos[], screenshots[]}

    -- Processing info (stored as JSON)
    processing_info TEXT,                      -- JSON: {method, processing_time, success, errors}

    -- Progress tracking
    archived BOOLEAN DEFAULT 0,
    favorited BOOLEAN DEFAULT 0,
    reading_progress REAL DEFAULT 0.0,         -- 0.0 to 1.0

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    indexed_at TEXT,

    -- Full-text search
    fts_content TEXT                           -- Computed column for FTS
);

-- Create indexes for contents
CREATE INDEX IF NOT EXISTS idx_contents_source_type ON contents(source_type);
CREATE INDEX IF NOT EXISTS idx_contents_content_type ON contents(content_type);
CREATE INDEX IF NOT EXISTS idx_contents_platform ON contents(source_type);
CREATE INDEX IF NOT EXISTS idx_contents_created_at ON contents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contents_updated_at ON contents(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_contents_archived ON contents(archived);
CREATE INDEX IF NOT EXISTS idx_contents_favorited ON contents(favorited);
CREATE INDEX IF NOT EXISTS idx_contents_reading_progress ON contents(reading_progress);

-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS contents_fts USING fts5(
    id, title, summary, main_content,
    content='contents',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS contents_ai AFTER INSERT ON contents BEGIN
    INSERT INTO contents_fts(rowid, id, title, summary, main_content)
    VALUES (NEW.rowid, NEW.id, NEW.title, NEW.summary, NEW.main_content);
END;

CREATE TRIGGER IF NOT EXISTS contents_ad AFTER DELETE ON contents BEGIN
    DELETE FROM contents_fts WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS contents_au AFTER UPDATE ON contents BEGIN
    UPDATE contents_fts
    SET title = NEW.title, summary = NEW.summary, main_content = NEW.main_content
    WHERE rowid = NEW.rowid;
END;

-- ============================================================================
-- ORGANIZATION NODES (PARA)
-- ============================================================================
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,                   -- PROJECT, AREA, RESOURCE, ARCHIVE, CUSTOM
    name TEXT NOT NULL,
    description TEXT,

    -- Hierarchy
    parent_id TEXT,
    order_index INTEGER DEFAULT 0,

    -- Status and properties
    status TEXT DEFAULT 'ACTIVE',              -- ACTIVE, INACTIVE, COMPLETED, ARCHIVED
    color TEXT DEFAULT '#3498db',
    icon TEXT DEFAULT '📁',

    -- Tags and metadata (JSON)
    tags TEXT,                                 -- JSON array of tags
    metadata TEXT,                             -- Additional metadata as JSON

    -- For projects: target dates
    target_date TEXT,
    started_at TEXT,
    completed_at TEXT,

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (parent_id) REFERENCES nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_node_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_parent_id ON nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_nodes_target_date ON nodes(target_date);
CREATE INDEX IF NOT EXISTS idx_nodes_order ON nodes(parent_id, order_index);

-- ============================================================================
-- NODE-CONTENT ASSOCIATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS node_contents (
    node_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    added_at TEXT DEFAULT (datetime('now')),
    order_index INTEGER DEFAULT 0,
    notes TEXT,

    PRIMARY KEY (node_id, content_id),
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_node_contents_node_id ON node_contents(node_id);
CREATE INDEX IF NOT EXISTS idx_node_contents_content_id ON node_contents(content_id);

-- ============================================================================
-- INBOX (Quick Capture)
-- ============================================================================
CREATE TABLE IF NOT EXISTS inbox (
    id TEXT PRIMARY KEY,
    content_id TEXT,                           -- Links to processed content
    raw_input TEXT NOT NULL,                   -- Original URL or text
    source_type TEXT,
    title TEXT,
    url TEXT,

    -- Processing status
    status TEXT DEFAULT 'PENDING',             -- PENDING, PROCESSED, SNOOZED, ARCHIVED
    processed_at TEXT,
    processed_content_id TEXT,

    -- Quick tags
    quick_tags TEXT,                           -- JSON array of quick tags

    -- Priority
    priority INTEGER DEFAULT 0,                -- Higher = more important

    -- Timestamps
    added_at TEXT DEFAULT (datetime('now')),
    due_date TEXT,

    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox(status);
CREATE INDEX IF NOT EXISTS idx_inbox_added_at ON inbox(added_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbox_priority ON inbox(priority DESC);
CREATE INDEX IF NOT EXISTS idx_inbox_due_date ON inbox(due_date);

-- ============================================================================
-- NOTES (Enhanced with Progressive Summarization)
-- ============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    content_id TEXT,                           -- Associated content
    node_id TEXT,                              -- Associated node/project

    -- Note content
    note_type TEXT NOT NULL,                   -- learning, inspiration, quote, actionable, etc.
    content TEXT NOT NULL,

    -- Progressive summarization
    summary_layer INTEGER DEFAULT 0,           -- 0-5: progressive summarization level
    highlights TEXT,                           -- JSON: array of highlighted text with colors
    bolded_text TEXT,                          -- JSON: array of bolded text
    supernotes TEXT,                           -- JSON: array of supernotes (layer 3)
    own_words TEXT,                            -- JSON: array of own summaries (layer 4)
    insights TEXT,                             -- JSON: array of new insights (layer 5)

    -- Direct quotes from source
    quotes TEXT,                               -- JSON: array of direct quotes

    -- Tags and metadata
    project_tags TEXT,                         -- JSON array of project-related tags
    mood_tags TEXT,                            -- JSON array of mood/emotion tags
    actionable BOOLEAN DEFAULT 0,

    -- Related items
    related_note_ids TEXT,                     -- JSON array of related note IDs
    related_content_ids TEXT,                  -- JSON array of related content IDs

    -- For question notes
    resolved BOOLEAN DEFAULT 0,
    resolution_note TEXT,

    -- Priority and status
    priority TEXT DEFAULT 'medium',            -- low, medium, high
    status TEXT DEFAULT 'active',              -- active, archived, deleted

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE SET NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_content_id ON notes(content_id);
CREATE INDEX IF NOT EXISTS idx_notes_node_id ON notes(node_id);
CREATE INDEX IF NOT EXISTS idx_notes_note_type ON notes(note_type);
CREATE INDEX IF NOT EXISTS idx_notes_summary_layer ON notes(summary_layer);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_actionable ON notes(actionable);
CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);

-- Full-text search for notes
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    id, content, quotes,
    content='notes',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, id, content, quotes)
    VALUES (NEW.rowid, NEW.id, NEW.content, COALESCE(NEW.quotes, ''));
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    DELETE FROM notes_fts WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    UPDATE notes_fts
    SET content = NEW.content, quotes = COALESCE(NEW.quotes, '')
    WHERE rowid = NEW.rowid;
END;

-- ============================================================================
-- BIDIRECTIONAL LINKS
-- ============================================================================
CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,                   -- Can be note_id or content_id
    source_type TEXT NOT NULL,                -- 'note' or 'content'
    target_id TEXT NOT NULL,                   -- Can be note_id, content_id, or node_id
    target_type TEXT NOT NULL,                -- 'note', 'content', or 'node'

    -- Link properties
    link_type TEXT DEFAULT 'RELATED',          -- REFERENCE, RELATED, OPPOSES, EXTENDS, EXAMPLE, QUESTION, APPLICATION, INSPIRED
    context TEXT,                              -- Description of the relationship

    -- Strength calculation
    strength REAL DEFAULT 1.0,                 -- 0.0 to 1.0, algorithm-calculated
    manual_strength BOOLEAN DEFAULT 0,         -- Whether strength was manually set

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id, source_type);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id, target_type);
CREATE INDEX IF NOT EXISTS idx_links_type ON links(link_type);
CREATE INDEX IF NOT EXISTS idx_links_strength ON links(strength DESC);

-- ============================================================================
-- LEARNING SESSIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS learning_sessions (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL,
    node_id TEXT,                              -- Optional: associated project/node

    -- Session timing
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER DEFAULT 0,

    -- Learning behavior
    highlights_count INTEGER DEFAULT 0,
    notes_added INTEGER DEFAULT 0,
    links_created INTEGER DEFAULT 0,
    summary_layer_reached INTEGER DEFAULT 0,

    -- Self-assessment
    comprehension INTEGER,                     -- 1-5: understanding level
    confidence INTEGER,                        -- 1-5: confidence in mastery
    mood TEXT,                                 -- mood during session

    -- Takeaways
    key_takeaways TEXT,                        -- JSON: array of key points learned
    questions_raised TEXT,                     -- JSON: array of new questions

    -- Session notes
    session_notes TEXT,

    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_content_id ON learning_sessions(content_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON learning_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_node_id ON learning_sessions(node_id);

-- ============================================================================
-- REVIEW SCHEDULES (Spaced Repetition)
-- ============================================================================
CREATE TABLE IF NOT EXISTS review_schedules (
    content_id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default',

    -- Scheduling
    last_reviewed TEXT,
    next_review TEXT NOT NULL,
    review_count INTEGER DEFAULT 0,

    -- SM-2 Algorithm parameters
    interval_days REAL DEFAULT 1.0,
    ease_factor REAL DEFAULT 2.5,
    quality_sum INTEGER DEFAULT 0,

    -- Statistics
    total_reviews INTEGER DEFAULT 0,
    total_time_minutes INTEGER DEFAULT 0,
    average_quality REAL,

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reviews_next_review ON review_schedules(next_review);
CREATE INDEX IF NOT EXISTS idx_reviews_last_reviewed ON review_schedules(last_reviewed);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON review_schedules(user_id);

-- ============================================================================
-- CREATION PROJECTS (Distinct from learning projects)
-- ============================================================================
CREATE TABLE IF NOT EXISTS creation_projects (
    id TEXT PRIMARY KEY,
    project_type TEXT NOT NULL,                -- ARTICLE, VIDEO_SCRIPT, PRESENTATION, BOOK, COURSE, PODCAST, RESEARCH_REPORT, SOCIAL_POST
    title TEXT NOT NULL,
    brief TEXT,                               -- Creation brief/description

    -- Content management
    source_materials TEXT,                    -- JSON: array of content IDs used as source
    quotes TEXT,                              -- JSON: array of quotes with citations
    inspirations TEXT,                        -- JSON: array of inspiration note IDs

    -- Structure
    outline TEXT,                             -- JSON: outline structure
    sections TEXT,                            -- JSON: sections with content
    images TEXT,                              -- JSON: array of images
    draft_content TEXT,                       -- Draft text content

    -- Output tracking
    published_url TEXT,
    published_at TEXT,
    engagement_stats TEXT,                    -- JSON: views, likes, shares, etc.

    -- Cover image
    cover_image TEXT,                         -- URL of cover image

    -- Status
    status TEXT DEFAULT 'RESEARCH',            -- RESEARCH, OUTLINING, DRAFTING, EDITING, PUBLISHED
    progress REAL DEFAULT 0.0,                -- 0.0 to 1.0

    -- Goals
    target_date TEXT,
    word_count_goal INTEGER,
    word_count_actual INTEGER DEFAULT 0,

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_creation_status ON creation_projects(status);
CREATE INDEX IF NOT EXISTS idx_creation_type ON creation_projects(project_type);
CREATE INDEX IF NOT EXISTS idx_creation_target_date ON creation_projects(target_date);

-- ============================================================================
-- CITATIONS (For creation projects)
-- ============================================================================
CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    source_content_id TEXT NOT NULL,
    quote_text TEXT NOT NULL,
    context TEXT,                             -- Usage context in the creation
    position TEXT,                            -- Where in the creation (chapter, section, etc.)
    citation_format TEXT,                     -- academic, blog, social, markdown

    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (project_id) REFERENCES creation_projects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_content_id) REFERENCES contents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_citations_project_id ON citations(project_id);
CREATE INDEX IF NOT EXISTS idx_citations_source_content_id ON citations(source_content_id);

-- ============================================================================
-- SKILLS
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    category TEXT,
    level TEXT DEFAULT 'BEGINNER',             -- BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
    parent_ids TEXT,                          -- JSON: array of parent skill IDs
    description TEXT,

    -- Progress
    progress REAL DEFAULT 0.0,                -- 0.0 to 1.0
    status TEXT DEFAULT 'not_started',        -- not_started, in_progress, completed, mastered
    started_at TEXT,
    completed_at TEXT,

    -- Metadata
    estimated_hours REAL DEFAULT 0.0,
    difficulty_score INTEGER DEFAULT 1,        -- 1-10
    tags TEXT,                                -- JSON: array of tags

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_level ON skills(level);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);

-- ============================================================================
-- SKILL-CONTENT ASSOCIATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS skill_contents (
    skill_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    order_index INTEGER DEFAULT 0,            -- Learning order
    completed BOOLEAN DEFAULT 0,
    completed_at TEXT,
    added_at TEXT DEFAULT (datetime('now')),

    PRIMARY KEY (skill_id, content_id),
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_skill_contents_skill_id ON skill_contents(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_contents_content_id ON skill_contents(content_id);

-- ============================================================================
-- TAGS
-- ============================================================================
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#666666',
    icon TEXT DEFAULT '🏷️',
    category TEXT DEFAULT 'general',
    use_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_use_count ON tags(use_count DESC);

-- ============================================================================
-- CONTENT-TAG ASSOCIATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_tags (
    content_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    tagged_at TEXT DEFAULT (datetime('now')),
    tagged_by TEXT DEFAULT 'user',             -- user, ai, system

    PRIMARY KEY (content_id, tag_id),
    FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_content_tags_content_id ON content_tags(content_id);
CREATE INDEX IF NOT EXISTS idx_content_tags_tag_id ON content_tags(tag_id);

-- ============================================================================
-- ACHIEVEMENTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default',
    achievement_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT '🏆',
    earned_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_achievements_earned_at ON achievements(earned_at DESC);

-- ============================================================================
-- REVIEW SESSIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS review_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default',
    items_reviewed INTEGER DEFAULT 0,
    items_correct INTEGER DEFAULT 0,
    total_time_minutes INTEGER DEFAULT 0,
    average_quality REAL DEFAULT 0.0,
    session_date TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_review_sessions_user_id ON review_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_review_sessions_date ON review_sessions(session_date DESC);

-- ============================================================================
-- SETTINGS
-- ============================================================================
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string',          -- string, int, float, bool, json
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Content with progress summary
CREATE VIEW IF NOT EXISTS v_content_with_progress AS
SELECT
    c.*,
    COALESCE(lp.status, 'not_started') as learning_status,
    COALESCE(lp.reading_progress, 0) as tracked_progress,
    COALESCE(lp.notes_count, 0) as notes_count,
    COALESCE(lp.last_reviewed, NULL) as last_reviewed
FROM contents c
LEFT JOIN learning_progress lp ON c.id = lp.content_id;

-- Node with content counts
CREATE VIEW IF NOT EXISTS v_node_stats AS
SELECT
    n.*,
    COUNT(DISTINCT nc.content_id) as content_count,
    COUNT(DISTINCT CASE WHEN nc.notes IS NOT NULL THEN nc.content_id END) as with_notes_count
FROM nodes n
LEFT JOIN node_contents nc ON n.id = nc.node_id
GROUP BY n.id;

-- Inbox with processed content
CREATE VIEW IF NOT EXISTS v_inbox_with_content AS
SELECT
    i.*,
    c.title as processed_title,
    c.summary as processed_summary,
    c.source_type as content_source_type
FROM inbox i
LEFT JOIN contents c ON i.processed_content_id = c.id;

-- Upcoming reviews
CREATE VIEW IF NOT EXISTS v_upcoming_reviews AS
SELECT
    rs.*,
    c.id as content_id,
    c.title as content_title,
    c.source_type,
    julianday(rs.next_review) - julianday(datetime('now')) as days_until_review
FROM review_schedules rs
JOIN contents c ON rs.content_id = c.id
WHERE rs.next_review > datetime('now')
ORDER BY rs.next_review ASC;

-- Due reviews
CREATE VIEW IF NOT EXISTS v_due_reviews AS
SELECT
    rs.*,
    c.id as content_id,
    c.title as content_title,
    c.source_type,
    julianday(datetime('now')) - julianday(rs.next_review) as overdue_days
FROM review_schedules rs
JOIN contents c ON rs.content_id = c.id
WHERE rs.next_review <= datetime('now')
ORDER BY rs.next_review ASC;

-- Notes summary by content
CREATE VIEW IF NOT EXISTS v_content_notes_summary AS
SELECT
    content_id,
    COUNT(*) as total_notes,
    SUM(CASE WHEN note_type = 'learning' THEN 1 ELSE 0 END) as learning_notes,
    SUM(CASE WHEN note_type = 'inspiration' THEN 1 ELSE 0 END) as inspiration_notes,
    SUM(CASE WHEN note_type = 'quote' THEN 1 ELSE 0 END) as quote_notes,
    SUM(CASE WHEN actionable = 1 THEN 1 ELSE 0 END) as actionable_notes,
    MAX(summary_layer) as max_summary_layer,
    MAX(created_at) as latest_note_at
FROM notes
WHERE content_id IS NOT NULL
GROUP BY content_id;
