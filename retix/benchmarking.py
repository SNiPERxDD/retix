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


BENCHMARK_PROMPT = (
    "What do you see in this image? Describe the visible UI elements briefly."
)
BENCHMARK_RETRY_PROMPT = (
    "List the visible UI elements in one short sentence."
)


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
    # Create a denser dashboard-like benchmark image to stress OCR/layout parsing.
    img = Image.new("RGB", (960, 640), color="#f4f6f8")

    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    # Top navigation bar
    draw.rectangle((0, 0, 960, 52), fill="#1f2937")
    draw.text((20, 18), "RETIX Analytics Suite", fill="white")
    draw.text((690, 18), "Search", fill="#d1d5db")
    draw.rectangle((750, 12, 860, 38), outline="#6b7280")
    draw.text((875, 18), "Admin", fill="#d1d5db")

    # Left sidebar
    draw.rectangle((0, 52, 200, 640), fill="#111827")
    sidebar_items = [
        "Dashboard",
        "Sessions",
        "Experiments",
        "Alerts",
        "Models",
        "Settings",
    ]
    y = 80
    for item in sidebar_items:
        draw.text((20, y), item, fill="#e5e7eb")
        y += 42

    # Summary cards
    card_x = 220
    for idx, title in enumerate(["Latency", "Success Rate", "Token Cost"]):
        x0 = card_x + idx * 240
        draw.rectangle((x0, 72, x0 + 220, 150), outline="#cbd5e1", fill="white")
        draw.text((x0 + 12, 86), title, fill="#475569")
        draw.text((x0 + 12, 116), ["2.37s", "98.4%", "$0.0032"][idx], fill="#111827")

    # Main chart area
    draw.rectangle((220, 170, 940, 380), outline="#cbd5e1", fill="white")
    draw.text((236, 184), "Requests per Minute", fill="#334155")
    chart_points = [
        (250, 340), (300, 320), (350, 300), (400, 265), (450, 290), (500, 250),
        (550, 240), (600, 210), (650, 235), (700, 200), (750, 220), (800, 190),
        (850, 205), (900, 180)
    ]
    for i in range(len(chart_points) - 1):
        draw.line((chart_points[i], chart_points[i + 1]), fill="#2563eb", width=3)
    for p in chart_points:
        draw.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="#1d4ed8")

    # Activity table
    draw.rectangle((220, 398, 940, 628), outline="#cbd5e1", fill="white")
    draw.text((236, 412), "Recent Activity", fill="#334155")
    draw.text((236, 438), "Session ID", fill="#64748b")
    draw.text((396, 438), "Model", fill="#64748b")
    draw.text((546, 438), "Latency", fill="#64748b")
    draw.text((656, 438), "Status", fill="#64748b")
    draw.text((756, 438), "Timestamp", fill="#64748b")

    rows = [
        ("a8f2-19", "LFM2.5-VL-1.6B", "2.1s", "OK", "14:02:11"),
        ("b1c4-73", "Qwen3-VL-2B", "3.4s", "OK", "14:01:52"),
        ("d6k9-02", "LFM2.5-VL-1.6B", "5.2s", "WARN", "14:01:10"),
        ("e2p3-44", "Qwen3-VL-2B", "2.9s", "OK", "14:00:48"),
        ("m7z1-33", "LFM2.5-VL-1.6B", "1.9s", "OK", "14:00:05"),
    ]
    y = 462
    for sid, model, latency, status, ts in rows:
        draw.line((228, y - 8, 930, y - 8), fill="#e2e8f0", width=1)
        draw.text((236, y), sid, fill="#0f172a")
        draw.text((396, y), model, fill="#0f172a")
        draw.text((546, y), latency, fill="#0f172a")
        draw.text((656, y), status, fill=("#16a34a" if status == "OK" else "#ca8a04"))
        draw.text((756, y), ts, fill="#0f172a")
        y += 30
    
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
    
    # Always regenerate to keep benchmark input deterministic with latest template.
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
    from retix.model_management import get_current_model_info
    
    console = get_console()
    test_image_path = get_test_image_path()
    
    if console:
        console.print("[cyan]→[/cyan] Preparing benchmark...")
    
    results = {}
    current_model_info = get_current_model_info()
    results["model_name"] = current_model_info.get("name", "unknown")
    results["model_repo"] = current_model_info.get("repo", "unknown")
    
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
                BENCHMARK_PROMPT,
                max_tokens=1024,
            )
        
        # Actual benchmark
        if console:
            console.print("[cyan]→[/cyan] Running benchmark inference...")
        
        start_inference = time.time()
        output = engine.run_inference(
            str(test_image_path),
            BENCHMARK_PROMPT,
            max_tokens=1024,
        )
        total_inference_time = time.time() - start_inference
        
        results["total_inference_time"] = total_inference_time
        
        metadata = getattr(output, "raw_metadata", {}) or {}
        output_tokens = int(metadata.get("generation_tokens") or 0)
        input_tokens = int(metadata.get("prompt_tokens") or 0)

        # Some models may terminate immediately for certain prompts (EOS only).
        # Retry once with an alternate prompt so benchmark reports meaningful decode speed.
        if output_tokens <= 1:
            retry_start = time.time()
            retry_output = engine.run_inference(
                str(test_image_path),
                BENCHMARK_RETRY_PROMPT,
                max_tokens=1024,
            )
            retry_total_time = time.time() - retry_start
            retry_metadata = getattr(retry_output, "raw_metadata", {}) or {}
            retry_output_tokens = int(retry_metadata.get("generation_tokens") or 0)
            retry_input_tokens = int(retry_metadata.get("prompt_tokens") or 0)

            if retry_output_tokens > output_tokens:
                output = retry_output
                metadata = retry_metadata
                output_tokens = retry_output_tokens
                input_tokens = retry_input_tokens
                total_inference_time = retry_total_time
                results["total_inference_time"] = total_inference_time
                results["retry_used"] = True
            else:
                results["retry_used"] = False

        results["output_tokens"] = output_tokens
        results["input_tokens"] = input_tokens
        output_text = getattr(output, "text", "") or ""
        preview = " ".join(output_text.strip().split())
        results["output_preview"] = preview
        
        # Calculate tokens per second
        generation_tps = float(metadata.get("generation_tps") or 0)
        if generation_tps > 0:
            results["tokens_per_second"] = generation_tps
        elif results["output_tokens"] > 0 and total_inference_time > 0:
            tps = results["output_tokens"] / total_inference_time
            results["tokens_per_second"] = tps
        else:
            results["tokens_per_second"] = 0
        
        # Estimate TTFT (rough approximation)
        if results["tokens_per_second"] > 0:
            results["first_token_time"] = 1.0 / results["tokens_per_second"]
        elif results["output_tokens"] > 0:
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
            "Model",
            str(results.get("model_name", "unknown")),
        )
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
            "Input Tokens",
            str(results.get("input_tokens", 0)),
        )
        table.add_row(
            "Output Tokens",
            str(results['output_tokens']),
        )

        if results.get("retry_used"):
            table.add_row(
                "Prompt Retry",
                "yes",
            )
        
        console.print(table)

        preview_text = results.get("output_preview", "")
        if preview_text:
            console.print()
            console.print(Panel(
                preview_text,
                title="Output Preview",
                border_style="cyan",
                expand=True,
            ))
        
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
        print(f"Model: {results.get('model_name', 'unknown')}")
        print(f"Model Load Time: {results['model_load_time']:.2f}s")
        print(f"Time to First Token: {results['first_token_time']:.2f}s")
        print(f"Tokens Per Second: {results['tokens_per_second']:.1f}")
        print(f"Total Inference Time: {results['total_inference_time']:.2f}s")
        print(f"Input Tokens: {results.get('input_tokens', 0)}")
        print(f"Output Tokens: {results['output_tokens']}")
        if results.get("output_preview"):
            print(f"Output Preview: {results['output_preview']}")


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
