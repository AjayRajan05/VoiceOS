---
name: voiceos-platform
description: "Configure, extend, and operate VoiceOS as a voice-first agent OS."
version: 1.0.0
author: VoiceOS Community
license: MIT
platforms: [linux, macos, windows]
metadata:
  voiceos:
    tags: [voiceos, setup, configuration, orchestrator, gateway, skills]
    related_skills: [voiceos-skill-authoring, claude-code, codex, opencode]
---

# VoiceOS Platform

VoiceOS is a voice-first operating layer: orchestrator, skills engine, gateway, delegation, and local tool execution.

## When to Use

- User asks how VoiceOS is configured or extended
- User wants gateway, skills, delegation, or voice pipeline behavior explained
- User needs paths for config, workspace, sessions, or bundled skills

## Key Paths

| Area | Location |
|------|----------|
| Config | `config/voiceos.yaml` |
| Sessions | `workspace/sessions/` |
| User skills | `workspace/skills/` |
| Bundled skills | `skills/bundled/voiceos/`, `skills/bundled/community/` |
| Gateway | `gateway/` |
| Architecture | `docs/ARCHITECTURE.md` |

## VoiceOS Tools

Use VoiceOS-native tools: `skills_list`, `skill_view`, `skill_create`, `delegate_task`, `send_message`, `web_search`, `web_research`, and OS tools prefixed with `os_`.

## Extending VoiceOS

1. Add user skills under `workspace/skills/<name>/SKILL.md` (see `voiceos-skill-authoring`).
2. Enable gateway platforms in `config/voiceos.yaml`.
3. Register shell hooks under `workspace/hooks/shell/`.
4. Use `python main.py --mcp` to expose tools via MCP.
