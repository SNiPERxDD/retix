"""
Skill generator for creating and managing .agent/vision-skill.md.
Automatically generates agent instructions and manages .gitignore entries.
"""

import sys
from pathlib import Path
from typing import Optional

from retix.path_utils import find_project_root, get_project_agent_dir, get_gitignore_path


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


def ensure_skill_exists(project_root: Optional[Path] = None) -> Path:
    """
    Ensure the .agent/vision-skill.md file exists.
    
    Creates both .agent directory and vision-skill.md if they don't exist.
    Handles .gitignore configuration to exclude .agent/ from version control.
    
    Args:
        project_root: Project root path. If None, searches for it.
    
    Returns:
        Path to the created/existing skill file
    """
    if project_root is None:
        project_root = find_project_root()
    else:
        project_root = Path(project_root).resolve()
    
    # Create .agent directory
    agent_dir = get_project_agent_dir(project_root)
    agent_dir.mkdir(parents=True, exist_ok=True)
    
    # Create vision-skill.md
    skill_file = agent_dir / "vision-skill.md"
    
    if not skill_file.exists():
        sys.stderr.write(f"Creating skill file: {skill_file}\n")
        sys.stderr.flush()
        skill_file.write_text(VISION_SKILL_TEMPLATE, encoding="utf-8")
    
    # Ensure .gitignore includes .agent/
    update_gitignore_for_agent(project_root)
    
    return skill_file


def update_gitignore_for_agent(project_root: Optional[Path] = None) -> None:
    """
    Idempotently update .gitignore to exclude .agent/ directory.
    
    Args:
        project_root: Project root path. If None, searches for it.
    """
    if project_root is None:
        project_root = find_project_root()
    else:
        project_root = Path(project_root).resolve()
    
    gitignore_path = get_gitignore_path(project_root)
    agent_entry = ".agent/"
    
    # If .gitignore exists, check if .agent/ is already listed
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        
        # Check if .agent/ is already in .gitignore (with line or exact match)
        lines = [line.strip() for line in gitignore_content.split("\n")]
        if agent_entry in lines or ".agent/" in gitignore_content:
            return  # Already present, no need to update
        
        # Append .agent/ to .gitignore
        if not gitignore_content.endswith("\n"):
            gitignore_content += "\n"
        gitignore_content += f"{agent_entry}\n"
    else:
        # Create new .gitignore
        gitignore_content = f"{agent_entry}\n"
    
    sys.stderr.write(f"Updating .gitignore to exclude {agent_entry}\n")
    sys.stderr.flush()
    
    gitignore_path.write_text(gitignore_content, encoding="utf-8")


def get_skill_instance_prompt() -> str:
    """
    Get a prompt to inject into agent context for skill discovery.
    
    This should be added to agent system prompts to make them aware of retix.
    
    Returns:
        Prompt text for agents
    """
    return """
You have access to a vision analysis tool called 'retix' that can analyze UI screenshots.
When you need to understand a visual layout, extract text, or verify visual properties:

1. Ask the user for a screenshot (or suggest taking one with `screencapture -x screenshot.png`)
2. Run: `retix describe screenshot.png` for general UI analysis
3. Run: `retix ocr screenshot.png` for text extraction
4. Run: `retix check screenshot.png "description here"` for verification

Full documentation is in `.retix/SKILL.md` in the current project.
The tool outputs to stdout only; loading messages go to stderr (won't interfere with parsing).
"""


def create_skill_file() -> str:
    """
    Generate skill file content for retix.
    
    Returns:
        Markdown content for .retix/SKILL.md
    """
    return VISION_SKILL_TEMPLATE
