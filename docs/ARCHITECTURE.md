# VoiceOS architecture

This document explains how VoiceOS is structured for contributors. For install steps see [GETTING_STARTED.md](GETTING_STARTED.md); for settings see [CONFIGURATION.md](CONFIGURATION.md).

---

## Design goals

VoiceOS is a **middle layer** between you and your operating system:

- **Local-first**: voice, permissions, and desktop control stay on your machine.
- **Optional compute offload**: heavy agent work can run in Docker workers when Redis is available.
- **Host-only OS automation**: `os_*` tools never run inside worker containers.
- **Permission-first**: risky actions require approval (or are denied) based on policy profile.
- **Extensible**: plugins, skills, and hooks add tools without forking core code.

---

## High-level picture

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST (your computer)                                             │
│                                                                   │
│  Voice / CLI  →  Session shell  →  Orchestrator  →  Agents     │
│                         │                │              │         │
│                         │                └──────► Tool executor   │
│                         │                         │    │    │     │
│                         │                    os_*  │  code │ web  │
│                         │                         ▼    ▼    ▼     │
│                    Host bridge (optional)    OS layer / plugins   │
│                         │                                         │
│  Microphone, TTS, permissions, audit, session store               │
└─────────────────────────┬─────────────────────────────────────────┘
                          │ Redis task queue (optional)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  COMPUTE (Docker workers, optional)                               │
│  Agent workers: research, coding, long tasks (no os_* tools)      │
└─────────────────────────────────────────────────────────────────┘
```

| Plane | Runs on | Responsibilities |
|-------|---------|------------------|
| **Host control plane** | Your OS process (`main.py` / `voiceos`) | Voice, CLI, permissions, OS automation, session resume |
| **Host bridge** | Separate local HTTP service (`voiceos-bridge`) | Optional IPC for OS intents when control plane and bridge are split |
| **Compute plane** | Docker containers (`voiceos-compute`) | Redis, workers, sandboxed code/research; no desktop access |

---

## Entry points

| Entry | Role |
|-------|------|
| `main.py` | Primary runtime: bootstraps config, events, orchestrator, voice/CLI |
| `voiceos` (`voiceos_host/cli.py`) | Installed CLI wrapper around `main.py` |
| `voiceos-doctor` | Health checks (Docker, Redis, LLM, mic, bridge) |
| `voiceos-compute` | Starts Redis + scales Docker workers |
| `voiceos-bridge` | Starts host bridge HTTP server on `127.0.0.1:18765` |
| `voiceos-shell` | Session shell utilities (wake word, PTT, greeting) |
| `voiceos-ecosystem` | List/validate plugin and tool execution surfaces |
| `voiceos-audit-export` | Export permission audit logs |

Configuration lives in `config/voiceos.yaml` (and `config/voiceos.hybrid.yaml` for hybrid mode). Environment overrides use `.env`.

---

## Request flow

### 1. Input

User input arrives through one of:

- **CLI**: `VoiceCLIIntegration` reads typed lines and calls the orchestrator.
- **Voice**: `VoicePipeline` transcribes speech; events flow through `SessionShell` (wake word / push-to-talk gating) or directly when the shell is disabled.
- **Gateway**: optional messaging integrations (Telegram, WhatsApp, email plugins).

### 2. Session shell (`core/session_shell/`)

When enabled, the session shell:

- Greets with available capabilities (OS tools, bridge status, resume hint).
- Gates voice input (wake word, push-to-talk, idle/armed states).
- Publishes accepted text as `USER_MESSAGE` on the event bus.

### 3. Orchestrator (`core/orchestrator.py`)

Central coordinator:

1. Resolves session continue/recall (`core/session/`).
2. Parses skill invocations (`skills/`).
3. Plans work via `agents/core/planner.py` and routes via `agents/core/router.py`.
4. Runs autonomous or delegated workflows when requested.
5. Invokes `ToolExecutor` for tool calls returned by the LLM.

### 4. Tool execution (`tools/tool_executor.py`)

For each tool call:

1. **Policy**: `PolicyEngine` + `PermissionEngine` check approval rules.
2. **Surface**: `core/ecosystem/` ensures `os_*` tools run only on the host.
3. **Guardrails**: budgets, spill-to-disk for large results, verify hooks.
4. **Execution**: dispatches to registered tool handlers in `tools/register_tools.py`.

OS tools route through `core/os_layer/` → `OSIntentExecutor` → platform adapter or host bridge.

### 5. Response

Results flow back through the orchestrator → TTS (voice mode) or console output (CLI). Turn state and memory sync via `SessionManager` and `MemoryLifecycle`.

---

## Core components

### Event bus (`core/events/`)

Pub/sub backbone. Key events include `USER_MESSAGE`, `SPEECH_TRANSCRIBED`, `ORCHESTRATOR_RESPONSE`, `PERMISSION_GRANTED`, and tool lifecycle events. Handlers in `core/events/event_handlers.py` wire subsystems together.

### Runtime bootstrap (`core/runtime/bootstrap.py`)

`build_runtime_context()` wires the full graph:

- `PermissionEngine` + `PolicyEngine` + optional Postgres audit
- `ToolRegistry` via `register_tools()`
- `ToolExecutor`, `LLMService`, `MemoryService`
- `SkillRegistry`, `DelegateRunner`, ecosystem registry
- Returns a `RuntimeContext` consumed by `main.py` and the orchestrator

### OS abstraction layer (`core/os_layer/`)

Desktop operations are expressed as **intents** (open app, click, type, screenshot, etc.), not raw OS API calls scattered through the codebase.

| Piece | Purpose |
|-------|---------|
| `intent.py` | Intent enum and request normalization |
| `executor.py` | `OSIntentExecutor`: local adapter or host bridge |
| `capabilities.py` | Per-OS capability YAML (`config/os_capabilities/`) |

Platform-specific code lives under `tools/os_control/platform/` (Windows, macOS, Linux).

### Host bridge (`host_bridge/`)

Optional HTTP service exposing `/health`, `/capabilities`, and `/intent` on localhost. Used when:

- `VOICEOS_BRIDGE_MODE=bridge`: control plane talks to bridge instead of calling OS APIs directly.
- Split deployments where only the bridge process has desktop access.

The bridge server uses `OSIntentExecutor(local_only=True)` to avoid recursive bridge calls.

### Policy and trust (`core/policy/`)

| Module | Role |
|--------|------|
| `profiles.py` | `personal`, `work`, `unattended` approval rules |
| `engine.py` | Decides prompt vs allow vs deny per tool/action |
| `snapshot.py` | Optional filesystem snapshot before risky autonomous runs |
| `audit_export.py` | CLI export of audit trail |

Workers use the `unattended` profile; they cannot prompt and must not receive `os_*` tools (`tools/tool_executor.py` enforces this).

### Ecosystem (`core/ecosystem/`)

Maps plugins and tools to **execution surfaces**:

| Surface | Meaning |
|---------|---------|
| `host` | Must run on the user's machine (browser, OS tools) |
| `worker` | Must run in Docker workers |
| `either` | Router decides based on task weight and runtime mode |

Declared in each plugin's `plugin.yaml` (`execution_surface` field). Validated with `voiceos-ecosystem validate`.

### Distributed runtime (`core/distributed/`)

| Mode | Behavior |
|------|----------|
| `local` | All agent work in the host process |
| `queued` | Tasks enqueued to Redis; workers pull jobs |
| `auto` | Uses `queued` when Redis is up, else `local` |

`voiceos-compute` brings up Redis (via Docker Compose) and worker containers. `scripts/wait_for_redis.py` blocks until Redis is ready during bootstrap.

### Sandbox (`core/sandbox/`)

Unified code execution: local subprocess or Docker-isolated runner based on `config` and `VOICEOS_SANDBOX_PREFER_DOCKER`. Workers always prefer container isolation.

### Plugins (`plugins/` + `core/plugins/`)

Bundled plugins extend VoiceOS with tools (browser, memory, code execution, integrations). At startup, `core/plugins/startup.py` discovers and registers plugin-provided tools.

Plugin integration stack:

- `secure_plugin_integration.py`: security boundaries
- `plugin_registry.py`: discovery and metadata
- `plugin_lifecycle.py`: load/unload hooks

### Skills (`skills/`)

Instruction packs (`SKILL.md` with YAML frontmatter). `skills/skills_guard.py` enforces install policy. Bundled packs live under `skills/bundled/`; user packs go in `workspace/skills/`.

### Agents (`agents/`)

| Area | Role |
|------|------|
| `core/planner.py`, `router.py` | Plan decomposition and agent routing |
| `autonomous/`, `runtime/` | Long-running autonomous loops |
| `delegation/` | Delegate subtasks to specialist agents |
| `roles/` | Legacy YAML role definitions (also mirrored under `skills/bundled/voiceos/`) |

Task weight (`agents/core/task_weight.py`) influences whether work stays on host or goes to workers.

---

## Data and persistence

| Store | Location | Purpose |
|-------|----------|---------|
| Sessions | `workspace/sessions/` (configurable) | Conversation history, resume |
| Memory | `memory/` + memory plugins | Long-term recall |
| Audit | `logs/audit.log` + optional Postgres (`scripts/init-db.sql`) | Permission and action audit |
| Tool spill | `workspace/tool-results/` | Large tool outputs offloaded from context |
| Models | `models/` (gitignored) | Local Whisper, TTS, LLM weights |

---

## Docker layout

`docker-compose.yml` uses profiles:

| Profile | Services |
|---------|----------|
| `core` | Redis, Postgres |
| `workers` | `voiceos-worker` containers (scalable) |
| `llm` | Optional Ollama sidecar |
| `full` | Legacy all-in-one (Linux GUI in container; not the recommended VoiceOS path) |

Hybrid setup: host runs `voiceos --mode hybrid`; compute runs via `voiceos-compute` or `scripts/start_hybrid.*`.

---

## Extension points (for contributors)

| Want to add… | Where to work |
|--------------|---------------|
| New desktop action | `core/os_layer/intent.py` + platform adapter + `register_tools.py` |
| New tool | `tools/` module + register in `register_tools.py` |
| New plugin | `plugins/my_plugin/plugin.yaml` + tool handlers |
| New skill | `skills/bundled/community/.../SKILL.md` or `workspace/skills/` |
| Hook into LLM/tools | `workspace/hooks/` or plugin extension points |
| OS capability matrix | `config/os_capabilities/*.yaml` |
| External integration API | `config/schemas/voiceos-intent.schema.json` |

**Rules:**

- OS/desktop tools → `execution_surface: host` only.
- Never route `os_*` to workers.
- Go through `PolicyEngine` / `PermissionEngine` for risky operations.
- Match existing patterns in neighboring modules.

---

## Related docs

| Document | Topics |
|----------|--------|
| [CONFIGURATION.md](CONFIGURATION.md) | YAML, `.env`, policy profiles |
| [DOCKER.md](DOCKER.md) | Workers, Redis, compose profiles |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, PR checklist, plugin/skill guides |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Doctor output, common failures |
