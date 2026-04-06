"""Main CLI interface for RETIX (v1.2.1).

RETIX: The Optic Nerve for Autonomous Agents.

Commands:
- setup: Bootstrap environment (bare python to full vision)
- describe: Analyze UI/Image context
- ocr: High-speed text extraction
- check: Verify visual claims (YES/NO)
- config: Initialize .retix context in current repo
- model: List or switch vision models
- bench: Benchmark hardware performance
- daemon: Background process management
- version: Show version info
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional

try:
    import rich_click as click
except ImportError:
    import click

from retix.config import MODEL_NAME, QUANTIZATION

# Performance baselines (in seconds)
PERFORMANCE_TARGETS = {
    "describe": {"warn": 15.0, "critical": 30.0},  # Describe is most intensive
    "ocr": {"warn": 5.0, "critical": 10.0},
    "check": {"warn": 3.0, "critical": 6.0},
}

def log_performance(command_name: str, elapsed_seconds: float) -> None:
    """Log performance metrics and alert on regressions."""
    targets = PERFORMANCE_TARGETS.get(command_name, {})
    warn_threshold = targets.get("warn")
    crit_threshold = targets.get("critical")
    
    if crit_threshold and elapsed_seconds > crit_threshold:
        click.secho(
            f"⚠ PERFORMANCE ALERT [{command_name}]: {elapsed_seconds:.2f}s exceeds critical threshold ({crit_threshold}s)",
            fg="red",
            err=True
        )
    elif warn_threshold and elapsed_seconds > warn_threshold:
        click.secho(
            f"⚠ PERFORMANCE WARNING [{command_name}]: {elapsed_seconds:.2f}s exceeds warning threshold ({warn_threshold}s)",
            fg="yellow",
            err=True
        )

# Get version
__version__ = "1.2.1"



CONTEXT_SETTINGS = {
    "help_option_names": ["--help", "-h"],
    "max_content_width": 120,
}

# Configure rich-click styling
if "rich_click" in sys.modules:
    click.rich_click.COMMAND_GROUPS = {
        "retix": [
            {
                "name": "Core Commands",
                "commands": ["describe", "ocr", "check"],
            },
            {
                "name": "Project Setup",
                "commands": ["setup", "config", "model", "bench"],
            },
            {
                "name": "Daemon",
                "commands": ["daemon"],
            },
            {
                "name": "Info",
                "commands": ["version"],
            },
        ],
    }


@click.group(
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    no_args_is_help=False,
)
@click.version_option(version=__version__, prog_name="retix")
@click.pass_context
def cli(ctx):
    """RETIX - The Optic Nerve for Autonomous Agents
    
    Analyze UI screenshots, extract text, and verify visual properties.
    Your agent now has eyes.
    
    \b
    QUICK START
      retix setup              Bootstrap your environment
      retix config             Initialize project context  
      retix describe <image>   Analyze a screenshot
    
    \b
    GITHUB
      https://github.com/SNiPERxDD/retix.git
    """
    # Show help if no command was provided
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    
    # Silently ensure the project skill file exists whenever we are inside a project.
    try:
        from retix.project_config import ensure_project_skill_file
        from retix.path_utils import find_project_root
        
        project_root = find_project_root()
        if project_root:
            ensure_project_skill_file(project_root)
    except Exception:
        pass


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Run setup using hardware-based automatic defaults.",
)
def setup(non_interactive: bool):
    """
    Bootstrap your environment from bare Python.
    
    Creates virtual environment, installs dependencies, and configures shell.
    
    [yellow]Requirements:[/yellow]
      • Python 3.10+
      • Xcode Command Line Tools
      • 3+ GB free disk space
    """
    from retix.bootstrap import run_bootstrap

    if not run_bootstrap(interactive=not non_interactive):
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("image", type=str)
@click.option(
    "--prompt",
    type=str,
    default=None,
    help="Custom prompt for analysis",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Use daemon mode if available",
)
def describe(image: str, prompt: Optional[str], output_json: bool, daemon: bool):
    """
    Analyze a UI screenshot in detail.
    
    Lists visible text, buttons, form fields, and visual issues.
    
    [cyan]Examples:[/cyan]
      retix describe screenshot.png
      retix describe ~/Desktop/ui.png --prompt "Focus on buttons"
      retix describe form.png --json
    """
    _ensure_skill_created()
    
    if not prompt:
        from retix.config import DEFAULT_PROMPT
        prompt = DEFAULT_PROMPT
    
    command_start_time = time.time()
    
    try:
        # Try daemon first if requested
        if daemon:
            try:
                from retix.daemon_server import DaemonClient
                client = DaemonClient()
                response = client.send_request({
                    "command": "describe",
                    "image_path": image,
                    "prompt": prompt,
                })
                
                if response.get("success"):
                    output = response.get("output", "")
                    if output_json:
                        click.echo(json.dumps(response))
                    else:
                        click.echo(output)
                    elapsed = time.time() - command_start_time
                    log_performance("describe", elapsed)
                    return
            except Exception as exc:
                sys.stderr.write(
                    f"[WARNING] Daemon unreachable ({exc}), falling back to cold start...\n"
                )
                sys.stderr.flush()
        
        # Local inference
        from retix.inference import get_vision_engine
        engine = get_vision_engine()
        result = engine.run_inference(image, prompt)
        
        if output_json:
            output_dict = {
                "text": result.text,
                "confidence": getattr(result, "confidence", 0.5),
            }
            click.echo(json.dumps(output_dict))
        else:
            click.echo(result.text)
        
        elapsed = time.time() - command_start_time
        log_performance("describe", elapsed)
    
    except FileNotFoundError as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("image", type=str)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Use daemon mode if available",
)
def ocr(image: str, output_json: bool, daemon: bool):
    """
    Extract text from an image (OCR).
    
    Useful for reading UI labels, buttons, form fields, and other visible text.
    
    [cyan]Examples:[/cyan]
      retix ocr screenshot.png
      retix ocr form.png --json
    """
    _ensure_skill_created()
    
    command_start_time = time.time()
    
    try:
        if daemon:
            try:
                from retix.daemon_server import DaemonClient
                client = DaemonClient()
                response = client.send_request({
                    "command": "ocr",
                    "image_path": image,
                })
                
                if response.get("success"):
                    if output_json:
                        click.echo(json.dumps(response))
                    else:
                        click.echo(response.get("output", ""))
                    elapsed = time.time() - command_start_time
                    log_performance("ocr", elapsed)
                    return
            except Exception as exc:
                sys.stderr.write(
                    f"[WARNING] Daemon unreachable ({exc}), falling back to cold start...\n"
                )
                sys.stderr.flush()
        
        from retix.inference import get_vision_engine
        engine = get_vision_engine()
        result = engine.run_ocr(image)
        
        if output_json:
            output_dict = {
                "text": result.text,
                "confidence": getattr(result, "confidence", 1.0),
            }
            click.echo(json.dumps(output_dict))
        else:
            click.echo(result.text)
        
        elapsed = time.time() - command_start_time
        log_performance("ocr", elapsed)
    
    except FileNotFoundError as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("image", type=str)
@click.argument("claim", type=str)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Use daemon mode if available",
)
def check(image: str, claim: str, output_json: bool, daemon: bool):
    """
    Verify if a claim is true about an image.
    
    Returns YES/NO with confidence score.
    
    [cyan]Examples:[/cyan]
      retix check screenshot.png "the button is red"
      retix check form.png "Submit button visible" --json
    """
    _ensure_skill_created()
    
    command_start_time = time.time()
    
    try:
        if daemon:
            try:
                from retix.daemon_server import DaemonClient
                client = DaemonClient()
                response = client.send_request({
                    "command": "verify",
                    "image_path": image,
                    "claim": claim,
                })
                
                if response.get("success"):
                    if output_json:
                        click.echo(json.dumps(response))
                    else:
                        verified = response.get("verified")
                        result_text = "YES" if verified else "NO"
                        click.echo(f"{result_text}")
                    elapsed = time.time() - command_start_time
                    log_performance("check", elapsed)
                    return
            except Exception as exc:
                sys.stderr.write(
                    f"[WARNING] Daemon unreachable ({exc}), falling back to cold start...\n"
                )
                sys.stderr.flush()
        
        from retix.inference import get_vision_engine
        engine = get_vision_engine()
        verified, confidence = engine.verify_claim(image, claim)
        
        if output_json:
            output_dict = {
                "verified": verified,
                "confidence": confidence,
                "claim": claim,
            }
            click.echo(json.dumps(output_dict))
        else:
            result_text = "YES" if verified else "NO"
            click.echo(f"{result_text} (confidence: {confidence:.2f})")
        
        elapsed = time.time() - command_start_time
        log_performance("check", elapsed)
    
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
def config():
    """
    Initialize .retix project context.
    
    Creates .retix/ folder with:
      • config.yaml - Project settings
      • SKILL.md - Agent integration file
    
    Updates .gitignore for .retix/ and core project hygiene entries
    """
    from retix.project_config import initialize_project_context
    
    if not initialize_project_context():
        sys.exit(1)


@cli.group(context_settings=CONTEXT_SETTINGS)
def model():
    """Manage vision models."""
    pass


@model.command("list")
def model_list():
    """Show available vision models."""
    from retix.model_management import display_model_list
    
    display_model_list()


@model.command("info")
@click.argument("model_id", required=False, default=None)
def model_info(model_id: Optional[str]):
    """Show detailed model information."""
    from retix.model_management import display_model_details, display_current_model
    
    if model_id:
        display_model_details(model_id)
    else:
        display_current_model()


@model.command("switch")
@click.argument("model_id", type=str)
def model_switch(model_id: str):
    """Switch to a different vision model."""
    from retix.model_management import switch_model
    
    if not switch_model(model_id):
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
def bench():
    """
    Benchmark hardware performance.
    
    Measures model load time, inference speed, and gives recommendations.
    
    [yellow]Note:[/yellow] This may download the model (~2GB) if not cached.
    """
    from retix.benchmarking import run_benchmark, display_benchmark_results
    from retix.safety_checks import validate_environment
    
    if not validate_environment():
        sys.exit(1)
    
    results = run_benchmark(warmup=True)
    display_benchmark_results(results)


@cli.group(context_settings=CONTEXT_SETTINGS)
def daemon():
    """Manage background daemon for faster inference."""
    pass


@daemon.command("start")
def daemon_start():
    """Start the background daemon."""
    try:
        from retix.daemon_server import start_daemon_background
        click.echo("Starting daemon...", err=True)
        start_daemon_background()
        click.echo("Daemon started.", err=True)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@daemon.command("stop")
def daemon_stop():
    """Stop the background daemon."""
    try:
        from retix.daemon_server import stop_daemon
        click.echo("Stopping daemon...", err=True)
        stop_daemon()
        click.echo("Daemon stopped.", err=True)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@daemon.command("status")
def daemon_status():
    """Check daemon status."""
    try:
        from retix.daemon_server import get_daemon_status
        status_info = get_daemon_status()
        
        if status_info.get("status") == "running":
            click.secho("Daemon is running", fg="green", err=True)
        else:
            click.secho("Daemon is not running", fg="yellow", err=True)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
def version():
    """Show version and system information."""
    active_model = MODEL_NAME
    try:
        from retix.project_config import load_config
        active_model = load_config().get("model", MODEL_NAME)
    except Exception:
        pass

    click.echo(f"retix version {__version__}")
    click.echo(f"Model: {active_model}")
    click.echo(f"Quantization: {QUANTIZATION}")
    click.echo(f"Cache: ~/.cache/retix/")
    
    try:
        from retix.safety_checks import get_system_info
        info = get_system_info()
        click.echo(f"Python: {info['python_version'].split()[0]}")
        click.echo(f"Platform: {info['os']} ({info['machine']})")
        click.echo(f"Free Memory: {info['free_memory_gb']:.1f}GB")
    except Exception:
        pass


def _ensure_skill_created() -> None:
    """Ensure skill file is created in the project."""
    try:
        from retix.project_config import ensure_project_skill_file
        from retix.path_utils import find_project_root
        
        project_root = find_project_root()
        if project_root:
            ensure_project_skill_file(project_root)
    except Exception:
        pass  # Silently ignore


# Main entry point
if __name__ == "__main__":
    cli()
