#!/bin/bash
# Download static ffmpeg + ffprobe binaries for LangMine
# These survive Docker container resets and work without system package managers.
# Falls back gracefully — audio.py uses system binaries if bin/ is empty.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$SCRIPT_DIR/../bin"
mkdir -p "$BIN_DIR"

ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64)   ARCH="arm64" ;;
    x86_64|amd64)    ARCH="amd64" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        echo "Install ffmpeg via your system package manager instead."
        exit 1
        ;;
esac

echo "Downloading static ffmpeg for $ARCH..."
URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${ARCH}-static.tar.xz"

curl -sL "$URL" | tar xJ -C "$BIN_DIR" --strip=1 --wildcards '*/ffmpeg' '*/ffprobe'

chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"
echo "Done: $BIN_DIR/ffmpeg ($(du -h "$BIN_DIR/ffmpeg" | cut -f1))"
echo "      $BIN_DIR/ffprobe ($(du -h "$BIN_DIR/ffprobe" | cut -f1))"
