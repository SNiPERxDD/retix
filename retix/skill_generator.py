"""
Skill file templates for RETIX project context generation.
"""


VISION_SKILL_TEMPLATE = """---
name: retix
description: Provides the agent with local visual perception via MLX-based vision models.
---

# RETIX Vision Skill

## Description
Provides the agent with local visual perception via MLX-based vision models.

## Usage Conditions
- Use when UI state must be verified from an image instead of source assumptions.
- Use OCR mode when extracting visible text from screenshots.
- Use claim verification for boolean checks in regression workflows.

## Commands

### Describe
```bash
retix describe <path_to_image.png>
```

### OCR
```bash
retix ocr <path_to_image.png>
```

### Check
```bash
retix check <path_to_image.png> "submit button is visible"
```

### Daemon Control
```bash
retix daemon start
retix daemon status
retix daemon stop
```

## Notes
- Model and tier are configured through `.retix/config.yaml`.
- Skill file location: `.retix/SKILL.md`.
- Command output is plain-text by default; use `--json` for structured output.
"""
