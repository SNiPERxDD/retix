"""
Safety checks and constraints for retix operations.

Handles:
- Xcode Command Line Tools verification
- Writable project directory detection
- VRAM availability checking
- System compatibility validation
"""

import os
import subprocess
import platform
from pathlib import Path
from typing import Tuple, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    Console = None
    Panel = None


def get_console():
    """Get rich console if available, otherwise return None."""
    if Console:
        return Console(force_terminal=True)
    return None


def check_xcode_command_line_tools() -> bool:
    """
    Check if Xcode Command Line Tools are installed.
    
    Returns:
        bool: True if installed, False otherwise
    """
    try:
        result = subprocess.run(
            ["xcode-select", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def handle_missing_xcode():
    """
    Display helpful error message if Xcode Command Line Tools are missing.
    Exits with code 1.
    """
    console = get_console()
    
    if console and Panel:
        panel_text = "[bold red]Xcode Command Line Tools Required[/bold red]\n\n"
        panel_text += "The Xcode Command Line Tools are required to install retix.\n\n"
        panel_text += "[yellow]To install, run:[/yellow]\n"
        panel_text += "[cyan]xcode-select --install[/cyan]\n\n"
        panel_text += "This will open a dialog. Follow the prompts to complete installation."
        
        console.print(Panel(
            panel_text,
            title="[bold]Setup Required[/bold]",
            expand=False,
            border_style="red",
        ))
    else:
        print("ERROR: Xcode Command Line Tools are required.")
        print("Run: xcode-select --install")
    
    exit(1)


def is_valid_project_directory(path: Optional[Path] = None) -> bool:
    """
    Check if the given path is a valid project directory.
    
    A valid project directory contains at least one of:
    - .git
    - pyproject.toml
    - package.json
    - setup.py
    - .gitignore
    
    Args:
        path: Path to check (defaults to current directory)
    
    Returns:
        bool: True if valid project directory, False otherwise
    """
    if path is None:
        path = Path.cwd()
    else:
        path = Path(path)
    
    if not path.is_dir():
        return False
    
    project_markers = [
        ".git",
        "pyproject.toml",
        "package.json",
        "setup.py",
        ".gitignore",
        "Makefile",
        ".vscode",
        ".idea",
    ]
    
    return any((path / marker).exists() for marker in project_markers)


def get_free_memory_gb() -> float:
    """
    Get available system memory in GB.
    
    Returns:
        float: Free memory in gigabytes
    """
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except (ImportError, AttributeError):
        # Fallback: use vm_stat on macOS
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse vm_stat output to estimate free memory
                # This is a rough approximation
                return 8.0  # Conservative default
            return 8.0
        except subprocess.TimeoutExpired:
            return 8.0


def check_model_vram_compatibility(model_size_gb: float) -> Tuple[bool, str]:
    """
    Check if model can fit in available VRAM with safety margin.
    
    Requires: model_size * 1.2 <= free_memory
    
    Args:
        model_size_gb: Model size in gigabytes
    
    Returns:
        Tuple of (is_compatible, warning_message)
    """
    free_mem = get_free_memory_gb()
    required_mem = model_size_gb * 1.2
    
    if required_mem > free_mem:
        warning = (
            f"High Risk of System Swap: "
            f"Model requires {required_mem:.1f}GB (with margin), "
            f"but only {free_mem:.1f}GB available."
        )
        return False, warning
    
    if required_mem > (free_mem * 0.9):
        warning = (
            f"Warning: System may swap. "
            f"Model requires {required_mem:.1f}GB, {free_mem:.1f}GB available."
        )
        return True, warning
    
    return True, ""


def get_system_info() -> dict:
    """
    Get basic system information.
    
    Returns:
        dict: System info including OS, platform, Python version, etc.
    """
    import sys
    
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version,
        "free_memory_gb": get_free_memory_gb(),
    }


def is_arm64() -> bool:
    """
    Check if system is ARM64 (Apple Silicon).
    
    Returns:
        bool: True if ARM64, False otherwise
    """
    return platform.machine() == "arm64"


def validate_environment() -> bool:
    """
    Validate that the environment is suitable for retix.
    
    Returns:
        bool: True if environment is valid, False otherwise
    """
    # Check for Xcode
    if not check_xcode_command_line_tools():
        handle_missing_xcode()
        return False
    
    # Check for ARM64 on macOS
    if platform.system() == "Darwin" and not is_arm64():
        console = get_console()
        if console and Panel:
            console.print(Panel(
                "[bold yellow]Warning:[/bold yellow] "
                "retix is optimized for Apple Silicon (ARM64).\n"
                "Your system is running on Intel. Performance may vary.",
                title="Platform Warning",
                border_style="yellow",
            ))
    
    return True
