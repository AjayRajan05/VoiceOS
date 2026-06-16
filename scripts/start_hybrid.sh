#!/usr/bin/env bash
# Start hybrid VoiceOS: Docker infra + host agent (voice + OS control)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting VoiceOS hybrid stack (core + workers)..."
docker compose --profile core --profile workers up -d --scale voiceos-worker=2

echo ""
echo "Optional LLM offload:"
echo "  docker compose --profile llm up -d"
echo "  ollama pull mistral"
echo ""
echo "Starting host agent (voice + OS tools)..."
exec python main.py --config config/voiceos.hybrid.yaml --mode hybrid
