"""CLI entry point for LangMine."""

import argparse
import sys

from langmine.config import load_config
from langmine.transcript import _extract_video_id


def main():
    """Main entry point for the langmine CLI."""
    parser = argparse.ArgumentParser(
        prog="langmine",
        description="YouTube sentence mining for language learning",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # mine
    mine_parser = subparsers.add_parser("mine", help="Mine sentences from a YouTube video")
    mine_parser.add_argument("url", nargs="?", help="YouTube video URL")
    mine_parser.add_argument("--dry-run", action="store_true", help="Show what would be mined without saving")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the LangMine web UI")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")

    args = parser.parse_args()

    if args.command == "mine":
        if not args.url:
            print("Error: A YouTube URL is required for the 'mine' command.", file=sys.stderr)
            mine_parser.print_usage()
            sys.exit(1)
        _cmd_mine(args)

    elif args.command == "serve":
        _cmd_serve(args)

    else:
        parser.print_help()


def _cmd_mine(args):
    """Run the mining pipeline with real adapters."""
    config = load_config()
    video_id = _extract_video_id(args.url)
    output_dir = config.data_dir if hasattr(config, 'data_dir') else "/tmp/langmine"

    # Wire up real adapters
    from langmine.adapters import (
        YouTubeTranscriptAdapter,
        YtdlpAudioAdapter,
        SQLitePersistence,
        GoogleTranslateAdapter,
        CcCedictAdapter,
        JiebaFrequencyAdapter,
    )
    from langmine.pipeline import process_video
    from langmine.domain.services.chinese import ChineseLanguageService

    transcript = YouTubeTranscriptAdapter()
    audio = YtdlpAudioAdapter()
    persistence = SQLitePersistence()
    processor = ChineseLanguageService(
        CcCedictAdapter(), GoogleTranslateAdapter(), JiebaFrequencyAdapter()
    )

    print(f"⛏️  Mining: {args.url}")
    print(f"   Output: {output_dir}")
    print()

    try:
        result = process_video(
            transcript_source=transcript,
            audio_processor=audio,
            persistence=persistence,
            language_processor=processor,
            video_id=video_id,
            output_dir=output_dir,
        )

        # Print results
        print(f"📊 Results for: {video_id}")
        print(f"   Total sentences: {result['total_sentences']}")
        print(f"   🔥 i+1 candidates: {len(result['i1_candidates'])}")
        print(f"   ✅ i+0 (all known): {result['i0_count']}")
        print(f"   📥 Stashed (i+2+): {result['stash_count']}")
        print()

        if result["i1_candidates"]:
            print("i+1 Sentences (learn these):")
            for i, s in enumerate(result["i1_candidates"][:10], 1):
                rank_str = f"#{s.unknown_word_rank}" if s.unknown_word_rank else "?"
                print(f"   {i}. {s.text}")
                print(f"      🆕 {s.unknown_word} ({rank_str})")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_serve(args):
    """Start the LangMine Flask web UI with real adapters."""
    from langmine.web.app import create_app
    from langmine.adapters import (
        YouTubeTranscriptAdapter,
        YtdlpAudioAdapter,
        SQLitePersistence,
        GoogleTranslateAdapter,
        CcCedictAdapter,
        JiebaFrequencyAdapter,
    )
    from langmine.domain.services.chinese import ChineseLanguageService

    persistence = SQLitePersistence()
    processor = ChineseLanguageService(
        CcCedictAdapter(), GoogleTranslateAdapter(), JiebaFrequencyAdapter()
    )
    transcript = YouTubeTranscriptAdapter()
    audio = YtdlpAudioAdapter()

    app = create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
    )

    print(f"⛏️  LangMine server starting at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
