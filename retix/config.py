"""
Configuration and constants for retix.
Defines model paths, cache locations, and system parameters.
"""

import os
from pathlib import Path
from typing import Final

# Model Configuration
MODEL_NAME: Final[str] = "mlx-community/Qwen3-VL-2B-Instruct-4bit"
MODEL_TYPE: Final[str] = "qwen3-vl-2b"
QUANTIZATION: Final[str] = "4bit"

# Cache and Storage Paths
CACHE_DIR: Final[Path] = Path.home() / ".cache" / "retix"
SOCKET_DIR: Final[Path] = Path.home() / ".local" / "var" / "retix"
PID_FILE: Final[Path] = SOCKET_DIR / "daemon.pid"
SOCKET_FILE: Final[Path] = SOCKET_DIR / "daemon.sock"

# Performance Targets (tweakable via environment variables - based on benchmark: 320x640@512tokens = ~4-5s, 320x480@256tokens = ~2-3s)
LATENCY_TARGET_MS: Final[int] = int(os.getenv("RETIX_LATENCY_TARGET_MS", "3000"))  # Target: 3s for describe command (cold start, tweakable)
LATENCY_WARN_MS: Final[int] = int(os.getenv("RETIX_LATENCY_WARN_MS", "5000"))      # Warn if exceeds 5s (indicates resolution issue, tweakable)
LATENCY_WARM_MS: Final[int] = int(os.getenv("RETIX_LATENCY_WARM_MS", "1000"))      # Warm/daemon target: 1s (tweakable)
MEMORY_LIMIT_GB: Final[float] = 3.0

# Tool Behavior
DEFAULT_PROMPT: Final[str] = (
    "Describe this UI in detail: list all visible text, buttons, input fields, "
    "and their approximate positions. Identify any obvious visual bugs or layout misalignments."
)

OCR_PROMPT: Final[str] = (
    "Extract all visible text from this image. Return only the text content in a structured format."
)

VERIFY_PROMPT_TEMPLATE: Final[str] = "Verify if the following is true about this image: {claim}. Answer with YES or NO only."

# Temperature and Sampling
DEFAULT_TEMPERATURE: Final[float] = 0.0  # Deterministic for grounded results
MAX_TOKENS: Final[int] = int(os.getenv("RETIX_MAX_TOKENS", "512"))  # Tweakable: Pareto optimal, 256-512 for balance

# Image Resolution Auto-Scaling (Pareto optimized, tweakable via environment variables)
MAX_IMAGE_WIDTH: Final[int] = int(os.getenv("RETIX_MAX_IMAGE_WIDTH", "640"))  # Tweakable
MAX_IMAGE_HEIGHT: Final[int] = int(os.getenv("RETIX_MAX_IMAGE_HEIGHT", "480"))  # Tweakable
MAX_IMAGE_PIXELS: Final[int] = int(os.getenv("RETIX_MAX_IMAGE_PIXELS", "307200"))  # 640x480 default cap, tweakable

# Task-specific token limits (tweakable via environment variables)
TASK_TOKEN_LIMITS: Final[dict] = {
    "describe": int(os.getenv("RETIX_TOKEN_DESCRIBE", "512")),      # Tweakable
    "ocr": int(os.getenv("RETIX_TOKEN_OCR", "256")),                # Tweakable
    "verify": int(os.getenv("RETIX_TOKEN_VERIFY", "10")),           # Tweakable
}

# Confidence Thresholds
OCR_CONFIDENCE_THRESHOLD: Final[float] = 0.7
WARNING_THRESHOLD: Final[float] = 0.6

# Daemon Configuration
DAEMON_CHECK_INTERVAL_SEC: Final[int] = 5
DAEMON_SHUTDOWN_TIMEOUT_SEC: Final[int] = 10


def ensure_cache_dir() -> Path:
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def ensure_socket_dir() -> Path:
    """Create socket directory if it doesn't exist."""
    SOCKET_DIR.mkdir(parents=True, exist_ok=True)
    return SOCKET_DIR
