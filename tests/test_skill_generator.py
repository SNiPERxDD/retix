"""
Tests for retix.skill_generator module.
"""

import pytest
from pathlib import Path
import tempfile

from retix.skill_generator import (
    ensure_skill_exists,
    update_gitignore_for_agent,
    get_skill_instance_prompt,
)


def test_ensure_skill_exists():
    """Test creating skill file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_file = ensure_skill_exists(Path(tmpdir))
        
        assert skill_file.exists()
        assert skill_file.name == "vision-skill.md"
        assert ".agent" in str(skill_file)
        
        content = skill_file.read_text()
        assert "Vision Skill" in content
        assert "retix describe" in content


def test_ensure_skill_exists_idempotent():
    """Test that skill creation is idempotent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create once
        skill_file_1 = ensure_skill_exists(Path(tmpdir))
        content_1 = skill_file_1.read_text()
        
        # Create again
        skill_file_2 = ensure_skill_exists(Path(tmpdir))
        content_2 = skill_file_2.read_text()
        
        # Should be identical
        assert skill_file_1 == skill_file_2
        assert content_1 == content_2


def test_update_gitignore_creates_new():
    """Test creating new .gitignore with .agent/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        update_gitignore_for_agent(Path(tmpdir))
        
        gitignore = Path(tmpdir) / ".gitignore"
        assert gitignore.exists()
        
        content = gitignore.read_text()
        assert ".agent/" in content


def test_update_gitignore_appends_idempotently():
    """Test that .agent/ is added to existing .gitignore only once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore = Path(tmpdir) / ".gitignore"
        gitignore.write_text("node_modules/\n")
        
        # Update once
        update_gitignore_for_agent(Path(tmpdir))
        content_1 = gitignore.read_text()
        
        # Update again
        update_gitignore_for_agent(Path(tmpdir))
        content_2 = gitignore.read_text()
        
        # Should be identical (idempotent)
        assert content_1 == content_2
        assert content_1.count(".agent/") == 1  # Only appears once


def test_get_skill_instance_prompt():
    """Test getting skill prompt for agents."""
    prompt = get_skill_instance_prompt()
    
    assert "retix" in prompt
    assert "describe" in prompt
    assert "ocr" in prompt
    assert "tool" in prompt.lower()
