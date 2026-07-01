# VoiceOS scripts

Convenience wrappers for install and startup. After `pip install -e .`, you can use the `voiceos*` CLIs directly instead.

## Install

| Script | What it does |
|--------|----------------|
| `install_voiceos.ps1` / `install_voiceos.sh` | Editable install (`pip install -e .`), first-time workspace setup, then `voiceos-doctor` |

**CLI equivalent:** `pip install -e .` then `voiceos-doctor`

## Start

| Script | What it does |
|--------|----------------|
| `start_bridge.ps1` / `start_bridge.sh` | Start the host bridge (OS automation IPC on `http://127.0.0.1:18765`) |
| `start_compute.ps1` / `start_compute.sh` | Start Redis + Docker workers only |
| `start_hybrid.ps1` / `start_hybrid.sh` | Bridge → compute → `voiceos --mode hybrid` (recommended full stack) |

**CLI equivalents:**

```bash
voiceos-bridge
voiceos-compute --workers 2
voiceos --mode hybrid
```

## Utilities

| Script | What it does |
|--------|----------------|
| `verify_setup.py` | Check Python version, folders, and core imports (used by CI) |
| `wait_for_redis.py` | Block until Redis is reachable (called by `voiceos-compute`) |
| `init-db.sql` | Postgres schema for optional audit persistence (`docker-compose` mounts this) |

## Typical flows

**Host only (voice + OS tools, no Docker workers):**

```bash
voiceos --mode cli
```

**Hybrid (host + workers):**

```bash
# Windows
.\scripts\start_hybrid.ps1

# macOS / Linux
./scripts/start_hybrid.sh
```

See [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md) and [docs/DOCKER.md](../docs/DOCKER.md) for full setup.
