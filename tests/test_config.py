"""Tests for retix.config module."""

import importlib

from retix.config import (
    MODEL_NAME,
    MODEL_TYPE,
    QUANTIZATION,
    ensure_cache_dir,
    ensure_socket_dir,
)


def test_model_constants():
    """Test that model constants are properly defined."""
    assert MODEL_NAME == "mlx-community/Qwen3-VL-2B-Instruct-4bit"
    assert MODEL_TYPE == "qwen3_vl"
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


def test_invalid_environment_values_fall_back_to_defaults(monkeypatch):
    """Test that malformed integer environment overrides do not crash import."""
    monkeypatch.setenv("RETIX_MAX_TOKENS", "")
    monkeypatch.setenv("RETIX_LATENCY_TARGET_MS", "not-a-number")
    monkeypatch.setenv("RETIX_TOKEN_DESCRIBE", "broken")

    import retix.config as config_module

    reloaded_module = importlib.reload(config_module)

    assert reloaded_module.MAX_TOKENS == 512
    assert reloaded_module.LATENCY_TARGET_MS == 3000
    assert reloaded_module.TASK_TOKEN_LIMITS["describe"] == 512

    monkeypatch.delenv("RETIX_MAX_TOKENS", raising=False)
    monkeypatch.delenv("RETIX_LATENCY_TARGET_MS", raising=False)
    monkeypatch.delenv("RETIX_TOKEN_DESCRIBE", raising=False)
    importlib.reload(config_module)
