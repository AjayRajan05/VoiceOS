# Install VoiceOS host control plane (Windows)
# Usage: .\scripts\install_voiceos.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Installing VoiceOS host control plane..." -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python is not installed. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

python -m pip install -e .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Preparing workspace and environment..." -ForegroundColor Cyan
python -c "from core.host.onboarding import run_first_time_setup; import json; print(json.dumps(run_first_time_setup(), indent=2))"

Write-Host ""
Write-Host "Running VoiceOS doctor..." -ForegroundColor Cyan
voiceos-doctor
$doctorCode = $LASTEXITCODE

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Start compute plane:  voiceos-compute"
Write-Host "  2. Or full hybrid:       .\scripts\start_hybrid.ps1"
Write-Host "  3. Host only (CLI):      voiceos --mode cli"
Write-Host ""

exit $doctorCode
