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
COPY --from=frontend /static /app/src/langmine/web/static/
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME /root/.langmine

CMD ["langmine", "serve", "--host", "0.0.0.0", "--port", "8080"]
