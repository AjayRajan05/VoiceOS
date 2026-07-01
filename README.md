# VoiceOS

**Talk to your computer. It listens, plans, and gets things done safely.**

VoiceOS is a free, open-source assistant you run on your own computer (Windows, macOS, or Linux). You can **speak** or **type** everyday requests (open apps, search the web, write files, run code, research topics, and multi-step projects), and VoiceOS handles the work using AI agents behind the scenes.

VoiceOS does **not** replace your operating system. It sits **on top** of it: your voice and keyboard stay on your machine, sensitive desktop actions stay on your machine, and heavy AI work can optionally run in Docker containers for speed and isolation.

---

## Who is this for?

- **Anyone** who wants a local, privacy-friendly AI assistant on their desktop  
- **Developers** who want voice + agents + OS automation in one stack  
- **Teams** who want permission prompts, audit logs, and optional Docker offload  

No cloud account is required. You can use local AI (Ollama) or optional API keys (OpenAI, Anthropic).

---

## What can VoiceOS do?

| You say or type… | VoiceOS can… |
|------------------|--------------|
| “Open Chrome” | Launch and control desktop apps |
| “Take a screenshot” | Automate keyboard, mouse, clipboard, windows |
| “Research quantum computing trends” | Search the web and summarize with an AI agent |
| “Write a Python script to parse CSV files” | Generate and run code in a sandbox |
| “Build a scraper and analyze the results” | Run a multi-step autonomous workflow |
| “Continue what we were doing” | Resume your last conversation (saved locally) |

VoiceOS asks for **approval** before risky actions (deleting files, running code, some OS operations) unless you change the policy profile.

---

## How it works (simple picture)

```
You (voice or keyboard)
        ↓
VoiceOS on your computer  ← microphone, speakers, permissions, desktop control
        ↓
Optional Docker workers   ← heavy research, coding, long agent tasks
        ↓
Your apps, files, and browser
```

- **Host** = your computer running VoiceOS (voice, safety, opening apps).  
- **Compute** = optional Docker workers for heavy tasks when Redis is running.  
- If Docker is off, VoiceOS still works; everything runs on your CPU.

---

## What you need

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | [python.org](https://www.python.org/downloads/); check “Add to PATH” on Windows |
| **Microphone** | For voice mode (optional if you only use typing) |
| **~8 GB RAM** | 16 GB+ recommended for local AI models |
| **Docker Desktop** | Optional but recommended for heavy tasks ([docker.com](https://www.docker.com/products/docker-desktop/)) |
| **Ollama** | Optional local LLM ([ollama.com](https://ollama.com)), or use cloud API keys |

---

## Quick start (5 steps)

### 1. Get the code

```bash
git clone https://github.com/AjayRajan05/VoiceOS.git
cd VoiceOS/project
```

### 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install VoiceOS

```bash
pip install -r requirements.txt
pip install -e .
```

On first run, VoiceOS can create a `.env` file from `.env.example` automatically.

### 4. Check your system

```bash
voiceos-doctor
```

This reports Docker, Redis, workers, microphone, LLM endpoint, and optional host bridge status. Fix anything marked **FAIL** before continuing (see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)).

### 5. Start VoiceOS

**Easiest (recommended on Windows):**
```powershell
.\scripts\start_hybrid.ps1
voiceos --mode hybrid
```

**macOS / Linux:**
```bash
./scripts/start_hybrid.sh
voiceos --mode hybrid
```

**Hybrid mode** = speak **and** type at the same time.

At the `VoiceOS>` prompt, try:
- `help`: list commands  
- `open notepad`: simple OS task  
- `research latest AI news`: agent task (uses Docker workers if available)  
- `quit`: exit  

---

## Commands you will use

After `pip install -e .`, these commands are available in your terminal:

| Command | What it does |
|---------|----------------|
| `voiceos` | Start VoiceOS (same as `python main.py`) |
| `voiceos-doctor` | Health check for your machine |
| `voiceos-compute` | Start Redis + Docker workers only |
| `voiceos-bridge` | Optional always-on OS automation service |
| `voiceos-shell` | Voice session with wake word (“hey voiceos”) |
| `voiceos-ecosystem` | List plugins/skills and export intent schema |
| `voiceos-audit-export` | Export permission audit log for review |

**Main program options:**
```bash
voiceos --mode hybrid    # voice + typing (default)
voiceos --mode cli       # typing only
voiceos --mode voice     # microphone only
voiceos --doctor         # run doctor and exit
voiceos --status         # show system status
python main.py --test    # run built-in tests
```

---

## Voice session (wake word)

For a hands-free style session:

```bash
voiceos-shell
```

Say **“hey voiceos”**, then your command; for example: *“hey voiceos, open Chrome”*.

Other useful phrases:
- *“continue what we were doing”*: resume last session  
- *“new conversation”*: start fresh  
- *“stop”* or *“cancel”*: interrupt speech  

---

## Docker and heavy tasks (optional)

For research, coding, and long agent work, start the **compute plane**:

```bash
voiceos-compute --workers 2
```

Or use the hybrid script (bridge + compute):

```powershell
.\scripts\start_hybrid.ps1   # Windows
./scripts/start_hybrid.sh    # macOS / Linux
```

Set in `.env`:
```bash
EXECUTION_MODE=auto
REDIS_URL=redis://localhost:6379/0
```

With `auto`, VoiceOS uses Docker workers when Redis is up; otherwise it falls back to your CPU with a startup warning.

| Tier | What you have | Experience |
|------|----------------|------------|
| Full hybrid | Docker + Redis + workers | Best for heavy tasks |
| Partial | Docker + Redis, no workers | Start workers with `voiceos-compute` |
| Local only | No Docker | Everything on host; CLI mode works well |

Details: [docs/DOCKER.md](docs/DOCKER.md)

---

## Safety and privacy

- **Local-first**: models and conversation history stay on your disk (`workspace/`, `models/`, `logs/`).  
- **Permission levels**: LOW / MEDIUM / HIGH; risky tools prompt you in the terminal.  
- **Policy profiles**: `personal` (default), `work` (stricter), `unattended` (no prompts, auto-deny risky actions). Set `VOICEOS_POLICY_PROFILE` in `.env`.  
- **Audit log**: `logs/audit.log` records approvals and worker actions. Export with `voiceos-audit-export`.  
- **Sandbox**: agent file work stays under `workspace/`; code can run in Docker workers.  
- **OS automation never runs in Docker workers**: opening apps and screenshots always stay on your computer.

---

## Configuration (short version)

Copy and edit environment settings:

```bash
cp .env.example .env
```

Important settings:

| Variable | Meaning |
|----------|---------|
| `LLM_ENDPOINT` | Ollama URL (default `http://localhost:11434/api/generate`) |
| `LLM_MODEL` | Model name (e.g. `mistral`, `llama3`) |
| `EXECUTION_MODE` | `auto`, `local`, or `queued` |
| `PERMISSION_LEVEL` | `low`, `medium`, or `high` |
| `VOICEOS_POLICY_PROFILE` | `personal`, `work`, or `unattended` |
| `VOICEOS_BRIDGE_MODE` | `auto`, `bridge`, or `local` |

Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

Main YAML config: `config/voiceos.yaml`

---

## Plugins and skills

VoiceOS ships with **bundled plugins** (browser, memory, code execution, messaging integrations, and more) under `plugins/`.

**Skills** are reusable instruction packs under `skills/bundled/`. You can add your own under `workspace/skills/`.

List extensions and where they run (host vs Docker):

```bash
voiceos-ecosystem list
voiceos-ecosystem validate
```

---

## Project layout (for contributors)

```
project/
├── main.py                 # Entry point
├── voiceos_host/           # CLI commands (voiceos, voiceos-doctor, …)
├── core/                   # Orchestrator, events, policy, session, doctor
├── agents/                 # Planner, router, autonomous loop
├── tools/                  # File, web, code, OS tools
├── host_bridge/            # Optional OS automation HTTP bridge
├── plugins/                # Bundled plugins
├── skills/                 # Bundled skills
├── config/                 # voiceos.yaml, OS capabilities, schemas
├── scripts/                # Install and start scripts
├── tests/                  # Automated tests
└── docs/                   # User and contributor documentation
```

Technical deep dive: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Contributing

We welcome issues, documentation fixes, plugins, skills, and code improvements.

1. Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)  
2. Run `voiceos-doctor` and `python -m pytest tests/ -q` before opening a PR  
3. Open an issue first for large changes  

---

## Documentation

| Document | Audience |
|----------|----------|
| [Getting started](docs/GETTING_STARTED.md) | Step-by-step install (beginner-friendly) |
| [Configuration](docs/CONFIGURATION.md) | All settings explained |
| [Docker guide](docs/DOCKER.md) | Containers, workers, GPU |
| [Architecture](docs/ARCHITECTURE.md) | How the system fits together |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common problems and fixes |
| [Contributing](docs/CONTRIBUTING.md) | How to help build VoiceOS |

---

## License

MIT License: see [LICENSE](LICENSE) if present in the repository, or the license field in `pyproject.toml`.

---

## Support

- **Health check:** `voiceos-doctor`  
- **Status:** `voiceos --status`  
- **Logs:** `logs/voiceos.log` and `logs/audit.log`  
- **Issues:** GitHub Issues on the project repository  

**VoiceOS**: your voice, your machine, your rules.
