"""Tests for M12 ImageSearch port and adapter."""

import pytest
from unittest.mock import patch, MagicMock

from langmine.domain.ports import ImageSearch


class TestImageSearchPort:
    """M12: ImageSearch port exists and is abstract."""

    def test_port_is_abstract(self):
        """ImageSearch is an ABC with abstract search() method."""
        assert hasattr(ImageSearch, "__abstractmethods__")
        assert "search" in ImageSearch.__abstractmethods__

    def test_port_cannot_be_instantiated(self):
        """ImageSearch cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ImageSearch()

    def test_search_signature(self):
        """search(query, count=5) → list[str]."""
        import inspect
        sig = inspect.signature(ImageSearch.search)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "query" in params
        assert "count" in params


class FakeImageSearch(ImageSearch):
    """Concrete implementation for testing."""
    def search(self, query, count=5):
        return [f"https://img.example.com/{query}_{i}" for i in range(count)]


class TestImageSearchContract:
    """M12: Verify contract through a fake implementation."""

    def test_returns_list_of_urls(self):
        """search() returns a list of URL strings."""
        searcher = FakeImageSearch()
        results = searcher.search("苹果", count=3)
        assert isinstance(results, list)
        assert len(results) == 3
        for url in results:
            assert url.startswith("https://")
            assert "苹果" in url

    def test_count_defaults_to_five(self):
        """Default count is 5."""
        searcher = FakeImageSearch()
        results = searcher.search("test")
        assert len(results) == 5


class TestGoogleImageSearchAdapter:
    """M12: GoogleImageSearch adapter via Google Custom Search API."""

    def test_adapter_importable(self):
        """Adapter module can be imported."""
        from langmine.adapters.google_image_search import GoogleImageSearch
        assert GoogleImageSearch is not None

    def test_adapter_implements_port(self):
        """GoogleImageSearch is an ImageSearch."""
        from langmine.adapters.google_image_search import GoogleImageSearch
        from langmine.domain.ports import ImageSearch
        assert issubclass(GoogleImageSearch, ImageSearch)

    def test_search_returns_urls(self):
        """search() parses Google CSE JSON and returns image URLs."""
        from langmine.adapters.google_image_search import GoogleImageSearch

        searcher = GoogleImageSearch(api_key="test-key", cse_id="test-cx")

        # Mock the HTTP response from Google CSE
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"link": "https://example.com/img1.jpg"},
                {"link": "https://example.com/img2.jpg"},
                {"link": "https://example.com/img3.jpg"},
            ]
        }

        with patch("requests.get", return_value=mock_response) as mock_get:
            results = searcher.search("苹果", count=3)

            assert len(results) == 3
            assert results == [
                "https://example.com/img1.jpg",
                "https://example.com/img2.jpg",
                "https://example.com/img3.jpg",
            ]

            # Verify query parameters
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "test-key" in str(call_args)
            assert "test-cx" in str(call_args)
            assert "苹果" in str(call_args)

    def test_search_empty_results(self):
        """Returns empty list when no images found."""
        from langmine.adapters.google_image_search import GoogleImageSearch

        searcher = GoogleImageSearch(api_key="test-key", cse_id="test-cx")
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No "items" key

        with patch("requests.get", return_value=mock_response):
            results = searcher.search("xyzunknown", count=5)
            assert results == []
