"""Tests for the CLI entry point."""

import os
import subprocess
import sys


def test_langmine_help():
    """`langmine --help` should exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "Usage" in result.stdout
    assert "langmine" in result.stdout.lower()


def test_langmine_mine_requires_url():
    """`langmine mine` without URL should show error or usage."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "mine"],
        capture_output=True,
        text=True,
    )
    # Should either exit non-zero or print an error
    assert result.returncode != 0 or "error" in (result.stdout + result.stderr).lower()


def test_langmine_serve_subcommand_exists():
    """`langmine serve --help` should be a recognized subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "serve", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "serve" in result.stdout.lower()


def test_langmine_export_subcommand_exists():
    """`langmine export --help` should be a recognized subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "export", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "export" in result.stdout.lower()


def test_langmine_cli_imports_and_runs():
    """The CLI module should be importable and have a main function."""
    from langmine.cli import main
    assert callable(main)


def test_serve_creates_app_with_real_adapters(tmp_path):
    """The serve command creates a Flask app with real adapter wiring."""

    from langmine.web.app import create_app
    from langmine.adapters import (
        SQLitePersistence, YouTubeTranscriptAdapter, YtdlpAudioAdapter,
        GoogleTranslateAdapter,
    )
    from langmine.languages.chinese import (
        ChineseLanguageService, CcCedictAdapter, JiebaFrequencyAdapter,
    )

    db_path = tmp_path / "test_langmine.db"
    app = create_app(
        persistence=SQLitePersistence(str(db_path)),
        language_processor=ChineseLanguageService(
            CcCedictAdapter(), GoogleTranslateAdapter(), JiebaFrequencyAdapter()
        ),
        transcript_source=YouTubeTranscriptAdapter(),
        audio_processor=YtdlpAudioAdapter(),
    )
    app.config["TESTING"] = True

    with app.test_client() as client:
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "videos" in data
