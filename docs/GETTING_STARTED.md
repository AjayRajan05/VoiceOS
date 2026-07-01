# Getting started with VoiceOS

This guide walks you through installing and running VoiceOS from scratch. No prior coding experience is required for the basic setup; copy and paste the commands for your operating system.

---

## Before you begin

1. **Install Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).  
   - On Windows: during install, check **“Add python.exe to PATH”**.  
2. **Install Git** from [git-scm.com](https://git-scm.com/) if you do not have it.  
3. **Optional but recommended:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) for faster research and coding tasks.  
4. **Optional:** [Ollama](https://ollama.com) for a free local AI brain. After installing, run: `ollama pull mistral`

---

## Step 1: Download VoiceOS

Open a terminal (PowerShell on Windows, Terminal on Mac/Linux):

```bash
git clone https://github.com/AjayRajan05/VoiceOS.git
cd VoiceOS/project
```

---

## Step 2: Python virtual environment

A virtual environment keeps VoiceOS packages separate from the rest of your system.

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run once:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` at the start of your prompt.

---

## Step 3: Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

The last command registers commands like `voiceos` and `voiceos-doctor`.

---

## Step 4: Environment file

```bash
cp .env.example .env
```

Edit `.env` in any text editor. Minimum for local Ollama:

```bash
LLM_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL=mistral
EXECUTION_MODE=auto
```

VoiceOS can also create `.env` automatically on first run if it is missing.

---

## Step 5: Run the doctor

```bash
voiceos-doctor
```

| Result | What to do |
|--------|------------|
| All OK | Continue to Step 6 |
| Docker WARN | Install/start Docker Desktop for heavy tasks, or ignore for CLI-only use |
| Redis WARN | Run `voiceos-compute` or `start_hybrid` script when you need workers |
| Microphone WARN | Use `--mode cli` if you do not need voice |
| LLM WARN | Start Ollama or set cloud API keys in `.env` |

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for details.

---

## Step 6: Start VoiceOS

### Typing only (simplest)

```bash
voiceos --mode cli
```

Type commands at `VoiceOS>` and press Enter.

### Voice + typing (recommended)

**Windows:**
```powershell
.\scripts\start_hybrid.ps1
voiceos --mode hybrid
```

**macOS / Linux:**
```bash
chmod +x scripts/*.sh
./scripts/start_hybrid.sh
voiceos --mode hybrid
```

Allow microphone access when your OS asks.

### Wake word session

```bash
voiceos-shell
```

Say **“hey voiceos”** then your request.

---

## Step 7: Try example commands

At the prompt or after the wake phrase:

```
help
open notepad
take a screenshot
research renewable energy trends
continue what we were doing
quit
```

---

## What gets created on your disk

| Folder | Purpose |
|--------|---------|
| `workspace/` | Agent work, sessions, skills you add |
| `models/` | Downloaded speech and LLM models |
| `logs/` | Application and audit logs |
| `memory/` | Long-term memory data (if enabled) |
| `output/` | Generated audio responses |

These folders are safe to back up. They are listed in `.gitignore` and are not pushed to Git.

---

## Next steps

- [CONFIGURATION.md](CONFIGURATION.md): tune voice, policy, Docker  
- [DOCKER.md](DOCKER.md): workers and GPU  
- [ARCHITECTURE.md](ARCHITECTURE.md): how components connect  
- [CONTRIBUTING.md](CONTRIBUTING.md): join development  
