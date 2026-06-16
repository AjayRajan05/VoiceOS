# 🐳 VoiceOS Docker Setup Guide

Complete guide for running VoiceOS in Docker, from quick start to production deployment.

---

## Quick Start

### Option 1: Docker Compose (Recommended)

Docker Compose starts VoiceOS with optional Redis and PostgreSQL services.

```bash
# Navigate to project directory
cd VoiceOS/project

# Build and start all services
docker-compose up --build

# Run in detached (background) mode
docker-compose up -d --build

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

---

### Option 2: Docker Only

```bash
# Build the image
docker build -t voiceos .

# Run in CLI mode
docker run -it --rm \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/memory:/app/memory \
  -e EXECUTION_MODE=local \
  voiceos python main.py --mode cli

# Run in hybrid mode (requires audio device passthrough)
docker run -it --rm \
  --device /dev/snd \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  voiceos python main.py --mode hybrid
```

---

## Volume Mounts

| Host Path | Container Path | Description |
|-----------|---------------|-------------|
| `./workspace` | `/app/workspace` | Agent task workspaces |
| `./models` | `/app/models` | Downloaded AI models (Whisper, LLM) |
| `./logs` | `/app/logs` | Application logs |
| `./memory` | `/app/memory` | Agent memory persistence |
| `./config` | `/app/config` | Configuration files |

Models are large (2–8 GB). Mounting `./models` ensures they survive container rebuilds.

---

## Services

The `docker-compose.yml` defines the following services:

### `voiceos` — Main Service

The primary VoiceOS application container.

- **Image**: Built from `Dockerfile`
- **Default command**: `python main.py --mode cli`
- **Python**: 3.11 (slim)
- **Non-root user**: Runs as `voiceos` user for security

### `redis` — Task Queue (Optional)

Required only when `EXECUTION_MODE=queued`.

```yaml
# Starts automatically with docker-compose up
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```

### `postgres` — Audit Database (Optional)

Required only when `DATABASE_URL` is configured (for persistent audit logs).

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: voiceos
    POSTGRES_USER: voiceos
    POSTGRES_PASSWORD: voiceos
  ports:
    - "5432:5432"
```

### `worker` — Distributed Worker (Optional)

Role-based agent worker for distributed execution:

- **Image**: Built from `Dockerfile.worker`
- **Scales** horizontally — run multiple workers

```bash
# Scale to 3 workers
docker-compose up --scale worker=3
```

---

## Configuration

### Environment Variables

Pass via `.env` file or `docker-compose.yml` `environment:` section:

```bash
# Core
VOICEOS_ENV=production
LOG_LEVEL=INFO
VOICEOS_WORKSPACE=/app/workspace

# LLM (Ollama running on host)
LLM_ENDPOINT=http://host.docker.internal:11434/api/generate
LLM_MODEL=mistral

# Speech
WHISPER_MODEL=base

# Security
PERMISSION_LEVEL=medium
SANDBOX_ENABLED=true

# Distributed (optional)
EXECUTION_MODE=local          # or: queued
REDIS_URL=redis://redis:6379/0

# Database (optional)
DATABASE_URL=postgresql://voiceos:voiceos@postgres:5432/voiceos
```

> **Note**: Use `host.docker.internal` to access services running on the host machine (e.g., Ollama).

---

## Running VoiceOS Modes in Docker

### CLI Mode (No Microphone)

```bash
docker-compose exec voiceos python main.py --mode cli
```

### Voice Mode (With Audio)

Voice mode requires audio device passthrough. This works on Linux with `/dev/snd` passthrough:

```bash
docker run -it --rm \
  --device /dev/snd \
  -e PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native \
  -v ${XDG_RUNTIME_DIR}/pulse/native:${XDG_RUNTIME_DIR}/pulse/native \
  -v $(pwd)/workspace:/app/workspace \
  voiceos python main.py --mode voice
```

> **Windows/macOS**: Native audio passthrough requires additional setup (PulseAudio for WSL2, or run locally without Docker for voice mode).

### System Status Check

```bash
docker-compose exec voiceos python main.py --status
```

### Run System Tests

```bash
docker-compose exec voiceos python main.py --test
```

### Interactive Shell

```bash
docker-compose exec voiceos bash
```

---

## Distributed Worker Mode

```bash
# 1. Set execution mode
echo "EXECUTION_MODE=queued" >> .env

# 2. Start full stack (includes Redis)
docker-compose up -d --build

# 3. Start workers
docker-compose up worker

# Or scale workers
docker-compose up --scale worker=3

# 4. Check worker status
docker-compose exec voiceos python main.py --status
```

---

## GPU Support

For faster Whisper STT and LLM inference with NVIDIA GPU:

```bash
# Requires nvidia-docker (nvidia-container-toolkit)
docker run -it --rm \
  --gpus all \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/models:/app/models \
  voiceos python main.py --mode cli
```

Or in `docker-compose.yml`:
```yaml
services:
  voiceos:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## Development Workflow

### Live Code Reloading

Mount the source code for development:

```bash
docker run -it --rm \
  -v $(pwd):/app \
  -v $(pwd)/workspace:/app/workspace \
  voiceos python main.py --mode cli
```

### Running Tests

```bash
# System integration tests
docker-compose exec voiceos python main.py --test

# Pytest unit tests
docker-compose exec voiceos python -m pytest tests/ -v

# Verify setup
docker-compose exec voiceos python scripts/verify_setup.py
```

### Debugging

```bash
# Enable debug logging
docker-compose exec voiceos bash -c "LOG_LEVEL=DEBUG python main.py --mode cli"

# View real-time logs
docker-compose logs -f voiceos

# Tail application log
docker-compose exec voiceos tail -f logs/voiceos.log

# Filter errors
docker-compose exec voiceos grep ERROR logs/voiceos.log

# Check container resource usage
docker stats voiceos_voiceos_1
```

---

## Security

### Container Hardening

The VoiceOS container applies these security defaults:

```yaml
security_opt:
  - no-new-privileges:true
user: "voiceos"           # Non-root user
read_only: false          # Workspace must be writable
```

### Resource Limits

Configured in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '0.5'
      memory: 1G
```

Increase memory to `8G` if using a 7B+ parameter LLM locally.

### Data Privacy

- All AI model inference runs locally inside the container
- No data leaves the container unless you configure external API keys
- Workspace files are isolated to the mounted volume
- Audit logs are written to `./logs/` on the host

---

## Production Deployment

### Recommended Production Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  voiceos:
    image: voiceos:latest
    restart: unless-stopped
    environment:
      - VOICEOS_ENV=production
      - LOG_LEVEL=WARNING
      - EXECUTION_MODE=queued
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
    security_opt:
      - no-new-privileges:true
    volumes:
      - voiceos_workspace:/app/workspace
      - voiceos_models:/app/models
      - voiceos_logs:/app/logs

volumes:
  voiceos_workspace:
    driver: local
  voiceos_models:
    driver: local
  voiceos_logs:
    driver: local
```

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Backup and Restore

### Backup

```bash
# Backup workspace, models, and memory
docker run --rm \
  -v voiceos_workspace:/data/workspace \
  -v voiceos_models:/data/models \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/voiceos-backup-$(date +%Y%m%d).tar.gz -C /data .
```

### Restore

```bash
docker run --rm \
  -v voiceos_workspace:/data/workspace \
  -v voiceos_models:/data/models \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/voiceos-backup-20260616.tar.gz -C /data
```

---

## Troubleshooting

### Common Issues

#### Container won't start

```bash
# Check startup logs
docker-compose logs voiceos

# Verify image built correctly
docker-compose build --no-cache voiceos
```

#### Models not persisting between restarts

Ensure you have the `./models` volume mounted:
```bash
# Check mounted volumes
docker inspect voiceos_voiceos_1 --format='{{json .Mounts}}'
```

#### Audio not working in container

Audio passthrough is Linux-only. For Windows/macOS, run VoiceOS locally without Docker for voice mode.

#### Permission issues on workspace

```bash
# Fix volume ownership
docker-compose exec voiceos chown -R voiceos:voiceos /app/workspace

# On host (Linux)
sudo chown -R $USER:$USER ./workspace ./logs ./memory
```

#### Memory issues (OOM errors)

```bash
# Check container memory usage
docker stats

# Increase memory limit in docker-compose.yml
# memory: 4G → memory: 8G

# Use a smaller Whisper model
# WHISPER_MODEL=tiny  (set in .env)
```

#### Redis connection refused

```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

---

## Health Checks

```bash
# Check container health status
docker-compose ps

# Manual health check
docker-compose exec voiceos python -c "import core.orchestrator; print('Orchestrator: OK')"

# Full system health
docker-compose exec voiceos python main.py --status
```

---

## Reporting Issues

When reporting Docker-related issues, include:

```bash
docker --version
docker-compose --version
docker-compose exec voiceos python --version
docker-compose logs --tail=50 voiceos
docker-compose exec voiceos python main.py --status
```
