# modules/topic_tracker.py
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from utils.logger import logger
from utils.helpers import ensure_dir

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "topics.db"))
ensure_dir(os.path.dirname(DB_PATH))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    last_posted TEXT,
    times_posted INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    category TEXT DEFAULT 'Other'
);
"""

def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.executescript(_SCHEMA)
        
        # Check if category column exists, add if not
        cur.execute("PRAGMA table_info(topics)")
        columns = [row[1] for row in cur.fetchall()]
        if 'category' not in columns:
            cur.execute("ALTER TABLE topics ADD COLUMN category TEXT DEFAULT 'Other'")
        
        conn.commit()
    finally:
        conn.close()

# Initialize on import
init_db()

def add_topic(topic: str, note: Optional[str] = None, category: str = "Other") -> int:
    """Insert a new topic (ignore if exists). Returns the topic id."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO topics (topic, created_at, note, category) VALUES (?, ?, ?, ?)",
                (topic, now, note, category)
            )
            conn.commit()
            logger.info(f"Added topic: {topic} (category: {category})")
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # Already exists: return existing id
            cur.execute("SELECT id FROM topics WHERE topic = ?", (topic,))
            row = cur.fetchone()
            return row["id"] if row else -1
    finally:
        conn.close()

def pick_next_topics(limit: int = 1) -> List[Dict]:
    """
    Select up to `limit` topics with status='pending' ordered by created_at.
    Marks them 'in_progress' so concurrent runs don't pick same topics.
    Returns list of dicts: {id, topic, status, created_at, ...}
    """
    conn = _get_conn()
    selected = []
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        rows = cur.execute(
            "SELECT * FROM topics WHERE status = 'pending' ORDER BY created_at LIMIT ?",
            (limit,)
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            cur.execute(
                "UPDATE topics SET status = 'in_progress' WHERE id IN ({seq})".format(
                    seq=",".join("?" * len(ids))
                ),
                ids
            )
        conn.commit()
        selected = [dict(r) for r in rows]
    except Exception as e:
        logger.exception("pick_next_topics failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
    return selected

def mark_posted(topic_id: int):
    """Mark the topic as done; set last_posted and increment times_posted."""
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE topics SET status = 'done', last_posted = ?, times_posted = times_posted + 1 WHERE id = ?",
            (now, topic_id)
        )
        conn.commit()
    finally:
        conn.close()

def mark_topic_done(topic: str):
    """Mark a topic as done by topic name (not ID)"""
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE topics SET status = 'done', last_posted = ?, times_posted = times_posted + 1 WHERE topic = ?",
            (now, topic)
        )
        conn.commit()
        logger.info(f"Marked topic done: {topic}")
    finally:
        conn.close()

def mark_topic_status(topic: str, status: str):
    """Mark topic with specific status by topic name"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE topics SET status = ? WHERE topic = ?",
            (status, topic)
        )
        conn.commit()
        logger.info(f"Updated topic {topic} status to: {status}")
    finally:
        conn.close()

def mark_failed(topic_id: int, note: Optional[str] = None):
    """Mark topic as failed by ID"""
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE topics SET status = 'failed', last_posted = ?, note = COALESCE(?, note) WHERE id = ?",
            (now, note, topic_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_pending_topics(limit: int = 100) -> List[Dict]:
    """Get all pending topics"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM topics WHERE status = 'pending' ORDER BY created_at LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_all_topics() -> List[Dict]:
    """Get all topics"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def reset_scheduling() -> bool:
    """Reset any in_progress topics back to pending. Returns True if changed any rows."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE topics SET status = 'pending' WHERE status = 'in_progress'")
        changed = cur.rowcount
        conn.commit()
        logger.info(f"Reset {changed} topics to pending")
        return changed > 0
    finally:
        conn.close()

def get_topic_by_id(topic_id: int) -> Optional[Dict]:
    """Get topic by ID"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_topic_by_name(topic: str) -> Optional[Dict]:
    """Get topic by name"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM topics WHERE topic = ?", (topic,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def delete_topic(topic: str) -> bool:
    """Delete a topic by name"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM topics WHERE topic = ?", (topic,))
        conn.commit()
        logger.info(f"Deleted topic: {topic}")
        return cur.rowcount > 0
    finally:
        conn.close()

def update_topic_category(topic: str, category: str):
    """Update topic category"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE topics SET category = ? WHERE topic = ?", (category, topic))
        conn.commit()
        logger.info(f"Updated {topic} category to: {category}")
    finally:
        conn.close()
