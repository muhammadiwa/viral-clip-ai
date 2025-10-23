#!/usr/bin/env bash
# Cross-platform Docker wrapper.
#
# 1. Prefer the local `docker` CLI (Linux/macOS, WSL with integration).
# 2. Fallback to Docker Desktop for Windows when running inside WSL without integration.

set -euo pipefail

if command -v docker >/dev/null 2>&1; then
	exec docker "$@"
fi

WINDOWS_DOCKER="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
if [ -x "$WINDOWS_DOCKER" ]; then
	exec "$WINDOWS_DOCKER" "$@"
fi

echo "docker executable not found. Install Docker or update docker-wrapper.sh" >&2
exit 1