---
name: voiceos-skill-authoring
description: "Author in-repo SKILL.md for VoiceOS: frontmatter, structure, and quality."
version: 1.1.0
author: VoiceOS Community
license: MIT
platforms: [linux, macos, windows]
metadata:
  voiceos:
    tags: [skills, authoring, voiceos, conventions, skill-md]
    related_skills: [plan, requesting-code-review]
---

# Authoring VoiceOS Skills (in-repo)

## Overview

VoiceOS skills live as `SKILL.md` files with YAML frontmatter (agentskills.io compatible).

Two locations:

1. **User skills:** `workspace/skills/<category>/<name>/SKILL.md` - created via `skill_create` or file tools.
2. **Bundled skills:** `skills/bundled/voiceos/` or `skills/bundled/community/<category>/<name>/SKILL.md` - committed to the repo.

## When to Use

- User asks to add or edit a skill in the VoiceOS tree
- You need frontmatter shape, size limits, or progressive disclosure guidance

## Required Frontmatter

```yaml
---
name: my-skill-name
description: Use when <trigger>. <one-line behavior>.
version: 1.1.0
author: VoiceOS Community
license: MIT
metadata:
  voiceos:
    tags: [Short, Tags]
    related_skills: [other-skill]
---
```

Validator source: `skills/skills_guard.py` + `skills/skill_utils.py`.

## Size Limits

- `description` ≤ 1024 chars
- Full `SKILL.md` ≤ 100,000 chars
- Aim for 8–15k chars; move bulky reference to `references/`, `templates/`, or `scripts/`

## Structure

```
# Title
## Overview
## When to Use
## Procedure / topic sections
## Common Pitfalls
## Verification Checklist
```

## Workflow

1. Survey peers: `skills/bundled/voiceos/` or `skills/bundled/community/<category>/`
2. Draft with `write_file` or `skill_create`
3. Validate name (≤64 chars, lowercase-hyphens) and description (≤1024 chars)
4. Commit bundled skills to git when shipping in-repo

## Verification Checklist

- [ ] `metadata.voiceos.tags` and `related_skills` present
- [ ] Description starts with "Use when ..."
- [ ] Body includes pitfalls and verification steps
- [ ] User skills go under `workspace/skills/`; bundled under `skills/bundled/`
