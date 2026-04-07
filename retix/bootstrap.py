"""Bootstrap module for RETIX setup command.

This module provides a production-grade setup workflow:
- Hardware-aware model tier selection (2B, 8B, MoE profile)
- Optional custom Hugging Face model repository
- Virtual environment bootstrap in ~/.cache/retix/venv
- Global editable install for CLI availability
"""

import os
import re
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error as url_error
from urllib import request as url_request

try:
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    Console = None
    Panel = None


REPO_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

BOOTSTRAP_DEPENDENCIES = [
    "click>=8.1.7",
    "rich-click>=1.7.0",
    "rich>=13.7.0",
    "pillow>=10.1.0",
    "numpy>=1.24.0",
    "mlx>=0.25.0",
    "mlx-vlm>=0.4.4",
    "torch>=2.0.0",
    "torchvision>=0.15.0",
    "pydantic>=2.5.0",
    "pyyaml>=6.0",
    "psutil>=5.9.6",
    "numexpr>=2.10.2",
    "bottleneck>=1.4.2",
]


def get_console() -> Optional["Console"]:
    """Return a rich console instance when available."""
    if Console:
        return Console(force_terminal=True)
    return None


def get_cache_dir() -> Path:
    """Get or create the RETIX cache directory."""
    cache_dir = Path.home() / ".cache" / "retix"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_venv_path() -> Path:
    """Return the path to the RETIX virtual environment."""
    return get_cache_dir() / "venv"


def get_venv_python() -> Path:
    """Return the Python executable path for the RETIX venv."""
    return get_venv_path() / "bin" / "python"


def get_uv_executable() -> Optional[str]:
    """Return the uv executable path when available."""
    return shutil.which("uv")


def get_retix_bin() -> Path:
    """Return the retix executable path for the RETIX venv."""
    return get_venv_path() / "bin" / "retix"


def ensure_cli_launcher(project_root: Path) -> bool:
    """Create a venv-local retix launcher that points at the repository source tree."""
    launcher_path = get_retix_bin()

    try:
        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        launcher_path.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            f"PROJECT_ROOT = Path(r\"{project_root}\").resolve()\n"
            "if str(PROJECT_ROOT) not in sys.path:\n"
            "    sys.path.insert(0, str(PROJECT_ROOT))\n\n"
            "from retix.main import cli\n\n"
            "if __name__ == '__main__':\n"
            "    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n"
            "    sys.exit(cli())\n"
        )
        launcher_path.chmod(0o755)
        return True
    except Exception:
        return False


def create_virtual_environment() -> bool:
    """Create the RETIX virtual environment in cache."""
    venv_path = get_venv_path()
    console = get_console()

    if venv_path.exists():
        if console:
            console.print(f"[green]OK[/green] virtual environment exists at {venv_path}")
        return True

    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            if console:
                console.print("[red]FAILED[/red] virtual environment creation")
                if result.stderr:
                    console.print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        if console:
            console.print("[red]FAILED[/red] virtual environment creation timed out")
        return False

    if console:
        console.print(f"[green]OK[/green] created virtual environment at {venv_path}")
    return True


def install_dependencies() -> bool:
    """Install setup dependencies into the RETIX venv using uv when available."""
    console = get_console()

    uv_executable = get_uv_executable()
    if uv_executable:
        command = [uv_executable, "pip", "install", "--python", str(get_venv_python())]
        command.extend(BOOTSTRAP_DEPENDENCIES)
    else:
        pip_path = get_venv_path() / "bin" / "pip"
        if not pip_path.exists():
            if console:
                console.print("[red]FAILED[/red] pip not found in virtual environment")
            return False
        command = [str(pip_path), "install"]
        command.extend(BOOTSTRAP_DEPENDENCIES)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            if console:
                console.print("[red]FAILED[/red] dependency install")
                if result.stderr:
                    console.print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        if console:
            console.print("[red]FAILED[/red] dependency install timed out")
        return False

    if console:
        if uv_executable:
            console.print("[green]OK[/green] dependencies installed in RETIX venv with uv")
        else:
            console.print("[green]OK[/green] dependencies installed in RETIX venv with pip")
    return True


def setup_model_cache() -> bool:
    """Create cache folders required by model downloads."""
    model_cache_dir = get_cache_dir() / "models"
    try:
        model_cache_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def detect_repo_root() -> Optional[Path]:
    """Detect repository root for editable package installation."""
    current = Path.cwd().resolve()
    for _ in range(12):
        if (current / "pyproject.toml").exists() and (current / "retix").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def install_editable_package(project_root: Path) -> bool:
    """Install RETIX in editable mode for global command availability."""
    console = get_console()

    uv_executable = get_uv_executable()
    try:
        if uv_executable:
            command = [uv_executable, "pip", "install", "--python", str(get_venv_python()), "-e", str(project_root)]
        else:
            command = [sys.executable, "-m", "pip", "install", "-e", str(project_root)]

        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            if console:
                console.print("[red]FAILED[/red] editable install")
                if result.stderr:
                    console.print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        if console:
            console.print("[red]FAILED[/red] editable install timed out")
        return False

    if not ensure_cli_launcher(project_root):
        if console:
            console.print("[red]FAILED[/red] could not create RETIX launcher")
        return False

    if console:
        if uv_executable:
            console.print("[green]OK[/green] editable install complete with uv")
        else:
            console.print("[green]OK[/green] editable install complete with pip")
    return True


def parse_hf_repo_identifier(value: str) -> Optional[str]:
    """Parse a Hugging Face URL or repo id into owner/repo format."""
    cleaned = value.strip()
    if not cleaned:
        return None

    if "huggingface.co/" in cleaned:
        marker = cleaned.split("huggingface.co/", maxsplit=1)[1]
        normalized = marker.strip("/").split("/")
        if len(normalized) >= 2:
            return f"{normalized[0]}/{normalized[1]}"
        return None

    return cleaned


def is_valid_hf_repo(repo_id: str) -> bool:
    """Validate Hugging Face repository id format."""
    return bool(REPO_ID_PATTERN.match(repo_id))


def check_hf_repo_access(repo_id: str) -> bool:
    """Check whether a Hugging Face repository endpoint is reachable."""
    url = f"https://huggingface.co/{repo_id}"
    try:
        request_obj = url_request.Request(url, method="HEAD")
        with url_request.urlopen(request_obj, timeout=4):
            return True
    except (url_error.URLError, TimeoutError, ValueError):
        return False


def add_to_shell_profile(interactive: bool) -> bool:
    """Offer to add RETIX venv bin path to the active shell profile."""
    console = get_console()
    shell = os.environ.get("SHELL", "")
    bin_path = get_venv_path() / "bin"

    if "zsh" in shell:
        profile_path = Path.home() / ".zshrc"
    elif "bash" in shell:
        profile_path = Path.home() / ".bash_profile"
    else:
        return True

    export_line = f'export PATH="{bin_path}:$PATH"  # Added by retix\n'

    try:
        existing = profile_path.read_text() if profile_path.exists() else ""
    except Exception:
        existing = ""

    if str(bin_path) in existing:
        return True

    if interactive and sys.stdin.isatty():
        if console:
            console.print(f"Add {bin_path} to PATH in {profile_path.name}? [y/N]")
        user_input = input().strip().lower()
        if user_input not in {"y", "yes"}:
            return True

    try:
        with open(profile_path, "a") as file_handle:
            if existing and not existing.endswith("\n"):
                file_handle.write("\n")
            file_handle.write(export_line)
    except Exception:
        return False

    return True


def select_model_configuration(interactive: bool = True) -> Dict[str, Any]:
    """Select a model configuration with hardware checks and warnings."""
    from retix.model_management import VISION_MODELS, recommend_model_tier
    from retix.safety_checks import check_model_vram_compatibility, get_free_memory_gb

    console = get_console()
    free_memory_gb = get_free_memory_gb()
    auto_tier = recommend_model_tier(free_memory_gb)

    selected_tier = auto_tier
    selected_repo = VISION_MODELS[auto_tier]["repo"]
    selected_size = VISION_MODELS[auto_tier]["vram_gb"]
    selection_mode = "auto"

    if interactive and sys.stdin.isatty():
        if console:
            console.print("Model selection (2B / 8B / MoE profile)")
            console.print(f"Detected free memory: {free_memory_gb:.1f} GB")
            console.print(f"Auto recommendation: {auto_tier}")
            console.print("1) auto")
            console.print("2) 2b")
            console.print("3) 8b")
            console.print("4) moe")
            console.print("5) custom Hugging Face repo")
            console.print("Select option [1-5]:")

        selection = input().strip() if sys.stdin.isatty() else "1"

        if selection == "2":
            selected_tier = "2b"
            selection_mode = "manual"
        elif selection == "3":
            selected_tier = "8b"
            selection_mode = "manual"
        elif selection == "4":
            selected_tier = "moe"
            selection_mode = "manual"
        elif selection == "5":
            selection_mode = "custom"
            if console:
                console.print("Enter Hugging Face model URL or owner/repo:")
            user_repo = input().strip()
            parsed_repo = parse_hf_repo_identifier(user_repo)

            if not parsed_repo or not is_valid_hf_repo(parsed_repo):
                raise ValueError("Invalid Hugging Face repository format. Expected owner/repo.")

            reachable = check_hf_repo_access(parsed_repo)
            if console and not reachable:
                console.print("[yellow]Warning[/yellow] repository endpoint was not reachable. Continuing by user request.")

            if console:
                console.print("Enter approximate model VRAM requirement in GB [default: 4.0]:")
            size_value = input().strip()
            selected_size = float(size_value) if size_value else 4.0
            selected_repo = parsed_repo
            selected_tier = "custom"
        else:
            selected_tier = auto_tier
            selection_mode = "auto"

    if selected_tier in VISION_MODELS:
        selected_repo = VISION_MODELS[selected_tier]["repo"]
        selected_size = VISION_MODELS[selected_tier]["vram_gb"]

    compatible, warning = check_model_vram_compatibility(selected_size)

    return {
        "model": selected_repo,
        "model_tier": selected_tier,
        "model_size_gb": selected_size,
        "quantization": "4bit",
        "selection_mode": selection_mode,
        "free_memory_gb": free_memory_gb,
        "compatible": compatible,
        "compatibility_warning": warning,
    }


def persist_global_model_selection(model_config: Dict[str, Any]) -> bool:
    """Persist model selection into global RETIX config."""
    from retix.project_config import load_global_config, save_global_config

    existing_config = load_global_config()
    existing_config.update(
        {
            "model": model_config["model"],
            "quantization": model_config.get("quantization", "4bit"),
            "model_tier": model_config.get("model_tier", "2b"),
            "model_size_gb": model_config.get("model_size_gb", 2.0),
            "selection_mode": model_config.get("selection_mode", "auto"),
        }
    )
    return save_global_config(existing_config)


def run_bootstrap(interactive: bool = True) -> bool:
    """Run complete RETIX bootstrap workflow."""
    from retix.safety_checks import validate_environment

    console = get_console()
    if console and Panel:
        console.print(
            Panel(
                "RETIX setup started",
                title="Setup",
                border_style="blue",
            )
        )

    if not validate_environment():
        return False

    if not create_virtual_environment():
        return False

    if not install_dependencies():
        return False

    if not setup_model_cache():
        if console:
            console.print("[red]FAILED[/red] model cache setup")
        return False

    try:
        model_config = select_model_configuration(interactive=interactive)
    except ValueError as exc:
        if console:
            console.print(f"[red]FAILED[/red] {exc}")
        return False

    if model_config.get("compatibility_warning") and console:
        console.print(f"[yellow]Warning[/yellow] {model_config['compatibility_warning']}")

    if not persist_global_model_selection(model_config):
        if console:
            console.print("[red]FAILED[/red] could not persist global model config")
        return False

    repo_root = detect_repo_root()
    if repo_root:
        if not install_editable_package(repo_root):
            return False

    if not add_to_shell_profile(interactive=interactive):
        if console:
            console.print("[yellow]Warning[/yellow] shell profile update skipped")

    if console and Panel:
        panel_body = (
            f"Setup complete\n\n"
            f"Model: {model_config['model']}\n"
            f"Tier: {model_config['model_tier']}\n"
            f"Global config: ~/.retix/config.yaml\n"
            f"Next: retix config"
        )
        console.print(Panel(panel_body, title="Success", border_style="green"))

    return True
