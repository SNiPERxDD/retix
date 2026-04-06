"""
Image preprocessing and optimization utilities.
Handles automatic downscaling of high-resolution images based on Pareto analysis.
"""

import sys
from pathlib import Path
from PIL import Image
import tempfile

from retix.config import MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT, MAX_IMAGE_PIXELS


def should_downscale(image: Image.Image) -> bool:
    """Check if image needs downscaling."""
    return (
        image.width > MAX_IMAGE_WIDTH
        or image.height > MAX_IMAGE_HEIGHT
        or (image.width * image.height) > MAX_IMAGE_PIXELS
    )


def _calculate_target_dimensions(image: Image.Image) -> tuple[int, int]:
    """Calculate resize dimensions while preserving aspect ratio."""
    orig_w, orig_h = image.size
    width_scale = MAX_IMAGE_WIDTH / orig_w
    height_scale = MAX_IMAGE_HEIGHT / orig_h
    pixel_scale = (MAX_IMAGE_PIXELS / (orig_w * orig_h)) ** 0.5
    scale = min(width_scale, height_scale, pixel_scale, 1.0)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))
    return new_w, new_h


def downscale_image(image_path: str, verbose: bool = False) -> str:
    """
    Downscale high-resolution images to Pareto optimal size.
    
    Benchmark results show:
    - 320x240: 2.3s (fastest)
    - 480x360: 2.7s
    - 640x480: 4.1s (good balance)
    - 800x600: 6.7s
    - 1024+: much slower
    
    Args:
        image_path: Path to image file
        verbose: Log downscaling operations
    
    Returns:
        Path to image (either original or downscaled temp file)
    """
    img = Image.open(image_path)
    orig_w, orig_h = img.size
    
    if not should_downscale(img):
        if verbose:
            sys.stderr.write(f"[OPTIMIZE] Image {orig_w}x{orig_h} - no downscaling needed\n")
            sys.stderr.flush()
        return image_path
    
    # Calculate new dimensions maintaining aspect ratio for any image shape
    new_w, new_h = _calculate_target_dimensions(img)
    scale = min(new_w / orig_w, new_h / orig_h)
    
    if verbose:
        sys.stderr.write(
            f"[OPTIMIZE] Downscaling {orig_w}x{orig_h} → {new_w}x{new_h} "
            f"(scale={scale:.2f}x)...\n"
        )
        sys.stderr.flush()
    
    # Use high-quality LANCZOS resampling
    downscaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Create temp directory if needed
    temp_dir = Path.home() / ".cache" / "retix" / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        dir=str(temp_dir)
    )
    temp_path = temp_file.name
    
    # Save with reasonable quality
    downscaled.save(temp_path, "PNG")
    temp_file.close()
    
    if verbose:
        orig_size_kb = Path(image_path).stat().st_size / 1024
        new_size_kb = Path(temp_path).stat().st_size / 1024
        sys.stderr.write(
            f"[OPTIMIZE] File size: {orig_size_kb:.1f}KB → {new_size_kb:.1f}KB\n"
        )
        sys.stderr.flush()
    
    return temp_path


def cleanup_downscaled(image_path: str) -> None:
    """Remove downscaled temp file if it was created."""
    path = Path(image_path)
    
    # Only delete if it's in our temp directory
    cache_dir = Path.home() / ".cache" / "retix" / "tmp"
    if path.parent == cache_dir:
        try:
            path.unlink()
        except Exception:
            pass
