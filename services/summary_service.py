"""
Progressive Summarization Service Module - Andy Matuschak's method

This module implements progressive summarization for notes:
- Layer 0: Original content
- Layer 1: Highlights (colored text)
- Layer 2: Bolded key points
- Layer 3: Supernotes (best highlights, marked with distinct style)
- Layer 4: Own words (summary in your own words)
- Layer 5: New insights (connections and new thoughts)

Features:
- Add highlights with color coding
- Create layered summaries
- Track summary progress
- Extract best-of highlights
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database import json_dumps, json_list, json_dict

logger = logging.getLogger(__name__)


class HighlightColor(Enum):
    """Highlight colors for progressive summarization"""
    YELLOW = "yellow"      # General highlights
    ORANGE = "orange"      # Important
    RED = "red"           # Very important
    BLUE = "blue"         # Personal thoughts
    GREEN = "green"       # Action items
    PURPLE = "purple"     # Quotes to remember


class SummaryLayer(Enum):
    """Progressive summarization layers"""
    ORIGINAL = 0       # Original content
    HIGHLIGHTS = 1     # Highlighted text
    BOLDED = 2         # Bolded key points
    SUPERNOTES = 3     # Best highlights (supernotes)
    OWN_WORDS = 4      # Summary in own words
    INSIGHTS = 5       # New insights and connections


@dataclass
class Highlight:
    """A highlighted text segment"""
    text: str
    color: str
    position: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SummaryLayer:
    """A layer in progressive summarization"""
    layer: int
    content: str
    highlights: List[Highlight]
    bolded_text: List[str]
    supernotes: List[str]
    own_words: List[str]
    insights: List[str]
    created_at: str
    updated_at: str


@dataclass
class NoteSummary:
    """Progressive summary for a note"""
    note_id: str
    content_id: Optional[str]
    current_layer: int
    highlights: List[Highlight]
    bolded_text: List[str]
    supernotes: List[str]
    own_words: List[str]
    insights: List[str]

    def get_best_highlights(self, limit: int = 5) -> List[Highlight]:
        """Get the best highlights (red and orange colored)"""
        best_colors = [HighlightColor.RED.value, HighlightColor.ORANGE.value]
        best = [h for h in self.highlights if h.color in best_colors]
        return sorted(best, key=lambda h: h.text)[:limit]

    def get_all_highlights_by_color(self, color: HighlightColor) -> List[Highlight]:
        """Get all highlights of a specific color"""
        return [h for h in self.highlights if h.color == color.value]


class ProgressiveSummaryService:
    """
    Service for managing progressive summarization

    Implements Andy Matuschak's method of building knowledge
    through successive layers of summarization
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def add_highlight(
        self,
        note_id: str,
        text: str,
        color: HighlightColor = HighlightColor.YELLOW,
        note: Optional[str] = None
    ) -> bool:
        """
        Add a highlight to a note

        Args:
            note_id: Note ID
            text: Text to highlight
            color: Highlight color
            note: Optional note about the highlight

        Returns:
            True if added
        """
        # Get current highlights
        note = self._get_note_raw(note_id)
        if not note:
            return False

        highlights = json_list(note['highlights']) if note['highlights'] else []

        # Check if already highlighted
        for h in highlights:
            if h.get('text') == text:
                logger.info(f"Text already highlighted: {text[:50]}...")
                return False

        # Add new highlight
        highlight = Highlight(
            text=text,
            color=color.value,
            position=len(highlights),
            note=note
        )

        highlights.append(asdict(highlight))

        # Update note
        self.db.update(
            "notes",
            {
                'highlights': json_dumps(highlights),
                'summary_layer': max(note['summary_layer'], SummaryLayer.HIGHLIGHTS.value),
                'updated_at': datetime.now().isoformat()
            },
            "id = ?",
            (note_id,)
        )

        logger.info(f"Added highlight to note {note_id}: {text[:50]}...")
        return True

    def add_bolded_text(self, note_id: str, text: str) -> bool:
        """
        Add bolded text (layer 2 summary)

        Args:
            note_id: Note ID
            text: Text to bold

        Returns:
            True if added
        """
        note = self._get_note_raw(note_id)
        if not note:
            return False

        bolded = json_list(note['bolded_text']) if note['bolded_text'] else []

        if text not in bolded:
            bolded.append(text)

            self.db.update(
                "notes",
                {
                    'bolded_text': json_dumps(bolded),
                    'summary_layer': max(note['summary_layer'], SummaryLayer.BOLDED.value),
                    'updated_at': datetime.now().isoformat()
                },
                "id = ?",
                (note_id,)
            )

            logger.info(f"Added bolded text to note {note_id}")
            return True

        return False

    def add_supernote(self, note_id: str, text: str) -> bool:
        """
        Add a supernote (layer 3 - best of the best)

        Args:
            note_id: Note ID
            text: Supernote text

        Returns:
            True if added
        """
        note = self._get_note_raw(note_id)
        if not note:
            return False

        supernotes = json_list(note['supernotes']) if note['supernotes'] else []

        if text not in supernotes:
            supernotes.append(text)

            self.db.update(
                "notes",
                {
                    'supernotes': json_dumps(supernotes),
                    'summary_layer': max(note['summary_layer'], SummaryLayer.SUPERNOTES.value),
                    'updated_at': datetime.now().isoformat()
                },
                "id = ?",
                (note_id,)
            )

            logger.info(f"Added supernote to note {note_id}")
            return True

        return False

    def add_own_words(self, note_id: str, text: str) -> bool:
        """
        Add summary in own words (layer 4)

        Args:
            note_id: Note ID
            text: Summary in own words

        Returns:
            True if added
        """
        note = self._get_note_raw(note_id)
        if not note:
            return False

        own_words = json_list(note['own_words']) if note['own_words'] else []

        if text not in own_words:
            own_words.append(text)

            self.db.update(
                "notes",
                {
                    'own_words': json_dumps(own_words),
                    'summary_layer': max(note['summary_layer'], SummaryLayer.OWN_WORDS.value),
                    'updated_at': datetime.now().isoformat()
                },
                "id = ?",
                (note_id,)
            )

            logger.info(f"Added own words summary to note {note_id}")
            return True

        return False

    def add_insight(self, note_id: str, text: str) -> bool:
        """
        Add new insight (layer 5 - connections and new thoughts)

        Args:
            note_id: Note ID
            text: Insight text

        Returns:
            True if added
        """
        note = self._get_note_raw(note_id)
        if not note:
            return False

        insights = json_list(note['insights']) if note['insights'] else []

        if text not in insights:
            insights.append(text)

            self.db.update(
                "notes",
                {
                    'insights': json_dumps(insights),
                    'summary_layer': max(note['summary_layer'], SummaryLayer.INSIGHTS.value),
                    'updated_at': datetime.now().isoformat()
                },
                "id = ?",
                (note_id,)
            )

            logger.info(f"Added insight to note {note_id}")
            return True

        return False

    def get_summary(self, note_id: str) -> Optional[NoteSummary]:
        """
        Get the complete progressive summary for a note

        Args:
            note_id: Note ID

        Returns:
            NoteSummary or None
        """
        note = self._get_note_raw(note_id)
        if not note:
            return None

        highlights_data = json_list(note['highlights']) if note['highlights'] else []
        highlights = [
            Highlight(
                text=h['text'],
                color=h['color'],
                position=h.get('position'),
                note=h.get('note'),
                created_at=h.get('created_at')
            )
            for h in highlights_data
        ]

        return NoteSummary(
            note_id=note_id,
            content_id=note['content_id'],
            current_layer=note['summary_layer'],
            highlights=highlights,
            bolded_text=json_list(note['bolded_text']),
            supernotes=json_list(note['supernotes']),
            own_words=json_list(note['own_words']),
            insights=json_list(note['insights'])
        )

    def get_layer(self, note_id: str, layer: SummaryLayer) -> Optional[str]:
        """
        Get a specific layer of the progressive summary

        Args:
            note_id: Note ID
            layer: Summary layer to get

        Returns:
            Layer content as formatted string or None
        """
        summary = self.get_summary(note_id)
        if not summary:
            return None

        if layer == SummaryLayer.HIGHLIGHTS:
            if not summary.highlights:
                return None
            return "\n".join([
                f"[{h.color}] {h.text}" for h in summary.highlights
            ])

        elif layer == SummaryLayer.BOLDED:
            if not summary.bolded_text:
                return None
            return "\n".join(summary.bolded_text)

        elif layer == SummaryLayer.SUPERNOTES:
            if not summary.supernotes:
                return None
            return "\n".join(summary.supernotes)

        elif layer == SummaryLayer.OWN_WORDS:
            if not summary.own_words:
                return None
            return "\n".join(summary.own_words)

        elif layer == SummaryLayer.INSIGHTS:
            if not summary.insights:
                return None
            return "\n".join(summary.insights)

        return None

    def get_formatted_summary(self, note_id: str) -> Optional[str]:
        """
        Get the full formatted progressive summary

        Args:
            note_id: Note ID

        Returns:
            Formatted summary string or None
        """
        summary = self.get_summary(note_id)
        if not summary:
            return None

        lines = []
        lines.append(f"Progressive Summary (Layer {summary.current_layer})")
        lines.append("=" * 50)

        if summary.highlights:
            lines.append(f"\n📌 Highlights ({len(summary.highlights)}):")
            for h in summary.highlights[:10]:
                emoji = {
                    'yellow': '🟡',
                    'orange': '🟠',
                    'red': '🔴',
                    'blue': '🔵',
                    'green': '🟢',
                    'purple': '🟣'
                }.get(h.color, '⚪')
                lines.append(f"  {emoji} {h.text[:80]}...")
            if len(summary.highlights) > 10:
                lines.append(f"  ... and {len(summary.highlights) - 10} more")

        if summary.bolded_text:
            lines.append(f"\n⭐ Key Points ({len(summary.bolded_text)}):")
            for i, text in enumerate(summary.bolded_text[:5], 1):
                lines.append(f"  {i}. {text[:80]}...")

        if summary.supernotes:
            lines.append(f"\n⭐ Supernotes ({len(summary.supernotes)}):")
            for i, text in enumerate(summary.supernotes[:5], 1):
                lines.append(f"  {i}. {text[:80]}...")

        if summary.own_words:
            lines.append(f"\n✍️ In My Own Words:")
            for i, text in enumerate(summary.own_words[:3], 1):
                lines.append(f"  {i}. {text[:100]}...")

        if summary.insights:
            lines.append(f"\n💡 Insights ({len(summary.insights)}):")
            for i, text in enumerate(summary.insights[:5], 1):
                lines.append(f"  {i}. {text[:100]}...")

        return "\n".join(lines)

    def remove_highlight(self, note_id: str, highlight_text: str) -> bool:
        """
        Remove a highlight from a note

        Args:
            note_id: Note ID
            highlight_text: Text of the highlight to remove

        Returns:
            True if removed
        """
        note = self._get_note_raw(note_id)
        if not note:
            return False

        highlights = json_list(note['highlights']) if note['highlights'] else []

        original_count = len(highlights)
        highlights = [h for h in highlights if h.get('text') != highlight_text]

        if len(highlights) < original_count:
            self.db.update(
                "notes",
                {'highlights': json_dumps(highlights)},
                "id = ?",
                (note_id,)
            )
            logger.info(f"Removed highlight from note {note_id}")
            return True

        return False

    def get_best_highlights(
        self,
        note_id: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get the best highlights from a note

        Args:
            note_id: Note ID
            limit: Maximum highlights to return

        Returns:
            List of highlight texts
        """
        summary = self.get_summary(note_id)
        if not summary:
            return []

        best = summary.get_best_highlights(limit)
        return [h.text for h in best]

    def promote_to_supernote(
        self,
        note_id: str,
        highlight_index: int
    ) -> bool:
        """
        Promote a highlight to a supernote

        Args:
            note_id: Note ID
            highlight_index: Index of the highlight to promote

        Returns:
            True if promoted
        """
        summary = self.get_summary(note_id)
        if not summary or highlight_index >= len(summary.highlights):
            return False

        highlight = summary.highlights[highlight_index]
        return self.add_supernote(note_id, highlight.text)

    def get_progress_summary(self, content_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary of progressive summarization progress

        Args:
            content_id: Optional content ID to filter by

        Returns:
            Progress statistics
        """
        where = "WHERE summary_layer > 0"
        params = []

        if content_id:
            where += " AND content_id = ?"
            params.append(content_id)

        rows = self.db.fetchall(f"""
            SELECT
                summary_layer,
                COUNT(*) as count
            FROM notes
            {where}
            GROUP BY summary_layer
            ORDER BY summary_layer
        """, params)

        by_layer = {row['summary_layer']: row['count'] for row in rows}

        total = sum(by_layer.values())
        avg_layer = sum(layer * count for layer, count in by_layer.items()) / total if total > 0 else 0

        # Count highlights
        highlights_count = self.db.fetchval(f"""
            SELECT
                SUM(CASE WHEN highlights IS NOT NULL THEN json_array_length(highlights) ELSE 0 END)
            FROM notes
            {where}
        """, params) or 0

        return {
            'total_notes_with_summaries': total,
            'by_layer': by_layer,
            'average_layer': round(avg_layer, 2),
            'total_highlights': highlights_count,
            'layer_distribution': {
                'highlights': by_layer.get(1, 0),
                'bolded': by_layer.get(2, 0),
                'supernotes': by_layer.get(3, 0),
                'own_words': by_layer.get(4, 0),
                'insights': by_layer.get(5, 0)
            }
        }

    def find_ready_for_next_layer(
        self,
        current_layer: SummaryLayer,
        limit: int = 20
    ) -> List[str]:
        """
        Find notes that are ready for the next layer of summarization

        Args:
            current_layer: Current layer to find notes at
            limit: Maximum results

        Returns:
            List of note IDs
        """
        rows = self.db.fetchall("""
            SELECT id FROM notes
            WHERE summary_layer = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (current_layer.value, limit))

        return [row['id'] for row in rows]

    def bulk_add_highlights(
        self,
        note_id: str,
        highlights: List[Tuple[str, HighlightColor]]
    ) -> int:
        """
        Add multiple highlights at once

        Args:
            note_id: Note ID
            highlights: List of (text, color) tuples

        Returns:
            Number of highlights added
        """
        added = 0
        for text, color in highlights:
            if self.add_highlight(note_id, text, color):
                added += 1

        return added

    def export_markdown(self, note_id: str) -> Optional[str]:
        """
        Export progressive summary as markdown

        Args:
            note_id: Note ID

        Returns:
            Markdown formatted string or None
        """
        summary = self.get_summary(note_id)
        if not summary:
            return None

        lines = []
        lines.append(f"# Progressive Summary - Layer {summary.current_layer}")
        lines.append("")

        if summary.highlights:
            lines.append("## Highlights")
            for h in summary.highlights:
                color_emoji = {
                    'yellow': '🟡',
                    'orange': '🟠',
                    'red': '🔴',
                    'blue': '🔵',
                    'green': '🟢',
                    'purple': '🟣'
                }.get(h.color, '⚪')
                lines.append(f"{color_emoji} {h.text}")
                if h.note:
                    lines.append(f"  _Note: {h.note}_")
            lines.append("")

        if summary.bolded_text:
            lines.append("## Key Points")
            for text in summary.bolded_text:
                lines.append(f"**{text}**")
            lines.append("")

        if summary.supernotes:
            lines.append("## Supernotes")
            for text in summary.supernotes:
                lines.append(f"- ⭐ {text}")
            lines.append("")

        if summary.own_words:
            lines.append("## In My Own Words")
            for text in summary.own_words:
                lines.append(text)
            lines.append("")

        if summary.insights:
            lines.append("## Insights & Connections")
            for text in summary.insights:
                lines.append(f"- 💡 {text}")

        return "\n".join(lines)

    def _get_note_raw(self, note_id: str) -> Optional[Any]:
        """Get raw note data from database"""
        return self.db.fetchone("SELECT * FROM notes WHERE id = ?", (note_id,))


if __name__ == "__main__":
    # Test the progressive summary service
    print("Progressive Summary Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    # First create a test note
    from repositories.content_repository import ContentRepository

    content_repo = ContentRepository(":memory:")
    test_content = Content(
        id="test_content_001",
        source_type="webpage",
        content_type="article",
        title="Test Article for Progressive Summarization",
        url="https://example.com/test",
        summary="This is a test article",
        main_content="Full content with some interesting points to highlight..."
    )
    content_repo.insert(test_content)

    # Create a test note
    note_id = "test_note_001"
    db = get_db(":memory:")
    db.insert("notes", {
        'id': note_id,
        'content_id': test_content.id,
        'note_type': 'learning',
        'content': 'Test note content',
        'summary_layer': 0,
        'highlights': None,
        'bolded_text': None,
        'supernotes': None,
        'own_words': None,
        'insights': None,
        'quotes': None,
        'project_tags': None,
        'mood_tags': None,
        'actionable': 0,
        'related_note_ids': None,
        'related_content_ids': None,
        'resolved': 0,
        'resolution_note': None,
        'priority': 'medium',
        'status': 'active',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    })

    service = ProgressiveSummaryService(":memory:")

    # Add some highlights
    service.add_highlight(note_id, "This is an important point", HighlightColor.RED)
    service.add_highlight(note_id, "This is worth noting", HighlightColor.ORANGE)
    service.add_highlight(note_id, "Just a regular highlight", HighlightColor.YELLOW)

    # Add bolded text
    service.add_bolded_text(note_id, "Key concept: progressive summarization builds knowledge over time")

    # Add supernote
    service.add_supernote(note_id, "The core idea is to make future reviewing more efficient")

    # Add own words
    service.add_own_words(note_id, "This method transforms passive reading into active knowledge building")

    # Get formatted summary
    formatted = service.get_formatted_summary(note_id)
    print("\n" + formatted)

    # Get best highlights
    best = service.get_best_highlights(note_id)
    print(f"\nBest highlights: {best}")

    # Export markdown
    markdown = service.export_markdown(note_id)
    print(f"\nMarkdown export:\n{markdown}")

    print("\n✓ Progressive summary service tests passed!")
