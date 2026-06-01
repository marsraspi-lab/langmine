"""SQLite database management for LangMine."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 5

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
    language_code TEXT NOT NULL DEFAULT 'zh',
    subtitle_language TEXT NOT NULL DEFAULT '',
    subtitle_kind TEXT NOT NULL DEFAULT ''
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
    language_code TEXT NOT NULL DEFAULT 'zh',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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
    language_code TEXT NOT NULL DEFAULT 'zh',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT DEFAULT '',
    new_value TEXT DEFAULT '',
    timestamp TEXT DEFAULT (datetime('now')),
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
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables and run migrations."""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.execute(
            "INSERT INTO schema_version (version) "
            "SELECT ? WHERE NOT EXISTS (SELECT 1 FROM schema_version)",
            (SCHEMA_VERSION,),
        )

        # Run migrations
        current = self._conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0] or 1

        if current < 2:
            # v1 → v2: added language_code column
            try:
                self._conn.execute(
                    "ALTER TABLE videos ADD COLUMN language_code TEXT NOT NULL DEFAULT 'zh'"
                )
            except sqlite3.OperationalError:
                pass  # Column may already exist from CREATE TABLE
            try:
                self._conn.execute(
                    "ALTER TABLE sentences ADD COLUMN language_code TEXT NOT NULL DEFAULT 'zh'"
                )
            except sqlite3.OperationalError:
                pass
            try:
                self._conn.execute(
                    "ALTER TABLE vocab ADD COLUMN language_code TEXT NOT NULL DEFAULT 'zh'"
                )
            except sqlite3.OperationalError:
                pass

        if current < 3:
            # v2 → v3: added created_at + updated_at columns
            for col, table in [("created_at", "sentences"), ("updated_at", "sentences"),
                               ("created_at", "vocab"), ("updated_at", "vocab")]:
                try:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT (datetime('now'))"
                    )
                except sqlite3.OperationalError:
                    pass  # Column may already exist from CREATE TABLE

        if current < 4:
            # v3 → v4: added events table
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    old_value TEXT DEFAULT '',
                    new_value TEXT DEFAULT '',
                    timestamp TEXT DEFAULT (datetime('now')),
                    language_code TEXT NOT NULL DEFAULT 'zh'
                )"""
            )

        if current < 5:
            # v4 → v5: added subtitle_language + subtitle_kind on videos
            for col in ["subtitle_language", "subtitle_kind"]:
                try:
                    self._conn.execute(
                        f"ALTER TABLE videos ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"
                    )
                except sqlite3.OperationalError:
                    pass

        self._conn.execute(
            "UPDATE schema_version SET version = ? WHERE version < ?",
            (SCHEMA_VERSION, SCHEMA_VERSION),
        )
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn
