# syntax=docker/dockerfile:1
# Hermes sandbox container for LangMine development
#
# Build:  docker build -t langmine-sandbox -f sandbox/Dockerfile .
# Run:    docker run -d --name langmine-sandbox langmine-sandbox
#
# This captures all system dependencies discovered while working
# on this project so the Hermes agent has everything it needs.
#
# Layer strategy (ordered by change frequency — slowest first):
#   1. Base image                    → never changes unless you pick a new tag
#   2. Stable system packages        → rarely change (curl, git, ffmpeg, ripgrep…)
#   3. GitHub CLI                    → changes with gh releases, less often than project
#   4. Playwright (deps + browsers)  → changes with Playwright releases, very infrequent
#   5. Python project dependencies   → changes when pyproject.toml changes
#   6. Shell aliases + workdir       → trivial, always rebuilds
#
# BuildKit cache mounts (--mount=type=cache) preserve package manager
# caches across builds so only new or changed packages are downloaded:
#   /var/cache/apt  → downloaded .deb files survive between builds
#   /var/lib/apt    → package lists survive; apt-get update is a delta
#   /root/.cache/pip → pip wheels survive; only new deps download
#   /root/.npm       → npm packages survive; npx caches Playwright

FROM nikolaik/python-nodejs:python3.14-nodejs26

# ── Layer 1: Stable system packages ─────────────────────────────────
# These rarely change. Adding a dep here invalidates layers 2-5, but
# this is the first RUN after FROM so the base image's apt cache is
# still warm.  BuildKit cache mounts make re-downloads near-instant.
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Base tools
    curl \
    ca-certificates \
    git \
    gnupg \
    jq \
    # Media: audio extraction + clipping
    ffmpeg \
    # Faster search: ripgrep (rg) + fd-find (fd)
    ripgrep \
    fd-find \
    && rm -rf /var/lib/apt/lists/*

# ── fd symlink (Debian packages it as fdfind to avoid name clash) ───
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd

# ── Layer 2: GitHub CLI ────────────────────────────────────────────
# Separate from system packages so gh version bumps don't invalidate
# the base apt layer (Layer 1 stays cached).
RUN \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 3: Playwright (system deps + browser binaries) ────────────
# Pre-installed to a persistent path so Hermes sandbox sessions
# don't re-download Chromium on every start.  Playwright releases
# are infrequent, so this layer almost always hits cache.
#
# npm cache mount keeps the Playwright package cached; apt cache
# mounts accelerate the fallback system-dep install path.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN \
    --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    npx -y playwright install-deps chromium 2>/dev/null || \
    ( apt-get update && apt-get install -y --no-install-recommends \
      libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
      libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
      && rm -rf /var/lib/apt/lists/* ) \
    && npx -y playwright install chromium

# ── Layer 4: Python project dependencies ───────────────────────────
# COPY pyproject.toml FIRST so pip install is cached until the
# dependency list actually changes.  This is the layer that gets the
# most rebuilds (every time you add a new pip package).
#
# pip cache mount preserves downloaded wheels — only new or changed
# packages trigger a download.
#
# We create a stub package to satisfy the editable install, then
# remove it — the real source is mounted/bound at runtime.
COPY pyproject.toml ./
RUN \
    --mount=type=cache,target=/root/.cache/pip \
    mkdir -p src/langmine && touch src/langmine/__init__.py \
    && pip install . \
    && rm -rf src/langmine

# ── Layer 5: Shell aliases + workdir ───────────────────────────────
RUN echo 'alias rg="rg --smart-case"' >> /root/.bashrc && \
    echo 'alias fd="fd --hidden"'    >> /root/.bashrc

WORKDIR /root/projects
