# Contributing to VoiceOS

Thank you for helping improve VoiceOS. This guide covers how to set up a development environment, run tests, and submit changes.

---

## Ways to contribute

- **Bug reports**: Include `voiceos-doctor` output and steps to reproduce  
- **Documentation**: Fix typos, clarify guides, translate sections  
- **Skills**: Add `SKILL.md` packs under `skills/bundled/community/`  
- **Plugins**: Extend `plugins/` with a valid `plugin.yaml`  
- **Code**: Orchestrator, tools, OS adapters, tests  

---

## Development setup

```bash
git clone https://github.com/AjayRajan05/VoiceOS.git
cd VoiceOS/project
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
voiceos-doctor
```

---

## Running tests

```bash
python main.py --test
python -m pytest tests/ -v
python -m pytest tests/ -q --tb=short
```

Run focused suites while developing:

```bash
python -m pytest tests/test_os_layer.py tests/test_policy.py -v
```

---

## Code style

- Match surrounding code style and naming  
- Keep changes focused: one feature or fix per PR  
- Prefer extending existing modules over duplicate helpers  
- OS desktop operations must go through `core/os_layer/` or `PlatformAdapter`  
- Never queue `os_*` tools to Docker workers  

---

## Adding a plugin

1. Create `plugins/my_plugin/plugin.yaml`:

```yaml
name: my_plugin
title: My Plugin
description: What it does
version: 1.0.0
execution_surface: either   # host | worker | either
provides_tools:
  - my_tool_name
```

2. Validate:

```bash
voiceos-ecosystem validate
```

3. Register tools via existing plugin integration patterns in `tools/` and `core/plugins/`.

---

## Adding a skill

1. Create `workspace/skills/my-skill/SKILL.md` or contribute under `skills/bundled/community/`.  
2. Use YAML frontmatter:

```yaml
---
name: my-skill
description: Short description under 120 characters
execution_surface: either
---
```

3. Body: clear instructions for the agent.

Install policy (`safe` / `cautious` / `dangerous`) is enforced by `skills/skills_guard.py`.

---

## Pull request checklist

- [ ] `voiceos-doctor` passes or explains new WARN items  
- [ ] `python -m pytest tests/ -q` passes  
- [ ] README or `docs/` updated if user-facing behavior changed  
- [ ] No secrets committed (`.env`, API keys)  
- [ ] OS intents remain host-only  

---

## Architecture reference

See [ARCHITECTURE.md](ARCHITECTURE.md) for component map and data flow.

---

## Code of conduct

Be respectful in issues and reviews. VoiceOS is a community project aimed at safe, local-first automation.
