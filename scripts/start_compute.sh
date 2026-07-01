#!/usr/bin/env bash
# Start VoiceOS compute plane only (Redis + Docker workers)
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v voiceos-compute >/dev/null 2>&1; then
  exec voiceos-compute "$@"
fi
exec python -m voiceos_host.compute_cli "$@"
