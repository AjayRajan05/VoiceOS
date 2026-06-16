# Start hybrid VoiceOS: Docker infra + host agent (voice + OS control)
# Usage: .\scripts\start_hybrid.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Starting VoiceOS hybrid stack (core + workers)..." -ForegroundColor Cyan
docker compose --profile core --profile workers up -d --scale voiceos-worker=2

Write-Host ""
Write-Host "Optional LLM offload:" -ForegroundColor Yellow
Write-Host "  docker compose --profile llm up -d"
Write-Host "  ollama pull mistral   # inside container or via host CLI on :11434"
Write-Host ""
Write-Host "Starting host agent (voice + OS tools)..." -ForegroundColor Cyan
python main.py --config config/voiceos.hybrid.yaml --mode hybrid
