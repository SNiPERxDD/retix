"""
Performance benchmarking for retix.

Measures:
- Model load time
- Time to first token (TTFT)
- Tokens per second (TPS)
- Overall latency
"""

import time
from pathlib import Path
from typing import Dict, Optional

from PIL import Image

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress
except ImportError:
    Console = None


def get_console():
    """Get rich console if available."""
    if Console:
        return Console(force_terminal=True)
    return None


def create_test_image() -> Image.Image:
    """
    Create a simple test image for benchmarking.
    
    Returns:
        PIL Image object
    """
    # Create a simple UI-like test image
    img = Image.new("RGB", (400, 300), color="white")
    
    # This creates a simple login form layout
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((150, 20), "Test Form", fill="black")
    
    # Form fields
    draw.rectangle((50, 80, 350, 100), outline="black")
    draw.text((60, 83), "Email input", fill="gray")
    
    draw.rectangle((50, 130, 350, 150), outline="black")
    draw.text((60, 133), "Password input", fill="gray")
    
    # Button
    draw.rectangle((120, 200, 280, 235), fill="blue")
    draw.text((150, 210), "Submit", fill="white")
    
    return img


def get_test_image_path() -> Path:
    """
    Get or create test image for benchmarking.
    
    Returns:
        Path to test image
    """
    cache_dir = Path.home() / ".cache" / "retix"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    test_image_path = cache_dir / "bench_test_image.png"
    
    if not test_image_path.exists():
        img = create_test_image()
        img.save(test_image_path)
    
    return test_image_path


def run_benchmark(warmup: bool = True) -> Dict[str, float]:
    """
    Run performance benchmark on current model.
    
    Args:
        warmup: Whether to run a warmup iteration first
    
    Returns:
        Dictionary with benchmark metrics:
        - model_load_time: Time to load model (seconds)
        - first_token_time: Time to first token (seconds)
        - tokens_per_second: Generation speed
        - total_inference_time: Total time for inference
        - input_tokens: Number of input tokens
        - output_tokens: Number of output tokens
    """
    from retix.inference import get_vision_engine
    
    console = get_console()
    test_image_path = get_test_image_path()
    
    if console:
        console.print("[cyan]→[/cyan] Preparing benchmark...")
    
    results = {}
    
    try:
        if console:
            console.print("[cyan]→[/cyan] Loading model...")
        
        # Measure model loading time
        start_load = time.time()
        engine = get_vision_engine()
        load_time = time.time() - start_load
        results["model_load_time"] = load_time
        
        if console:
            console.print(f"[green]✓[/green] Model loaded in {load_time:.2f}s")
        
        # Warmup run (optional)
        if warmup:
            if console:
                console.print("[cyan]→[/cyan] Running warmup...")
            
            engine.run_inference(
                str(test_image_path),
                "What do you see in this image? Describe the UI briefly.",
            )
        
        # Actual benchmark
        if console:
            console.print("[cyan]→[/cyan] Running benchmark inference...")
        
        start_inference = time.time()
        output = engine.run_inference(
            str(test_image_path),
            "Describe this UI form. What elements do you see?",
        )
        total_inference_time = time.time() - start_inference
        
        results["total_inference_time"] = total_inference_time
        
        # Extract token counts if available
        if hasattr(output, "generation_tokens"):
            results["output_tokens"] = output.generation_tokens
            results["input_tokens"] = output.prompt_tokens
        else:
            results["output_tokens"] = len(output.text.split()) if hasattr(output, "text") else 0
            results["input_tokens"] = 0
        
        # Calculate tokens per second
        if results["output_tokens"] > 0 and total_inference_time > 0:
            tps = results["output_tokens"] / total_inference_time
            results["tokens_per_second"] = tps
        else:
            results["tokens_per_second"] = 0
        
        # Estimate TTFT (rough approximation)
        if results["output_tokens"] > 0:
            results["first_token_time"] = total_inference_time / (results["output_tokens"] + 1)
        else:
            results["first_token_time"] = 0
        
        return results
    
    except Exception as e:
        if console:
            console.print(f"[red]✗[/red] Benchmark failed: {e}")
        
        # Return default/failed results
        return {
            "model_load_time": 0,
            "first_token_time": 0,
            "tokens_per_second": 0,
            "total_inference_time": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e),
        }


def display_benchmark_results(results: Dict[str, float]):
    """
    Display benchmark results in formatted output.
    
    Args:
        results: Benchmark results dictionary
    """
    console = get_console()
    
    if "error" in results:
        if console:
            console.print(f"[red]Benchmark failed:[/red] {results['error']}")
        return
    
    if console and Table:
        table = Table(title="Benchmark Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        
        table.add_row(
            "Model Load Time",
            f"{results['model_load_time']:.2f}s",
        )
        table.add_row(
            "Time to First Token",
            f"{results['first_token_time']:.2f}s",
        )
        table.add_row(
            "Tokens Per Second",
            f"{results['tokens_per_second']:.1f}",
        )
        table.add_row(
            "Total Inference Time",
            f"{results['total_inference_time']:.2f}s",
        )
        table.add_row(
            "Output Tokens",
            str(results['output_tokens']),
        )
        
        console.print(table)
        
        # Recommendations
        console.print()
        recommendations = []
        
        if results["tokens_per_second"] < 10:
            recommendations.append(
                "[yellow]→ Consider using a smaller model with[/yellow] "
                "[cyan]retix model switch 2b[/cyan]"
            )
        
        if results["model_load_time"] > 5:
            recommendations.append(
                "[yellow]→ Model load is slow. Recommend using daemon mode:[/yellow] "
                "[cyan]retix daemon start[/cyan]"
            )
        
        if recommendations:
            console.print("\n[cyan]Recommendations:[/cyan]")
            for rec in recommendations:
                console.print(f"  {rec}")
    else:
        print(f"Model Load Time: {results['model_load_time']:.2f}s")
        print(f"Time to First Token: {results['first_token_time']:.2f}s")
        print(f"Tokens Per Second: {results['tokens_per_second']:.1f}")
        print(f"Total Inference Time: {results['total_inference_time']:.2f}s")
        print(f"Output Tokens: {results['output_tokens']}")


def suggest_configuration(results: Dict[str, float]) -> str:
    """
    Suggest optimal configuration based on benchmark results.
    
    Args:
        results: Benchmark results dictionary
    
    Returns:
        Configuration suggestion string
    """
    if results["tokens_per_second"] < 5:
        return "Use a smaller model tier with: retix model switch 2b"
    elif results["tokens_per_second"] < 20:
        return "Standard performance. Daemon mode recommended for repeated calls."
    else:
        return "Excellent performance. System is well-optimized."
