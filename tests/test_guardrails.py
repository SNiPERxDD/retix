"""
Tests for retix.guardrails module.
"""

import pytest
from retix.guardrails import (
    validate_temperature,
    estimate_ocr_confidence,
    has_suspicious_patterns,
    create_ocr_result,
    create_description_result,
    parse_verification_response,
    InferenceResult,
)


def test_validate_temperature():
    """Test temperature enforcement."""
    # Temperature should be clamped to 0
    assert validate_temperature(0.5) == 0.0
    assert validate_temperature(0.0) == 0.0
    assert validate_temperature(-0.1) == -0.1  # Though negative is unusual


def test_inference_result_creation():
    """Test creating InferenceResult."""
    result = InferenceResult(
        text="Test output",
        confidence=0.9,
        warnings=["Warning 1"],
    )
    
    assert result.text == "Test output"
    assert result.confidence == 0.9
    assert len(result.warnings) == 1


def test_inference_result_to_output():
    """Test InferenceResult output formatting."""
    result = InferenceResult(
        text="Test output",
        warnings=["Test warning"],
    )
    
    output = result.to_output(include_warnings=True)
    assert "Test output" in output
    assert "Test warning" in output
    assert "[WARNING:" in output


def test_estimate_ocr_confidence_valid():
    """Test OCR confidence estimation for valid text."""
    confidence = estimate_ocr_confidence("Hello World This is valid text")
    assert 0.0 <= confidence <= 1.0


def test_estimate_ocr_confidence_empty():
    """Test OCR confidence for empty text."""
    confidence = estimate_ocr_confidence("")
    assert confidence < 0.5  # Should be low confidence


def test_estimate_ocr_confidence_repetitive():
    """Test OCR confidence for highly repetitive text."""
    confidence = estimate_ocr_confidence("aaaa aaaa aaaa aaaa aaaa")
    assert confidence < 0.7  # Should penalize repetition


def test_has_suspicious_patterns():
    """Test suspicious pattern detection."""
    # Normal text should not be suspicious
    assert not has_suspicious_patterns("This is normal text")
    
    # Excessive special characters should be suspicious
    assert has_suspicious_patterns("!@#$%^&*()!@#$%^&*()")


def test_create_ocr_result():
    """Test creating OCR result."""
    result = create_ocr_result("Sample text")
    
    assert result.text == "Sample text"
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0


def test_create_description_result():
    """Test creating description result."""
    result = create_description_result("UI Description")
    
    assert result.text == "UI Description"
    assert result.confidence == 0.95
    assert not result.has_warnings


def test_parse_verification_yes():
    """Test parsing YES response."""
    verified, confidence = parse_verification_response("YES")
    assert verified is True
    assert confidence > 0.8


def test_parse_verification_no():
    """Test parsing NO response."""
    verified, confidence = parse_verification_response("NO")
    assert verified is False
    assert confidence > 0.8


def test_parse_verification_ambiguous():
    """Test parsing ambiguous response."""
    verified, confidence = parse_verification_response("Maybe")
    assert verified is None
    assert confidence < 0.5
