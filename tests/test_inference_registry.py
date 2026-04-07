"""Tests for MLX-VLM registry hardening in retix.inference."""

import sys
from types import ModuleType
from types import SimpleNamespace

import retix.inference as inference_module


def test_inject_qwen3_model_remapping_populates_utils_remap(monkeypatch):
    """Test that qwen3_vl is remapped to a supported architecture module."""
    qwen2_module = ModuleType("mlx_vlm.models.qwen2_vl")
    models_module = SimpleNamespace(qwen2_vl=qwen2_module)
    utils_module = SimpleNamespace(MODEL_REMAPPING={})

    monkeypatch.setattr(inference_module, "QWEN2_VL_MODULE_NAMES", ("qwen2_vl",))
    monkeypatch.setitem(sys.modules, "mlx_vlm.models.qwen2_vl", qwen2_module)
    monkeypatch.delitem(sys.modules, "mlx_vlm.models.qwen3_vl", raising=False)

    injected = inference_module._inject_qwen3_model_remapping(utils_module, models_module)

    assert injected is True
    assert utils_module.MODEL_REMAPPING["qwen3_vl"] == "qwen2_vl"
    assert sys.modules["mlx_vlm.models.qwen3_vl"] is qwen2_module


def test_inject_qwen3_model_remapping_works_with_lazy_models_module(monkeypatch):
    """Test remapping injection when qwen fallback module is importable but not pre-attached."""
    qwen2_module = ModuleType("mlx_vlm.models.qwen2_vl")
    models_module = SimpleNamespace()
    utils_module = SimpleNamespace(MODEL_REMAPPING={})

    monkeypatch.setattr(inference_module, "QWEN2_VL_MODULE_NAMES", ("qwen2_vl",))
    monkeypatch.setitem(sys.modules, "mlx_vlm.models.qwen2_vl", qwen2_module)
    monkeypatch.delitem(sys.modules, "mlx_vlm.models.qwen3_vl", raising=False)

    injected = inference_module._inject_qwen3_model_remapping(utils_module, models_module)

    assert injected is True
    assert utils_module.MODEL_REMAPPING["qwen3_vl"] == "qwen2_vl"
    assert sys.modules["mlx_vlm.models.qwen3_vl"] is qwen2_module


def test_inject_qwen3_model_remapping_returns_false_without_fallback(monkeypatch):
    """Test that remapping is not injected when no compatible fallback module exists."""
    models_module = SimpleNamespace()
    utils_module = SimpleNamespace(MODEL_REMAPPING={})

    monkeypatch.setattr(
        inference_module,
        "QWEN2_VL_MODULE_NAMES",
        ("retix_nonexistent_fallback",),
    )

    injected = inference_module._inject_qwen3_model_remapping(utils_module, models_module)

    assert injected is False


def test_inject_qwen3_registry_support_populates_registry_alias(monkeypatch):
    """Test that the Qwen3 alias is injected into the model registry."""
    qwen2_module = SimpleNamespace(Model=object())
    models_module = SimpleNamespace(MODEL_MAPPING={}, qwen2_vl=qwen2_module)

    monkeypatch.setattr(inference_module, "QWEN2_VL_MODULE_NAMES", ("qwen2_vl",))

    injected = inference_module._inject_qwen3_registry_support(models_module)

    assert injected is True
    assert models_module.MODEL_MAPPING["qwen3_vl"] is qwen2_module.Model
    assert models_module.qwen3_vl is qwen2_module


def test_inject_qwen3_registry_support_returns_false_without_fallback(monkeypatch):
    """Test that the helper no-ops if no compatible fallback exists."""
    models_module = SimpleNamespace(MODEL_MAPPING={})

    monkeypatch.setattr(
        inference_module,
        "QWEN2_VL_MODULE_NAMES",
        ("retix_nonexistent_fallback",),
    )

    injected = inference_module._inject_qwen3_registry_support(models_module)

    assert injected is False