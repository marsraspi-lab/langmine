"""SQLite database management for LangMine."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_id TEXT UNIQUE NOT NULL,
    title TEXT,
    channel TEXT,
    duration_sec INTEGER,
    transcript_json TEXT,
    audio_path TEXT,
    processed_at TEXT DEFAULT (datetime('now')),
    language_code TEXT NOT NULL DEFAULT 'zh'
);

CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id),
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_segmented TEXT,
    non_words_json TEXT,
    reading TEXT,
    translation_de TEXT,
    unknown_word TEXT,
    unknown_word_rank INTEGER,
    known_synonyms_json TEXT,
    audio_clip_path TEXT,
    screenshot_path TEXT,
    screenshot_enabled INTEGER DEFAULT 1,
    status TEXT DEFAULT 'new',
    language_code TEXT NOT NULL DEFAULT 'zh'
);

CREATE TABLE IF NOT EXISTS vocab (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_simplified TEXT NOT NULL,
    word_traditional TEXT,
    reading TEXT,
    definition_de TEXT,
    hsk_level INTEGER,
    frequency_rank INTEGER,
    status TEXT DEFAULT 'known',
    language_code TEXT NOT NULL DEFAULT 'zh'
);
"""


class Database:
    """SQLite database with singleton-per-path behavior."""

    _instances: dict[str, "Database"] = {}

    def __new__(cls, db_path: str | Path):
        key = str(db_path)
        if key not in cls._instances:
            instance = super().__new__(cls)
            instance._conn = None
            cls._instances[key] = instance
        return cls._instances[key]

    def __init__(self, db_path: str | Path):
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables and run migrations."""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn
