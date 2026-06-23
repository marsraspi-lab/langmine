from langmine.languages.chinese.frequency import SubtlexChAdapter


def test_subtlex_list_words_first_page():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=0, limit=100)
    assert len(words) == 100
    assert words[0] == ("的", 1)
    assert words[1][1] == 2
    assert words[99][1] == 100


def test_subtlex_list_words_middle_page():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=100, limit=100)
    assert len(words) == 100
    assert words[0][1] == 101
    assert words[99][1] == 200


def test_subtlex_list_words_last_page_partial():
    adapter = SubtlexChAdapter()
    total = adapter.count_words()
    words = adapter.list_words(offset=total - 10, limit=100)
    assert len(words) == 10


def test_subtlex_count_words():
    adapter = SubtlexChAdapter()
    assert adapter.count_words() == 99121


def test_subtlex_list_words_returns_tuples():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=0, limit=5)
    for w in words:
        assert isinstance(w, tuple)
        assert len(w) == 2
        assert isinstance(w[0], str)
        assert isinstance(w[1], int)
