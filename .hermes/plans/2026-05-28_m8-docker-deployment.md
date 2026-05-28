# M8: Docker Deployment

**Goal:** Ship LangMine as a Docker image so users can run it with one command — no Python, Node, or ffmpeg install needed.

**Date:** 2026-05-28

---

## Decisions (from grilling)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Image scope | Minimal: backend + pre-built frontend + ffmpeg. Anki runs on host. |
| 2 | AnkiConnect bridge | Default URL → `http://host.docker.internal:8765`, documented `--add-host` flag |
| 3 | Build strategy | Multi-stage: `node:lts-alpine` (build) → `python:3.11-slim` (runtime) |
| 4 | Persistence | Single volume `~/.langmine/` — DB, config, CC-CEDICT, audio clips |
| 5 | `data_dir` config | New field, defaults to `~/.langmine/data/` (currently hardcoded `/tmp/langmine`) |

---

## Files to create

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build |
| `docker-compose.yml` | One-command startup for users |
| `.dockerignore` | Exclude `node_modules`, `.git`, `__pycache__`, `bin/` (ffmpeg in image via apt) |

## Files to modify

| File | Change |
|------|--------|
| `src/langmine/config.py` | Add `data_dir: str = "~/.langmine/data"` to `Config`, wire into YAML round-trip |
| `src/langmine/cli.py` | Use `config.data_dir` (remove fallback to `/tmp/langmine`) |
| `src/langmine/web/routes.py` | Use `config.data_dir` (same) |
| `tests/test_config.py` | Add test for `data_dir` field |

## Files to update

| File | Change |
|------|--------|
| `README.md` | Add Docker quick-start section |

---

## Step-by-step

### Step 1: Add `data_dir` to config (TDD)

- Add `data_dir: str = "~/.langmine/data"` field to `Config` dataclass
- Add to `_config_to_dict` under `"storage"` key
- Add to `_dict_to_config`
- Wire into `load_config` / `save_config`
- Add test in `test_config.py`

### Step 2: Update CLI and routes

- `cli.py:58`: remove `hasattr` fallback, use `config.data_dir` directly
- `routes.py:67`: same

### Step 3: Dockerfile

```dockerfile
# Stage 1: Build Svelte frontend
FROM node:lts-alpine AS frontend
COPY src/langmine/web/frontend/package*.json /build/
WORKDIR /build
RUN npm ci
COPY src/langmine/web/frontend/ /build/
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
COPY --from=frontend /build/../static /app/src/langmine/web/static/
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME /root/.langmine

CMD ["langmine", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

### Step 4: docker-compose.yml

```yaml
services:
  langmine:
    image: marsraspi-lab/langmine:latest
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ~/.langmine:/root/.langmine
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

### Step 5: .dockerignore

```
.git/
__pycache__/
*.pyc
.eggs/
*.egg-info/
node_modules/
bin/
.pytest_cache/
.hermes/
src/langmine/web/frontend/node_modules/
```

### Step 6: README — Docker quick-start section

Document the three ways to run:

1. `docker compose up` (recommended)
2. `docker run` one-liner with `--add-host`
3. Building from source with `docker build`

### Step 7: Default AnkiConnect URL

Change `Config.anki_connect_url` default from `"http://localhost:8765"` to `"http://host.docker.internal:8765"`. Bare-metal Linux users without Docker can override it in config. This way the Docker experience works out of the box.

---

## Verification

```bash
# Docker image builds
docker build -t langmine .

# Container starts and responds
docker run --rm -p 8080:8080 -v $(pwd)/tmp_langmine:/root/.langmine langmine &
sleep 3
curl http://localhost:8080/api/videos

# Config round-trips with data_dir field
python -m pytest tests/test_config.py -v
```

---

## Risks & open questions

- **CC-CEDICT / SUBTLEX-CH data files** — these are in `data/` and copied into the image. ~8MB. No action needed.
- **AnkiConnect on bare-metal Linux** — `host.docker.internal` doesn't resolve natively. The `extra_hosts` in compose fixes it. `docker run` users need the `--add-host` flag documented.
- **Image size** — estimate ~200MB (python slim ~50MB + ffmpeg ~30MB + app ~5MB + data ~8MB + deps ~100MB). Reasonable.
