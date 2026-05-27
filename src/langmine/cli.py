"""CLI entry point for LangMine."""

import argparse
import sys


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
        print(f"Mining: {args.url}")
        if args.dry_run:
            print("(dry run — no data saved)")

    elif args.command == "serve":
        print(f"Starting LangMine server at http://{args.host}:{args.port}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
