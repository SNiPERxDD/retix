"""Tests for retix.skill_generator module."""

from retix.skill_generator import VISION_SKILL_TEMPLATE


def test_skill_template_contains_project_skill_path():
    """Test that the skill template points at the project-local skill file."""
    assert ".retix/SKILL.md" in VISION_SKILL_TEMPLATE


def test_skill_template_contains_core_commands():
    """Test that the skill template documents the core CLI commands."""
    assert "retix describe" in VISION_SKILL_TEMPLATE
    assert "retix ocr" in VISION_SKILL_TEMPLATE
    assert "retix check" in VISION_SKILL_TEMPLATE
    assert "retix daemon start" in VISION_SKILL_TEMPLATE
