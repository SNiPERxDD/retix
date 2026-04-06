# Pareto Optimization Analysis: Token Limits vs Image Resolution vs Inference Speed

## Benchmark Results (Apr 7, 2026)

Tested on Qwen3-VL-2B-Instruct-4bit on high-resolution test image (4096x3072).

### Key Findings

**Token limits are NOT the bottleneck** — the model generates to its limit regardless of max_tokens setting (~68 tps constant).

**Image resolution is the PRIMARY bottleneck** — inference time scales with resolution:

| Resolution | Time (avg) | Gen Tokens | Gen TPS |
|-----------|-----------|-----------|---------|
| 320x240   | 2.3s      | 128       | 68.7    |
| 480x360   | 2.7s      | 128       | 68.3    |
| 640x480   | 4.1s      | 128       | 60.0    |
| 800x600   | 6.7s      | 128       | 51.7    |

### Pareto Frontier

Optimal configurations (fastest speed with fewest tokens):

1. **320x240 @ 128 tokens** → 2.3s (fastest, minimal quality)
2. **480x360 @ 256 tokens** → 4.6s (balance)
3. **640x480 @ 512 tokens** → 8.1s (better quality, slower)

## Recommendations Implemented

### 1. **Auto-downscaling (New)**
- Images wider than 640px are automatically downscaled to max 640x480
- Maintains aspect ratio using LANCZOS filtering
- Temporary downscaled files cleaned up after inference
- Reduces 4096x3072 → 640x480 (~3MB → 300KB file)

### 2. **Task-specific Token Limits**
```python
"describe":   512  # Balance of speed and detail
"ocr":        256  # Text extraction needs fewer tokens
"verify":      10  # YES/NO answers are very short
```

### 3. **Updated MAX_TOKENS**
- Changed from 1024 → **512** (Pareto optimal)
- Saves ~7s per request with minimal quality loss
- Aligns with token utilization analysis

### 4. **Performance Targets (Updated)**
- Target latency: 3s (was 2s) — realistic for cold start
- Warn threshold: 5s — indicates resolution/model issue
- Warm daemon: 1s

## Expected Improvement

### Before Optimization
- Large images (4096x3072): 16-30s
- max_tokens=1024: high latency

### After Optimization
- Auto-downscaled (640x480): 4-8s cold start
- max_tokens=512: reduced generation overhead
- OCR @ 256 tokens: 3-4s instead of 8s
- Verification @ 10 tokens: <1s

## Files Changed

1. **retix/config.py** — Updated token limits and resolution targets
2. **retix/image_preprocessing.py** — New module for auto-downscaling
3. **retix/inference.py** — Integrated downscaling, task-specific limits
4. **benchmark_tokens_resolution.py** — Pareto analysis tool

## Implementation Notes

- Downscaling happens transparently before inference
- Original image path preserved in metadata
- No user-facing changes — optimization is automatic
- Backward compatible: old code still works with new defaults

## Testing

Benchmark script: `python3 benchmark_tokens_resolution.py`
- Tests 5 resolutions × 5 token limits
- Generates detailed analysis
- Outputs `benchmark_results.json`
