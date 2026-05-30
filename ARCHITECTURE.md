# Architecture Review Checklist

Run after every milestone. If any check fails, fix before proceeding.

## Rule: Domain code knows nothing about the outside world.

---

## 0. Language Extension Isolation

```bash
# domain/ must NEVER import from languages/
grep -r "from langmine.languages" src/langmine/domain/      # must be empty

# web/ must NEVER import from languages/
grep -r "from langmine.languages" src/langmine/web/         # must be empty

# Language packages must NEVER cross-import each other
grep -r "from langmine.languages" src/langmine/languages/chinese/ | grep -v languages.chinese  # must be empty

# Language packages must NEVER import from web/
grep -r "from langmine.web" src/langmine/languages/          # must be empty
```

- [ ] `domain/` imports nothing from `languages/`
- [ ] `web/` imports nothing from `languages/`
- [ ] No cross-imports between language packages
- [ ] `languages/` imports nothing from `web/`

---

## 1. Import Direction

```bash
# Domain code must NEVER import from adapters
# This should produce ZERO results:
grep -r "from langmine.adapters" src/langmine/domain/    # must be empty
grep -r "import.*adapters" src/langmine/domain/          # must be empty
```

- [ ] `domain/` imports nothing from `adapters/`
- [ ] `domain/` imports nothing from `audio.py`, `transcript.py`, `db.py` (old modules)

## 2. Domain Models Are Pure

```bash
# Domain models must have zero I/O in their definitions
# Check for: sqlite3, subprocess, requests, open(), Path.write, etc.
grep -r "sqlite3\|subprocess\|requests\|open(\|\.write(" src/langmine/domain/models.py
```

- [ ] `Video`, `Sentence`, `VocabWord` are plain dataclasses
- [ ] No database imports, no API calls, no file I/O in model definitions
- [ ] No methods that touch external systems

## 3. Domain Ports Are Abstract

- [ ] All port classes inherit from `ABC`
- [ ] All port methods are decorated with `@abstractmethod`
- [ ] No port contains implementation code (no `subprocess.run`, no `sqlite3.connect`)

## 4. Domain Logic (pipeline, classifier, etc.)

- [ ] Domain modules accept ports as arguments, never instantiate adapters directly
- [ ] Convenience wrappers (like `extract_one_sentence()`) live at the edge, not in domain
- [ ] All tests for domain logic use `InMemoryPersistence` or mocks, not SQLite

## 5. Adapter Boundaries

- [ ] Each adapter implements exactly one port
- [ ] Adapters contain ALL external system specifics (API keys, paths, subprocess calls)
- [ ] No adapter imports another adapter
- [ ] No business logic in adapters (only translation between port ↔ external system)

## 6. Test Isolation

```bash
# Domain tests should NOT require network/ffmpeg/SQLite
# They should pass with --ignore for adapter tests
pytest tests/ --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py -v
```

- [ ] Domain logic tests pass without ffmpeg, yt-dlp, or internet
- [ ] At least one test exercises each port with an in-memory fake

## 7. Dependency Graph

```text
Allowed:
  cli → pipeline → domain
  cli → language_factory → languages/<lang>         (single switch point)
  adapters → domain (implements ports)
  adapters → external libs (subprocess, sqlite3, requests)
  languages/<lang> → domain ports (implements LanguageProcessor)
  languages/<lang> → external NLP libs (jieba, pypinyin, etc.)

Forbidden:
  domain → adapters        ← THE CARDINAL SIN
  domain → languages       ← must go through factory
  domain → external libs
  web → languages          ← must go through factory
  port → port              (ports are independent)
  adapter → adapter
  languages/<lang> → languages/<other_lang>    ← cross-language
  languages/<lang> → web
```

- [ ] No forbidden dependency edges exist

---

## Review History

| Milestone | Date | Result | Notes |
|-----------|------|--------|-------|
| Post-refactor | ✅ Pass | Domain ports + models created. Pipeline uses `mine_one_sentence(ports)`. Convenience wrapper at edge. |
| Post-refactor review | ✅ Pass | Check 1: zero domain→adapter imports. Check 2: models pure. Check 3: 21 abstract methods. Check 4: 8 port references in pipeline. Check 6: 36/36 domain tests pass without ffmpeg. |
| Chinese service split | ✅ Pass | Check 1: zero domain→adapter imports. Check 2: ChineseLanguageService has zero I/O imports (jieba/pypinyin are pure in-memory algorithms). Check 3: LanguageProcessor in domain/ports.py. Check 4: 7 port references in ChineseLanguageService (self._dict/_translator/_frequency). Check 5: 48/48 domain tests pass. |
| M3: Web UI | ✅ Pass | Check 1: zero domain→adapter imports. Check 2: models pure. Check 3: web module at edge — injects ports from config, no adapter imports. Check 4: web imports domain ports only, adapters wired in CLI. Check 6: 83/83 domain tests pass without ffmpeg/network. New: 21 web API tests (fake ports), 1 serve wiring test. |
| M4–M9 (Translate, Export, Stash, Polish, Docker, Vocab) | ✅ Pass | All milestones: domain imports checked, adapters isolated, E2E coverage grows (37 tests). Cardinal rule preserved across all additions. |
| M10–M14 (Reading, Cloze, Image, Preview, Ruby) | ✅ Pass | All milestones: 203 pytest + 42 E2E. `ImageSearch` port added, `ruby_json` on Sentence model, VocabPage deep-dive. No domain→adapter violations. |
| Decouple Chinese | ✅ Pass | Check 0 (new): zero domain→languages, zero web→languages, no cross-language imports. `language_factory.py` as single switch point. `languages/chinese/` has 6 source files + 4 tests. 217 tests pass. |
