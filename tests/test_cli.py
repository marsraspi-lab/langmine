"""Tests for the CLI entry point."""

import subprocess
import sys


def test_langmine_help():
    """`langmine --help` should exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "--help"],
        capture_output=True,
        text=True,
        cwd="/root/projects/langmine",
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
        cwd="/root/projects/langmine",
    )
    # Should either exit non-zero or print an error
    assert result.returncode != 0 or "error" in (result.stdout + result.stderr).lower()


def test_langmine_serve_subcommand_exists():
    """`langmine serve --help` should be a recognized subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "langmine.cli", "serve", "--help"],
        capture_output=True,
        text=True,
        cwd="/root/projects/langmine",
    )
    assert result.returncode == 0
    assert "serve" in result.stdout.lower()


def test_langmine_cli_imports_and_runs():
    """The CLI module should be importable and have a main function."""
    from langmine.cli import main
    assert callable(main)
