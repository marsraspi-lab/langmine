"""Architecture rule tests — AST-based, no false positives.

Each test verifies one forbidden dependency edge from ARCHITECTURE.md.
Parses Python source with ``ast`` so docstrings, comments, and string
literals never trigger false positives (unlike grep).

These run with every ``pytest`` invocation — instant local feedback.
"""

import ast
from pathlib import Path

SRC = Path("src/langmine")


# ── helpers ────────────────────────────────────────────────────────────────

def _py_files(*subdirs: str) -> list[Path]:
    """All .py files under src/langmine/<subdir>/ (recursive, sorted)."""
    result: list[Path] = []
    for d in subdirs:
        result.extend(sorted((SRC / d).rglob("*.py")))
    return result


def _module_refs(file: Path) -> list[tuple[int, str]]:
    """Return [(lineno, module), …] for every import in *file*.

    ``import X.Y``       → module = "X.Y"
    ``from X.Y import Z`` → module = "X.Y"
    """
    tree = ast.parse(file.read_text())
    refs: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                refs.append((node.lineno, node.module))
    return refs


def _deny(prefix: str, files: list[Path], rule: str) -> None:
    """Assert no file in *files* imports a module starting with *prefix*."""
    for f in files:
        for lineno, mod in _module_refs(f):
            if mod.startswith(prefix):
                rel = f.relative_to(SRC.parent)
                raise AssertionError(
                    f"{rel}:{lineno}: imports {mod!r} — {rule}"
                )


def _deny_except(
    prefix: str,
    files: list[Path],
    allowed: set[str],
    rule: str,
) -> None:
    """Like _deny, but *allowed* filenames (basename) are exempt."""
    for f in files:
        if f.name in allowed:
            continue
        for lineno, mod in _module_refs(f):
            if mod.startswith(prefix):
                rel = f.relative_to(SRC.parent)
                raise AssertionError(
                    f"{rel}:{lineno}: imports {mod!r} — {rule}"
                )


# ── file groups ────────────────────────────────────────────────────────────

_ALL_PY = sorted(SRC.rglob("*.py"))
_DOMAIN = _py_files("domain")
_WEB = _py_files("web")
_LANGUAGES = _py_files("languages")
_ADAPTERS = [f for f in _py_files("adapters") if f.name != "__init__.py"]
_LEAVES = [
    SRC / "pipeline.py",
    SRC / "config.py",
    SRC / "db.py",
    SRC / "transcript.py",
    SRC / "transcript_parser.py",
    SRC / "audio.py",
]
# Everything except language_factory.py and intra-package languages/ imports.
_OUTSIDE_LANGUAGES = [
    f for f in _ALL_PY
    if str(f.relative_to(SRC)) != "language_factory.py"
    and "languages/" not in str(f.relative_to(SRC))
]


# ── 0. domain/ is pure ──────────────────────────────────────────────────────

def test_domain_never_imports_adapters():
    _deny("langmine.adapters", _DOMAIN,
          "domain/ must not import adapters — use ports instead")


def test_domain_never_imports_languages():
    _deny("langmine.languages", _DOMAIN,
          "domain/ must not import languages/ — use LanguageProcessor port")


def test_domain_never_does_io():
    for mod in ("sqlite3", "subprocess", "requests", "urllib"):
        _deny(mod, _DOMAIN,
              f"domain/ must not import {mod} — no I/O in domain logic")


# ── 1. web/ uses ports, not adapters/languages ──────────────────────────────

def test_web_never_imports_languages():
    _deny("langmine.languages", _WEB,
          "web/ must not import languages/ — use language_factory instead")


def test_only_app_py_imports_adapters_in_web():
    _deny_except("langmine.adapters", _WEB, {"app.py"},
                 "web/ must not import adapters — only app.py may wire adapters")


# ── 2. language_factory.py is the SINGLE entry point to languages/ ──────────

def test_only_factory_imports_languages():
    _deny("langmine.languages", _OUTSIDE_LANGUAGES,
          "only language_factory.py may import from languages/")


# ── 3. languages/ is self-contained ─────────────────────────────────────────

def test_languages_never_imports_web():
    _deny("langmine.web", _LANGUAGES,
          "languages/ must not import web/ — web is an outer layer")


def test_languages_never_imports_adapters():
    _deny("langmine.adapters", _LANGUAGES,
          "languages/ must not import adapters/ — "
          "language services use ports, define their own adapters")


def test_no_cross_language_imports():
    lang_root = SRC / "languages"
    lang_dirs = sorted(d for d in lang_root.iterdir() if d.is_dir())
    for lang_dir in lang_dirs:
        lang_name = lang_dir.name
        lang_files = sorted(lang_dir.rglob("*.py"))
        for other_dir in lang_dirs:
            other_name = other_dir.name
            if lang_name == other_name:
                continue
            for f in lang_files:
                for lineno, mod in _module_refs(f):
                    if mod.startswith(f"langmine.languages.{other_name}"):
                        rel = f.relative_to(SRC.parent)
                        raise AssertionError(
                            f"{rel}:{lineno}: imports {mod!r} — "
                            f"{lang_name} must not import from {other_name}"
                        )


# ── 4. adapters are independent ─────────────────────────────────────────────

def test_adapters_never_import_other_adapters():
    _deny("langmine.adapters", _ADAPTERS,
          "adapters must not import other adapters — each adapter stands alone "
          "(__init__.py re-exports are exempt)")


# ── 5. leaf modules are adapter-free ────────────────────────────────────────

def test_leaf_modules_never_import_adapters():
    _deny("langmine.adapters", _LEAVES,
          "top-level utility modules must not import adapters — "
          "pipeline, config, db, transcript, transcript_parser, audio")
