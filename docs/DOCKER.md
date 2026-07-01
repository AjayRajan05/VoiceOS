# Docker guide

Docker is **optional**. VoiceOS runs without it for typing, light OS commands, and local agents. Docker is **recommended** when you want faster, isolated execution for research, coding, and long autonomous tasks.

---

## What Docker provides

| Service | Purpose |
|---------|---------|
| Redis | Task queue between host and workers |
| voiceos-worker | Agent and code execution containers |
| Ollama (optional profile) | LLM in a container |

The **host** always keeps: microphone, speakers, permissions, and desktop automation.

---

## Prerequisites

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux).  
2. Ensure Docker is running: `docker info`  
3. Install VoiceOS on the host (`pip install -e .`) — voice does not run inside the worker container on Windows/Mac.

---

## Quick start (recommended)

**Windows:**
```powershell
pip install -e .
.\scripts\start_hybrid.ps1
voiceos --mode hybrid
```

**macOS / Linux:**
```bash
pip install -e .
./scripts/start_hybrid.sh
voiceos --mode hybrid
```

This starts (when configured): host bridge, Redis, workers, and prints doctor hints.

---

## Manual compute plane

Start only Redis and workers:

```bash
voiceos-compute --workers 2
```

In another terminal:

```bash
voiceos --mode hybrid
```

Ensure `.env` contains:
```bash
EXECUTION_MODE=auto
REDIS_URL=redis://localhost:6379/0
```

---

## Docker Compose profiles

From the project root:

```bash
# Core infrastructure (Redis, Postgres)
docker compose --profile core up -d

# Workers
docker compose --profile workers up -d

# Optional LLM (Ollama)
docker compose --profile llm up -d

# Scale workers
docker compose --profile workers up -d --scale voiceos-worker=3
```

### GPU (Linux + NVIDIA)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d
```

---

## Prebuilt worker image

Skip local builds by setting in `.env`:

```bash
VOICEOS_WORKER_IMAGE=ghcr.io/your-org/voiceos-worker:latest
```

---

## Volume mounts

| Host path | Purpose |
|-----------|---------|
| `./workspace` | Shared agent workspace |
| `./models` | Model cache (large; persist across rebuilds) |
| `./logs` | Logs |
| `./memory` | Memory plugin data |
| `./config` | Configuration |

---

## What not to run in Docker

- **Voice input** on Windows/Mac — use host `voiceos` for microphone access.  
- **OS desktop automation** — always on host (`os_*` tools blocked in workers).  

---

## Verify

```bash
voiceos-doctor
voiceos --status
```

Expect **full_hybrid** when Docker, Redis, and at least one worker are healthy.

---

## Stop services

```bash
docker compose --profile workers down
docker compose --profile core down
```

To remove volumes (deletes queued data): add `-v` (use with care).
