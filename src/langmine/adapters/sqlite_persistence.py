"""SQLite persistence adapter — wraps db.py behind Persistence port.

This is one possible implementation of the Persistence port.
Swap for FileSystemPersistence, PostgresPersistence, or InMemoryPersistence
without changing any domain code.
"""

from pathlib import Path

from langmine.domain.ports import Persistence
from langmine.domain.models import Video, Sentence, VocabWord
from langmine.db import Database


class SQLitePersistence(Persistence):
    """Stores all LangMine data in SQLite."""

    def __init__(self, db_path: str = "~/.langmine/langmine.db"):
        self._db = Database(Path(db_path).expanduser())

    @property
    def conn(self):
        return self._db.conn

    # === Videos ===

    def save_video(self, video: Video) -> None:
        if video.id:
            self.conn.execute(
                """UPDATE videos SET title=?, channel=?, duration_sec=?,
                   transcript_json=?, audio_path=?
                   WHERE id=?""",
                (video.title, video.channel, video.duration_sec,
                 video.transcript_json, video.audio_path, video.id),
            )
        else:
            cursor = self.conn.execute(
                """INSERT OR REPLACE INTO videos
                   (youtube_id, title, channel, duration_sec,
                    transcript_json, audio_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (video.youtube_id, video.title, video.channel,
                 video.duration_sec, video.transcript_json, video.audio_path),
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

    def list_videos(self) -> list[Video]:
        rows = self.conn.execute(
            "SELECT * FROM videos ORDER BY processed_at DESC"
        ).fetchall()
        return [self._row_to_video(r) for r in rows]

    def video_exists(self, youtube_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM videos WHERE youtube_id = ?", (youtube_id,)
        ).fetchone()
        return row is not None

    # === Sentences ===

    def save_sentences(self, sentences: list[Sentence]) -> None:
        for s in sentences:
            if s.id:
                self.conn.execute(
                    """UPDATE sentences SET status=?, translation_de=?,
                       pinyin=?, text_segmented=?, unknown_word=?,
                       screenshot_enabled=?
                       WHERE id=?""",
                    (s.status, s.translation_de, s.pinyin,
                     s.text_segmented, s.unknown_word,
                     int(s.screenshot_enabled), s.id),
                )
            else:
                cursor = self.conn.execute(
                    """INSERT INTO sentences
                       (video_id, start_ms, end_ms, text, text_segmented,
                        non_words_json, pinyin, translation_de, unknown_word,
                        unknown_word_rank, known_synonyms_json,
                        audio_clip_path, screenshot_path, screenshot_enabled,
                        status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (s.video_id, s.start_ms, s.end_ms, s.text,
                     s.text_segmented, s.non_words_json, s.pinyin,
                     s.translation_de, s.unknown_word, s.unknown_word_rank,
                     s.known_synonyms_json, s.audio_clip_path,
                     s.screenshot_path, int(s.screenshot_enabled), s.status),
                )
                s.id = cursor.lastrowid
        self.conn.commit()

    def get_sentences_by_video(
        self, video_id: int, status: str | None = None
    ) -> list[Sentence]:
        query = "SELECT * FROM sentences WHERE video_id = ?"
        params: tuple = (video_id,)
        if status:
            query += " AND status = ?"
            params = (video_id, status)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    def get_stash_candidates(self, limit: int = 20) -> list[Sentence]:
        rows = self.conn.execute(
            """SELECT * FROM sentences WHERE status = 'stashed'
               ORDER BY unknown_word_rank ASC NULLS LAST
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    def update_sentence(self, sentence: Sentence) -> None:
        if not sentence.id:
            raise ValueError("Cannot update sentence without id")
        self.conn.execute(
            """UPDATE sentences SET status=?, translation_de=?,
               pinyin=?, text_segmented=?, unknown_word=?,
               screenshot_enabled=? WHERE id=?""",
            (sentence.status, sentence.translation_de, sentence.pinyin,
             sentence.text_segmented, sentence.unknown_word,
             int(sentence.screenshot_enabled), sentence.id),
        )
        self.conn.commit()

    def get_sentences_by_status(self, status: str) -> list[Sentence]:
        rows = self.conn.execute(
            "SELECT * FROM sentences WHERE status = ?", (status,)
        ).fetchall()
        return [self._row_to_sentence(r) for r in rows]

    def reclassify_stashed(self, video_id: int) -> int:
        """Re-run i+1 classification on stashed sentences for a video.
        Returns count of sentences that dropped to i+1.
        Stub for now — full implementation in M2."""
        return 0

    # === Vocab ===

    def save_vocab_word(self, word: VocabWord) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO vocab
               (word_simplified, word_traditional, pinyin, definition_de,
                hsk_level, frequency_rank, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (word.word_simplified, word.word_traditional, word.pinyin,
             word.definition_de, word.hsk_level, word.frequency_rank,
             word.status),
        )
        self.conn.commit()

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        row = self.conn.execute(
            "SELECT * FROM vocab WHERE word_simplified = ?", (word_simplified,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_vocab(row)

    def get_known_words(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT word_simplified FROM vocab WHERE status = 'known'"
        ).fetchall()
        return {r[0] for r in rows}

    def mark_word_known(self, word_simplified: str) -> None:
        self.conn.execute(
            "UPDATE vocab SET status = 'known' WHERE word_simplified = ?",
            (word_simplified,),
        )
        self.conn.commit()

    def mark_word_learning(self, word_simplified: str) -> None:
        self.conn.execute(
            "UPDATE vocab SET status = 'learning' WHERE word_simplified = ?",
            (word_simplified,),
        )
        self.conn.commit()

    def get_vocab_stats(self) -> dict:
        known = self.conn.execute(
            "SELECT COUNT(*) FROM vocab WHERE status = 'known'"
        ).fetchone()[0]
        learning = self.conn.execute(
            "SELECT COUNT(*) FROM vocab WHERE status = 'learning'"
        ).fetchone()[0]
        total = self.conn.execute(
            "SELECT COUNT(*) FROM vocab"
        ).fetchone()[0]
        return {"known": known, "learning": learning, "total": total}

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
        )

    def _row_to_sentence(self, row) -> Sentence:
        return Sentence(
            id=row["id"],
            video_id=row["video_id"],
            start_ms=row["start_ms"],
            end_ms=row["end_ms"],
            text=row["text"],
            text_segmented=row["text_segmented"] or "",
            non_words_json=row["non_words_json"] or "",
            pinyin=row["pinyin"] or "",
            translation_de=row["translation_de"] or "",
            unknown_word=row["unknown_word"],
            unknown_word_rank=row["unknown_word_rank"],
            known_synonyms_json=row["known_synonyms_json"] or "",
            audio_clip_path=row["audio_clip_path"] or "",
            screenshot_path=row["screenshot_path"] or "",
            screenshot_enabled=bool(row["screenshot_enabled"]),
            status=row["status"] or "new",
        )

    def _row_to_vocab(self, row) -> VocabWord:
        return VocabWord(
            id=row["id"],
            word_simplified=row["word_simplified"],
            word_traditional=row["word_traditional"] or "",
            pinyin=row["pinyin"] or "",
            definition_de=row["definition_de"] or "",
            hsk_level=row["hsk_level"],
            frequency_rank=row["frequency_rank"],
            status=row["status"] or "known",
        )
