"""
Learning Session Service Module - Track learning activities and review schedules

This module provides:
- Learning session tracking
- Spaced repetition scheduling (SM-2 algorithm)
- Review management
- Learning statistics
- Progress insights

Features:
- Record each learning session
- Track comprehension and confidence
- Schedule reviews based on retention
- Calculate learning statistics
- Provide learning insights
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database.connection import json_dumps, json_list, json_dict

logger = logging.getLogger(__name__)


class Mood(Enum):
    """Learning mood states"""
    FOCUSED = "focused"
    CURIOUS = "curious"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    BORED = "bored"
    EXCITED = "excited"
    CALM = "calm"
    ANXIOUS = "anxious"


@dataclass
class LearningSession:
    """A single learning session"""
    id: str
    content_id: str

    started_at: str
    duration: int                      # Duration in seconds

    # Learning behaviors
    highlights_count: int = 0
    notes_added: int = 0
    links_created: int = 0
    summary_layer: int = 0             # Progressive summary layer reached (0-5)

    # Self-assessment
    comprehension: int = 3             # 1-5 scale
    confidence: int = 3                # 1-5 scale
    mood: str = Mood.CALM.value

    # Outputs
    key_takeaways: List[str] = None
    questions: List[str] = None
    session_notes: Optional[str] = None

    created_at: str = None

    def __post_init__(self):
        if self.key_takeaways is None:
            self.key_takeaways = []
        if self.questions is None:
            self.questions = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['key_takeaways'] = json_dumps(self.key_takeaways)
        data['questions'] = json_dumps(self.questions)
        return data


@dataclass
class ReviewSchedule:
    """Spaced repetition schedule"""
    content_id: str

    last_reviewed: Optional[str] = None
    next_review: str = None
    review_count: int = 0
    interval_days: int = 1

    # SM-2 algorithm parameters
    ease_factor: float = 2.5           # EF: 1.3 - 3.0 (default 2.5)
    quality: Optional[int] = None       # Last review quality: 0-5

    updated_at: str = None

    def __post_init__(self):
        if self.next_review is None:
            self.next_review = (datetime.now() + timedelta(days=1)).isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LearningSessionService:
    """
    Service for managing learning sessions and review schedules

    Implements:
    - Session tracking and recording
    - Spaced repetition (SM-2 algorithm)
    - Review scheduling
    - Learning statistics
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def start_session(self, content_id: str) -> LearningSession:
        """
        Start a new learning session

        Args:
            content_id: Content being learned

        Returns:
            LearningSession object
        """
        session_id = self._generate_session_id()

        session = LearningSession(
            id=session_id,
            content_id=content_id,
            started_at=datetime.now().isoformat(),
            duration=0
        )

        # Save to database
        self.db.insert("learning_sessions", {
            'id': session.id,
            'content_id': session.content_id,
            'started_at': session.started_at,
            'duration': session.duration,
            'highlights_count': session.highlights_count,
            'notes_added': session.notes_added,
            'links_created': session.links_created,
            'summary_layer': session.summary_layer,
            'comprehension': session.comprehension,
            'confidence': session.confidence,
            'mood': session.mood,
            'key_takeaways': json_dumps(session.key_takeaways),
            'questions': json_dumps(session.questions),
            'session_notes': session.session_notes,
            'created_at': session.created_at
        })

        logger.info(f"Started learning session: {session_id} for content: {content_id}")
        return session

    def end_session(
        self,
        session_id: str,
        duration: int,
        comprehension: int = 3,
        confidence: int = 3,
        mood: str = Mood.CALM.value,
        key_takeaways: Optional[List[str]] = None,
        questions: Optional[List[str]] = None,
        notes: Optional[str] = None
    ) -> Optional[LearningSession]:
        """
        End and update a learning session

        Args:
            session_id: Session ID
            duration: Session duration in seconds
            comprehension: Comprehension rating (1-5)
            confidence: Confidence rating (1-5)
            mood: Learning mood
            key_takeaways: Key takeaways from session
            questions: Questions raised during session
            notes: Additional session notes

        Returns:
            Updated LearningSession or None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        # Update session
        session.duration = duration
        session.comprehension = max(1, min(5, comprehension))
        session.confidence = max(1, min(5, confidence))
        session.mood = mood

        if key_takeaways:
            session.key_takeaways = key_takeaways
        if questions:
            session.questions = questions
        if notes:
            session.session_notes = notes

        # Update database
        self.db.update(
            "learning_sessions",
            {
                'duration': session.duration,
                'comprehension': session.comprehension,
                'confidence': session.confidence,
                'mood': session.mood,
                'key_takeaways': json_dumps(session.key_takeaways),
                'questions': json_dumps(session.questions),
                'session_notes': session.session_notes
            },
            "id = ?",
            (session_id,)
        )

        logger.info(f"Ended learning session: {session_id}, duration: {duration}s")
        return session

    def get_session(self, session_id: str) -> Optional[LearningSession]:
        """Get a learning session by ID"""
        row = self.db.fetchone(
            "SELECT * FROM learning_sessions WHERE id = ?",
            (session_id,)
        )
        if row:
            return self._row_to_session(row)
        return None

    def get_sessions_for_content(
        self,
        content_id: str,
        limit: int = 50
    ) -> List[LearningSession]:
        """Get all learning sessions for a content"""
        rows = self.db.fetchall("""
            SELECT * FROM learning_sessions
            WHERE content_id = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (content_id, limit))

        return [self._row_to_session(row) for row in rows]

    def get_recent_sessions(self, limit: int = 50) -> List[LearningSession]:
        """Get recent learning sessions across all content"""
        rows = self.db.fetchall("""
            SELECT * FROM learning_sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))

        return [self._row_to_session(row) for row in rows]

    # ==================== Review Scheduling (SM-2 Algorithm) ====================

    def get_review_schedule(self, content_id: str) -> Optional[ReviewSchedule]:
        """Get review schedule for content"""
        row = self.db.fetchone(
            "SELECT * FROM review_schedules WHERE content_id = ?",
            (content_id,)
        )
        if row:
            return self._row_to_schedule(row)
        return None

    def schedule_review(
        self,
        content_id: str,
        quality: int
    ) -> ReviewSchedule:
        """
        Schedule next review using SM-2 algorithm

        Args:
            content_id: Content to review
            quality: Review quality (0-5):
                5: Perfect response
                4: Correct response after hesitation
                3: Correct response recalled with serious difficulty
                2: Incorrect response; where the correct one seemed easy to recall
                1: Incorrect response; the correct one remembered
                0: Complete blackout

        Returns:
            Updated ReviewSchedule
        """
        schedule = self.get_review_schedule(content_id)

        if not schedule:
            # Create new schedule
            schedule = ReviewSchedule(
                content_id=content_id,
                last_reviewed=datetime.now().isoformat(),
                review_count=1,
                interval_days=1,
                ease_factor=2.5,
                quality=quality
            )
        else:
            # Update existing schedule using SM-2
            schedule.last_reviewed = datetime.now().isoformat()
            schedule.review_count += 1
            schedule.quality = quality

            # SM-2 Algorithm
            # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            new_ef = schedule.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

            # EF cannot be less than 1.3
            schedule.ease_factor = max(1.3, new_ef)

            if quality < 3:
                # If quality < 3, reset interval
                schedule.interval_days = 1
                schedule.review_count = 1
            else:
                # Calculate next interval
                if schedule.review_count == 1:
                    schedule.interval_days = 1
                elif schedule.review_count == 2:
                    schedule.interval_days = 6
                else:
                    schedule.interval_days = int(schedule.interval_days * schedule.ease_factor)

        # Calculate next review date
        next_date = datetime.fromisoformat(schedule.last_reviewed) + timedelta(days=schedule.interval_days)
        schedule.next_review = next_date.isoformat()
        schedule.updated_at = datetime.now().isoformat()

        # Save to database
        self._save_schedule(schedule)

        logger.info(f"Scheduled review for {content_id}: next in {schedule.interval_days} days")
        return schedule

    def get_due_reviews(self, limit: int = 50) -> List[Tuple[str, ReviewSchedule]]:
        """
        Get content items due for review

        Returns:
            List of (content_id, ReviewSchedule) tuples
        """
        now = datetime.now().isoformat()

        rows = self.db.fetchall("""
            SELECT * FROM review_schedules
            WHERE next_review <= ?
            ORDER BY next_review ASC
            LIMIT ?
        """, (now, limit))

        return [(row['content_id'], self._row_to_schedule(row)) for row in rows]

    def get_upcoming_reviews(self, days: int = 7, limit: int = 50) -> List[Tuple[str, ReviewSchedule]]:
        """Get reviews coming up in the next N days"""
        now = datetime.now()
        future = (now + timedelta(days=days)).isoformat()

        rows = self.db.fetchall("""
            SELECT * FROM review_schedules
            WHERE next_review > ? AND next_review <= ?
            ORDER BY next_review ASC
            LIMIT ?
        """, (now.isoformat(), future, limit))

        return [(row['content_id'], self._row_to_schedule(row)) for row in rows]

    # ==================== Statistics and Insights ====================

    def get_learning_stats(self, content_id: str) -> Dict[str, Any]:
        """Get learning statistics for a content"""
        sessions = self.get_sessions_for_content(content_id)

        if not sessions:
            return {
                'total_sessions': 0,
                'total_duration': 0,
                'avg_comprehension': 0,
                'avg_confidence': 0,
                'last_session': None
            }

        total_duration = sum(s.duration for s in sessions)
        avg_comprehension = sum(s.comprehension for s in sessions) / len(sessions)
        avg_confidence = sum(s.confidence for s in sessions) / len(sessions)

        mood_counts = {}
        for s in sessions:
            mood_counts[s.mood] = mood_counts.get(s.mood, 0) + 1

        # Get review schedule
        schedule = self.get_review_schedule(content_id)

        return {
            'total_sessions': len(sessions),
            'total_duration': total_duration,
            'total_duration_formatted': self._format_duration(total_duration),
            'avg_comprehension': round(avg_comprehension, 2),
            'avg_confidence': round(avg_confidence, 2),
            'last_session': sessions[0].started_at if sessions else None,
            'mood_distribution': mood_counts,
            'review_schedule': {
                'next_review': schedule.next_review if schedule else None,
                'interval_days': schedule.interval_days if schedule else 0,
                'ease_factor': schedule.ease_factor if schedule else 0
            }
        }

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall learning statistics"""
        # Total sessions
        total_sessions = self.db.fetchval("SELECT COUNT(*) FROM learning_sessions") or 0

        # Total learning time
        total_duration = self.db.fetchval("SELECT SUM(duration) FROM learning_sessions") or 0

        # Average comprehension and confidence
        avg_comprehension = self.db.fetchval(
            "SELECT AVG(comprehension) FROM learning_sessions"
        ) or 0

        avg_confidence = self.db.fetchval(
            "SELECT AVG(confidence) FROM learning_sessions"
        ) or 0

        # Active review schedules
        active_schedules = self.db.fetchval("SELECT COUNT(*) FROM review_schedules") or 0

        # Due reviews
        due_reviews = len(self.get_due_reviews(limit=1000))

        # Most learned content
        top_content = self.db.fetchall("""
            SELECT content_id, COUNT(*) as session_count,
                   SUM(duration) as total_duration
            FROM learning_sessions
            GROUP BY content_id
            ORDER BY session_count DESC
            LIMIT 10
        """)

        return {
            'total_sessions': total_sessions,
            'total_duration': total_duration,
            'total_duration_formatted': self._format_duration(total_duration),
            'avg_comprehension': round(avg_comprehension, 2),
            'avg_confidence': round(avg_confidence, 2),
            'active_schedules': active_schedules,
            'due_reviews': due_reviews,
            'top_content': [dict(row) for row in top_content]
        }

    def get_learning_streak(self) -> Dict[str, Any]:
        """Calculate learning streak information"""
        # Get sessions ordered by date
        rows = self.db.fetchall("""
            SELECT DATE(started_at) as session_date,
                   COUNT(*) as sessions,
                   SUM(duration) as duration
            FROM learning_sessions
            GROUP BY DATE(started_at)
            ORDER BY session_date DESC
        """)

        if not rows:
            return {'current_streak': 0, 'longest_streak': 0, 'total_days': 0}

        today = datetime.now().date()
        current_streak = 0
        longest_streak = 0
        temp_streak = 0

        for i, row in enumerate(rows):
            session_date = datetime.fromisoformat(row['session_date']).date()

            if i == 0:
                # Check if most recent session was today or yesterday
                if (today - session_date).days <= 1:
                    temp_streak = 1
                else:
                    break
            else:
                prev_date = datetime.fromisoformat(rows[i-1]['session_date']).date()
                if (prev_date - session_date).days == 1:
                    temp_streak += 1
                else:
                    break

            longest_streak = max(longest_streak, temp_streak)

        current_streak = temp_streak

        return {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'total_days': len(rows)
        }

    def get_mood_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get mood trends over time"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        rows = self.db.fetchall("""
            SELECT DATE(started_at) as session_date,
                   mood,
                   COUNT(*) as count
            FROM learning_sessions
            WHERE started_at >= ?
            GROUP BY DATE(started_at), mood
            ORDER BY session_date DESC
        """, (cutoff,))

        trends = []
        for row in rows:
            trends.append({
                'date': row['session_date'],
                'mood': row['mood'],
                'count': row['count']
            })

        return trends

    def _save_schedule(self, schedule: ReviewSchedule):
        """Save or update review schedule"""
        existing = self.db.fetchone(
            "SELECT content_id FROM review_schedules WHERE content_id = ?",
            (schedule.content_id,)
        )

        data = {
            'content_id': schedule.content_id,
            'last_reviewed': schedule.last_reviewed,
            'next_review': schedule.next_review,
            'review_count': schedule.review_count,
            'interval_days': schedule.interval_days,
            'ease_factor': schedule.ease_factor,
            'updated_at': schedule.updated_at
        }

        if existing:
            self.db.update(
                "review_schedules",
                data,
                "content_id = ?",
                (schedule.content_id,)
            )
        else:
            self.db.insert("review_schedules", data)

    def _row_to_session(self, row: Any) -> LearningSession:
        """Convert database row to LearningSession"""
        return LearningSession(
            id=row['id'],
            content_id=row['content_id'],
            started_at=row['started_at'],
            duration=row['duration'],
            highlights_count=row['highlights_count'],
            notes_added=row['notes_added'],
            links_created=row['links_created'],
            summary_layer=row['summary_layer'],
            comprehension=row['comprehension'],
            confidence=row['confidence'],
            mood=row['mood'],
            key_takeaways=json_list(row['key_takeaways']),
            questions=json_list(row['questions']),
            session_notes=row['session_notes'],
            created_at=row['created_at']
        )

    def _row_to_schedule(self, row: Any) -> ReviewSchedule:
        """Convert database row to ReviewSchedule"""
        return ReviewSchedule(
            content_id=row['content_id'],
            last_reviewed=row['last_reviewed'],
            next_review=row['next_review'],
            review_count=row['review_count'],
            interval_days=row['interval_days'],
            ease_factor=row['ease_factor'],
            updated_at=row['updated_at']
        )

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = self.db.fetchval("SELECT COUNT(*) FROM learning_sessions") or 0
        return f"session_{timestamp}_{count:03d}"

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration in human-readable format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


if __name__ == "__main__":
    # Test the learning session service
    print("Learning Session Service Module")
    print("=" * 50)

    from database.connection import init_database
    init_database(":memory:")

    service = LearningSessionService(":memory:")

    # Create a test content
    content_id = "test_content_001"

    # Start a session
    session = service.start_session(content_id)
    print(f"Started session: {session.id}")

    # End the session
    service.end_session(
        session.id,
        duration=1800,  # 30 minutes
        comprehension=4,
        confidence=4,
        mood= Mood.FOCUSED.value,
        key_takeaways=["Learned about progressive summarization"],
        questions=["How to implement this in practice?"]
    )

    # Get stats
    stats = service.get_learning_stats(content_id)
    print(f"\nLearning stats:")
    print(f"  Total sessions: {stats['total_sessions']}")
    print(f"  Total duration: {stats['total_duration_formatted']}")
    print(f"  Avg comprehension: {stats['avg_comprehension']}")
    print(f"  Avg confidence: {stats['avg_confidence']}")

    # Schedule a review
    schedule = service.schedule_review(content_id, quality=5)
    print(f"\nReview scheduled:")
    print(f"  Next review: {schedule.next_review}")
    print(f"  Interval: {schedule.interval_days} days")
    print(f"  Ease factor: {schedule.ease_factor:.2f}")

    # Overall stats
    overall = service.get_overall_stats()
    print(f"\nOverall stats:")
    print(f"  Total sessions: {overall['total_sessions']}")
    print(f"  Total duration: {overall['total_duration_formatted']}")
    print(f"  Active schedules: {overall['active_schedules']}")
    print(f"  Due reviews: {overall['due_reviews']}")

    print("\n✓ Learning session service tests passed!")
