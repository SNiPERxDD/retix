"""
Vision model management for retix.

Manages:
- Model listing and discovery
- Model switching and validation
- Model information (VRAM, quantization)
- Model downloads and caching
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
except ImportError:
    Console = None


def get_console():
    """Get rich console if available."""
    if Console:
        return Console(force_terminal=True)
    return None


# Available vision models grouped by PRD v1.2 tiers.
VISION_MODELS = {
    "2b": {
        "name": "Qwen3-VL-2B-Instruct-4bit",
        "repo": "mlx-community/Qwen3-VL-2B-Instruct-4bit",
        "vram_gb": 2.0,
        "quantization": "4bit",
        "tokens_per_second": 50,
        "description": "Compact tier for laptops and low-memory runs",
        "recommended_for": "Fast local iterations",
    },
    "8b": {
        "name": "Qwen3-VL-7B-Instruct-4bit (8B-class)",
        "repo": "mlx-community/Qwen3-VL-7B-Instruct-4bit",
        "vram_gb": 4.5,
        "quantization": "4bit",
        "tokens_per_second": 30,
        "description": "Higher-capacity model for stronger reasoning",
        "recommended_for": "Balanced quality and speed",
    },
    "moe": {
        "name": "Moondream-2-4bit (MoE-friendly profile)",
        "repo": "mlx-community/Moondream-2-4bit",
        "vram_gb": 1.5,
        "quantization": "4bit",
        "tokens_per_second": 60,
        "description": "Lightweight profile for limited RAM systems",
        "recommended_for": "Lowest memory footprint",
    },
}


MODEL_ALIASES = {
    "qwen3-vl-2b": "2b",
    "qwen3-vl-7b": "8b",
    "llama-vision-7b": "8b",
    "moondream": "moe",
}


def normalize_model_id(model_id: str) -> str:
    """Normalize model identifiers and support legacy aliases."""
    lowered = model_id.lower().strip()
    return MODEL_ALIASES.get(lowered, lowered)


def list_available_models() -> Dict[str, Dict]:
    """
    Get list of all available vision models.
    
    Returns:
        Dictionary of model ID -> model info
    """
    return VISION_MODELS.copy()


def get_model_info(model_id: str) -> Optional[Dict]:
    """
    Get information about a specific model.
    
    Args:
        model_id: Model identifier (short name)
    
    Returns:
        Model info dict or None if not found
    """
    return VISION_MODELS.get(normalize_model_id(model_id))


def display_model_list():
    """Display available models in formatted table."""
    console = get_console()
    
    if console and Table:
        table = Table(title="Available Vision Models")
        table.add_column("Tier", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("VRAM", justify="right")
        table.add_column("Quantization", style="yellow")
        table.add_column("TPS", justify="right", style="magenta")
        
        for model_id, info in VISION_MODELS.items():
            table.add_row(
                model_id,
                info["name"],
                f"{info['vram_gb']:.1f}GB",
                info["quantization"],
                str(info["tokens_per_second"]),
            )
        
        console.print(table)
        
        console.print("\n[dim]TPS = Tokens Per Second (approximate)[/dim]")
        console.print("[dim]Select models with: retix model switch <tier>[/dim]")
    else:
        for model_id, info in VISION_MODELS.items():
            print(f"{model_id:20} {info['name']:40} {info['vram_gb']:.1f}GB")


def display_model_details(model_id: str):
    """Display detailed information about a model."""
    console = get_console()
    info = get_model_info(model_id)
    
    if not info:
        if console:
            console.print(f"[red]Model not found:[/red] {model_id}")
        else:
            print(f"Model not found: {model_id}")
        return
    
    if console and Panel:
        details = (
            f"[bold]{info['name']}[/bold]\n\n"
            f"[cyan]Repository:[/cyan] {info['repo']}\n"
            f"[cyan]VRAM Required:[/cyan] {info['vram_gb']:.1f}GB\n"
            f"[cyan]Quantization:[/cyan] {info['quantization']}\n"
            f"[cyan]Performance:[/cyan] ~{info['tokens_per_second']} tokens/sec\n\n"
            f"[yellow]{info['description']}[/yellow]\n\n"
            f"[green]Recommended for:[/green] {info['recommended_for']}"
        )
        
        console.print(Panel(
            details,
            title="Model Details",
            expand=False,
            border_style="blue",
        ))
    else:
        print(f"Model: {info['name']}")
        print(f"Repository: {info['repo']}")
        print(f"VRAM: {info['vram_gb']:.1f}GB")
        print(f"Quantization: {info['quantization']}")


def can_run_model(model_id: str) -> Tuple[bool, str]:
    """
    Check if model can run on current system.
    
    Args:
        model_id: Model identifier
    
    Returns:
        Tuple of (can_run, reason_or_empty_string)
    """
    from retix.safety_checks import check_model_vram_compatibility
    
    info = get_model_info(model_id)
    if not info:
        return False, f"Unknown model: {model_id}"
    
    is_compatible, warning = check_model_vram_compatibility(info["vram_gb"])
    if not is_compatible:
        return False, warning
    
    if warning:
        return True, warning
    
    return True, ""


def switch_model(model_id: str, project_root: Optional[Path] = None) -> bool:
    """
    Switch to a different vision model.
    
    Args:
        model_id: Model identifier to switch to
        project_root: Project root path (auto-detected if None)
    
    Returns:
        bool: True if successful, False otherwise
    """
    from retix.project_config import load_config, save_config
    from retix.safety_checks import check_model_vram_compatibility
    
    console = get_console()
    
    model_id = normalize_model_id(model_id)
    info = get_model_info(model_id)
    if not info:
        if console:
            console.print(f"[red]Unknown model:[/red] {model_id}")
        return False
    
    # Check VRAM
    can_run, warning = can_run_model(model_id)
    if warning and console:
        console.print(f"[yellow]⚠[/yellow] {warning}")
    
    if not can_run:
        if console:
            console.print(f"[red]✗[/red] Model cannot run on this system")
        return False
    
    # Update config
    config = load_config(project_root)
    config["model"] = info["repo"]
    config["quantization"] = info["quantization"]
    
    if not save_config(config, project_root):
        if console:
            console.print("[red]✗[/red] Failed to save configuration")
        return False
    
    if console and Panel:
        console.print(Panel(
            f"[green]✓[/green] Switched to {info['name']}\n\n"
            f"VRAM: {info['vram_gb']:.1f}GB | "
            f"Performance: ~{info['tokens_per_second']} tokens/sec",
            title="Model Switched",
            border_style="green",
        ))
    
    return True


def get_current_model_info(project_root: Optional[Path] = None) -> Dict:
    """Get information about currently selected model."""
    from retix.project_config import load_config
    
    config = load_config(project_root)
    repo = config.get("model", "mlx-community/Qwen3-VL-2B-Instruct-4bit")
    
    # Match to our models
    for model_id, info in VISION_MODELS.items():
        if info["repo"] == repo:
            return info
    
    # Return generic info
    return {
        "name": repo.split("/")[-1],
        "repo": repo,
        "vram_gb": 2.0,
        "quantization": config.get("quantization", "4bit"),
        "tokens_per_second": 50,
        "description": "Custom model",
    }


def recommend_model_tier(free_memory_gb: float) -> str:
    """Recommend a model tier based on currently free memory."""
    if free_memory_gb >= 16.0:
        return "moe"
    if free_memory_gb >= 12.0:
        return "8b"
    return "2b"


def display_current_model(project_root: Optional[Path] = None):
    """Display information about currently loaded model."""
    from retix.safety_checks import get_free_memory_gb
    
    console = get_console()
    info = get_current_model_info(project_root)
    free_mem = get_free_memory_gb()
    
    if console and Panel:
        status = "Ready" if free_mem > info["vram_gb"] * 1.2 else "May swap"
        
        details = (
            f"[cyan]Model:[/cyan] {info['name']}\n"
            f"[cyan]VRAM Required:[/cyan] {info['vram_gb']:.1f}GB\n"
            f"[cyan]Free Memory:[/cyan] {free_mem:.1f}GB\n"
            f"[cyan]Status:[/cyan] [{'green' if status == 'Ready' else 'yellow'}]{status}[/]\n\n"
            f"[dim]Performance: ~{info.get('tokens_per_second', 50)} tokens/sec[/dim]"
        )
        
        console.print(Panel(
            details,
            title="Current Model",
            expand=False,
            border_style="blue",
        ))
    else:
        print(f"Model: {info['name']}")
        print(f"VRAM: {info['vram_gb']:.1f}GB")
        print(f"Performance: ~{info.get('tokens_per_second', 50)} tokens/sec")
