"""
Tests for retix.main CLI module.
"""

import pytest
from click.testing import CliRunner
from retix.main import cli


def test_cli_version():
    """Test version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_cli_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    
    assert result.exit_code == 0
    assert "describe" in result.output.lower()
    assert "ocr" in result.output.lower()
    assert "check" in result.output.lower()


def test_daemon_help():
    """Test daemon help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    
    assert result.exit_code == 0
    assert "start" in result.output.lower()
    assert "stop" in result.output.lower()


def test_describe_help():
    """Test describe command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["describe", "--help"])
    
    assert result.exit_code == 0
    assert "describe" in result.output.lower()


def test_ocr_help():
    """Test OCR command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["ocr", "--help"])
    
    assert result.exit_code == 0
    assert "ocr" in result.output.lower()


def test_check_help():
    """Test check command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--help"])
    
    assert result.exit_code == 0
    assert "verify" in result.output.lower()


def test_version_command():
    """Test version subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    
    assert result.exit_code == 0
    assert "retix" in result.output or "version" in result.output.lower()
