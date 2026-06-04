"""Video mining and management API routes."""

import os
import queue
import threading

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    request,
    stream_with_context,
)

from ._helpers import (
    _get_audio_processor,
    _get_classifier,
    _get_language_code,
    _get_persistence,
    _get_processor,
    _get_transcript_source,
    _sentence_to_dict,
    _video_with_counts,
)

videos_bp = Blueprint("videos", __name__)


@videos_bp.route("/api/videos")
def list_videos():
    """List all videos with sentence counts by status."""
    persistence = _get_persistence()
    lang = _get_language_code()
    videos = persistence.list_videos(language_code=lang)

    return jsonify(
        {"videos": [_video_with_counts(persistence, v, lang) for v in videos]}
    )


@videos_bp.route("/api/videos/<int:video_id>", methods=["DELETE"])
def delete_video_route(video_id: int):
    """Delete a video and all its sentences."""
    persistence = _get_persistence()
    deleted = persistence.delete_video(video_id)
    if not deleted:
        return jsonify({"error": "Video not found"}), 404
    return jsonify({"ok": True})


@videos_bp.route("/api/videos/mine", methods=["POST"])
def mine_video():
    """Mine a YouTube video with SSE progress streaming.

    Accepts JSON with 'url' or multipart/form-data with 'url' + optional
    transcript file (.srt/.vtt). Streams progress as text/event-stream.
    """
    persistence = _get_persistence()
    processor = _get_processor()
    audio = _get_audio_processor()
    transcript = _get_transcript_source()
    is_file_upload = False

    # ── Parse request (must happen before streaming) ──────────────────
    if request.content_type and "multipart" in request.content_type:
        url = request.form.get("url", "").strip()
        if not url:
            return jsonify({"error": "Missing 'url' field"}), 400
        file = request.files.get("file")
        if file and file.filename:
            InlineTranscriptSource = current_app.config.get(
                "LANGMINE_INLINE_TRANSCRIPT_CLASS"
            )
            parse_subtitle_file = current_app.config.get("LANGMINE_PARSE_SUBTITLE_FILE")
            if InlineTranscriptSource and parse_subtitle_file:
                content = file.read().decode("utf-8")
                chunks = parse_subtitle_file(content, filename=file.filename)
                if not chunks:
                    return jsonify(
                        {"error": "No subtitle entries found in uploaded file"}
                    ), 400
                transcript = InlineTranscriptSource(chunks)
                is_file_upload = True
    else:
        data = request.get_json(silent=True)
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' field"}), 400
        url = data["url"]

    from langmine.transcript import _extract_video_id

    video_id = _extract_video_id(url)

    # Parse optional subtitle language selection (M26)
    language = (
        request.form.get("language", "")
        if request.content_type and "multipart" in request.content_type
        else data.get("language", "")
    )
    if language and not is_file_upload and transcript is not None:
        try:
            subs = transcript.list_subtitles(video_id)
            match = next((s for s in subs if s.language_code == language), None)
        except Exception:
            pass

    # ── Choose code path ─────────────────────────────────────────────
    accept = request.headers.get("Accept", "")
    use_sse = "text/event-stream" in accept

    if not use_sse:
        # Synchronous path — backward compatible, no threading needed.
        # Used by test client and non-browser clients.
        try:
            from langmine.pipeline import MineError, process_video

            config = current_app.config["LANGMINE_CONFIG"]
            output_dir = config.data_dir
            os.makedirs(output_dir, exist_ok=True)

            result = process_video(
                transcript_source=transcript,
                audio_processor=audio,
                persistence=persistence,
                language_processor=processor,
                video_id=video_id,
                output_dir=output_dir,
                config=config,
                subtitle_language=language if not is_file_upload else "",
            )

            video = persistence.get_video(video_id)
            if video and video.id:
                persistence.log_event(
                    entity_type="video",
                    entity_id=video.id,
                    action="mined",
                    new_value=video_id,
                    language_code=config.source_language,
                )
                # Persist subtitle language + kind (M26)
                if language:
                    video.subtitle_language = language
                    try:
                        subs = transcript.list_subtitles(video_id)
                        match = next(
                            (s for s in subs if s.language_code == language), None
                        )
                        video.subtitle_kind = match.kind if match else ""
                    except Exception:
                        pass
                    persistence.save_video(video)

            return jsonify(
                {
                    "video_id": video.id if video else None,
                    "youtube_id": video_id,
                    "i1_candidates": len(result["i1_candidates"]),
                    "i0_count": result["i0_count"],
                    "stash_count": result["stash_count"],
                    "total_sentences": result["total_sentences"],
                    "i1_count": len(result["i1_candidates"]),
                }
            )
        except MineError as e:
            return jsonify({"error": str(e), "stage": e.stage}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Mining failed: {e}"}), 500

    # SSE streaming path — live progress for the browser
    import json as _json

    progress_queue: queue.Queue = queue.Queue()

    def _do_mine(app):
        """Run mining in a thread, pushing progress to the queue."""
        with app.app_context():
            try:
                from langmine.pipeline import MineError, process_video

                config = current_app.config["LANGMINE_CONFIG"]
                output_dir = config.data_dir
                os.makedirs(output_dir, exist_ok=True)

                def _on_progress(msg: str):
                    progress_queue.put(("progress", msg))

                result = process_video(
                    transcript_source=transcript,
                    audio_processor=audio,
                    persistence=persistence,
                    language_processor=processor,
                    video_id=video_id,
                    output_dir=output_dir,
                    config=config,
                    progress_callback=_on_progress,
                    subtitle_language=language if not is_file_upload else "",
                )

                video = persistence.get_video(video_id)
                if video and video.id:
                    persistence.log_event(
                        entity_type="video",
                        entity_id=video.id,
                        action="mined",
                        new_value=video_id,
                        language_code=config.source_language,
                    )
                    # Persist subtitle language + kind (M26)
                    if language:
                        video.subtitle_language = language
                        try:
                            subs = transcript.list_subtitles(video_id)
                            match = next(
                                (s for s in subs if s.language_code == language), None
                            )
                            video.subtitle_kind = match.kind if match else ""
                        except Exception:
                            pass
                        persistence.save_video(video)

                progress_queue.put(
                    (
                        "done",
                        {
                            "video_id": video.id if video else None,
                            "youtube_id": video_id,
                            "i1_candidates": len(result["i1_candidates"]),
                            "i0_count": result["i0_count"],
                            "stash_count": result["stash_count"],
                            "total_sentences": result["total_sentences"],
                            "i1_count": len(result["i1_candidates"]),
                        },
                    )
                )
            except MineError as e:
                msg = str(e)
                stage = e.stage
                if stage == "transcript":
                    # Enrich with subtitle info if available
                    try:
                        subs = transcript.list_subtitles(video_id)
                    except Exception:
                        subs = []
                    if subs:
                        langs = ", ".join(
                            f"{s.language_name} ({s.kind})" for s in subs[:3]
                        )
                        msg = f"This video has subtitles ({langs}) but download failed. Try again."
                    else:
                        msg = "This video has no subtitles in any language."
                    stage = "transcript"
                progress_queue.put(("error", {"message": msg, "stage": stage}))
            except ValueError as e:
                progress_queue.put(("error", {"message": str(e), "stage": "unknown"}))
            except Exception as e:
                progress_queue.put(
                    ("error", {"message": f"Mining failed: {e}", "stage": "unknown"})
                )

    def _sse_stream():
        """SSE generator: yield progress events + final result."""
        app = current_app._get_current_object()
        thread = threading.Thread(target=_do_mine, args=(app,), daemon=True)
        thread.start()

        while True:
            try:
                kind, payload = progress_queue.get(timeout=0.2)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

            if kind == "progress":
                yield f"data: {_json.dumps({'status': payload})}\n\n"
            elif kind == "done":
                yield f"data: {_json.dumps(payload)}\n\n"
                return
            elif kind == "error":
                yield f"data: {_json.dumps({'error': payload})}\n\n"
                return

    return Response(
        stream_with_context(_sse_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@videos_bp.route("/api/videos/subtitles")
def list_subtitles():
    """List available subtitle tracks for a YouTube video."""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    from langmine.transcript import _extract_video_id

    try:
        video_id = _extract_video_id(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    transcript_source = _get_transcript_source()
    if transcript_source is None:
        return jsonify({"subtitles": [], "available": False}), 200

    try:
        subs = transcript_source.list_subtitles(video_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"subtitles": [], "available": False}), 200

    return jsonify(
        {
            "subtitles": [
                {
                    "language_code": s.language_code,
                    "language_name": s.language_name,
                    "kind": s.kind,
                }
                for s in subs
            ],
            "available": len(subs) > 0,
        }
    )


@videos_bp.route("/api/videos/preview", methods=["POST"])
def preview_video():
    """Estimate difficulty for a YouTube video before mining.

    Fetches transcript, segments into sentences, and classifies each
    word against the user's known vocabulary. Does NOT persist anything.
    Returns stats and annotated sentences with word-level highlighting.
    """
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' field"}), 400

    url = data["url"].strip()
    if not url:
        return jsonify({"error": "Missing 'url' field"}), 400

    from langmine.transcript import _extract_video_id, merge_sentences

    config = current_app.config["LANGMINE_CONFIG"]
    video_id = _extract_video_id(url)

    transcript_source = _get_transcript_source()
    persistence = _get_persistence()
    processor = _get_processor()

    if transcript_source is None or processor is None:
        return jsonify(
            {"error": "Transcript source or language processor not configured."}
        ), 503

    try:
        chunks = transcript_source.fetch(video_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    merged = merge_sentences(chunks, gap_ms=config.sentence_gap_ms)
    known_words = persistence.get_known_words()

    preview_sentences = []
    total_content_words = 0
    total_known_words = 0
    unknown_counts = []

    for m in merged:
        tokens = processor.segment(m.text)
        # Classify each token
        words = []
        sentence_unknown = 0
        for token in tokens:
            if processor.is_non_word(token):
                status = "non-word"
            elif processor.is_proper_name(token, context_sentence=m.text):
                status = "proper-name"
                # Proper names are not content words — do NOT increment counters
            elif token in known_words:
                status = "known"
                total_content_words += 1
                total_known_words += 1
            else:
                status = "learning"
                total_content_words += 1
                sentence_unknown += 1
            words.append({"token": token, "status": status})

        unknown_counts.append(sentence_unknown)

        entry = {
            "text": m.text,
            "text_segmented": " / ".join(tokens),
            "reading": processor.get_reading(m.text),
            "translation_de": processor.translate_sentence(m.text),
            "words": words,
            "start_ms": m.start_ms,
            "end_ms": m.end_ms,
            "unknown_count": sentence_unknown,
        }
        preview_sentences.append(entry)

    total_sentences = len(merged)
    i1_count = sum(1 for u in unknown_counts if u == 1)
    i0_count = sum(1 for u in unknown_counts if u == 0)
    stash_count = sum(1 for u in unknown_counts if u >= 2)
    known_word_pct = (
        round(total_known_words / total_content_words * 100, 1)
        if total_content_words > 0
        else 0.0
    )
    avg_unknown = (
        round(sum(unknown_counts) / total_sentences, 1) if total_sentences > 0 else 0.0
    )

    return jsonify(
        {
            "total_sentences": total_sentences,
            "i1_estimated": i1_count,
            "i0_count": i0_count,
            "stash_count": stash_count,
            "known_word_pct": known_word_pct,
            "avg_unknown_per_sentence": avg_unknown,
            "sentences": preview_sentences,
        }
    )


@videos_bp.route("/api/videos/<int:video_id>/sentences")
def get_sentences(video_id: int):
    """Get sentences for a video, optionally filtered by status."""
    persistence = _get_persistence()
    lang = _get_language_code()
    status = request.args.get("status")
    if status == "all":
        status = None  # "all" means no filter — every sentence visible

    sentences = persistence.get_sentences_by_video(
        video_id, status=status, language_code=lang
    )

    return jsonify(
        {
            "video_id": video_id,
            "filter_status": status,
            "sentences": [
                _sentence_to_dict(s, persistence, processor=_get_processor())
                for s in sentences
            ],
        }
    )


@videos_bp.route("/api/videos/<int:video_id>/transcript")
def get_transcript(video_id: int):
    """Return all sentences in time-order for the reading view."""
    persistence = _get_persistence()
    lang = _get_language_code()
    sentences = persistence.get_sentences_by_video(video_id, language_code=lang)
    # Sort chronologically for reading order
    sentences.sort(key=lambda s: s.start_ms)
    return jsonify(
        {
            "video_id": video_id,
            "sentences": [
                _sentence_to_dict(s, persistence, processor=_get_processor())
                for s in sentences
            ],
        }
    )


@videos_bp.route("/api/videos/<int:video_id>/reclassify", methods=["POST"])
def reclassify_sentences(video_id: int):
    """Re-classify all sentences for a video (M22).

    Re-runs classification with current known_words,
    saves updated statuses, returns sentences sorted by
    best-candidate-first (i1 by frequency, then i0, then stashed).
    Supports offset/limit pagination.
    """
    persistence = _get_persistence()
    _get_language_code()
    processor = _get_processor()

    classifier = _get_classifier()

    results = classifier.reclassify_all(video_id)

    # Paginate
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 50, type=int)
    page = results[offset : offset + limit]

    return jsonify(
        {
            "video_id": video_id,
            "total": len(results),
            "offset": offset,
            "limit": limit,
            "sentences": [
                _sentence_to_dict(s, persistence, processor=processor) for s in page
            ],
        }
    )
