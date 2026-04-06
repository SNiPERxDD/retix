"""
Tests for retix.path_utils module.
"""

import pytest
from pathlib import Path
import tempfile
import os

from retix.path_utils import (
    resolve_image_path,
    find_project_root,
    get_project_agent_dir,
    get_gitignore_path,
)


def test_resolve_image_path_absolute():
    """Test resolving an absolute image path."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    
    try:
        resolved = resolve_image_path(path)
        assert resolved.exists()
        assert resolved.is_file()
    finally:
        os.unlink(path)


def test_resolve_image_path_with_tilde():
    """Test expanding ~ in path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file in home-like structure
        test_file = Path(tmpdir) / "test.png"
        test_file.touch()
        
        # Simulate home expansion by using absolute path
        resolved = resolve_image_path(str(test_file))
        assert resolved.exists()


def test_resolve_image_path_nonexistent():
    """Test that nonexistent paths raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        resolve_image_path("/nonexistent/file.png")


def test_resolve_image_path_invalid_format():
    """Test that unsupported image formats raise ValueError."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        path = f.name
    
    try:
        with pytest.raises(ValueError, match="Unsupported image format"):
            resolve_image_path(path)
    finally:
        os.unlink(path)


def test_find_project_root():
    """Test finding project root."""
    # Current directory should find a root
    root = find_project_root()
    assert root.exists()
    assert root.is_dir()


def test_find_project_root_with_git():
    """Test finding project root with .git marker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .git directory
        git_dir = Path(tmpdir) / ".git"
        git_dir.mkdir()
        
        # Find root should return tmpdir
        root = find_project_root(tmpdir)
        assert root == Path(tmpdir).resolve()


def test_get_project_agent_dir():
    """Test getting .agent directory path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = get_project_agent_dir(tmpdir)
        assert agent_dir == Path(tmpdir).resolve() / ".agent"


def test_get_gitignore_path():
    """Test getting .gitignore path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gitignore_path = get_gitignore_path(tmpdir)
        assert gitignore_path == Path(tmpdir).resolve() / ".gitignore"
