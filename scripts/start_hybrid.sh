#!/usr/bin/env bash
# Start hybrid VoiceOS: compute plane + host agent (voice + OS control)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "VoiceOS hybrid bootstrap"

if [[ -x "$(dirname "$0")/start_bridge.sh" ]]; then
  "$(dirname "$0")/start_bridge.sh" || true
fi

if command -v voiceos-compute >/dev/null 2>&1; then
  voiceos-compute --workers 2
else
  python -m voiceos_host.compute_cli --workers 2
fi

echo "Running hybrid preflight..."
python -c "
from core.host.onboarding import preflight_hybrid, print_onboarding_banner
ok, report = preflight_hybrid()
print_onboarding_banner(report)
import sys
sys.exit(0 if ok else 1)
" || echo "Preflight reported issues. Run: voiceos-doctor"

echo "Starting host control plane (voice + OS tools)..."
if command -v voiceos >/dev/null 2>&1; then
  exec voiceos --mode hybrid
fi
exec python main.py --mode hybrid
