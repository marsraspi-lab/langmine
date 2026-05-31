# Hermes sandbox container for LangMine development
#
# Build:  docker build -t langmine-sandbox -f sandbox/Dockerfile .
# Run:    docker run -d --name langmine-sandbox langmine-sandbox
#
# This captures all system dependencies discovered while working
# on this project so the Hermes agent has everything it needs.

FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Base tools
    curl \
    ca-certificates \
    git \
    gnupg \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    nodejs \
    npm \
    jq \
    # GitHub CLI
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    # Playwright / Chromium E2E deps
    && npx -y playwright install-deps chromium 2>/dev/null || \
       apt-get install -y \
         libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
         libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 \
         libxcomposite1 libxdamage1 libxfixes3 \
         libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    # Pre-install Playwright Chromium
    && npx -y playwright install chromium \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root/projects
