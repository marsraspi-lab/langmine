"""Server entry point for LangMine."""

import argparse
from importlib.metadata import version as _pkg_version


def _get_version() -> str:
    """Return the installed package version."""
    try:
        return _pkg_version("langmine")
    except Exception:
        return "unknown"


def main():
    """Start the LangMine Flask web UI with real adapters."""
    parser = argparse.ArgumentParser(
        prog="langmine",
        description="YouTube sentence mining for language learning (Web UI)",
    )
    parser.add_argument(
        "--version", action="version", version=f"langmine {_get_version()}"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")

    args = parser.parse_args()

    from langmine.web.app import create_production_app

    app = create_production_app()

    print(f"⛏️  LangMine server starting at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
