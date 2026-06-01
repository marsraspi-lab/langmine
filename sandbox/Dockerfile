# Hermes sandbox container for LangMine development
#
# Build:  docker build -t langmine-sandbox -f sandbox/Dockerfile .
# Run:    docker run -d --name langmine-sandbox langmine-sandbox
#
# This captures all system dependencies discovered while working
# on this project so the Hermes agent has everything it needs.

FROM nikolaik/python-nodejs:python3.14-nodejs26

# ── System packages ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Base tools
    curl \
    ca-certificates \
    git \
    gnupg \
    jq \
    # Faster search: ripgrep (rg) + fd-find (fd)
    ripgrep \
    fd-find \
    # GitHub CLI
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── fd symlink (Debian packages it as fdfind to avoid name clash) ──
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd

# ── Playwright / Chromium E2E deps ────────────────────────────────
RUN npx -y playwright install-deps chromium 2>/dev/null || \
    apt-get update && apt-get install -y --no-install-recommends \
      libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
      libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Pre-install Playwright browsers to persistent path ────────────
# Playwright extraction can exceed Docker's default /tmp (often tmpfs).
# Install to a persistent location so the Hermes sandbox doesn't
# re-download on every session.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN npx -y playwright install chromium

# ── Aliases ───────────────────────────────────────────────────────
RUN echo 'alias rg="rg --smart-case"' >> /root/.bashrc && \
    echo 'alias fd="fd --hidden"'    >> /root/.bashrc

WORKDIR /root/projects
