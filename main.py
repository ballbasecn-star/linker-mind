"""
Linker Mind - Main Entry Point (Refactored v2.0)

A second brain and creative workspace system with:
- Multi-modal content extraction and storage
- PARA organization system
- Progressive summarization
- Bidirectional linking
- Creative project management
- SQLite database storage

Usage:
    python main.py                          # Interactive mode
    python main.py --url <URL>              # Process a URL
    python main.py --text "note content"   # Add text note
    python main.py --search <query>         # Search content
    python main.py --stats                   # Show statistics
    python main.py --db init                 # Initialize database
    python main.py --db migrate              # Migrate from JSON
    python main.py --inbox                   # Inbox management
    python main.py --node list               # Organization nodes
    python main.py --creation list           # Creation projects
"""
import os
import sys
import argparse
from typing import Optional
from pathlib import Path
from datetime import datetime

from url_detector import URLDetector, URLInfo, URLType
from content_processor import ProcessorFactory, ProcessedContent, WebPageProcessor, SocialMediaProcessor, VideoProcessor, TextMemoProcessor
from ai_analyzer import AIAnalyzer, StorageManager

# Import new database services
try:
    from database.connection import init_database, get_db, DatabaseConnection
    from repositories.content_repository import ContentRepository, Content
    from services.inbox_service import InboxService, InboxStatus, ProcessAction
    from services.node_service import NodeService, NodeType, NodeStatus
    from services.summary_service import ProgressiveSummaryService, SummaryLayer, HighlightColor
    from services.link_service import LinkService, LinkType, LinkSourceType
    from services.creation_service import CreationWorkshopService, CreationType, CreationStatus
    from services.search_service import EnhancedSearchService, SearchQuery, SortType
    from services.session_service import LearningSessionService, Mood
    from services.graph_service import KnowledgeGraphService, GraphType, NodeType
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Database modules not available: {e}")
    DATABASE_AVAILABLE = False

STORAGE_FILE = "linker_data.json"
DATABASE_FILE = "linker_mind.db"


class LinkerMind:
    """
    Main application class that orchestrates content processing and new database features
    """

    def __init__(self, storage_file: str = STORAGE_FILE, enable_ai: bool = True, db_path: str = DATABASE_FILE):
        """
        Initialize Linker Mind v2.0

        Args:
            storage_file: Path to JSON storage file (legacy)
            enable_ai: Whether to enable AI analysis
            db_path: Path to SQLite database
        """
        self.storage_file = storage_file
        self.enable_ai = enable_ai
        self.db_path = db_path

        # Initialize legacy components
        self.detector = URLDetector()
        self.processor_factory = ProcessorFactory.create_default()
        self.analyzer = AIAnalyzer() if enable_ai else None
        self.storage = StorageManager(storage_file)

        # Initialize new database services
        if DATABASE_AVAILABLE:
            # Ensure database is initialized
            if not Path(db_path).exists():
                init_database(db_path)

            # Initialize services
            self.content_repo = ContentRepository(db_path)
            self.inbox_service = InboxService(db_path)
            self.node_service = NodeService(db_path)
            self.summary_service = ProgressiveSummaryService(db_path)
            self.link_service = LinkService(db_path)
            self.creation_service = CreationWorkshopService(db_path)
            self.search_service = EnhancedSearchService(db_path)
            self.session_service = LearningSessionService(db_path)
            self.graph_service = KnowledgeGraphService(db_path)
        else:
            self.content_repo = None
            self.inbox_service = None
            self.node_service = None
            self.summary_service = None
            self.link_service = None
            self.creation_service = None
            self.search_service = None
            self.session_service = None
            self.graph_service = None

        # MCP tool references (injected if available)
        self._web_reader_func = None
        self._video_analyzer_func = None

    def set_mcp_tools(self, web_reader_func=None, video_analyzer_func=None):
        """
        Set MCP tool functions for enhanced processing

        Args:
            web_reader_func: MCP webReader function
            video_analyzer_func: MCP analyze_video function
        """
        self._web_reader_func = web_reader_func
        self._video_analyzer_func = video_analyzer_func

    def process(self, user_input: str) -> Optional[ProcessedContent]:
        """
        Process user input (URL or text)

        Args:
            user_input: URL or text content to process

        Returns:
            ProcessedContent if successful, None otherwise
        """
        print(f"\n{'='*60}")
        print(f"🔍 Processing: {user_input[:80]}...")
        print(f"{'='*60}\n")

        try:
            # Detect input type
            if user_input.startswith(("http://", "https://")):
                url_info = self.detector.detect(user_input)
                print(f"📌 Detected Type: {url_info.url_type.value.upper()}")
                print(f"📌 Platform: {url_info.platform}")

                content = self._process_url(url_info)
            else:
                print(f"📝 Processing as text note...")
                content = self._process_text(user_input)

            if not content:
                print("❌ Processing failed")
                return None

            # Run AI analysis if enabled
            if self.analyzer:
                print(f"\n🤖 Running AI analysis...")
                content = self.analyzer.analyze(content)

            # Save to storage
            self.storage.save(content)

            # Print summary
            self._print_summary(content)

            return content

        except Exception as e:
            print(f"❌ Error during processing: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_url(self, url_info: URLInfo) -> Optional[ProcessedContent]:
        """
        Process a URL with the appropriate processor

        Args:
            url_info: URL information from detector

        Returns:
            ProcessedContent if successful
        """
        processor = self.processor_factory.get_processor(url_info)

        print(f"⚙️  Using processor: {processor.__class__.__name__}")

        # Inject MCP tools for specialized processors
        if isinstance(processor, SocialMediaProcessor) and self._web_reader_func:
            return processor.extract(url_info, web_reader_func=self._web_reader_func)
        elif isinstance(processor, VideoProcessor) and self._video_analyzer_func:
            return processor.extract(url_info, video_analyzer_func=self._video_analyzer_func)
        elif isinstance(processor, TextMemoProcessor):
            # TextMemoProcessor expects a string, not URLInfo
            return processor.extract(url_info.url)
        else:
            # For TwitterProcessor, inject web_reader_func if available
            if processor.__class__.__name__ == "TwitterProcessor" and self._web_reader_func:
                processor.web_reader_func = self._web_reader_func
            # For DouyinProcessor, inject web_reader_func if available
            if processor.__class__.__name__ == "DouyinProcessor" and self._web_reader_func:
                processor.set_mcp_tools(self._web_reader_func)
            return processor.extract(url_info)

    def _process_text(self, text: str) -> Optional[ProcessedContent]:
        """
        Process plain text input

        Args:
            text: Text content to process

        Returns:
            ProcessedContent if successful
        """
        processor = TextMemoProcessor()
        return processor.extract(text)

    def _print_summary(self, content: ProcessedContent):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print(f"✅ Processing Complete!")
        print(f"{'='*60}")
        print(f"🆔 ID: {content.id}")
        print(f"📅 Time: {content.timestamp}")
        print(f"📌 Type: {content.source_type} ({content.platform})")

        if content.content.get("title"):
            print(f"📌 Title: {content.content['title']}")

        if content.content.get("summary"):
            summary = content.content["summary"]
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"📝 Summary: {summary}")

        if content.ai_analysis.get("key_points"):
            print(f"\n💡 Key Points:")
            for i, point in enumerate(content.ai_analysis["key_points"][:3], 1):
                print(f"   {i}. {point}")

        if content.ai_analysis.get("topics"):
            topics_str = ", ".join(content.ai_analysis["topics"][:5])
            print(f"\n🏷️  Topics: {topics_str}")

        if content.ai_analysis.get("sentiment"):
            sentiment = content.ai_analysis["sentiment"]
            emoji = {"positive": "😊", "neutral": "😐", "negative": "😟", "unknown": "❓"}
            print(f"😊 Sentiment: {sentiment} {emoji.get(sentiment, '')}")

        proc_time = content.processing_info.get("processing_time", 0)
        if proc_time > 0:
            print(f"\n⏱️  Processing time: {proc_time:.2f}s")

        print(f"{'='*60}\n")

    def search(self, query: str) -> list[dict]:
        """
        Search stored content (legacy - using JSON storage)

        Args:
            query: Search query

        Returns:
            List of matching items
        """
        print(f"\n🔍 Searching for: {query}")

        # Use enhanced search if available, otherwise use legacy
        if self.search_service:
            search_query = SearchQuery(query=query, limit=50)
            search_results = self.search_service.search(search_query)
            print(f"📊 Found {len(search_results)} result(s)\n")

            for i, result in enumerate(search_results[:20], 1):
                print(f"{i}. [{result.id}] {result.title}")
                print(f"   Type: {result.source_type} | Platform: {result.platform}")
                if result.summary:
                    summary = result.summary[:100] if result.summary else ""
                    print(f"   {summary}...")
                print()

            return [r.to_dict() for r in search_results]
        else:
            # Legacy search
            results = self.storage.search(query)

            print(f"📊 Found {len(results)} result(s)\n")

            for i, item in enumerate(results, 1):
                # Extract title (handle both old and new formats)
                title = item.get("title", "")
                if not title:
                    content_val = item.get('content', {})
                    if isinstance(content_val, dict):
                        title = content_val.get('title', 'No title')
                    else:
                        title = 'No title'

                # Extract summary (handle both old and new formats)
                summary = ""
                content_val = item.get('content', {})
                if isinstance(content_val, dict):
                    summary = content_val.get('summary', '')[:100]
                else:
                    summary = str(content_val)[:100]

                print(f"{i}. [{item.get('id')}] {title}")
                print(f"   Type: {item.get('source_type')} | Platform: {item.get('platform', 'unknown')}")
                if summary:
                    print(f"   {summary}...")
                print()

            return results

    def show_stats(self):
        """Display storage statistics"""
        # Use database stats if available, otherwise legacy
        if self.content_repo:
            stats = self.content_repo.get_statistics()

            print(f"\n{'='*60}")
            print(f"📊 Linker Mind Statistics (v2.0)")
            print(f"{'='*60}")
            print(f"📁 Total Items: {stats['total']}")
            print(f"\n📊 By Source Type:")
            for source_type, count in stats['by_source_type'].items():
                print(f"   {source_type}: {count}")

            print(f"\n📊 By Content Type:")
            for content_type, count in stats['by_content_type'].items():
                print(f"   {content_type}: {count}")

            print(f"\n⭐ Favorited: {stats['favorited']}")
            print(f"🖼️  With Media: {stats['with_media']}")
            print(f"📖 Average Progress: {stats['average_reading_progress']}%")
            print(f"🤖 With AI Analysis: {stats['with_ai_analysis']}")
            print(f"{'='*60}\n")

            # Show inbox stats if available
            if self.inbox_service:
                inbox_stats = self.inbox_service.get_stats()
                print(f"\n📥 Inbox:")
                print(f"   Pending: {inbox_stats.pending}")
                print(f"   Processed: {inbox_stats.processed}")
                print(f"   Snoozed: {inbox_stats.snoozed}")
                print(f"   Overdue: {inbox_stats.overdue}")

            # Show node stats if available
            if self.node_service:
                all_nodes = self.node_service.get_projects(active_only=True)
                all_areas = self.node_service.get_areas()
                print(f"\n📁 Organization:")
                print(f"   Active Projects: {len(all_nodes)}")
                print(f"   Areas: {len(all_areas)}")

            # Show creation project stats if available
            if self.creation_service:
                creation_stats = self.creation_service.get_statistics()
                print(f"\n🎨 Creation Projects: {creation_stats.get('total_projects', 0)}")

        else:
            # Legacy stats
            stats = self.storage.get_stats()

            print(f"\n{'='*60}")
            print(f"📊 Linker Mind Statistics")
            print(f"{'='*60}")
            print(f"📁 Total Items: {stats['total_items']}")
            print(f"\n📊 By Type:")
            for type_name, count in stats['by_type'].items():
                print(f"   {type_name}: {count}")

            print(f"\n🌐 By Platform:")
            for platform, count in stats['by_platform'].items():
                print(f"   {platform}: {count}")

            print(f"\n🖼️  With Media: {stats['with_media']}")
            print(f"⏱️  Avg Processing Time: {stats['avg_processing_time']}s")
            print(f"{'='*60}\n")

    # ==================== New v2.0 Features ====================

    def db_init(self):
        """Initialize the SQLite database"""
        if not DATABASE_AVAILABLE:
            print("❌ Database modules not available")
            return False

        print("🗄️  Initializing database...")
        success = init_database(self.db_path)
        if success:
            print(f"✅ Database initialized at: {self.db_path}")
        else:
            print("❌ Database initialization failed")
        return success

    def db_migrate(self):
        """Migrate data from JSON files to SQLite"""
        if not DATABASE_AVAILABLE:
            print("❌ Database modules not available")
            return False

        from database.migration import DataMigration

        print("📦 Starting migration from JSON to SQLite...")
        migrator = DataMigration(self.db_path, json_dir=".")

        result = migrator.migrate_all(skip_existing=True)

        print(f"\n✅ Migration complete:")
        print(f"   Contents: {result['contents_migrated']}")
        print(f"   Projects: {result['projects_migrated']}")
        print(f"   Notes: {result['notes_migrated']}")
        print(f"   Citations: {result['citations_migrated']}")
        print(f"   Progress: {result['progress_migrated']}")
        print(f"   Skills: {result['skills_migrated']}")

        if result['errors']:
            print(f"\n⚠️  Errors: {len(result['errors'])}")

        return True

    def db_reset(self):
        """Reset the database (delete and recreate)"""
        if not DATABASE_AVAILABLE:
            print("❌ Database modules not available")
            return False

        from database.connection import reset_database

        print("⚠️  This will delete all database data. Confirm? (y/N): ", end='')
        try:
            # In non-interactive mode, this will fail safely
            pass
        except:
            pass

        print("\n🗑️  Resetting database...")
        success = reset_database(self.db_path)
        if success:
            print("✅ Database reset complete")
            # Reinitialize
            self.db_init()
        else:
            print("❌ Database reset failed")
        return success

    def db_vacuum(self):
        """Vacuum the database to reclaim space"""
        if not DATABASE_AVAILABLE:
            print("❌ Database modules not available")
            return False

        print("🧹 Vacuuming database...")
        db = get_db(self.db_path)
        db.vacuum()
        print("✅ Database vacuumed")
        return True

    # ==================== Inbox Commands ====================

    def inbox_list(self, limit: int = 20):
        """List pending inbox items"""
        if not self.inbox_service:
            print("❌ Inbox service not available")
            return

        items = self.inbox_service.get_unprocessed(include_snoozed=False, limit=limit)

        print(f"\n📥 Inbox ({len(items)} pending items)")
        print("=" * 50)

        if not items:
            print("🎉 Inbox is empty!")
            return

        for i, item in enumerate(items, 1):
            priority_emoji = "🔴" if item.priority >= 8 else "🟡" if item.priority >= 5 else "⚪"
            tags_str = ", ".join(item.quick_tags[:3]) if item.quick_tags else ""

            print(f"\n{i}. {priority_emoji} [{item.id}]")
            print(f"   {item.title or item.raw_input[:60]}")
            print(f"   Type: {item.source_type or 'unknown'} | Tags: {tags_str}")

            if item.due_date:
                print(f"   📅 Due: {item.due_date}")

        print(f"\n{'='*50}")

    def inbox_add(self, raw_input: str, **kwargs):
        """Add item to inbox"""
        if not self.inbox_service:
            print("❌ Inbox service not available")
            return

        item = self.inbox_service.add(
            raw_input=raw_input,
            source_type=kwargs.get('source_type'),
            title=kwargs.get('title'),
            url=kwargs.get('url'),
            quick_tags=kwargs.get('tags', []),
            priority=kwargs.get('priority', 0)
        )

        print(f"✅ Added to inbox: {item.id}")

    def inbox_process(self, item_id: str, action: str = "process"):
        """Process an inbox item"""
        if not self.inbox_service:
            print("❌ Inbox service not available")
            return

        action_map = {
            'process': ProcessAction.PROCESS,
            'delete': ProcessAction.DELETE,
            'snooze': ProcessAction.SNOOZE,
            'archive': ProcessAction.ARCHIVE
        }

        process_action = action_map.get(action.lower())
        if not process_action:
            print(f"❌ Unknown action: {action}")
            print(f"   Available: process, delete, snooze, archive")
            return

        success = self.inbox_service.process(item_id, process_action)

        if success:
            print(f"✅ Item processed: {action}")
        else:
            print(f"❌ Processing failed: item not found")

    # ==================== Node/Organization Commands ====================

    def node_list(self, node_type: str = "PROJECT"):
        """List organization nodes"""
        if not self.node_service:
            print("❌ Node service not available")
            return

        type_map = {
            'project': NodeType.PROJECT,
            'area': NodeType.AREA,
            'resource': NodeType.RESOURCE,
            'archive': NodeType.ARCHIVE
        }

        node_type_enum = type_map.get(node_type.lower())
        if not node_type_enum:
            print(f"❌ Unknown node type: {node_type}")
            print(f"   Available: project, area, resource, archive")
            return

        nodes = self.node_service.get_by_type(node_type_enum)

        emoji_map = {
            NodeType.PROJECT: "🚀",
            NodeType.AREA: "📁",
            NodeType.RESOURCE: "📚",
            NodeType.ARCHIVE: "📦"
        }

        print(f"\n{emoji_map.get(node_type_enum, '📁')} {node_type.capitalize()}s ({len(nodes)} items)")
        print("=" * 50)

        if not nodes:
            print(f"No {node_type} nodes found")
            return

        for node in nodes:
            status_emoji = "✅" if node.status == "COMPLETED" else "🔵"
            progress = ""

            print(f"\n{status_emoji} [{node.id}]")
            print(f"   {node.icon} {node.name}")
            if node.description:
                print(f"   📝 {node.description[:80]}")

            if node.target_date:
                print(f"   📅 Target: {node.target_date}")

            tags_str = ", ".join(node.tags[:3]) if node.tags else ""
            if tags_str:
                print(f"   🏷️  {tags_str}")

        print(f"\n{'='*50}")

    def node_create(self, node_type: str, name: str, **kwargs):
        """Create a new organization node"""
        if not self.node_service:
            print("❌ Node service not available")
            return

        type_map = {
            'project': NodeType.PROJECT,
            'area': NodeType.AREA,
            'resource': NodeType.RESOURCE,
            'archive': NodeType.ARCHIVE
        }

        node_type_enum = type_map.get(node_type.lower())
        if not node_type_enum:
            print(f"❌ Unknown node type: {node_type}")
            return

        node = self.node_service.create(
            node_type=node_type_enum,
            name=name,
            description=kwargs.get('description'),
            tags=kwargs.get('tags', []),
            target_date=kwargs.get('target_date')
        )

        print(f"✅ Created {node_type}: {node.id}")
        print(f"   Name: {node.name}")
        print(f"   Status: {node.status}")

    # ==================== Creation Commands ====================

    def creation_list(self, status: str = "active"):
        """List creation projects"""
        if not self.creation_service:
            print("❌ Creation service not available")
            return

        if status == "active":
            projects = self.creation_service.get_active_projects()
        else:
            projects = self.creation_service.get_by_status(CreationStatus(status))

        print(f"\n🎨 Creation Projects ({len(projects)} items)")
        print("=" * 50)

        if not projects:
            print("No creation projects found")
            return

        for project in projects:
            status_emoji = {
                'research': '🔬',
                'outlining': '📋',
                'drafting': '✍️',
                'editing': '✂️',
                'published': '✅'
            }.get(project.status, '📄')

            print(f"\n{status_emoji} [{project.id}]")
            print(f"   {project.title}")
            if project.brief:
                print(f"   📝 {project.brief[:80]}")

            print(f"   Type: {project.project_type} | Progress: {int(project.progress * 100)}%")

            if project.word_count_goal:
                progress_pct = project.get_word_count_progress()
                print(f"   📊 Words: {project.word_count_actual}/{project.word_count_goal} ({progress_pct}%)")

        print(f"\n{'='*50}")

    def creation_create(self, project_type: str, title: str, **kwargs):
        """Create a new creation project"""
        if not self.creation_service:
            print("❌ Creation service not available")
            return

        type_map = {
            'article': CreationType.ARTICLE,
            'video_script': CreationType.VIDEO_SCRIPT,
            'presentation': CreationType.PRESENTATION,
            'book': CreationType.BOOK,
            'course': CreationType.COURSE,
            'podcast': CreationType.PODCAST,
            'research_report': CreationType.RESEARCH_REPORT,
            'social_post': CreationType.SOCIAL_POST
        }

        creation_type_enum = type_map.get(project_type.lower())
        if not creation_type_enum:
            print(f"❌ Unknown creation type: {project_type}")
            print(f"   Available: article, video_script, presentation, book, course, podcast, research_report, social_post")
            return

        project = self.creation_service.create(
            project_type=creation_type_enum,
            title=title,
            brief=kwargs.get('brief'),
            target_date=kwargs.get('target_date'),
            word_count_goal=kwargs.get('word_count_goal')
        )

        print(f"✅ Created creation project: {project.id}")
        print(f"   Type: {project.project_type}")
        print(f"   Title: {project.title}")

    # ==================== Summary Commands ====================

    def summary_show(self, note_id: str):
        """Show progressive summary for a note"""
        if not self.summary_service:
            print("❌ Progressive summary service not available")
            return

        summary = self.summary_service.get_formatted_summary(note_id)
        if summary:
            print("\n" + summary)
        else:
            print(f"❌ Note not found: {note_id}")

    def summary_add_highlight(self, note_id: str, text: str, color: str = "yellow"):
        """Add a highlight to a note"""
        if not self.summary_service:
            print("❌ Progressive summary service not available")
            return

        color_map = {
            'yellow': HighlightColor.YELLOW,
            'orange': HighlightColor.ORANGE,
            'red': HighlightColor.RED,
            'blue': HighlightColor.BLUE,
            'green': HighlightColor.GREEN,
            'purple': HighlightColor.PURPLE
        }

        highlight_color = color_map.get(color.lower(), HighlightColor.YELLOW)

        success = self.summary_service.add_highlight(note_id, text, highlight_color)
        if success:
            print(f"✅ Highlight added to note {note_id}")
        else:
            print(f"❌ Failed to add highlight")

    # ==================== Link Commands ====================

    def link_create(self, source_id: str, target_id: str, link_type: str = "related"):
        """Create a bidirectional link"""
        if not self.link_service:
            print("❌ Link service not available")
            return

        type_map = {
            'reference': LinkType.REFERENCE,
            'related': LinkType.RELATED,
            'opposes': LinkType.OPPOSES,
            'extends': LinkType.EXTENDS,
            'example': LinkType.EXAMPLE,
            'question': LinkType.QUESTION,
            'application': LinkType.APPLICATION,
            'inspired': LinkType.INSPIRED
        }

        link_type_enum = type_map.get(link_type.lower(), LinkType.RELATED)

        # Detect entity types (default to note)
        source_type = LinkSourceType.NOTE
        target_type = LinkSourceType.NOTE

        link = self.link_service.create(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            link_type=link_type_enum
        )

        print(f"✅ Link created: {source_id} → {target_id} ({link_type})")

    def link_backlinks(self, entity_id: str):
        """Show backlinks for an entity"""
        if not self.link_service:
            print("❌ Link service not available")
            return

        backlinks = self.link_service.get_backlinks_to(entity_id, LinkSourceType.NOTE)

        print(f"\n🔗 Backlinks to {entity_id} ({len(backlinks)} items)")
        print("=" * 50)

        for i, backlink in enumerate(backlinks, 1):
            print(f"\n{i}. From: {backlink.source_id}")
            print(f"   Type: {backlink.link_type}")
            if backlink.context:
                print(f"   📝 {backlink.context[:80]}")
            print(f"   Strength: {backlink.strength:.2f}")

        if not backlinks:
            print("No backlinks found")

    # ==================== Enhanced Search Commands ====================

    def search_enhanced(self, query: str, **filters):
        """Enhanced search with filters"""
        if not self.search_service:
            print("❌ Enhanced search service not available")
            # Fall back to legacy search
            self.search(query)
            return

        search_query = SearchQuery(
            query=query,
            content_types=filters.get('content_types'),
            source_types=filters.get('source_types'),
            tags=filters.get('tags'),
            favorited_only=filters.get('favorited_only', False),
            limit=50
        )

        results = self.search_service.search(search_query)

        print(f"\n🔍 Search results for: {query}")
        print(f"📊 Found {len(results)} results")
        print("=" * 50)

        for i, result in enumerate(results[:20], 1):
            type_emoji = "📄" if result.type == 'content' else "📝"
            print(f"\n{i}. {type_emoji} [{result.id}]")
            print(f"   {result.title}")

            if result.summary:
                summary = result.summary[:100] if len(result.summary) > 100 else result.summary
                print(f"   📝 {summary}...")

            tags_str = ", ".join(result.tags[:3]) if result.tags else ""
            if tags_str:
                print(f"   🏷️  {tags_str}")

        print(f"\n{'='*50}")

    # ==================== Learning Session Commands ====================

    def learning_start(self, content_id: str):
        """Start a learning session"""
        if not self.session_service:
            print("❌ Learning session service not available")
            return

        session = self.session_service.start_session(content_id)
        print(f"✅ Started learning session: {session.id}")
        print(f"   Content: {content_id}")
        print(f"   Started: {session.started_at}")
        print(f"\n💡 Remember to end the session with:")
        print(f"   /learning end {session.id} --duration <seconds> --comprehension <1-5> --confidence <1-5>")

    def learning_end(
        self,
        session_id: str,
        duration: int,
        comprehension: int = 3,
        confidence: int = 3,
        mood: str = "calm",
        takeaways: Optional[list] = None,
        questions: Optional[list] = None,
        notes: Optional[str] = None
    ):
        """End a learning session"""
        if not self.session_service:
            print("❌ Learning session service not available")
            return

        session = self.session_service.end_session(
            session_id=session_id,
            duration=duration,
            comprehension=comprehension,
            confidence=confidence,
            mood=mood,
            key_takeaways=takeaways or [],
            questions=questions or [],
            notes=notes
        )

        if session:
            duration_formatted = self.session_service._format_duration(duration)
            print(f"✅ Ended learning session: {session_id}")
            print(f"   Duration: {duration_formatted}")
            print(f"   Comprehension: {session.comprehension}/5")
            print(f"   Confidence: {session.confidence}/5")
            print(f"   Mood: {session.mood}")

            if session.key_takeaways:
                print(f"   Takeaways: {len(session.key_takeaways)}")
            if session.questions:
                print(f"   Questions: {len(session.questions)}")
        else:
            print(f"❌ Session not found: {session_id}")

    def learning_stats(self, content_id: str):
        """Show learning statistics for content"""
        if not self.session_service:
            print("❌ Learning session service not available")
            return

        stats = self.session_service.get_learning_stats(content_id)

        print(f"\n📊 Learning Statistics for: {content_id}")
        print("=" * 50)
        print(f"   Total Sessions: {stats['total_sessions']}")
        print(f"   Total Duration: {stats['total_duration_formatted']}")
        print(f"   Avg Comprehension: {stats['avg_comprehension']}/5")
        print(f"   Avg Confidence: {stats['avg_confidence']}/5")

        if stats['last_session']:
            print(f"   Last Session: {stats['last_session']}")

        if stats['mood_distribution']:
            print(f"\n   Mood Distribution:")
            for mood, count in stats['mood_distribution'].items():
                print(f"      {mood}: {count}")

        schedule = stats.get('review_schedule', {})
        if schedule.get('next_review'):
            print(f"\n   📅 Next Review: {schedule['next_review']}")
            print(f"      Interval: {schedule['interval_days']} days")
            print(f"      Ease Factor: {schedule['ease_factor']:.2f}")

        print("=" * 50)

    def learning_reviews(self, limit: int = 20):
        """Show content due for review"""
        if not self.session_service:
            print("❌ Learning session service not available")
            return

        due_reviews = self.session_service.get_due_reviews(limit=limit)

        print(f"\n📚 Due for Review ({len(due_reviews)} items)")
        print("=" * 50)

        if not due_reviews:
            print("🎉 No reviews due!")
            return

        for i, (content_id, schedule) in enumerate(due_reviews, 1):
            overdue_days = (datetime.now() - datetime.fromisoformat(schedule.next_review)).days
            print(f"\n{i}. [{content_id}]")
            print(f"   Overdue by: {overdue_days} days")
            print(f"   Reviews: {schedule.review_count}")
            print(f"   Interval: {schedule.interval_days} days")
            print(f"   Ease Factor: {schedule.ease_factor:.2f}")

        print("=" * 50)

    def learning_schedule_review(self, content_id: str, quality: int):
        """Schedule next review after completing a review"""
        if not self.session_service:
            print("❌ Learning session service not available")
            return

        schedule = self.session_service.schedule_review(content_id, quality)

        print(f"✅ Review scheduled for: {content_id}")
        print(f"   Next review: {schedule.next_review}")
        print(f"   Interval: {schedule.interval_days} days")
        print(f"   Ease Factor: {schedule.ease_factor:.2f}")
        print(f"   Review Count: {schedule.review_count}")

    # ==================== Knowledge Graph Commands ====================

    def graph_force(self, limit: int = 100, min_weight: float = 0.1):
        """Generate force-directed graph data"""
        if not self.graph_service:
            print("❌ Knowledge graph service not available")
            return

        graph = self.graph_service.get_force_directed_graph(limit=limit, min_weight=min_weight)

        print(f"\n🕸️ Force-Directed Graph")
        print("=" * 50)
        print(f"   Nodes: {len(graph.nodes)}")
        print(f"   Edges: {len(graph.edges)}")
        print(f"   Generated: {graph.metadata.get('generated_at', 'N/A')}")

        # Show top nodes by importance
        top_nodes = sorted(graph.nodes, key=lambda n: n.size, reverse=True)[:10]
        print(f"\n   Top Nodes by Importance:")
        for i, node in enumerate(top_nodes, 1):
            print(f"      {i}. {node.label[:50]} (size: {node.size:.2f})")

        print(f"\n💾 Export with: /graph export force <filename>")

    def graph_timeline(self, days: int = 30):
        """Show timeline of content"""
        if not self.graph_service:
            print("❌ Knowledge graph service not available")
            return

        timeline = self.graph_service.get_timeline(days=days)

        print(f"\n📅 Timeline ({days} days)")
        print("=" * 50)
        print(f"   Days with activity: {len(timeline)}")

        for day_entry in timeline[:10]:
            print(f"\n   {day_entry['date']} ({day_entry['count']} items):")
            for item in day_entry['items'][:3]:
                print(f"      - {item['title'][:50]}")

    def graph_clusters(self, min_size: int = 3):
        """Show topic clusters"""
        if not self.graph_service:
            print("❌ Knowledge graph service not available")
            return

        clusters = self.graph_service.get_topic_clusters(min_cluster_size=min_size)

        print(f"\n🔗 Topic Clusters (min size: {min_size})")
        print("=" * 50)
        print(f"   Found {len(clusters)} clusters")

        for i, cluster in enumerate(clusters[:10], 1):
            print(f"\n{i}. Cluster ({cluster['content_count']} items):")
            print(f"   Topics: {', '.join(cluster['topics'][:5])}")

    def graph_stats(self):
        """Show graph statistics"""
        if not self.graph_service:
            print("❌ Knowledge graph service not available")
            return

        stats = self.graph_service.get_statistics()

        print(f"\n📊 Knowledge Graph Statistics")
        print("=" * 50)
        print(f"   Total Nodes: {stats['total_nodes']}")
        print(f"   ├─ Content: {stats['content_nodes']}")
        print(f"   ├─ Notes: {stats['note_nodes']}")
        print(f"   └─ Skills: {stats['skill_nodes']}")
        print(f"\n   Total Edges: {stats['total_edges']}")
        print(f"   Avg Connections: {stats['avg_connections']}")

        if stats['most_connected']:
            print(f"\n   Most Connected Nodes:")
            for i, node in enumerate(stats['most_connected'][:5], 1):
                print(f"      {i}. {node['source_id']} ({node['connection_count']} connections)")

    def graph_connections(self, node_id: str, depth: int = 2):
        """Show local graph around a node"""
        if not self.graph_service:
            print("❌ Knowledge graph service not available")
            return

        graph = self.graph_service.get_node_connections(node_id=node_id, depth=depth)

        print(f"\n🕸️ Local Graph for: {node_id}")
        print("=" * 50)
        print(f"   Nodes: {len(graph.nodes)}")
        print(f"   Edges: {len(graph.edges)}")
        print(f"   Depth: {depth}")

        # Show connected nodes
        center = graph.nodes[0] if graph.nodes else None
        if center and center.id == node_id:
            print(f"\n   Center: {center.label}")

        other_nodes = [n for n in graph.nodes if n.id != node_id]
        if other_nodes:
            print(f"\n   Connected Nodes:")
            for node in other_nodes[:10]:
                print(f"      - {node.label[:50]}")

    # ==================== Stats Command (Enhanced) ====================

    def interactive_mode(self):
        """Run in interactive CLI mode"""
        print(f"\n{'='*60}")
        print(f"🧠 Linker Mind v2.0 - Interactive Mode")
        print(f"{'='*60}")
        print(f"Commands:")
        print(f"  <URL or text>  - Process content")
        print(f"\n📌 Content Commands:")
        print(f"  /search <query> - Search stored content")
        print(f"  /stats          - Show statistics")
        print(f"\n📥 Inbox Commands:")
        print(f"  /inbox list    - List inbox items")
        print(f"  /inbox add     - Add to inbox")
        print(f"  /inbox process <id> [action] - Process inbox item")
        print(f"\n📁 Organization (PARA):")
        print(f"  /node list [type] - List nodes (project/area/resource/archive)")
        print(f"  /node create <type> <name> - Create node")
        print(f"\n🎨 Creation:")
        print(f"  /creation list - List creation projects")
        print(f"  /creation create <type> <title> - Create project")
        print(f"\n🧠 Smart Features:")
        print(f"  /link create <from> <to> [type] - Create link")
        print(f"  /link backlinks <id> - Show backlinks")
        print(f"  /summary show <id> - Show progressive summary")
        print(f"\n📚 Learning & Reviews:")
        print(f"  /learning start <content_id> - Start learning session")
        print(f"  /learning end <session_id> --duration <s> --comprehension <1-5> - End session")
        print(f"  /learning stats <content_id> - Show learning statistics")
        print(f"  /learning reviews - Show due reviews")
        print(f"\n🕸️ Knowledge Graph:")
        print(f"  /graph force - Show force-directed graph")
        print(f"  /graph timeline [days] - Show timeline")
        print(f"  /graph clusters - Show topic clusters")
        print(f"  /graph connections <node_id> - Show local graph")
        print(f"  /graph stats - Show graph statistics")
        print(f"\n🗄️ Database:")
        print(f"  /db init      - Initialize database")
        print(f"  /db migrate   - Migrate from JSON")
        print(f"  /db vacuum    - Vacuum database")
        print(f"  /db reset     - Reset database")
        print(f"\n📖 Help:")
        print(f"  /help           - Show detailed help")
        print(f"  /quit or /exit  - Exit")
        print(f"{'='*60}\n")

        while True:
            try:
                user_input = input("linker> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == "/help":
                    self._show_help()
                    continue

                if user_input.lower() == "/stats":
                    self.show_stats()
                    continue

                if user_input.lower().startswith("/search "):
                    query = user_input[8:].strip()
                    if query:
                        self.search(query)
                    continue

                # Handle space-separated commands
                parts = user_input.split()
                command = parts[0].lower()
                args = parts[1:]

                if command == "/db":
                    if len(args) >= 1:
                        db_command = args[0]

                        if db_command == "init":
                            self.db_init()
                        elif db_command == "migrate":
                            self.db_migrate()
                        elif db_command == "reset":
                            self.db_reset()
                        elif db_command == "vacuum":
                            self.db_vacuum()
                        else:
                            print(f"❌ Unknown db command: {db_command}")
                            print("   Available: init, migrate, reset, vacuum")

                elif command == "/inbox":
                    if len(args) >= 1:
                        inbox_command = args[0]

                        if inbox_command == "list":
                            self.inbox_list()
                        elif inbox_command == "add":
                            if len(args) >= 2:
                                self.inbox_add(args[1])
                            else:
                                print("Usage: /inbox add <raw_input>")
                        elif inbox_command == "process":
                            if len(args) >= 2:
                                action = args[1] if len(args) >= 3 else "process"
                                self.inbox_process(args[1], action)
                            else:
                                print("Usage: /inbox process <item_id> [action]")
                        else:
                            print("❌ Unknown inbox command")
                            print("   Available: list, add, process")

                elif command == "/node":
                    if len(args) >= 1:
                        node_command = args[0]

                        if node_command == "list":
                            node_type = args[1] if len(args) >= 2 else "project"
                            self.node_list(node_type)
                        elif node_command == "create":
                            if len(args) >= 3:
                                node_type = args[0]
                                name = ' '.join(args[1:-1])  # Rejoin name parts
                                self.node_create(node_type, name)
                            else:
                                print("Usage: /node create <type> <name>")
                        else:
                            print("❌ Unknown node command")
                            print("   Available: list, create")

                elif command == "/creation":
                    if len(args) >= 1:
                        creation_command = args[0]

                        if creation_command == "list":
                            status = args[1] if len(args) >= 2 else "active"
                            self.creation_list(status)
                        elif creation_command == "create":
                            if len(args) >= 3:
                                creation_type = args[0]
                                title = ' '.join(args[1:-1])  # Rejoin title parts
                                self.creation_create(creation_type, title)
                            else:
                                print("Usage: /creation create <type> <title>")
                        else:
                            print("❌ Unknown creation command")
                            print("   Available: list, create")

                elif command == "/link":
                    if len(args) >= 2:
                        if args[0] == "create" and len(args) >= 3:
                            source_id = args[1]
                            target_id = args[2]
                            link_type = args[3] if len(args) >= 4 else "related"
                            self.link_create(source_id, target_id, link_type)
                        elif args[0] == "backlinks" and len(args) >= 2:
                            self.link_backlinks(args[1])
                        else:
                            print("Usage: /link create <from> <to> [type]")
                            print("        /link backlinks <id>")
                    else:
                        print("Usage: /link create <from> <to> [type]")
                        print("        /link backlinks <id>")

                elif command == "/summary":
                    if len(args) >= 1:
                        summary_command = args[0]

                        if summary_command == "show":
                            if len(args) >= 2:
                                self.summary_show(args[1])
                            else:
                                print("Usage: /summary show <note_id>")
                        elif summary_command == "highlight" and len(args) >= 3:
                            note_id = args[1]
                            text = args[2]
                            color = args[3] if len(args) >= 4 else "yellow"
                            self.summary_add_highlight(note_id, text, color)
                        else:
                            print("Usage: /summary show <note_id>")
                            print("        /summary highlight <note_id> <text> [color]")
                    else:
                        print("Usage: /summary show <note_id>")

                elif command == "/learning":
                    if len(args) >= 1:
                        learning_command = args[0]

                        if learning_command == "start" and len(args) >= 2:
                            self.learning_start(args[1])
                        elif learning_command == "end" and len(args) >= 2:
                            # Parse session_id and optional flags
                            session_id = args[1]
                            duration = 0
                            comprehension = 3
                            confidence = 3
                            mood = "calm"

                            # Simple parsing for --key value pairs
                            i = 2
                            while i < len(args):
                                if args[i] == "--duration" and i + 1 < len(args):
                                    duration = int(args[i + 1])
                                    i += 2
                                elif args[i] == "--comprehension" and i + 1 < len(args):
                                    comprehension = int(args[i + 1])
                                    i += 2
                                elif args[i] == "--confidence" and i + 1 < len(args):
                                    confidence = int(args[i + 1])
                                    i += 2
                                elif args[i] == "--mood" and i + 1 < len(args):
                                    mood = args[i + 1]
                                    i += 2
                                else:
                                    i += 1

                            if duration > 0:
                                self.learning_end(session_id, duration, comprehension, confidence, mood)
                            else:
                                print("Error: --duration required for end command")
                        elif learning_command == "stats" and len(args) >= 2:
                            self.learning_stats(args[1])
                        elif learning_command == "reviews":
                            self.learning_reviews()
                        else:
                            print("Usage: /learning start <content_id>")
                            print("        /learning end <session_id> --duration <s> [--comprehension <1-5>] [--confidence <1-5>]")
                            print("        /learning stats <content_id>")
                            print("        /learning reviews")
                    else:
                        print("Usage: /learning start|end|stats|reviews ...")

                elif command == "/graph":
                    if len(args) >= 1:
                        graph_command = args[0]

                        if graph_command == "force":
                            limit = 100
                            # Parse optional limit
                            if len(args) >= 2 and args[1].isdigit():
                                limit = int(args[1])
                            self.graph_force(limit=limit)

                        elif graph_command == "timeline":
                            days = 30
                            if len(args) >= 2 and args[1].isdigit():
                                days = int(args[1])
                            self.graph_timeline(days=days)

                        elif graph_command == "clusters":
                            min_size = 3
                            if len(args) >= 2 and args[1].isdigit():
                                min_size = int(args[1])
                            self.graph_clusters(min_size=min_size)

                        elif graph_command == "stats":
                            self.graph_stats()

                        elif graph_command == "connections" and len(args) >= 2:
                            depth = 2
                            if len(args) >= 3 and args[2].isdigit():
                                depth = int(args[2])
                            self.graph_connections(args[1], depth=depth)

                        else:
                            print("Usage: /graph force [limit]")
                            print("        /graph timeline [days]")
                            print("        /graph clusters [min_size]")
                            print("        /graph connections <node_id> [depth]")
                            print("        /graph stats")
                    else:
                        print("Usage: /graph force|timeline|clusters|connections|stats ...")

                # Process as URL or text
                else:
                    self.process(user_input)

            except KeyboardInterrupt:
                print(f"\n\n👋 Interrupted. Use /quit to exit.")
            except EOFError:
                print(f"\n👋 Goodbye!")
                break

    @staticmethod
    def _show_help():
        """Display help information"""
        print(f"\n{'='*60}")
        print(f"📖 Linker Mind v2.0 Help")
        print(f"{'='*60}")
        print(f"\n🌐 Supported URL Types:")
        print(f"   • Web pages        - https://example.com")
        print(f"   • Twitter/X        - https://twitter.com/user/status/123")
        print(f"   • WeChat Articles  - https://mp.weixin.qq.com/s/...")
        print(f"   • Douyin           - https://www.douyin.com/video/...")
        print(f"   • YouTube          - https://youtube.com/watch?v=...")
        print(f"   • Bilibili         - https://bilibili.com/video/...")
        print(f"   • Direct Videos    - https://example.com/video.mp4")
        print(f"\n📝 Text Notes:")
        print(f"   Simply type any text to save as a note")
        print(f"\n🗄️ Database Commands:")
        print(f"   /db init       - Initialize SQLite database")
        print(f"   /db migrate    - Migrate data from JSON to SQLite")
        print(f"   /db vacuum    - Optimize database")
        print(f"   /db reset      - Reset database (CAUTION: deletes all data)")
        print(f"\n📥 Inbox Commands:")
        print(f"   /inbox list                    - List pending items")
        print(f"   /inbox add <url or text>       - Add to inbox")
        print(f"   /inbox process <id> [action]    - Process (process|delete|snooze|archive)")
        print(f"\n📁 Organization (PARA):")
        print(f"   /node list [type]              - List nodes (project|area|resource|archive)")
        print(f"   /node create <type> <name>       - Create node")
        print(f"                                   Types: project, area, resource, archive")
        print(f"\n🎨 Creation Projects:")
        print(f"   /creation list [status]          - List projects")
        print(f"   /creation create <type> <title>    - Create creation project")
        print(f"                                      Types: article, video_script, presentation, book, course, etc.")
        print(f"\n🔗 Bidirectional Links:")
        print(f"   /link create <from> <to> [type]  - Create link between items")
        print(f"   /link backlinks <id>            - Show all links pointing to an item")
        print(f"   Types: reference, related, opposes, extends, example, question, application, inspired")
        print(f"\n🧠 Progressive Summarization:")
        print(f"   /summary show <note_id>           - Show progressive summary")
        print(f"   /summary highlight <id> <text> [color] - Add highlight")
        print(f"   Colors: yellow, orange, red, blue, green, purple")
        print(f"\n📚 Learning & Reviews:")
        print(f"   /learning start <content_id>      - Start a learning session")
        print(f"   /learning end <id> --duration <s> --comprehension <1-5> - End session")
        print(f"   /learning stats <content_id>       - Show learning statistics")
        print(f"   /learning reviews                  - Show content due for review")
        print(f"\n🕸️ Knowledge Graph:")
        print(f"   /graph force [limit]               - Generate force-directed graph data")
        print(f"   /graph timeline [days]             - Show content timeline")
        print(f"   /graph clusters [min_size]         - Show topic clusters")
        print(f"   /graph connections <node_id> [depth] - Show local graph around node")
        print(f"   /graph stats                       - Show graph statistics")
        print(f"\n🔍 Enhanced Search:")
        print(f"   /search <query>                - Full-text search with FTS")
        print(f"\n💾 Data Storage:")
        print(f"   JSON: {STORAGE_FILE}")
        if DATABASE_AVAILABLE:
            print(f"   SQLite: {DATABASE_FILE}")
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Linker Mind v2.0 - Second brain and creative workspace system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Interactive mode
  python main.py --url <URL>              # Process a URL
  python main.py --search <query>         # Search content
  python main.py --stats                  # Show statistics

  # Database operations
  python main.py --db init                # Initialize database
  python main.py --db migrate             # Migrate from JSON
  python main.py --db vacuum              # Vacuum database
  python main.py --db reset               # Reset database

  # Inbox management
  python main.py --inbox list             # List inbox items
  python main.py --inbox add <text>       # Add to inbox

  # Organization (PARA)
  python main.py --node list project      # List projects
  python main.py --node create project "My Project"  # Create node

  # Creation projects
  python main.py --creation list          # List creation projects
  python main.py --creation create article "My Article"  # Create project
        """
    )

    # Legacy content processing arguments
    parser.add_argument("--url", "-u", help="URL to process")
    parser.add_argument("--text", "-t", help="Text content to process")
    parser.add_argument("--search", "-s", help="Search stored content")
    parser.add_argument("--stats", action="store_true", help="Show storage statistics")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI analysis")

    # Database arguments
    db_parser = parser.add_argument_group("Database Operations")
    db_parser.add_argument("--db", choices=['init', 'migrate', 'reset', 'vacuum'],
                          help="Database operations")

    # Inbox arguments
    inbox_parser = parser.add_argument_group("Inbox Management")
    inbox_parser.add_argument("--inbox", nargs='?', const='list',
                             choices=['list', 'add', 'process'],
                             help="Inbox management (list, add, process)")
    inbox_parser.add_argument("--inbox-id", help="Inbox item ID (for process command)")
    inbox_parser.add_argument("--inbox-action", default='process',
                             choices=['process', 'delete', 'snooze', 'archive'],
                             help="Action for inbox process command")
    inbox_parser.add_argument("--inbox-raw", help="Raw input for inbox add")

    # Node/Organization arguments
    node_parser = parser.add_argument_group("Organization (PARA)")
    node_parser.add_argument("--node", choices=['list', 'create'],
                            help="Node operations")
    node_parser.add_argument("--node-type",
                            choices=['project', 'area', 'resource', 'archive'],
                            default='project',
                            help="Node type (for list/create)")
    node_parser.add_argument("--node-name", help="Node name (for create)")
    node_parser.add_argument("--node-desc", help="Node description (for create)")
    node_parser.add_argument("--node-tags", nargs='*', help="Node tags (for create)")
    node_parser.add_argument("--node-date", help="Target date (for create)")

    # Creation arguments
    creation_parser = parser.add_argument_group("Creation Projects")
    creation_parser.add_argument("--creation", nargs='?', const='list',
                                choices=['list', 'create'],
                                help="Creation project operations")
    creation_parser.add_argument("--creation-type",
                                choices=['article', 'video_script', 'presentation', 'book',
                                        'course', 'podcast', 'research_report', 'social_post'],
                                default='article',
                                help="Creation project type (for create)")
    creation_parser.add_argument("--creation-title", help="Creation project title (for create)")
    creation_parser.add_argument("--creation-brief", help="Creation project brief (for create)")
    creation_parser.add_argument("--creation-target-date", help="Target date (for create)")
    creation_parser.add_argument("--creation-words", type=int, help="Word count goal (for create)")
    creation_parser.add_argument("--creation-status",
                                choices=['research', 'outlining', 'drafting', 'editing',
                                        'reviewing', 'finalizing', 'published'],
                                help="Status filter (for list)")

    # Link arguments
    link_parser = parser.add_argument_group("Bidirectional Links")
    link_parser.add_argument("--link", choices=['create', 'backlinks'],
                            help="Link operations")
    link_parser.add_argument("--link-from", help="Source ID (for create)")
    link_parser.add_argument("--link-to", help="Target ID (for create)")
    link_parser.add_argument("--link-type",
                            choices=['reference', 'related', 'opposes', 'extends',
                                    'example', 'question', 'application', 'inspired'],
                            default='related',
                            help="Link type (for create)")
    link_parser.add_argument("--link-id", help="Entity ID (for backlinks)")

    # Summary arguments
    summary_parser = parser.add_argument_group("Progressive Summarization")
    summary_parser.add_argument("--summary", choices=['show', 'highlight'],
                               help="Summary operations")
    summary_parser.add_argument("--summary-id", help="Note ID")
    summary_parser.add_argument("--summary-text", help="Highlight text")
    summary_parser.add_argument("--summary-color",
                               choices=['yellow', 'orange', 'red', 'blue', 'green', 'purple'],
                               default='yellow',
                               help="Highlight color")

    # Learning arguments
    learning_parser = parser.add_argument_group("Learning & Reviews")
    learning_parser.add_argument("--learning", nargs='?', const='reviews',
                                choices=['start', 'end', 'stats', 'reviews'],
                                help="Learning session operations")
    learning_parser.add_argument("--learning-content-id", help="Content ID (for start/stats)")
    learning_parser.add_argument("--learning-session-id", help="Session ID (for end)")
    learning_parser.add_argument("--learning-duration", type=int, help="Duration in seconds (for end)")
    learning_parser.add_argument("--learning-comprehension", type=int, choices=range(1, 6),
                                default=3, help="Comprehension 1-5 (for end)")
    learning_parser.add_argument("--learning-confidence", type=int, choices=range(1, 6),
                                default=3, help="Confidence 1-5 (for end)")
    learning_parser.add_argument("--learning-mood",
                                choices=['focused', 'curious', 'confused', 'frustrated',
                                        'bored', 'excited', 'calm', 'anxious'],
                                default='calm', help="Learning mood (for end)")
    learning_parser.add_argument("--learning-review-quality", type=int, choices=range(0, 6),
                                help="Review quality 0-5 (for scheduling next review)")

    # Graph arguments
    graph_parser = parser.add_argument_group("Knowledge Graph")
    graph_parser.add_argument("--graph", nargs='?', const='stats',
                             choices=['force', 'timeline', 'clusters', 'stats', 'connections'],
                             help="Graph visualization operations")
    graph_parser.add_argument("--graph-limit", type=int, default=100,
                             help="Limit for graph operations")
    graph_parser.add_argument("--graph-days", type=int, default=30,
                             help="Days for timeline")
    graph_parser.add_argument("--graph-min-size", type=int, default=3,
                             help="Minimum cluster size")
    graph_parser.add_argument("--graph-node-id", help="Node ID (for connections)")
    graph_parser.add_argument("--graph-depth", type=int, default=2,
                             help="Depth for connections")

    args = parser.parse_args()

    # Initialize application
    app = LinkerMind(enable_ai=not args.no_ai)

    # Route to appropriate command
    # Priority: Database > Inbox > Node > Creation > Link > Summary > Legacy

    # Database commands
    if args.db:
        if args.db == 'init':
            app.db_init()
        elif args.db == 'migrate':
            app.db_migrate()
        elif args.db == 'reset':
            app.db_reset()
        elif args.db == 'vacuum':
            app.db_vacuum()
        return

    # Inbox commands
    if args.inbox:
        if args.inbox == 'list':
            app.inbox_list()
        elif args.inbox == 'add':
            if args.inbox_raw:
                app.inbox_add(args.inbox_raw)
            else:
                print("Error: --inbox-raw required for add command")
        elif args.inbox == 'process':
            if args.inbox_id:
                app.inbox_process(args.inbox_id, args.inbox_action)
            else:
                print("Error: --inbox-id required for process command")
        return

    # Node commands
    if args.node:
        if args.node == 'list':
            app.node_list(args.node_type)
        elif args.node == 'create':
            if args.node_name:
                app.node_create(
                    node_type=args.node_type,
                    name=args.node_name,
                    description=args.node_desc,
                    tags=args.node_tags or [],
                    target_date=args.node_date
                )
            else:
                print("Error: --node-name required for create command")
        return

    # Creation commands
    if args.creation:
        if args.creation == 'list':
            app.creation_list(args.creation_status or 'active')
        elif args.creation == 'create':
            if args.creation_title:
                app.creation_create(
                    project_type=args.creation_type,
                    title=args.creation_title,
                    brief=args.creation_brief,
                    target_date=args.creation_target_date,
                    word_count_goal=args.creation_words
                )
            else:
                print("Error: --creation-title required for create command")
        return

    # Link commands
    if args.link:
        if args.link == 'create':
            if args.link_from and args.link_to:
                app.link_create(args.link_from, args.link_to, args.link_type)
            else:
                print("Error: --link-from and --link-to required for create command")
        elif args.link == 'backlinks':
            if args.link_id:
                app.link_backlinks(args.link_id)
            else:
                print("Error: --link-id required for backlinks command")
        return

    # Summary commands
    if args.summary:
        if args.summary == 'show':
            if args.summary_id:
                app.summary_show(args.summary_id)
            else:
                print("Error: --summary-id required for show command")
        elif args.summary == 'highlight':
            if args.summary_id and args.summary_text:
                app.summary_add_highlight(args.summary_id, args.summary_text, args.summary_color)
            else:
                print("Error: --summary-id and --summary-text required for highlight command")
        return

    # Learning commands
    if args.learning:
        if args.learning == 'start':
            if args.learning_content_id:
                app.learning_start(args.learning_content_id)
            else:
                print("Error: --learning-content-id required for start command")
        elif args.learning == 'end':
            if args.learning_session_id and args.learning_duration:
                app.learning_end(
                    session_id=args.learning_session_id,
                    duration=args.learning_duration,
                    comprehension=args.learning_comprehension,
                    confidence=args.learning_confidence,
                    mood=args.learning_mood
                )
            else:
                print("Error: --learning-session-id and --learning-duration required for end command")
        elif args.learning == 'stats':
            if args.learning_content_id:
                app.learning_stats(args.learning_content_id)
            else:
                print("Error: --learning-content-id required for stats command")
        elif args.learning == 'reviews':
            app.learning_reviews()
        return

    # Graph commands
    if args.graph:
        if args.graph == 'force':
            app.graph_force(limit=args.graph_limit)
        elif args.graph == 'timeline':
            app.graph_timeline(days=args.graph_days)
        elif args.graph == 'clusters':
            app.graph_clusters(min_size=args.graph_min_size)
        elif args.graph == 'stats':
            app.graph_stats()
        elif args.graph == 'connections':
            if args.graph_node_id:
                app.graph_connections(args.graph_node_id, depth=args.graph_depth)
            else:
                print("Error: --graph-node-id required for connections command")
        return

    # Legacy commands
    if args.interactive:
        app.interactive_mode()
    elif args.stats:
        app.show_stats()
    elif args.search:
        app.search(args.search)
    elif args.url:
        app.process(args.url)
    elif args.text:
        app.process(args.text)
    else:
        # Default: interactive mode
        app.interactive_mode()


if __name__ == "__main__":
    main()
