#!/usr/bin/env bash
# Start VoiceOS host bridge in the background
set -euo pipefail
cd "$(dirname "$0")/.."

PID_FILE="workspace/.voiceos-bridge.pid"
mkdir -p workspace

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Host bridge already running (PID $old_pid)"
    exit 0
  fi
fi

echo "Starting VoiceOS host bridge in background..."
if command -v voiceos-bridge >/dev/null 2>&1; then
  nohup voiceos-bridge > logs/voiceos-bridge.log 2>&1 &
else
  nohup python -m voiceos_host.bridge_cli > logs/voiceos-bridge.log 2>&1 &
fi

sleep 2
python -c "from host_bridge.client import BridgeClient; import sys; sys.exit(0 if BridgeClient().is_available() else 1)" \
  && echo "Host bridge is up at http://127.0.0.1:18765" \
  || echo "Bridge may still be starting. See logs/voiceos-bridge.log"
