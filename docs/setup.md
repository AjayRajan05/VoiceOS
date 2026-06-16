# ⚙️ VoiceOS Setup Guide

Complete guide for installing, configuring, and running VoiceOS locally or with Docker.

---

## 📋 System Requirements

### Minimum Requirements

| Requirement | Value |
|------------|-------|
| **Python** | 3.10 or higher |
| **RAM** | 8 GB (16 GB recommended for local LLM) |
| **Storage** | 10 GB free (models can be 4–7 GB) |
| **OS** | Windows 10+, macOS 12+, Ubuntu 20.04+ |
| **Microphone** | Required for voice mode |

### Optional

| Component | Purpose |
|----------|---------|
| **NVIDIA GPU** | Accelerated Whisper STT and LLM inference |
| **Docker + Compose** | Containerized deployment |
| **Redis** | Distributed worker queue (`EXECUTION_MODE=queued`) |
| **PostgreSQL** | Persistent audit logging |
| **Ollama** | Local LLM backend (alternative to GGUF) |

---

## 🚀 Local Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AjayRajan05/VoiceOS.git
cd VoiceOS/project
```

### 2. Create a Virtual Environment

```bash
# Create environment
python -m venv .venv

# Activate on Windows
.venv\Scripts\activate

# Activate on macOS / Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Core dependencies (required)
pip install -r requirements.txt

# Optional extras: GPU acceleration, Coqui TTS, advanced scraping
pip install -r requirements-optional.txt

# Or install optional deps via the helper script
python scripts/install_deps.py --optional
```

> **Windows note**: `Coqui TTS` may require extra steps on Windows. Use `Kokoro` (already included in `requirements.txt`) as the default TTS engine.

### 4. Configure Environment

```bash
# Copy the environment template
cp .env.example .env
```

Open `.env` and set the required values — see [Environment Variables](#-environment-variables) below.

### 5. Verify Setup

```bash
python scripts/verify_setup.py
```

This checks Python version, dependencies, microphone availability, workspace directory, and model paths.

### 6. Run VoiceOS

```bash
# Default hybrid mode (voice + CLI)
python main.py

# Voice only
python main.py --mode voice

# CLI only (no microphone needed)
python main.py --mode cli

# Use a custom config file
python main.py --config config/voiceos.yaml

# Check system health and exit
python main.py --status

# Run system tests and exit (no microphone needed)
python main.py --test
```

---

## 🐳 Docker Deployment

Docker is the easiest way to get a full isolated stack running.

### Quick Start

```bash
# Build and start the full stack (VoiceOS + Redis + Postgres)
docker-compose up --build

# Run in detached (background) mode
docker-compose up -d --build

# Stop all services
docker-compose down
```

### Run with GPU Support

```bash
docker-compose --profile gpu up --build
```

### Persistent Volumes

| Volume | Host Path | Description |
|--------|-----------|-------------|
| `workspace` | `./workspace` | Agent task workspaces |
| `models` | `./models` | Downloaded AI models |
| `logs` | `./logs` | Application logs |
| `memory` | `./memory` | Agent memory persistence |
| `config` | `./config` | Configuration files |

Models and workspaces persist between container restarts.

### Interact with the Container

```bash
# Interactive shell
docker-compose exec voiceos bash

# Run VoiceOS CLI inside container
docker-compose exec voiceos python main.py --mode cli

# Check system status
docker-compose exec voiceos python main.py --status

# View real-time logs
docker-compose logs -f voiceos
```

---

## 🔧 Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
# ─── Core ─────────────────────────────────────────────
VOICEOS_ENV=development          # development | production | testing
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
VOICEOS_WORKSPACE=./workspace    # Path to workspace directory

# ─── LLM Backend ──────────────────────────────────────
# Option A: Ollama (recommended for beginners)
LLM_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL=mistral

# Option B: GGUF file (direct llama.cpp)
# LLM_MODEL=mistral-7b-instruct.gguf
# MODELS_DIRECTORY=./models

MAX_RAM_THRESHOLD=12             # Max RAM (GB) for model selection

# ─── Voice ────────────────────────────────────────────
WHISPER_MODEL=base               # tiny | base | small | medium | large
TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
TTS_OUTPUT_PATH=./output/response.wav
MICROPHONE_DEVICE=default        # Use default system microphone

# ─── Optional Cloud API Keys ──────────────────────────
OPENAI_API_KEY=                  # Leave empty if using local LLM
ANTHROPIC_API_KEY=

# ─── Security ─────────────────────────────────────────
PERMISSION_LEVEL=medium          # low | medium | high
SANDBOX_ENABLED=true

# ─── Distributed Execution ────────────────────────────
EXECUTION_MODE=local             # local | queued
REDIS_URL=redis://localhost:6379/0

# ─── Web UI (legacy, currently ignored) ───────────────
WEB_PORT=8000
```

---

## ⚙️ Configuration File

Main settings live in `config/voiceos.yaml`:

```yaml
# Execution mode: local or queued (distributed workers)
execution_mode: local

# Logging
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Voice settings
voice:
  enable_interrupts: true
  enable_backchannel: false

# LLM provider
llm:
  provider: local          # local | api | remote
  model: mistral

# Feature flags
enable_workspace_isolation: true
enable_agent_memory: true
enable_event_handlers: true
```

### Agent Role Configuration

Agent roles are defined in `agents/roles/`:

```yaml
# agents/roles/researcher/agent.yaml
name: "researcher"
version: "1.0.0"
description: "Specialized in web research and information synthesis"
permission_level: "medium"
max_execution_time: 300

tools:
  - browser_tool
  - document_processor
  - enhanced_file_manager

capabilities:
  - web_research
  - data_analysis
  - source_verification
```

---

## 🤖 AI Model Setup

### Automatic Download (Default)

On first run, `ModelManager` detects your available RAM and downloads the appropriate models automatically:

```
models/
├── whisper/
│   └── base.pt              # Whisper STT (auto-downloaded)
├── tts/
│   └── ljspeech/            # TTS model (auto-downloaded)
└── llm/
    └── mistral-7b.gguf      # LLM (auto-downloaded if RAM >= 8 GB)
```

### Ollama (Recommended Alternative)

```bash
# Install Ollama from https://ollama.com
ollama pull mistral

# Set in .env
LLM_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL=mistral
```

### Manual Model Placement

Place your own models in the `models/` directory and update `MODELS_DIRECTORY` in `.env`.

### Supported Models

| Component | Supported Options |
|----------|------------------|
| **STT** | Whisper: `tiny`, `base`, `small`, `medium`, `large` |
| **TTS** | Kokoro (default), Coqui TTS (optional) |
| **LLM** | Mistral-7B, Llama 2, CodeLlama (GGUF); any Ollama model |

---

## 🌐 Web Interface

> **Note**: The `--web` flag is currently deprecated. VoiceOS operates as a CLI/voice application. A React GUI dashboard is planned for a future release.

---

## 🔁 Distributed Mode (Workers)

For large workloads, enable Redis-based distributed execution:

```bash
# 1. Start Redis (or use docker-compose which includes Redis)
docker run -d -p 6379:6379 redis:alpine

# 2. Set execution mode in .env or config/voiceos.yaml
EXECUTION_MODE=queued

# 3. Start VoiceOS
python main.py

# 4. Start one or more workers with specific roles
python workers/agent_worker.py --roles researcher,developer,analyst

# 5. Check distributed status
python main.py --status
```

---

## 🔍 Troubleshooting

### Import Errors

```bash
# Ensure your virtual environment is activated
which python    # macOS/Linux — should point to .venv
.venv\Scripts\python --version   # Windows

# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### Model Download Failures

```bash
# Trigger model download manually
python -c "from model_manager.model_manager import ModelManager; ModelManager().ensure_models()"
```

### Audio Issues

```bash
# List available audio devices
python -c "import sounddevice; print(sounddevice.query_devices())"

# Test your microphone
python -c "import sounddevice as sd; sd.rec(int(1 * 44100), samplerate=44100, channels=1)"
```

### Permission Errors on Workspace

```bash
# Linux/macOS
chmod -R 755 workspace/

# Windows (PowerShell)
icacls workspace /grant %USERNAME%:F /T
```

### Debug Logging

```bash
# Enable verbose logging
LOG_LEVEL=DEBUG python main.py

# Tail log file
Get-Content logs/voiceos.log -Wait   # Windows PowerShell
tail -f logs/voiceos.log              # macOS/Linux
```

### Log File Locations

| Log | Path |
|-----|------|
| Main application | `logs/voiceos.log` |
| Error log | `logs/errors.log` |
| Agent operations | `workspace/logs/agent_operations.log` |
| Tool executions | `workspace/logs/tool_operations.log` |

---

## 📚 Next Steps

After a successful setup:

1. **[Usage Guide](usage.md)** — Commands, voice interaction patterns, and workflows
2. **[Agent System](agents.md)** — How agents work and how to define custom roles
3. **[Architecture](architecture.md)** — System design and data flow
4. **[Tool API Reference](tool_api.md)** — Native tool classes and methods
5. **[Docker Instructions](../docker-instructions.md)** — Advanced Docker/Compose configuration

---

## 🆘 Getting Help

- **Docs**: Full documentation in `docs/`
- **Setup Verification**: `python scripts/verify_setup.py`
- **System Tests**: `python main.py --test`
- **GitHub Issues**: Report bugs or request features
