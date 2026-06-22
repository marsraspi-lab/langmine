"""SQLite persistence adapter — wraps db.py behind Persistence port.

This is one possible implementation of the Persistence port.
Swap for FileSystemPersistence, PostgresPersistence, or InMemoryPersistence
without changing any domain code.
"""

from datetime import UTC, datetime
from pathlib import Path

from langmine.db import Database
from langmine.domain.models import Sentence, Video, VocabWord
from langmine.domain.ports import Persistence


class SQLitePersistence(Persistence):
    """Stores all LangMine data in SQLite."""

    def __init__(self, db_path: str = "~/.langmine/langmine.db"):
        self._db = Database(Path(db_path).expanduser())

    @property
    def conn(self):
        return self._db.conn

    def _lang_filter(self, language_code: str) -> tuple[str, list]:
        """Return (WHERE_clause_suffix, param_list) for language filtering."""
        if language_code:
            return (" AND language_code = ?", [language_code])
        return ("", [])

    # === Videos ===

    def save_video(self, video: Video) -> None:
        if video.id:
            self.conn.execute(
                """UPDATE videos SET title=?, channel=?, duration_sec=?,
                   transcript_json=?, audio_path=?,
                   subtitle_language=?, subtitle_kind=?,
                   target_subtitle_language=?, target_subtitle_kind=?,
                   target_transcript_json=?
                   WHERE id=?""",
                (
                    video.title,
                    video.channel,
                    video.duration_sec,
                    video.transcript_json,
                    video.audio_path,
                    video.subtitle_language,
                    video.subtitle_kind,
                    video.target_subtitle_language,
                    video.target_subtitle_kind,
                    video.target_transcript_json,
                    video.id,
                ),
            )
        else:
            cursor = self.conn.execute(
                """INSERT OR REPLACE INTO videos
                   (youtube_id, title, channel, duration_sec,
                    transcript_json, audio_path, language_code,
                    subtitle_language, subtitle_kind,
                    target_subtitle_language, target_subtitle_kind,
                    target_transcript_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    video.youtube_id,
                    video.title,
                    video.channel,
                    video.duration_sec,
                    video.transcript_json,
                    video.audio_path,
                    video.language_code,
                    video.subtitle_language,
                    video.subtitle_kind,
                    video.target_subtitle_language,
                    video.target_subtitle_kind,
                    video.target_transcript_json,
                ),
            )
            video.id = cursor.lastrowid
        self.conn.commit()

    def get_video(self, youtube_id: str) -> Video | None:
        row = self.conn.execute(
            "SELECT * FROM videos WHERE youtube_id = ?", (youtube_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_video(row)

    def list_videos(self, language_code: str = "") -> list[Video]:
        suffix, params = self._lang_filter(language_code)
        rows = self.conn.execute(
            f"SELECT * FROM videos WHERE 1=1{suffix} ORDER BY processed_at DESC",
            params,
        ).fetchall()
        return [self._row_to_video(r) for r in rows]

    def delete_video(self, video_id: int) -> bool:
        """Delete a video and all related data (cascading delete).

        Deletes: sentences, events, vocab entries for this video's words,
        and the video itself. Returns True if a video was deleted.
        """
        # Verify the video exists
        row = self.conn.execute(
            "SELECT id FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return False

        # Delete events for this video and its sentences
        self.conn.execute(
            "DELETE FROM events WHERE entity_type = 'video' AND entity_id = ?",
            (video_id,),
        )
        self.conn.execute(
            "DELETE FROM events WHERE entity_type = 'sentence' AND entity_id IN "
            "(SELECT id FROM sentences WHERE video_id = ?)",
            (video_id,),
        )

        # Delete sentences
        self.conn.execute("DELETE FROM sentences WHERE video_id = ?", (video_id,))

        # Delete the video
        self.conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))

        self.conn.commit()
        return True

    # === Sentences ===

    def save_sentences(self, sentences: list[Sentence]) -> None:
        now = datetime.now(UTC).isoformat()
        for s in sentences:
            if s.id:
                self.conn.execute(
                    """UPDATE sentences SET status=?, translation=?,
                       reading=?, text_segmented=?, unknown_word=?,
                       screenshot_enabled=?, updated_at=?
                       WHERE id=?""",
                    (
                        s.status,
                        s.translation,
                        s.reading,
                        s.text_segmented,
                        s.unknown_word,
                        int(s.screenshot_enabled),
                        now,
                        s.id,
                    ),
                )
            else:
                s.created_at = now
                s.updated_at = now
                cursor = self.conn.execute(
                    """INSERT INTO sentences
                       (video_id, start_ms, end_ms, text, text_segmented,
                        non_words_json, reading, translation, unknown_word,
                        unknown_word_rank, known_synonyms_json,
                        audio_clip_path, screenshot_path, screenshot_enabled,
                        status, language_code, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        s.video_id,
                        s.start_ms,
                        s.end_ms,
                        s.text,
                        s.text_segmented,
                        s.non_words_json,
                        s.reading,
                        s.translation,
                        s.unknown_word,
                        s.unknown_word_rank,
                        s.known_synonyms_json,
                        s.audio_clip_path,
                        s.screenshot_path,
                        int(s.screenshot_enabled),
                        s.status,
                        s.language_code,
                        now,
                        now,
                    ),
                )
                s.id = cursor.lastrowid
        self.conn.commit()

    def get_sentences_by_video(
        self, video_id: int, status: str | None = None, language_code: str = ""
    ) -> list[Sentence]:
        query = "SELECT * FROM sentences WHERE video_id = ?"
        params: list = [video_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        if language_code:
            query += " AND language_code = ?"
            params.append(language_code)
        rows = self.conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    def update_sentence(self, sentence: Sentence) -> None:
        if not sentence.id:
            raise ValueError("Cannot update sentence without id")
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """UPDATE sentences SET status=?, translation=?,
               reading=?, text_segmented=?, unknown_word=?,
               screenshot_path=?, screenshot_enabled=?, updated_at=? WHERE id=?""",
            (
                sentence.status,
                sentence.translation,
                sentence.reading,
                sentence.text_segmented,
                sentence.unknown_word,
                sentence.screenshot_path,
                int(sentence.screenshot_enabled),
                now,
                sentence.id,
            ),
        )
        self.conn.commit()

    def get_sentences_by_status(
        self, status: str, language_code: str = ""
    ) -> list[Sentence]:
        query = "SELECT * FROM sentences WHERE status = ?"
        params: list = [status]
        if language_code:
            query += " AND language_code = ?"
            params.append(language_code)
        rows = self.conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    # === Vocab ===

    def save_vocab_word(self, word: VocabWord) -> None:
        now = datetime.now(UTC).isoformat()
        existing = self.get_vocab_word(word.word_simplified)
        if existing:
            word.created_at = existing.created_at  # preserve original creation time
            self.conn.execute(
                """UPDATE vocab SET word_traditional=?, reading=?, definition_de=?,
                   hsk_level=?, frequency_rank=?, status=?, language_code=?,
                   updated_at=?
                   WHERE word_simplified=?""",
                (
                    word.word_traditional,
                    word.reading,
                    word.definition_de,
                    word.hsk_level,
                    word.frequency_rank,
                    word.status,
                    word.language_code,
                    now,
                    word.word_simplified,
                ),
            )
            self.conn.commit()
        else:
            word.created_at = now
            word.updated_at = now
            self.conn.execute(
                """INSERT INTO vocab
                   (word_simplified, word_traditional, reading, definition_de,
                    hsk_level, frequency_rank, status, language_code,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    word.word_simplified,
                    word.word_traditional,
                    word.reading,
                    word.definition_de,
                    word.hsk_level,
                    word.frequency_rank,
                    word.status,
                    word.language_code,
                    now,
                    now,
                ),
            )
            self.conn.commit()
            # Log first-encountered event
            self.log_event(
                entity_type="word",
                entity_id=word.id or 0,
                action="first_encountered",
                new_value=word.word_simplified,
                language_code=word.language_code,
            )

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        row = self.conn.execute(
            "SELECT * FROM vocab WHERE word_simplified = ?", (word_simplified,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_vocab(row)

    def get_known_words(self, language_code: str = "") -> set[str]:
        query = "SELECT word_simplified FROM vocab WHERE status IN ('known', 'ignored')"
        params: list = []
        if language_code:
            query += " AND language_code = ?"
            params.append(language_code)
        rows = self.conn.execute(query, tuple(params)).fetchall()
        return {r[0] for r in rows}

    def mark_word_known(self, word_simplified: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE vocab SET status = 'known', updated_at = ? WHERE word_simplified = ?",
            (now, word_simplified),
        )
        self.conn.commit()

    def mark_word_learning(self, word_simplified: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE vocab SET status = 'learning', updated_at = ? WHERE word_simplified = ?",
            (now, word_simplified),
        )
        self.conn.commit()

    def mark_word_ignored(self, word_simplified: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE vocab SET status = 'ignored', updated_at = ? WHERE word_simplified = ?",
            (now, word_simplified),
        )
        self.conn.commit()

    def get_vocab_stats(self, language_code: str = "") -> dict:
        suffix, params = self._lang_filter(language_code)
        known = self.conn.execute(
            f"SELECT COUNT(*) FROM vocab WHERE status = 'known'{suffix}", params
        ).fetchone()[0]
        learning = self.conn.execute(
            f"SELECT COUNT(*) FROM vocab WHERE status = 'learning'{suffix}", params
        ).fetchone()[0]
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM vocab WHERE 1=1{suffix}", params
        ).fetchone()[0]
        return {"known": known, "learning": learning, "total": total}

    def list_vocab(
        self,
        page: int = 1,
        per_page: int = 200,
        status: str | None = None,
        search: str | None = None,
        sort: str = "frequency",
        language_code: str = "",
    ) -> tuple[list[VocabWord], int]:
        where = []
        params: list = []

        if status:
            where.append("status = ?")
            params.append(status)
        if search:
            where.append("(word_simplified LIKE ? OR reading LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if language_code:
            where.append("language_code = ?")
            params.append(language_code)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        # Total count
        count_row = self.conn.execute(
            f"SELECT COUNT(*) FROM vocab {where_clause}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        # Sort
        sort_map = {
            "frequency": "frequency_rank ASC NULLS LAST",
            "hsk": "hsk_level ASC NULLS LAST",
            "recent": "id DESC",
        }
        order = sort_map.get(sort, sort_map["frequency"])

        offset = (page - 1) * per_page
        rows = self.conn.execute(
            f"SELECT * FROM vocab {where_clause} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()

        return [self._row_to_vocab(r) for r in rows], total

    def get_sentences_by_word(self, word: str) -> list[Sentence]:
        rows = self.conn.execute(
            """SELECT * FROM sentences
               WHERE unknown_word = ? OR text LIKE ?
               ORDER BY start_ms""",
            (word, f"%{word}%"),
        ).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    # === Events ===

    def log_event(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: str = "",
        new_value: str = "",
        language_code: str = "",
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT INTO events
               (entity_type, entity_id, action, old_value, new_value,
                timestamp, language_code)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity_type, entity_id, action, old_value, new_value, now, language_code),
        )
        self.conn.commit()

    # === Row mappers ===

    def _row_to_video(self, row) -> Video:
        return Video(
            id=row["id"],
            youtube_id=row["youtube_id"],
            title=row["title"] or "",
            channel=row["channel"] or "",
            duration_sec=row["duration_sec"] or 0,
            transcript_json=row["transcript_json"] or "",
            audio_path=row["audio_path"] or "",
            processed_at=row["processed_at"],
            language_code=row["language_code"] or "",
            subtitle_language=row["subtitle_language"] or "",
            subtitle_kind=row["subtitle_kind"] or "",
            target_subtitle_language=row["target_subtitle_language"] or "",
            target_subtitle_kind=row["target_subtitle_kind"] or "",
            target_transcript_json=row["target_transcript_json"] or "",
        )

    def _row_to_sentence(self, row) -> Sentence:
        row = dict(row)
        return Sentence(
            id=row["id"],
            video_id=row["video_id"],
            start_ms=row["start_ms"],
            end_ms=row["end_ms"],
            text=row["text"],
            text_segmented=row.get("text_segmented", ""),
            non_words_json=row.get("non_words_json", ""),
            reading=row.get("reading", ""),
            translation=row.get("translation", ""),
            unknown_word=row["unknown_word"],
            unknown_word_rank=row["unknown_word_rank"],
            known_synonyms_json=row.get("known_synonyms_json", ""),
            audio_clip_path=row.get("audio_clip_path", ""),
            screenshot_path=row.get("screenshot_path", ""),
            screenshot_enabled=bool(row["screenshot_enabled"]),
            status=row.get("status", "new"),
            language_code=row.get("language_code", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def _row_to_vocab(self, row) -> VocabWord:
        return VocabWord(
            id=row["id"],
            word_simplified=row["word_simplified"],
            word_traditional=row["word_traditional"] or "",
            reading=row["reading"] or "",
            definition_de=row["definition_de"] or "",
            hsk_level=row["hsk_level"],
            frequency_rank=row["frequency_rank"],
            status=row["status"] or "known",
            language_code=row["language_code"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
