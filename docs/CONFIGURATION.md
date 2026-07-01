# Configuration

VoiceOS settings come from **environment variables** (`.env`) and **YAML** (`config/voiceos.yaml`). Environment variables override YAML when both define the same behavior.

---

## Environment variables (`.env`)

Copy `.env.example` to `.env` and edit.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICEOS_ENV` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `VOICEOS_WORKSPACE` | `./workspace` | Workspace root |

### AI / LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENDPOINT` | Ollama URL | HTTP endpoint for text generation |
| `LLM_MODEL` | `mistral` | Model name at the endpoint |
| `OPENAI_API_KEY` | empty | Optional OpenAI fallback |
| `ANTHROPIC_API_KEY` | empty | Optional Anthropic fallback |

### Voice

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `base` | Speech-to-text model size |
| `TTS_MODEL` | Coqui default | Text-to-speech model |
| `MICROPHONE_DEVICE` | `default` | Input device name |

### Execution and Docker

| Variable | Default | Description |
|----------|---------|-------------|
| `EXECUTION_MODE` | `auto` | `auto` \| `local` \| `queued` |
| `REDIS_URL` | `redis://localhost:6379/0` | Task queue for workers |
| `VOICEOS_SANDBOX_PREFER_DOCKER` | `true` | Run code in workers when possible |
| `VOICEOS_WORKER_IMAGE` | (build local) | Prebuilt worker image URL |

### Security and policy

| Variable | Default | Description |
|----------|---------|-------------|
| `PERMISSION_LEVEL` | `medium` | `low` \| `medium` \| `high` |
| `SANDBOX_ENABLED` | `true` | Sandbox file/code execution |
| `VOICEOS_POLICY_PROFILE` | `personal` | `personal` \| `work` \| `unattended` |

| Profile | Behavior |
|---------|----------|
| personal | Prompt for destructive OS actions; snapshots before autonomous runs |
| work | Prompt for OS tools, writes, and autonomous tasks |
| unattended | Auto-deny risky host actions (for headless/workers) |

### Host bridge

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICEOS_BRIDGE_MODE` | `auto` | `auto` \| `bridge` \| `local` |
| `VOICEOS_BRIDGE_HOST` | `127.0.0.1` | Bridge bind address |
| `VOICEOS_BRIDGE_PORT` | `18765` | Bridge HTTP port |

### Session shell

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICEOS_SHELL_ENABLED` | from yaml | Enable session shell |
| `VOICEOS_SHELL_INPUT_MODE` | `wake_word` | `always_on` \| `wake_word` \| `push_to_talk` |
| `VOICEOS_WAKE_PHRASES` | hey voiceos,… | Comma-separated wake phrases |
| `VOICEOS_PTT_KEY` | `space` | Push-to-talk key |

---

## YAML configuration (`config/voiceos.yaml`)

Key sections:

```yaml
execution_mode: auto          # auto | local | queued

voice:
  turn_policy: interrupt      # interrupt | queue | steer
  enable_interrupts: true

session:
  enabled: true
  path: workspace/sessions

session_shell:
  enabled: false
  input_mode: wake_word

security:
  policy_profile: personal
  snapshot_before_autonomous: true

distributed:
  redis_url: redis://localhost:6379/0

sandbox:
  prefer_docker_workers: true

skills:
  install_policy: cautious    # safe | cautious | dangerous
  hub_enabled: false
```

Slim host-only config: `config/voiceos.host.yaml`  
Hybrid-focused config: `config/voiceos.hybrid.yaml`

Use a custom file:
```bash
voiceos --config config/voiceos.host.yaml
```

---

## OS capabilities

Per-platform feature flags live in:

- `config/os_capabilities/windows.yaml`
- `config/os_capabilities/darwin.yaml`
- `config/os_capabilities/linux.yaml`

VoiceOS uses these to report what desktop automation is supported on your machine.

---

## Public intent schema

External integrations can use the OS-neutral intent contract:

- File: `config/schemas/voiceos-intent.schema.json`
- Regenerate: `voiceos-ecosystem export-intent-schema`

---

## Recommended setups

### Home user (voice + typing, local AI)

```bash
EXECUTION_MODE=auto
VOICEOS_POLICY_PROFILE=personal
LLM_ENDPOINT=http://localhost:11434/api/generate
```

### Developer (Docker offload)

```bash
EXECUTION_MODE=auto
REDIS_URL=redis://localhost:6379/0
```

Run `voiceos-compute --workers 2` before `voiceos --mode hybrid`.

### Typing only, no Docker

```bash
EXECUTION_MODE=local
```

```bash
voiceos --mode cli
```
