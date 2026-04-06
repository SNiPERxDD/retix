"""Tests for MLX-VLM registry hardening in retix.inference."""

from types import SimpleNamespace

from retix.inference import _inject_qwen3_registry_support


def test_inject_qwen3_registry_support_populates_registry_alias():
    """Test that the Qwen3 alias is injected into the model registry."""
    qwen2_module = SimpleNamespace(Model=object())
    models_module = SimpleNamespace(MODEL_MAPPING={}, qwen2_vl=qwen2_module)

    injected = _inject_qwen3_registry_support(models_module)

    assert injected is True
    assert models_module.MODEL_MAPPING["qwen3_vl"] is qwen2_module.Model
    assert models_module.qwen3_vl is qwen2_module


def test_inject_qwen3_registry_support_returns_false_without_fallback():
    """Test that the helper no-ops if no compatible fallback exists."""
    models_module = SimpleNamespace(MODEL_MAPPING={})

    injected = _inject_qwen3_registry_support(models_module)

    assert injected is False