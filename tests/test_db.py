"""Tests for database schema and migrations."""

import sqlite3
import tempfile
from pathlib import Path

from langmine.db import Database


def test_database_creates_all_tables():
    """Database initialization should create videos, sentences, and vocab tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db = Database(db_path)

        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "videos" in table_names
        assert "sentences" in table_names
        assert "vocab" in table_names
        conn.close()


def test_videos_table_schema():
    """Videos table should have the expected columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db = Database(db_path)

        conn = sqlite3.connect(db_path)
        columns = conn.execute("PRAGMA table_info(videos)").fetchall()
        col_names = [c[1] for c in columns]

        assert "id" in col_names
        assert "youtube_id" in col_names
        assert "title" in col_names
        assert "channel" in col_names
        assert "duration_sec" in col_names
        assert "transcript_json" in col_names
        assert "audio_path" in col_names
        assert "processed_at" in col_names
        conn.close()


def test_sentences_table_schema():
    """Sentences table should have the expected columns including status field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db = Database(db_path)

        conn = sqlite3.connect(db_path)
        columns = conn.execute("PRAGMA table_info(sentences)").fetchall()
        col_names = [c[1] for c in columns]

        assert "status" in col_names
        assert "unknown_word" in col_names
        assert "audio_clip_path" in col_names
        assert "screenshot_path" in col_names
        assert "screenshot_enabled" in col_names
        assert "video_id" in col_names
        conn.close()


def test_vocab_table_schema():
    """Vocab table should have the expected columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db = Database(db_path)

        conn = sqlite3.connect(db_path)
        columns = conn.execute("PRAGMA table_info(vocab)").fetchall()
        col_names = [c[1] for c in columns]

        assert "word_simplified" in col_names
        assert "reading" in col_names
        assert "hsk_level" in col_names
        assert "frequency_rank" in col_names
        assert "status" in col_names
        conn.close()


def test_database_is_singleton_per_path():
    """Calling Database() twice with the same path should reuse the connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db1 = Database(db_path)
        db2 = Database(db_path)
        assert db1 is db2


def test_migration_version_tracking():
    """Database should track schema version for future migrations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"
        db = Database(db_path)

        conn = sqlite3.connect(db_path)
        version = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()
        assert version is not None
        assert version[0] >= 1
        conn.close()
