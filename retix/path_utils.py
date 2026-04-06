"""
Path utilities for resolving absolute paths in various contexts.
Handles ~ expansion, relative paths, and current working directory resolution.
"""

import os
from pathlib import Path
from typing import Union


def resolve_image_path(image_path: str) -> Path:
    """
    Resolve an image path to an absolute Path object.
    
    Handles:
    - Tilde expansion (~)
    - Relative paths (resolved against current working directory)
    - Absolute paths (returned as-is)
    
    Args:
        image_path: Path to the image (str)
    
    Returns:
        Absolute Path object
    
    Raises:
        FileNotFoundError: If the resolved path does not exist or is not a file
        ValueError: If the path is invalid
    """
    if not image_path:
        raise ValueError("Image path cannot be empty")
    
    # Expand user home directory
    expanded = os.path.expanduser(image_path)
    
    # Resolve to absolute path
    absolute_path = Path(expanded).resolve()
    
    # Verify the path exists and is a file
    if not absolute_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path} (resolved to {absolute_path})")
    
    if not absolute_path.is_file():
        raise ValueError(f"Path is not a file: {absolute_path}")
    
    # Verify it's an image file
    valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    if absolute_path.suffix.lower() not in valid_extensions:
        raise ValueError(
            f"Unsupported image format: {absolute_path.suffix}. "
            f"Supported formats: {', '.join(valid_extensions)}"
        )
    
    return absolute_path


def find_project_root(start_path: Union[str, Path] = ".") -> Path:
    """
    Find the project root by searching for common markers (git, pyproject.toml, etc).
    
    Args:
        start_path: Starting directory for search. Defaults to current directory.
    
    Returns:
        Path to the project root
    """
    path = Path(start_path).resolve()
    
    # If start_path is a file, start from its parent
    if path.is_file():
        path = path.parent
    
    # Search up the directory tree for project markers
    markers = {".git", "pyproject.toml", "package.json", ".gitignore", "README.md"}
    
    while path != path.parent:  # Stop at filesystem root
        if any((path / marker).exists() for marker in markers):
            return path
        path = path.parent
    
    # If no marker found, return the starting path
    return Path(start_path).resolve()


def get_gitignore_path(project_root: Union[str, Path] = None) -> Path:
    """
    Get the .gitignore path for the project.
    
    Args:
        project_root: Project root path. If None, searches for it.
    
    Returns:
        Path to .gitignore file
    """
    if project_root is None:
        project_root = find_project_root()
    else:
        project_root = Path(project_root).resolve()
    
    return project_root / ".gitignore"
