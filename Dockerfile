# syntax=docker/dockerfile:1
# Stage 1: Build Svelte frontend
FROM node:lts-alpine AS frontend
COPY src/langmine/web/frontend/package*.json /build/
WORKDIR /build
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY src/langmine/web/frontend/ /build/
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ARG VERSION=unknown
LABEL org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.title="LangMine" \
      org.opencontainers.image.description="YouTube sentence mining for language learning"

WORKDIR /app

# Copy dependency manifest first so pip install is cached
# unless pyproject.toml changes (Docker layer optimization).
# --mount=type=cache preserves pip's download cache across builds
# so only changed/new deps are re-downloaded.
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p src/langmine && touch src/langmine/__init__.py \
    && pip install . \
    && rm -rf src/langmine

# Copy application code (fast — deps already installed above)
COPY . .
COPY --from=frontend /static /app/src/langmine/web/static/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME /root/.langmine

CMD ["langmine", "--host", "0.0.0.0", "--port", "8080"]
