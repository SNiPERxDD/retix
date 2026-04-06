"""
Tests for retix.config module.
"""

import pytest
from pathlib import Path
from retix.config import (
    MODEL_NAME,
    QUANTIZATION,
    CACHE_DIR,
    ensure_cache_dir,
    ensure_socket_dir,
)


def test_model_constants():
    """Test that model constants are properly defined."""
    assert MODEL_NAME == "mlx-community/Qwen3-VL-2B-Instruct-4bit"
    assert QUANTIZATION == "4bit"


def test_cache_dir_creation():
    """Test that cache directory can be created."""
    cache_dir = ensure_cache_dir()
    
    assert cache_dir.exists()
    assert cache_dir.is_dir()
    assert ".cache/retix" in str(cache_dir)


def test_socket_dir_creation():
    """Test that socket directory can be created."""
    socket_dir = ensure_socket_dir()
    
    assert socket_dir.exists()
    assert socket_dir.is_dir()
    assert ".local/var/retix" in str(socket_dir)
