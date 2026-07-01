# Start VoiceOS host bridge in the background (Windows)
# Usage: .\scripts\start_bridge.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$pidFile = Join-Path (Get-Location) "workspace\.voiceos-bridge.pid"
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "Host bridge already running (PID $oldPid)" -ForegroundColor Green
        exit 0
    }
}

Write-Host "Starting VoiceOS host bridge in background..." -ForegroundColor Cyan
if (Get-Command voiceos-bridge -ErrorAction SilentlyContinue) {
    Start-Process -FilePath "voiceos-bridge" -WindowStyle Hidden
} else {
    Start-Process -FilePath "python" -ArgumentList "-m", "voiceos_host.bridge_cli" -WindowStyle Hidden
}

Start-Sleep -Seconds 2
python -c "from host_bridge.client import BridgeClient; import sys; sys.exit(0 if BridgeClient().is_available() else 1)"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Host bridge is up at http://127.0.0.1:18765" -ForegroundColor Green
} else {
    Write-Host "Bridge may still be starting. Check workspace/.voiceos-bridge.pid" -ForegroundColor Yellow
}
