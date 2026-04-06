"""
Configuration management for retix projects.

Manages:
- Local .retix/ directory
- config.yaml with project overrides
- Skill file management
- .gitignore integration
"""

from pathlib import Path
from typing import Optional, Dict, Any

import yaml

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    Console = None


GLOBAL_RETIX_DIR = Path.home() / ".retix"
GLOBAL_CONFIG_FILE = GLOBAL_RETIX_DIR / "config.yaml"


def get_console():
    """Get rich console if available."""
    if Console:
        return Console(force_terminal=True)
    return None


def find_project_root() -> Optional[Path]:
    """
    Find the project root directory by looking for markers.
    
    Returns:
        Path to project root or None if not in a project directory
    """
    markers = [".git", "pyproject.toml", "package.json", "setup.py"]
    
    current = Path.cwd()
    for _ in range(10):  # Limit search depth
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent
    
    return None


def get_retix_dir(project_root: Optional[Path] = None) -> Path:
    """
    Get or create .retix directory.
    
    Args:
        project_root: Project root path (auto-detected if None)
    
    Returns:
        Path to .retix directory
    """
    if project_root is None:
        from retix.path_utils import find_project_root as find_root
        project_root = find_root()
    
    if project_root is None:
        project_root = Path.cwd()
    
    retix_dir = project_root / ".retix"
    retix_dir.mkdir(parents=True, exist_ok=True)
    return retix_dir


def get_global_config_path() -> Path:
    """Get path to global RETIX config file."""
    GLOBAL_RETIX_DIR.mkdir(parents=True, exist_ok=True)
    return GLOBAL_CONFIG_FILE


def load_global_config() -> Dict[str, Any]:
    """Load global RETIX config from ~/.retix/config.yaml."""
    default_global_config: Dict[str, Any] = {}
    global_config_path = get_global_config_path()

    if not global_config_path.exists():
        return default_global_config

    try:
        with open(global_config_path, "r") as file_handle:
            loaded = yaml.safe_load(file_handle)
            if loaded and isinstance(loaded, dict):
                default_global_config.update(loaded)
    except Exception:
        return default_global_config

    return default_global_config


def save_global_config(config: Dict[str, Any]) -> bool:
    """Save global RETIX config to ~/.retix/config.yaml."""
    global_config_path = get_global_config_path()
    try:
        with open(global_config_path, "w") as file_handle:
            yaml.safe_dump(config, file_handle, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def get_config_path(project_root: Optional[Path] = None) -> Path:
    """Get path to .retix/config.yaml."""
    retix_dir = get_retix_dir(project_root)
    return retix_dir / "config.yaml"


def load_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from .retix/config.yaml.
    
    Returns default config if file doesn't exist.
    
    Args:
        project_root: Project root path (auto-detected if None)
    
    Returns:
        Configuration dictionary
    """
    config_path = get_config_path(project_root)
    
    default_config = {
        "model": "mlx-community/Qwen3-VL-2B-Instruct-4bit",
        "quantization": "4bit",
        "temperature": 0.0,
        "max_tokens": 1024,
        "cache_dir": str(Path.home() / ".cache" / "retix"),
    }
    
    # Merge global config first, then local project overrides.
    default_config.update(load_global_config())

    if not config_path.exists():
        return default_config
    
    try:
        with open(config_path, "r") as f:
            loaded = yaml.safe_load(f)
            if loaded:
                default_config.update(loaded)
            return default_config
    except Exception:
        return default_config


def save_config(
    config: Dict[str, Any],
    project_root: Optional[Path] = None
) -> bool:
    """
    Save configuration to .retix/config.yaml.
    
    Args:
        config: Configuration dictionary
        project_root: Project root path (auto-detected if None)
    
    Returns:
        bool: True if successful, False otherwise
    """
    config_path = get_config_path(project_root)
    
    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception:
        return False


def get_gitignore_path(project_root: Optional[Path] = None) -> Path:
    """Get path to .gitignore in project root."""
    if project_root is None:
        from retix.path_utils import find_project_root as find_root
        project_root = find_root()
    
    if project_root is None:
        project_root = Path.cwd()
    
    return project_root / ".gitignore"


def update_gitignore(project_root: Optional[Path] = None) -> bool:
    """
    Add RETIX context and hygiene entries to .gitignore if not present.
    
    Args:
        project_root: Project root path (auto-detected if None)
    
    Returns:
        bool: True if successful or already present, False on error
    """
    gitignore_path = get_gitignore_path(project_root)
    entries_to_add = [".retix/", ".agent/", "archive/", ".env", "venv/"]
    header = "# RETIX Agent Context"
    
    try:
        # Read existing content
        if gitignore_path.exists():
            content = gitignore_path.read_text()
        else:
            content = ""
        
        # Check if already added
        if header in content:
            return True
        
        # Append new entries
        if content and not content.endswith("\n"):
            content += "\n"
        
        content += f"\n{header}\n"
        for entry in entries_to_add:
            content += f"{entry}\n"
        
        gitignore_path.write_text(content)
        return True
    except Exception:
        return False


def initialize_project_context(project_root: Optional[Path] = None) -> bool:
    """
    Initialize complete .retix context for a project.
    
    Creates:
    - .retix/ directory
    - config.yaml with defaults
    - Skill file
    - Updates .gitignore
    
    Args:
        project_root: Project root path (auto-detected if None)
    
    Returns:
        bool: True if successful, False otherwise
    """
    console = get_console()
    
    # Find or create project root context
    if project_root is None:
        from retix.path_utils import find_project_root as find_root
        project_root = find_root()
    
    if project_root is None:
        project_root = Path.cwd()

    try:
        from retix.safety_checks import is_valid_project_directory
        if not is_valid_project_directory(project_root):
            if console:
                console.print("[yellow]Skipped:[/yellow] current directory is not a recognized project root")
            return False
    except Exception:
        # If safety checks cannot be loaded, continue with best effort behavior.
        pass
    
    if console:
        console.print(f"[cyan]→[/cyan] Initializing retix in {project_root}")
    
    # Create .retix directory
    retix_dir = get_retix_dir(project_root)
    
    # Load and save default config
    config = load_config(project_root)
    if not save_config(config, project_root):
        if console:
            console.print("[red]✗[/red] Failed to save config")
        return False
    
    # Create skill file
    from retix.skill_generator import create_skill_file
    skill_path = retix_dir / "SKILL.md"
    if not skill_path.exists():
        try:
            skill_content = create_skill_file()
            skill_path.write_text(skill_content)
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Failed to create skill file: {e}")
    
    # Update .gitignore
    if not update_gitignore(project_root):
        if console:
            console.print("[yellow]⚠[/yellow] Failed to update .gitignore")
    
    if console and Panel:
        console.print(Panel(
            f"[green]✓[/green] Project context initialized\n\n"
            f"Location: [cyan]{retix_dir}[/cyan]\n\n"
            "[dim]Your agent now has vision skills via .retix/SKILL.md[/dim]",
            title="Success",
            border_style="green",
        ))
    
    return True


def ensure_project_skill_file(project_root: Optional[Path] = None) -> Optional[Path]:
    """Ensure only the project skill file exists without reinitializing the full context."""
    if project_root is None:
        from retix.path_utils import find_project_root as find_root
        project_root = find_root()

    if project_root is None:
        return None

    project_root = Path(project_root).resolve()
    retix_dir = get_retix_dir(project_root)
    skill_path = retix_dir / "SKILL.md"

    if skill_path.exists():
        return skill_path

    from retix.skill_generator import create_skill_file

    skill_path.write_text(create_skill_file(), encoding="utf-8")
    return skill_path


def display_config(project_root: Optional[Path] = None):
    """Display current configuration."""
    console = get_console()
    config = load_config(project_root)
    
    if console and Panel:
        config_text = ""
        for key, value in config.items():
            config_text += f"[cyan]{key}:[/cyan] {value}\n"
        
        console.print(Panel(
            config_text,
            title="Current Configuration",
            expand=False,
        ))
    else:
        for key, value in config.items():
            print(f"{key}: {value}")
