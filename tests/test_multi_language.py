"""Tests for multi-language data isolation.

Sentences, videos, and vocab must be partitioned by language_code.
Switching languages filters data — never purges.
"""

from langmine.domain.models import Sentence, Video, VocabWord


class TestLanguageCodeOnModels:
    """language_code must exist on all persistent domain models."""

    def test_sentence_has_language_code(self):
        s = Sentence(video_id=1, start_ms=0, end_ms=1000, text="hello")
        assert hasattr(s, "language_code"), "Sentence missing language_code field"
        assert s.language_code == ""  # default is empty string

    def test_video_has_language_code(self):
        v = Video(youtube_id="abc123")
        assert hasattr(v, "language_code"), "Video missing language_code field"
        assert v.language_code == ""

    def test_vocab_has_language_code(self):
        w = VocabWord(word_simplified="test")
        assert hasattr(w, "language_code"), "VocabWord missing language_code field"
        assert w.language_code == ""


class TestLanguageIsolation:
    """Data from one language must not leak into another."""

    def test_known_words_are_language_scoped(self):
        """Known Chinese words should not count when mining Spanish."""
        from langmine.domain.ports import Persistence

        class FakePersistence(Persistence):
            def __init__(self):
                self._vocab = {}
                self._sentences = []
                self._videos = []
                self._next_id = 1

            def save_vocab_word(self, w):
                w.id = self._next_id
                self._next_id += 1
                self._vocab[w.word_simplified] = w

            def get_known_words(self, language_code=None):
                return {
                    w.word_simplified
                    for w in self._vocab.values()
                    if w.status in ("known", "ignored")
                    and (language_code is None or w.language_code == language_code)
                }

            # stubs
            def save_video(self, v):
                pass

            def get_video(self, yt_id):
                pass

            def list_videos(self, language_code=None):
                return []

            def delete_video(self, video_id):
                return False

            def save_sentences(self, ss):
                pass

            def get_sentences_by_video(self, vid, status=None, language_code=None):
                return []

            def update_sentence(self, s):
                pass

            def get_sentences_by_status(self, status, language_code=None):
                return []

            def get_vocab_word(self, w):
                pass

            def mark_word_known(self, w):
                pass

            def mark_word_learning(self, w):
                pass

            def get_vocab_stats(self, language_code=None):
                return {"known": 0, "learning": 0, "total": 0}

            def list_vocab(
                self,
                page=1,
                per_page=200,
                status=None,
                search=None,
                sort="frequency",
                language_code=None,
            ):
                return [], 0

            def get_sentences_by_word(self, word):
                return []

            def get_sentences_by_words(self, words, max_per_word=5):
                return {w: [] for w in words}

            def mark_word_ignored(self, word_simplified: str) -> None:
                if word_simplified in self._vocab:
                    self._vocab[word_simplified].status = "ignored"
                else:
                    self._vocab[word_simplified] = VocabWord(
                        word_simplified=word_simplified, status="ignored"
                    )

            def update_vocab_status(self, word_simplified, status, language_code=""):
                if word_simplified in self._vocab:
                    self._vocab[word_simplified].status = status
                else:
                    self._vocab[word_simplified] = VocabWord(
                        word_simplified=word_simplified,
                        status=status,
                        language_code=language_code or "zh",
                    )

            def log_event(
                self,
                entity_type: str,
                entity_id: int,
                action: str,
                old_value: str = "",
                new_value: str = "",
                language_code: str = "",
            ) -> None:
                pass

        p = FakePersistence()
        p.save_vocab_word(
            VocabWord(
                word_simplified="我们",
                reading="wǒmen",
                status="known",
                language_code="zh",
            )
        )
        p.save_vocab_word(
            VocabWord(
                word_simplified="hola",
                reading="ola",
                status="known",
                language_code="es",
            )
        )

        zh_known = p.get_known_words(language_code="zh")
        es_known = p.get_known_words(language_code="es")

        assert "我们" in zh_known, "Chinese known word missing in zh scope"
        assert "hola" not in zh_known, "Spanish word leaked into Chinese known words"
        assert "hola" in es_known, "Spanish known word missing in es scope"
        assert "我们" not in es_known, "Chinese word leaked into Spanish known words"

    def test_list_vocab_filters_by_language(self):
        """Vocab listing must be scoped to one language."""
        from langmine.domain.ports import Persistence

        class FakePersistence(Persistence):
            def __init__(self):
                self._vocab = {}

            def save_vocab_word(self, w):
                self._vocab[w.word_simplified] = w

            def list_vocab(
                self,
                page=1,
                per_page=200,
                status=None,
                search=None,
                sort="frequency",
                language_code=None,
            ):
                words = list(self._vocab.values())
                if language_code:
                    words = [w for w in words if w.language_code == language_code]
                return words, len(words)

            # stubs
            def save_video(self, v):
                pass

            def get_video(self, yt_id):
                pass

            def list_videos(self, language_code=None):
                return []

            def delete_video(self, video_id):
                return False

            def save_sentences(self, ss):
                pass

            def get_sentences_by_video(self, vid, status=None, language_code=None):
                return []

            def update_sentence(self, s):
                pass

            def get_sentences_by_status(self, status, language_code=None):
                return []

            def get_known_words(self, language_code=None):
                return set()

            def get_vocab_word(self, w):
                pass

            def mark_word_known(self, w):
                pass

            def mark_word_learning(self, w):
                pass

            def get_vocab_stats(self, language_code=None):
                return {"known": 0, "learning": 0, "total": 0}

            def get_sentences_by_word(self, word):
                return []

            def get_sentences_by_words(self, words, max_per_word=5):
                return {w: [] for w in words}

            def mark_word_ignored(self, word_simplified: str) -> None:
                pass

            def update_vocab_status(self, word_simplified, status, language_code=""):
                pass

            def log_event(
                self,
                entity_type: str,
                entity_id: int,
                action: str,
                old_value: str = "",
                new_value: str = "",
                language_code: str = "",
            ) -> None:
                pass

        p = FakePersistence()
        p.save_vocab_word(VocabWord(word_simplified="我们", language_code="zh"))
        p.save_vocab_word(VocabWord(word_simplified="gracias", language_code="es"))

        zh_words, zh_total = p.list_vocab(language_code="zh")
        assert zh_total == 1
        assert zh_words[0].word_simplified == "我们"

        es_words, es_total = p.list_vocab(language_code="es")
        assert es_total == 1
        assert es_words[0].word_simplified == "gracias"
