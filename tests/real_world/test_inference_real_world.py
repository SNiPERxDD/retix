"""Real-world inference tests for RETIX.

This suite is designed for execution on real screenshots:
- login UI
- dashboard UI
- code editor UI

To run:
    RETIX_RUN_REAL_WORLD=1 pytest tests/real_world -m real_world
"""

from pathlib import Path
import os

import pytest

from retix.inference import get_vision_engine


def _is_real_world_enabled() -> bool:
    """Check if real-world tests are explicitly enabled."""
    return os.environ.get("RETIX_RUN_REAL_WORLD", "0") == "1"


def _has_mlx_runtime() -> bool:
    """Check whether MLX runtime dependencies are available."""
    try:
        import mlx  # noqa: F401
        import mlx_vlm  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_screenshot(case_name: str) -> Path:
    """Resolve screenshot path for a real-world test case."""
    repo_root = Path(__file__).resolve().parents[2]
    screenshots_dir = Path(__file__).resolve().parent / "screenshots"

    case_to_path = {
        "login": screenshots_dir / "login.png",
        "dashboard": screenshots_dir / "dashboard.png",
        "code_editor": screenshots_dir / "code_editor.png",
    }

    # Use repository sample screenshot as fallback for login when dedicated fixtures are absent.
    if case_name == "login" and not case_to_path["login"].exists():
        fallback = repo_root / "test_ui_screenshot.png"
        if fallback.exists():
            return fallback

    return case_to_path[case_name]


@pytest.mark.real_world
@pytest.mark.parametrize("case_name", ["login", "dashboard", "code_editor"])
def test_real_world_inference(case_name: str) -> None:
    """Run RETIX describe inference against real-world screenshot cases."""
    if not _is_real_world_enabled():
        pytest.skip("Set RETIX_RUN_REAL_WORLD=1 to run real-world tests")

    if not _has_mlx_runtime():
        pytest.skip("MLX runtime not available")

    screenshot_path = _resolve_screenshot(case_name)
    if not screenshot_path.exists():
        pytest.skip(f"Missing screenshot fixture for {case_name}: {screenshot_path}")

    engine = get_vision_engine(use_mock=False)
    result = engine.run_inference(
        str(screenshot_path),
        "Describe the key UI components and visible text.",
    )

    assert isinstance(result.text, str)
    assert len(result.text.strip()) > 0
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.real_world
def test_real_world_ocr_login() -> None:
    """Run OCR inference on the login screenshot case."""
    if not _is_real_world_enabled():
        pytest.skip("Set RETIX_RUN_REAL_WORLD=1 to run real-world tests")

    if not _has_mlx_runtime():
        pytest.skip("MLX runtime not available")

    screenshot_path = _resolve_screenshot("login")
    if not screenshot_path.exists():
        pytest.skip(f"Missing login screenshot fixture: {screenshot_path}")

    engine = get_vision_engine(use_mock=False)
    result = engine.run_ocr(str(screenshot_path))

    assert isinstance(result.text, str)
    assert len(result.text.strip()) > 0
    assert 0.0 <= result.confidence <= 1.0
