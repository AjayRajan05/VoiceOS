# VoiceOS plugins

This folder contains **bundled plugins** shipped with VoiceOS (browser, memory, code execution, integrations, and more).

## For users

Plugins are loaded automatically at startup. You do not need to configure them for basic use.

Check status:

```bash
voiceos-ecosystem list
voiceos-ecosystem validate
```

## For developers

Each plugin is a folder with a `plugin.yaml` manifest:

```yaml
name: my_plugin
title: My Plugin
description: What it does
version: 1.0.0
execution_surface: either    # host | worker | either
provides_tools:
  - my_tool_name
```

| `execution_surface` | Runs on |
|---------------------|---------|
| `host` | Your computer only (browser UI, desktop) |
| `worker` | Docker workers only |
| `either` | Host or worker, decided at runtime |

**Rules:**
- OS/desktop tools (`os_*`) must use `host` only.
- Workers never execute OS automation.

## Documentation

- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md): system overview  
- [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md): how to add plugins  
- [config/schemas/voiceos-intent.schema.json](../config/schemas/voiceos-intent.schema.json): OS intent API for integrations  

## Custom plugins

Add new plugins under `plugins/your_plugin/` with `plugin.yaml`, or use hooks under `workspace/hooks/`.

Do not commit secrets or API keys inside plugin folders.
