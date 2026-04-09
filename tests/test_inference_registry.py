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
    monkeypatch.setattr(
        inference_module,
        "_resolve_mlx_model_module",
        lambda *_args, **_kwargs: None,
    )

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


def test_format_prompt_for_generation_uses_template_when_available():
    """Test prompt formatting uses processor chat template when supported."""
    captured = {}

    def _apply_chat_template(messages, add_generation_prompt):
        captured["messages"] = messages
        captured["add_generation_prompt"] = add_generation_prompt
        return "formatted-template-prompt"

    processor = SimpleNamespace(apply_chat_template=_apply_chat_template)

    formatted = inference_module._format_prompt_for_generation(
        processor, "describe this image"
    )

    assert formatted == "formatted-template-prompt"
    assert captured["add_generation_prompt"] is True
    assert captured["messages"][0]["content"][1]["text"] == "describe this image"


def test_format_prompt_for_generation_falls_back_without_template_method():
    """Test prompt formatting falls back to image-token prompt when template is unavailable."""
    processor = SimpleNamespace(image_token="<image>")

    formatted = inference_module._format_prompt_for_generation(
        processor, "describe this image"
    )

    assert formatted == "<image>\ndescribe this image"


def test_format_prompt_for_generation_uses_tokenizer_template_when_available():
    """Test prompt formatting uses tokenizer chat template when processor lacks one."""
    captured = {}

    def _tokenizer_apply_chat_template(messages, add_generation_prompt, tokenize):
        captured["messages"] = messages
        captured["add_generation_prompt"] = add_generation_prompt
        captured["tokenize"] = tokenize
        return "formatted-tokenizer-template"

    tokenizer = SimpleNamespace(apply_chat_template=_tokenizer_apply_chat_template)
    processor = SimpleNamespace(tokenizer=tokenizer)

    formatted = inference_module._format_prompt_for_generation(
        processor, "describe this image"
    )

    assert formatted == "formatted-tokenizer-template"
    assert captured["add_generation_prompt"] is True
    assert captured["tokenize"] is False
    assert captured["messages"][0]["content"][1]["text"] == "describe this image"


def test_format_prompt_for_generation_handles_missing_template_error():
    """Test prompt formatting falls back when processor raises missing-template error."""

    def _apply_chat_template(messages, add_generation_prompt):
        raise ValueError(
            "Cannot use apply_chat_template because this processor does not have a chat template."
        )

    processor = SimpleNamespace(apply_chat_template=_apply_chat_template)

    formatted = inference_module._format_prompt_for_generation(
        processor, "describe this image"
    )

    assert formatted == "<image>\ndescribe this image"


def test_format_prompt_for_generation_uses_existing_image_token_once():
    """Test fallback does not duplicate image token if prompt already includes one."""
    processor = SimpleNamespace(image_token="<image>")
    prompt = "<image>\ndescribe this image"

    formatted = inference_module._format_prompt_for_generation(processor, prompt)

    assert formatted == prompt


def test_should_retry_generation_for_empty_immediate_eos():
    """Retry should trigger when output is empty and generation ended immediately."""
    assert inference_module._should_retry_generation("", 1) is True
    assert inference_module._should_retry_generation("   ", 0) is True


def test_should_retry_generation_false_for_nonempty_output():
    """Retry should not trigger when there is usable output text."""
    assert inference_module._should_retry_generation("hello", 1) is False
    assert inference_module._should_retry_generation("visible ui", 10) is False


def test_build_retry_prompt_appends_instruction():
    """Retry prompt should preserve original prompt and add a deterministic nudge."""
    original = "Describe the screen"
    retry_prompt = inference_module._build_retry_prompt(original)

    assert "Describe the screen" in retry_prompt
    assert "Respond with at least one short sentence" in retry_prompt


def test_ensure_nonempty_output_text_passthrough_nonempty():
    """Non-empty generation text should pass through unchanged."""
    text, used_fallback = inference_module._ensure_nonempty_output_text("hello world")

    assert text == "hello world"
    assert used_fallback is False


def test_ensure_nonempty_output_text_replaces_empty():
    """Empty generation text should be replaced with a helpful fallback message."""
    text, used_fallback = inference_module._ensure_nonempty_output_text("   ")

    assert "Model returned an empty response" in text
    assert used_fallback is True