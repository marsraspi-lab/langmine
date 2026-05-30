"""Tests for M11 cloze deletion in AnkiConnect adapter."""

from unittest.mock import patch, MagicMock

from langmine.domain.models import Sentence
from langmine.adapters.anki_connect import AnkiConnectAdapter


def _make_sentence(text="我们 一般 早上 起床", unknown="一般",
                   reading="wǒmen yībān", translation="Wir stehen auf",
                   audio="/tmp/audio.mp3"):
    """Create a Sentence with reasonable defaults for export testing."""
    return Sentence(
        video_id=1, start_ms=1000, end_ms=3000,
        text=text, text_segmented=text.replace(" ", " / "),
        reading=reading, translation_de=translation,
        unknown_word=unknown, unknown_word_rank=1847,
        audio_clip_path=audio, status="kept",
    )


class TestAnkiConnectCloze:
    """M11: AnkiConnectAdapter.export() with card_type='cloze'."""

    def test_export_accepts_card_type(self):
        """export() accepts card_type parameter without error."""
        adapter = AnkiConnectAdapter()
        # Verify the method signature includes card_type
        import inspect
        sig = inspect.signature(adapter.export)
        assert "card_type" in sig.parameters

    def test_cloze_uses_cloze_model_name(self):
        """With card_type='cloze', uses cloze_note_type for model."""
        adapter = AnkiConnectAdapter()

        with patch.object(adapter, "_invoke") as mock_invoke:
            with patch("os.path.exists", return_value=False):
                mock_invoke.side_effect = [
                    {"result": None},      # createDeck
                    {"result": None},      # createModel
                    {"result": [None]},    # canAddNotes
                    {"result": [1001]},    # addNotes
                ]

            adapter.export(
                sentences=[_make_sentence()],
                deck_name="Test",
                note_type_name="LangMine Cloze",
                card_type="cloze",
                card_css=".card{}",
                card_front="{{cloze:sentence_zh}}",
                card_back="{{sentence_zh}}",
            )

            # Check that createModel was called with isCloze
            create_model_calls = [
                c for c in mock_invoke.call_args_list
                if c[0][0] == "createModel"
            ]
            assert len(create_model_calls) == 1
            params = create_model_calls[0][0][1]

            assert "isCloze" in params, (
                "createModel must include isCloze for cloze notes"
            )

    def test_cloze_replaces_unknown_word_in_sentence(self):
        """Cloze export wraps unknown word in {{c1::...}}."""
        adapter = AnkiConnectAdapter()

        with patch.object(adapter, "_invoke") as mock_invoke:
            with patch("os.path.exists", return_value=False):
                mock_invoke.side_effect = [
                    {"result": None},      # createDeck
                    {"result": None},      # createModel
                    {"result": [None]},    # canAddNotes
                    {"result": [1001]},    # addNotes
                ]

            adapter.export(
                sentences=[_make_sentence(text="我们 一般 早上 起床", unknown="一般")],
                deck_name="Test",
                note_type_name="LangMine Cloze",
                card_type="cloze",
                card_css=".card{}",
                card_front="{{cloze:sentence_zh}}",
                card_back="{{sentence_zh}}",
            )

            # Find the addNotes call
            add_calls = [
                c for c in mock_invoke.call_args_list
                if c[0][0] == "addNotes"
            ]
            assert len(add_calls) == 1
            notes = add_calls[0][0][1]["notes"]
            assert len(notes) == 1

            sentence_zh = notes[0]["fields"]["sentence_zh"]
            assert "{{c1::一般}}" in sentence_zh, (
                f"Expected {{c1::一般}} in sentence field, got: {sentence_zh}"
            )
            # Original text should still be there (word just wrapped)
            assert "我们" in sentence_zh
            assert "早上" in sentence_zh
            assert "起床" in sentence_zh

    def test_cloze_preserves_audio_field(self):
        """Cloze export still includes audio references."""
        adapter = AnkiConnectAdapter()

        with patch.object(adapter, "_invoke") as mock_invoke:
            with patch.object(adapter, "_store_media") as mock_store:
                with patch("os.path.exists", return_value=True):
                    mock_invoke.side_effect = [
                        {"result": None},      # createDeck
                        {"result": None},      # createModel
                        {"result": [None]},    # canAddNotes
                        {"result": [1001]},    # addNotes
                    ]

                    adapter.export(
                        sentences=[_make_sentence(audio="/tmp/real.mp3")],
                        deck_name="Test",
                        note_type_name="LangMine Cloze",
                        card_type="cloze",
                        card_css=".card{}",
                        card_front="{{cloze:sentence_zh}}{{#audio}}{{audio}}{{/audio}}",
                        card_back="{{sentence_zh}}",
                    )

            add_calls = [
                c for c in mock_invoke.call_args_list
                if c[0][0] == "addNotes"
            ]
            notes = add_calls[0][0][1]["notes"]
            assert "[sound:" in notes[0]["fields"]["audio"], (
                "Audio field should contain [sound:...] reference"
            )

    def test_basic_export_unchanged(self):
        """Default card_type='basic' preserves existing behavior."""
        adapter = AnkiConnectAdapter()

        with patch.object(adapter, "_invoke") as mock_invoke:
            with patch("os.path.exists", return_value=False):
                mock_invoke.side_effect = [
                    {"result": None},      # createDeck
                    {"result": None},      # createModel
                    {"result": [None]},    # canAddNotes
                    {"result": [1001]},    # addNotes
                ]

            adapter.export(
                sentences=[_make_sentence(text="我们 一般 早上 起床", unknown="一般")],
                deck_name="Test",
                note_type_name="LangMine Sentence",
                card_type="basic",
            )

            add_calls = [
                c for c in mock_invoke.call_args_list
                if c[0][0] == "addNotes"
            ]
            notes = add_calls[0][0][1]["notes"]
            sentence_zh = notes[0]["fields"]["sentence_zh"]

            # Basic export: no cloze wrapping
            assert "{{c1::" not in sentence_zh, (
                "Basic export should NOT wrap words in cloze markers"
            )
            assert sentence_zh == "我们 一般 早上 起床"


class TestClozeImageUrlExport:
    """M12: cloze_image_url is included in cloze export."""

    def test_cloze_image_url_in_export_fields(self):
        """When sentence has cloze_image_url, it appears in the note."""
        adapter = AnkiConnectAdapter()

        with patch.object(adapter, "_invoke") as mock_invoke:
            with patch.object(adapter, "_store_media") as mock_store:
                with patch("os.path.exists", return_value=False):
                    mock_invoke.side_effect = [
                        {"result": None},
                        {"result": None},
                        {"result": [None]},
                        {"result": [1001]},
                    ]

                    s = _make_sentence(text="我们 一般 早上 起床", unknown="一般")
                    s.cloze_image_url = "https://example.com/hint.jpg"

                    adapter.export(
                        sentences=[s],
                        deck_name="Test",
                        note_type_name="LangMine Cloze",
                        card_type="cloze",
                        card_css=".card{}",
                        card_front="{{cloze:sentence_zh}}",
                        card_back="{{sentence_zh}}",
                    )

            add_calls = [
                c for c in mock_invoke.call_args_list
                if c[0][0] == "addNotes"
            ]
            notes = add_calls[0][0][1]["notes"]
            screenshot_field = notes[0]["fields"]["screenshot"]
            assert "hint.jpg" in screenshot_field, (
                f"cloze_image_url should appear in screenshot field, got: {screenshot_field}"
            )
