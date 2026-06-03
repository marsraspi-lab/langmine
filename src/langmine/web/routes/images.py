"""Image search API routes."""

from flask import Blueprint, jsonify, request, current_app

from ._helpers import _get_image_searcher

images_bp = Blueprint("images", __name__)

@images_bp.route("/api/images/search")
def search_images():
    """Search for images of a word. Query params: q, count (default 5)."""
    searcher = _get_image_searcher()
    if searcher is None:
        return jsonify({"error": "Image search not configured."}), 503

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing 'q' query parameter."}), 400

    count = request.args.get("count", 5, type=int)
    try:
        urls = searcher.search(query, count=count)
        return jsonify({"query": query, "images": urls})
    except Exception as e:
        return jsonify({"error": f"Image search failed: {e}"}), 500

