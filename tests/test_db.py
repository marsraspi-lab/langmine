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


def test_migration_v5_to_v6_renames_pinyin_to_reading():
    """v1 DBs used 'pinyin' column; migration should rename to 'reading'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "langmine.db"

        # Create a v1-format DB with the old column name
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version VALUES (1)")
        conn.execute("""
            CREATE TABLE sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                text TEXT NOT NULL,
                pinyin TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE vocab (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_simplified TEXT NOT NULL,
                pinyin TEXT
            )
        """)
        conn.execute("INSERT INTO sentences (video_id, start_ms, end_ms, text, pinyin) VALUES (1, 0, 1000, '测试', 'ce4 shi4')")
        conn.execute("INSERT INTO vocab (word_simplified, pinyin) VALUES ('测试', 'ce4 shi4')")
        conn.commit()
        conn.close()

        # Open with Database class — migration should fire
        db = Database(db_path)

        # Verify columns were renamed
        sent_cols = [r[1] for r in db.conn.execute("PRAGMA table_info(sentences)")]
        assert "reading" in sent_cols, f"reading not in sentences columns: {sent_cols}"
        assert "pinyin" not in sent_cols

        vocab_cols = [r[1] for r in db.conn.execute("PRAGMA table_info(vocab)")]
        assert "reading" in vocab_cols, f"reading not in vocab columns: {vocab_cols}"
        assert "pinyin" not in vocab_cols

        # Data survived
        sent = db.conn.execute("SELECT text, reading FROM sentences LIMIT 1").fetchone()
        assert sent["reading"] == "ce4 shi4"
        vocab = db.conn.execute("SELECT word_simplified, reading FROM vocab LIMIT 1").fetchone()
        assert vocab["reading"] == "ce4 shi4"

        # Version bumped to 6
        ver = db.conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        assert ver == 6
