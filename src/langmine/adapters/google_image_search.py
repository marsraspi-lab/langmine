"""Google Custom Search adapter — image search for LangMine.

Uses Google Custom Search JSON API (free tier: 100 queries/day).
Requires GOOGLE_API_KEY and GOOGLE_CSE_ID set in environment or config.
"""

import requests

from langmine.domain.ports import ImageSearch


class GoogleImageSearch(ImageSearch):
    """Search for images using Google Custom Search API."""

    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cse_id: str):
        self._api_key = api_key
        self._cse_id = cse_id

    def search(self, query: str, count: int = 5) -> list[str]:
        """Return up to `count` image URLs for a query."""
        params = {
            "key": self._api_key,
            "cx": self._cse_id,
            "q": query,
            "searchType": "image",
            "num": min(count, 10),  # Google max is 10
        }
        resp = requests.get(self.BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        return [item["link"] for item in items[:count]]
