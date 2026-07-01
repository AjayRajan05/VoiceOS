# Start hybrid VoiceOS: compute plane + host agent (voice + OS control)
# Usage: .\scripts\start_hybrid.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "VoiceOS hybrid bootstrap" -ForegroundColor Cyan

Write-Host "Starting host bridge (OS automation IPC)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "start_bridge.ps1")

if (Get-Command voiceos-compute -ErrorAction SilentlyContinue) {
    voiceos-compute --workers 2
} else {
    python -m voiceos_host.compute_cli --workers 2
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running hybrid preflight..." -ForegroundColor Cyan
python -c @"
from core.host.onboarding import preflight_hybrid, print_onboarding_banner
ok, report = preflight_hybrid()
print_onboarding_banner(report)
import sys
sys.exit(0 if ok else 1)
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "Preflight reported blocking issues. Fix with: voiceos-doctor" -ForegroundColor Yellow
}

Write-Host "Starting host control plane (voice + OS tools)..." -ForegroundColor Cyan
if (Get-Command voiceos -ErrorAction SilentlyContinue) {
    voiceos --mode hybrid
} else {
    python main.py --mode hybrid
}
