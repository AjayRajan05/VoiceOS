#!/usr/bin/env bash
# Install VoiceOS host control plane
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing VoiceOS host control plane..."
command -v python3 >/dev/null || command -v python >/dev/null || {
  echo "Python 3.10+ is required." >&2
  exit 1
}

PY=python3
command -v python3 >/dev/null || PY=python

"$PY" -m pip install -e .

echo "Preparing workspace and environment..."
"$PY" -c "from core.host.onboarding import run_first_time_setup; import json; print(json.dumps(run_first_time_setup(), indent=2))"

echo ""
echo "Running VoiceOS doctor..."
voiceos-doctor || doctor_code=$?
doctor_code=${doctor_code:-0}

echo ""
echo "Next steps:"
echo "  1. Start compute plane:  voiceos-compute"
echo "  2. Or full hybrid:       ./scripts/start_hybrid.sh"
echo "  3. Host only (CLI):      voiceos --mode cli"
echo ""

exit "$doctor_code"
