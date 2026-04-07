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


def test_normalize_qwen3_config_for_qwen2_fallback_copies_text_fields():
    """Test qwen3 nested text config keys are copied to root-level fallback fields."""
    config = {
        "model_type": "qwen3_vl",
        "text_config": {
            "hidden_size": 1536,
            "num_hidden_layers": 12,
            "intermediate_size": 8960,
            "num_attention_heads": 12,
            "rms_norm_eps": 1e-6,
            "vocab_size": 151936,
        },
    }

    changed = inference_module._normalize_qwen3_config_for_qwen2_fallback(
        config, "qwen2_5_vl"
    )

    assert changed is True
    assert config["hidden_size"] == 1536
    assert config["num_hidden_layers"] == 12
    assert config["vocab_size"] == 151936
    assert config["model_type"] == "qwen2_5_vl"
    assert config["text_config"]["model_type"] == "qwen2_5_vl"


def test_normalize_qwen3_config_for_qwen2_fallback_ignores_non_qwen3():
    """Test config normalization no-ops for non-qwen3 model types."""
    config = {
        "model_type": "llava",
        "text_config": {"hidden_size": 4096},
    }

    changed = inference_module._normalize_qwen3_config_for_qwen2_fallback(
        config, "qwen2_5_vl"
    )

    assert changed is False
    assert "hidden_size" not in config


def test_inject_qwen3_load_config_adapter_patches_once():
    """Test load_config wrapper injects normalization and avoids double-patching."""
    captured = {
        "config": {
            "model_type": "qwen3_vl",
            "text_config": {"hidden_size": 2048},
        }
    }

    utils_module = SimpleNamespace(load_config=lambda *args, **kwargs: captured["config"])

    first = inference_module._inject_qwen3_load_config_adapter(
        utils_module, "qwen2_5_vl"
    )
    second = inference_module._inject_qwen3_load_config_adapter(
        utils_module, "qwen2_5_vl"
    )
    adapted = utils_module.load_config()

    assert first is True
    assert second is False
    assert adapted["hidden_size"] == 2048
    assert adapted["model_type"] == "qwen2_5_vl"
    assert adapted["text_config"]["model_type"] == "qwen2_5_vl"


def test_has_native_qwen3_support_detects_present_module(monkeypatch):
    """Test native support detection returns true when qwen3_vl module is present."""
    qwen3_module = ModuleType("mlx_vlm.models.qwen3_vl")
    models_module = SimpleNamespace()

    monkeypatch.setitem(sys.modules, "mlx_vlm.models.qwen3_vl", qwen3_module)

    assert inference_module._has_native_qwen3_support(models_module) is True


def test_has_native_qwen3_support_detects_missing_module(monkeypatch):
    """Test native support detection returns false when qwen3_vl module is absent."""
    models_module = SimpleNamespace()

    monkeypatch.delitem(sys.modules, "mlx_vlm.models.qwen3_vl", raising=False)

    assert inference_module._has_native_qwen3_support(models_module) is False


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