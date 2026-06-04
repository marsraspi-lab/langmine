# Architecture Review Checklist

Run after every milestone. If any check fails, fix before proceeding.
All checks are enforced in CI (`.github/workflows/ci.yml`).

---

## 0. Domain Purity

The cardinal rule: domain knows nothing about the outside world.

```bash
# domain/ must NEVER import adapters, languages, web, or external I/O
! grep -rn "^\s*(from.*adapters\|import.*adapters)" src/langmine/domain/
! grep -rn "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/domain/
! grep -rn "^\s*(from langmine.web\|import langmine.web)" src/langmine/domain/
! grep -rn "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/
```

- [ ] `domain/` imports nothing from `adapters/`, `languages/`, or `web/`
- [ ] `domain/` contains no I/O calls (sqlite3, subprocess, requests, urllib)
- [ ] `domain/models.py` — pure dataclasses, no methods that touch external systems
- [ ] `domain/ports.py` — all ports inherit `ABC`, all methods `@abstractmethod`, no implementation code. 4 focused persistence interfaces (`VideoRepository`, `SentenceRepository`, `VocabRepository`, `EventStore`) plus `Persistence` (composite).
- [ ] `domain/classifier.py` — accepts ports as arguments, never instantiates adapters

---

## 1. Web Layer

Web sits at the outermost edge. It talks to domain ports, never to adapters directly.

```bash
# web/ must NEVER import from languages/
! grep -rn "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/web/

# Only app.py may import adapters (wiring point)
WEB_ADAPTERS=$(grep -rl "^\s*from langmine.adapters" src/langmine/web/ || true)
for f in $WEB_ADAPTERS; do case "$f" in */app.py) ;; *) echo "FAIL: $f" ;; esac; done
```

- [ ] `web/` imports nothing from `languages/` (use `language_factory`)
- [ ] Only `web/app.py` imports from `adapters/`
- [ ] `web/routes.py` retrieves ports from `current_app.config`, never imports adapters
- [ ] `web/server.py` imports nothing from adapters — just calls `create_production_app()`

---

## 2. Language Factory Gate

`language_factory.py` is the ONLY module allowed to import from `languages/`.

```bash
# Only language_factory.py + intra-package imports are allowed
LANG_IMPORTERS=$(grep -rl "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/ --include="*.py" || true)
for f in $LANG_IMPORTERS; do
  case "$f" in */language_factory.py|*/languages/*) ;; *) echo "FAIL: $f" ;; esac; done
```

- [ ] No file outside `language_factory.py` or `languages/` imports from `languages/`
- [ ] Language packages self-register via `register_language()` in `__init__.py` (Open/Closed)
- [ ] Factory discovers languages via `pkgutil.iter_modules()` — no match/case per language
- [ ] `Translator` is injected as a port (wired in `app.py`), not hardcoded in the factory

---

## 3. Language Extension Isolation

Each language extension is self-contained.

```bash
# languages/ must never import from web/
! grep -rn "^\s*(from langmine.web\|import langmine.web)" src/langmine/languages/

# languages/ must never import from adapters/ (use ports, not shared adapters)
! grep -rn "^\s*(from langmine.adapters\|import langmine.adapters)" src/langmine/languages/

# No cross-language imports
LANGS=$(ls -d src/langmine/languages/*/ 2>/dev/null || true)
for d1 in $LANGS; do n1=$(basename "$d1"); for d2 in $LANGS; do n2=$(basename "$d2")
  if [ "$n1" != "$n2" ] && grep -rq "from langmine.languages.$n2\|import langmine.languages.$n2" "$d1" 2>/dev/null
  then echo "FAIL: $n1 imports $n2"; fi
done; done
```

- [ ] `languages/` imports nothing from `web/`
- [ ] `languages/` imports nothing from `adapters/` (defines its own adapters)
- [ ] No cross-imports between language packages
- [ ] Language service depends on ports (`Dictionary`, `Translator`, `FrequencySource`), not concrete adapters

---

## 4. Adapter Independence

Each adapter stands alone — no adapter imports another adapter.

```bash
# Adapter files must not import from sibling adapters (__init__.py re-exports are fine)
for f in src/langmine/adapters/*.py; do
  case "$(basename "$f")" in __init__.py) continue ;; esac
  grep -q "^\s*from langmine.adapters" "$f" && echo "FAIL: $(basename "$f") imports another adapter"
done
```

- [ ] Each adapter implements exactly one port
- [ ] Adapters contain ALL external system specifics (API keys, paths, subprocess calls)
- [ ] No business logic in adapters (only translation between port ↔ external system)
- [ ] No adapter imports another adapter

---

## 5. Leaf Module Purity

Top-level utility modules must not import adapters.

```bash
for f in src/langmine/pipeline.py src/langmine/config.py src/langmine/db.py \
         src/langmine/transcript.py src/langmine/transcript_parser.py src/langmine/audio.py; do
  grep -q "^\s*(from langmine.adapters\|import langmine.adapters)" "$f" 2>/dev/null && echo "FAIL: $f"
done
```

- [ ] `pipeline.py` uses ports only, no adapter imports
- [ ] `config.py`, `db.py`, `transcript.py`, `transcript_parser.py`, `audio.py` are adapter-free

---

## 6. Test Isolation

```bash
# Domain tests must pass without ffmpeg/network/SQLite
pytest tests/ --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py -v
```

- [ ] Domain logic tests pass without ffmpeg, yt-dlp, or internet
- [ ] At least one test exercises each port with an in-memory fake
- [ ] Fakes live inline in test files (not a shared test-utils module)

---

## 7. Dependency Graph

```text
Allowed:
  app.py → domain ports + adapters               (wiring)
  app.py → language_factory → languages/<lang>   (single switch point)
  web/routes.py → domain ports                   (API uses ports via app.config)
  adapters/ → domain ports                       (implements ports)
  languages/<lang>/ → domain ports               (implements LanguageProcessor)
  pipeline.py → domain ports                     (pure domain logic at top level)

Forbidden:
  domain → adapters          ← THE CARDINAL SIN
  domain → languages         ← must go through factory
  domain → external libs     ← sqlite3, subprocess, requests, urllib
  web → languages            ← must go through factory
  web → adapters             ← except app.py (wiring)
  languages → web            ← languages are inner layer
  languages → adapters       ← languages define their own adapters, use ports
  languages/<X> → languages/<Y>  ← cross-language
  adapter → adapter          ← each adapter stands alone
  leaf modules → adapters    ← pipeline, config, db, transcript, transcript_parser, audio
```

- [ ] No forbidden dependency edges exist

---

## Review History

| Milestone | Date | Result | Notes |
|-----------|------|--------|-------|
| Post-refactor review | | ✅ Pass | Check 1: zero domain→adapter imports. Check 2: models pure. Check 3: 21 abstract methods. Check 4: 8 port references in pipeline. Check 6: 36/36 domain tests pass without ffmpeg. |
| Chinese service split | | ✅ Pass | ChineseLanguageService has zero I/O imports. LanguageProcessor in domain/ports.py. 48/48 domain tests pass. |
| M3: Web UI | | ✅ Pass | Web module at edge — injects ports from config. 83/83 domain tests pass. 21 web API tests (fake ports). |
| M4–M9 (Translate, Export, Stash, Polish, Docker, Vocab) | | ✅ Pass | All milestones: domain imports checked, adapters isolated, E2E coverage grows (37 tests). |
| M10–M14 (Reading, Cloze, Image, Preview, Ruby) | | ✅ Pass | 203 pytest + 42 E2E. `ImageSearch` port added. |
| Decouple Chinese | | ✅ Pass | `language_factory.py` as single switch point. `languages/chinese/` has 6 source files. 217 tests pass. |
| Multi-Language | | ✅ Pass | `language_code` column on videos, sentences, vocab. DB schema v2. Factory exposes templates + manifest. 200 tests pass. |
| Architecture hardening | 2026-06-03 | ✅ Pass | Deleted dead code (`processors.py`, `hsk.py`, `domain/services/`). Moved `Translator` wiring to `app.py`. Added 5 new CI checks (factory gate, languages→adapters, adapter→adapter, leaf modules, anchored patterns). 229 tests pass across 11 architecture rules. |
| SOLID Phase 4 — Persistence Split | 2026-06-04 | ✅ Pass | Split `Persistence` god port (17 methods) into 4 focused interfaces: `VideoRepository`, `SentenceRepository`, `VocabRepository`, `EventStore`. `Persistence` inherits from all 4 for backwards compat. `SentenceClassifier` depends on `SentenceRepository` + `VocabRepository` (3 of 17 methods). `bootstrap_proficiency` accepts `VocabRepository`. Zero test churn — all FakePersistence subclasses unchanged. 267 tests pass. |
| SOLID Phase 5 — Language Registry | 2026-06-04 | ✅ Pass | Replaced 8 match/case blocks in `language_factory.py` with self-registration pattern. Each language package calls `register_language()` in its `__init__.py`. Factory uses `pkgutil.iter_modules()` for auto-discovery and `importlib.import_module()` for lazy loading. Adding a language no longer requires any factory edits — just create a package with standard exports. 252 tests pass, 11/11 architecture checks pass. |
