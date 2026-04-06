#!/usr/bin/env python3
"""
Benchmark token limits vs image resolution vs inference speed.
Finds Pareto optimal configuration for fast inference.
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Tuple
from PIL import Image
import tempfile

from retix.inference import get_vision_engine
from retix.config import DEFAULT_PROMPT


def get_test_image_info(image_path: str) -> Dict:
    """Get original image information."""
    img = Image.open(image_path)
    return {
        "path": image_path,
        "resolution": img.size,  # (width, height)
        "file_size_kb": Path(image_path).stat().st_size / 1024,
        "format": img.format,
    }


def create_resized_image(image_path: str, target_width: int) -> Tuple[str, Dict]:
    """
    Create a resized version of the image maintaining aspect ratio.
    Returns temp file path and metadata.
    """
    img = Image.open(image_path)
    orig_w, orig_h = img.size
    
    # Calculate new height maintaining aspect ratio
    scale = target_width / orig_w
    new_h = int(orig_h * scale)
    
    # Resize using high-quality filter
    resized = img.resize((target_width, new_h), Image.Resampling.LANCZOS)
    
    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = temp_file.name
    resized.save(temp_path, "PNG")
    temp_file.close()
    
    file_size_kb = Path(temp_path).stat().st_size / 1024
    
    return temp_path, {
        "resolution": (target_width, new_h),
        "file_size_kb": file_size_kb,
        "scale": f"{scale:.2f}x"
    }


def run_benchmark(
    image_path: str,
    resolutions: List[int],
    token_limits: List[int],
    warmup: bool = True,
) -> List[Dict]:
    """
    Run comprehensive benchmark across configurations.
    
    Args:
        image_path: Path to test image
        resolutions: Pixel widths to test
        token_limits: Max token values to test
        warmup: Run warmup inference first
    
    Returns:
        List of benchmark results
    """
    engine = get_vision_engine()
    results = []
    
    print("\n" + "="*80, file=sys.stderr)
    print("IMAGE RESOLUTION BENCHMARKS", file=sys.stderr)
    print("="*80, file=sys.stderr)
    
    # Get original image info
    orig_info = get_test_image_info(image_path)
    orig_w, orig_h = orig_info["resolution"]
    print(f"\nOriginal image: {orig_w}x{orig_h} ({orig_info['file_size_kb']:.1f} KB)", file=sys.stderr)
    
    # Optional warmup
    if warmup:
        print("\n[WARMUP] Running warmup inference...", file=sys.stderr)
        try:
            temp_path, _ = create_resized_image(image_path, 320)
            engine.run_inference(temp_path, DEFAULT_PROMPT, max_tokens=256)
            Path(temp_path).unlink()
        except Exception as e:
            print(f"Warmup error: {e}", file=sys.stderr)
    
    print("\n" + "-"*80, file=sys.stderr)
    print("Testing resolution x token combinations...", file=sys.stderr)
    print("-"*80, file=sys.stderr)
    
    for res_width in resolutions:
        print(f"\n[Resolution: {res_width}px width]", file=sys.stderr)
        
        # Skip if resolution is original (don't resize)
        if res_width == orig_w:
            temp_path = image_path
            res_info = orig_info
        else:
            temp_path, res_info = create_resized_image(image_path, res_width)
        
        res_h = res_info["resolution"][1] if "resolution" in res_info else orig_h
        print(f"  Resolution: {res_width}x{res_h}, File: {res_info['file_size_kb']:.1f} KB", file=sys.stderr)
        
        for max_tokens in token_limits:
            try:
                # Run inference
                start = time.time()
                result = engine.run_inference(
                    temp_path,
                    DEFAULT_PROMPT,
                    max_tokens=max_tokens
                )
                elapsed = time.time() - start
                
                meta = result.raw_metadata
                gen_tokens = meta.get("generation_tokens", 0)
                prompt_tokens = meta.get("prompt_tokens", 0)
                gen_tps = meta.get("generation_tps", 0)
                
                record = {
                    "resolution_width": res_width,
                    "resolution_height": res_h,
                    "file_size_kb": res_info["file_size_kb"],
                    "max_tokens_limit": max_tokens,
                    "actual_gen_tokens": gen_tokens,
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": prompt_tokens + gen_tokens,
                    "generation_tps": gen_tps,
                    "inference_time_ms": int(elapsed * 1000),
                    "tokens_per_ms": gen_tokens / (elapsed * 1000) if elapsed > 0 else 0,
                }
                results.append(record)
                
                print(
                    f"    max_tokens={max_tokens:4d} | "
                    f"time={elapsed:6.2f}s | "
                    f"gen_toks={gen_tokens:3d} | "
                    f"gen_tps={gen_tps:6.1f} | "
                    f"file={res_info['file_size_kb']:6.1f}KB",
                    file=sys.stderr
                )
                
            except Exception as e:
                print(f"    max_tokens={max_tokens:4d} | ERROR: {e}", file=sys.stderr)
        
        # Clean up temp file
        if res_width != orig_w:
            Path(temp_path).unlink()
    
    return results


def find_pareto_frontier(results: List[Dict]) -> List[Dict]:
    """
    Find Pareto optimal configurations (fastest speed, fewest tokens).
    A point is Pareto optimal if no other point is strictly faster with fewer tokens.
    """
    if not results:
        return []
    
    # Sort by inference time
    sorted_results = sorted(results, key=lambda r: r["inference_time_ms"])
    
    frontier = []
    min_tokens_seen = float('inf')
    
    for record in sorted_results:
        gen_tokens = record["actual_gen_tokens"]
        if gen_tokens <= min_tokens_seen:
            frontier.append(record)
            min_tokens_seen = gen_tokens
    
    return frontier


def print_analysis(results: List[Dict]) -> None:
    """Print detailed analysis and recommendations."""
    if not results:
        print("No results to analyze.", file=sys.stderr)
        return
    
    print("\n" + "="*80, file=sys.stderr)
    print("ANALYSIS & RECOMMENDATIONS", file=sys.stderr)
    print("="*80, file=sys.stderr)
    
    # Group by resolution
    by_resolution = {}
    for r in results:
        res_key = f"{r['resolution_width']}x{r['resolution_height']}"
        if res_key not in by_resolution:
            by_resolution[res_key] = []
        by_resolution[res_key].append(r)
    
    print("\n[By Resolution - Average Performance]", file=sys.stderr)
    for res_key in sorted(by_resolution.keys()):
        records = by_resolution[res_key]
        avg_time = sum(r["inference_time_ms"] for r in records) / len(records)
        avg_tokens = sum(r["actual_gen_tokens"] for r in records) / len(records)
        avg_file_size = records[0]["file_size_kb"]  # Same for all in group
        print(
            f"  {res_key:15s} | "
            f"avg_time={avg_time:7.0f}ms | "
            f"avg_gen_toks={avg_tokens:5.0f} | "
            f"file_size={avg_file_size:6.1f}KB",
            file=sys.stderr
        )
    
    # Find Pareto frontier
    frontier = find_pareto_frontier(results)
    
    print("\n[Pareto Frontier - Best Speed/Quality Trade-offs]", file=sys.stderr)
    print("Resolution x MaxTokens → Time | Tokens | Speed", file=sys.stderr)
    for record in frontier:
        res_key = f"{record['resolution_width']}x{record['resolution_height']}"
        tps = record["inference_time_ms"] / 1000
        print(
            f"  {res_key:15s} x {record['max_tokens_limit']:4d} → "
            f"{record['inference_time_ms']:6.0f}ms | "
            f"{record['actual_gen_tokens']:4d} toks | "
            f"{record['generation_tps']:6.1f} tps",
            file=sys.stderr
        )
    
    # Fastest result
    fastest = min(results, key=lambda r: r["inference_time_ms"])
    print("\n[Fastest Configuration]", file=sys.stderr)
    res_key = f"{fastest['resolution_width']}x{fastest['resolution_height']}"
    print(
        f"  Resolution: {res_key} at {fastest['max_tokens_limit']} tokens",
        file=sys.stderr
    )
    print(
        f"  Time: {fastest['inference_time_ms']:.0f}ms | "
        f"Tokens: {fastest['actual_gen_tokens']} | "
        f"Speed: {fastest['generation_tps']:.1f} tps",
        file=sys.stderr
    )
    
    # Most efficient (best tps per KB)
    for r in results:
        r["efficiency"] = r["generation_tps"] / (r["file_size_kb"] + 0.1)  # Avoid division by zero
    
    most_efficient = max(results, key=lambda r: r["efficiency"])
    print("\n[Most Efficient (tps per KB)]", file=sys.stderr)
    res_key = f"{most_efficient['resolution_width']}x{most_efficient['resolution_height']}"
    print(
        f"  Resolution: {res_key} at {most_efficient['max_tokens_limit']} tokens",
        file=sys.stderr
    )
    print(
        f"  Efficiency: {most_efficient['efficiency']:.2f} tps/KB | "
        f"Time: {most_efficient['inference_time_ms']:.0f}ms",
        file=sys.stderr
    )
    
    # Recommendations
    print("\n[Recommendations]", file=sys.stderr)
    
    # Overall recommendation
    recommended = frontier[0] if frontier else fastest
    rec_res = f"{recommended['resolution_width']}x{recommended['resolution_height']}"
    rec_tokens = recommended['max_tokens_limit']
    print(f"\n  1. Recommended config: {rec_res} with max_tokens={rec_tokens}", file=sys.stderr)
    print(
        f"     → Achieves {recommended['inference_time_ms']:.0f}ms with "
        f"{recommended['actual_gen_tokens']} tokens",
        file=sys.stderr
    )
    
    # Token limit recommendation
    print("\n  2. Token Limit Analysis:", file=sys.stderr)
    by_tokens = {}
    for r in results:
        tok = r['max_tokens_limit']
        if tok not in by_tokens:
            by_tokens[tok] = []
        by_tokens[tok].append(r)
    
    for tok in sorted(by_tokens.keys()):
        records = by_tokens[tok]
        avg_actual = sum(r["actual_gen_tokens"] for r in records) / len(records)
        utilization = (avg_actual / tok) * 100 if tok > 0 else 0
        print(
            f"     max_tokens={tok}: avg {avg_actual:.0f} gen tokens "
            f"({utilization:.0f}% utilized)",
            file=sys.stderr
        )
    
    # Resolution recommendation
    print("\n  3. Resolution Trade-offs:", file=sys.stderr)
    fastest_res = min(by_resolution.keys(), key=lambda k: sum(r["inference_time_ms"] for r in by_resolution[k]))
    quality_res = max(by_resolution.keys(), key=lambda k: sum(r["resolution_width"] * r["resolution_height"] for r in by_resolution[k]))
    print(f"     Fastest: {fastest_res}", file=sys.stderr)
    print(f"     Best quality (largest): {quality_res}", file=sys.stderr)


def main():
    """Main benchmark entry point."""
    # Use a portable path for test image (home directory or current working directory)
    test_image = Path.home() / "Downloads" / "test.jpeg"
    
    if not test_image.exists():
        # Fallback: look in current working directory
        test_image = Path("test.jpeg")
    
    if not test_image.exists():
        print(f"Error: Test image not found at {Path.home() / 'Downloads' / 'test.jpeg'} or ./test.jpeg", file=sys.stderr)
        print("Usage: Place test.jpeg in ~/Downloads or current directory", file=sys.stderr)
        sys.exit(1)
    
    # Test configurations
    resolutions = [
        320,   # Very low - fast
        480,   # Low - good speed
        640,   # Medium - balance
        800,   # High - better quality
    ]
    
    token_limits = [
        128,   # Very short
        256,   # Short
        512,   # Medium
        768,   # Extended
        1024,  # Current default
    ]
    
    print(f"\nBenchmarking {test_image}", file=sys.stderr)
    
    # Run benchmark
    results = run_benchmark(
        str(test_image),
        resolutions=resolutions,
        token_limits=token_limits,
        warmup=True
    )
    
    # Analyze results
    print_analysis(results)
    
    # Output JSON for further analysis
    output_file = Path("benchmark_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[Results saved to {output_file}]", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
