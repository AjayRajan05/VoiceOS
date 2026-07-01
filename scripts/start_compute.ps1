# Start VoiceOS compute plane only (Redis + Docker workers)
# Usage: .\scripts\start_compute.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (Get-Command voiceos-compute -ErrorAction SilentlyContinue) {
    voiceos-compute @args
} else {
    python -m voiceos_host.compute_cli @args
}
