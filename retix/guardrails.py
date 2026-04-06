"""
Guardrails for hallucination prevention and result quality assurance.
Implements confidence checking, temperature enforcement, and validation logic.
"""

import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from retix.config import (
    DEFAULT_TEMPERATURE,
    OCR_CONFIDENCE_THRESHOLD,
    WARNING_THRESHOLD,
)


@dataclass
class InferenceResult:
    """Structured inference result with metadata."""
    
    text: str
    confidence: float = 1.0
    has_warnings: bool = False
    warnings: list[str] = None
    raw_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.raw_metadata is None:
            self.raw_metadata = {}
    
    def to_output(self, include_warnings: bool = True) -> str:
        """
        Convert result to output format.
        
        Args:
            include_warnings: Whether to include warnings in the output
        
        Returns:
            Formatted output string
        """
        output = self.text
        
        if include_warnings and self.warnings:
            warning_text = "\n".join(f"[WARNING: {w}]" for w in self.warnings)
            output = f"{output}\n\n{warning_text}"
        
        return output


def validate_temperature(temperature: float) -> float:
    """
    Enforce temperature constraints for grounded results.
    
    The model must use temperature=0 for deterministic, hallucination-resistant output.
    
    Args:
        temperature: Requested temperature value
    
    Returns:
        Validated and potentially adjusted temperature
    """
    if temperature > DEFAULT_TEMPERATURE:
        # Log that we're overriding
        return DEFAULT_TEMPERATURE
    
    return temperature


def estimate_ocr_confidence(text: str, original_image_size: Tuple[int, int] = None) -> float:
    """
    Estimate confidence score for OCR task.
    
    Uses heuristics to detect potential hallucinations in text extraction.
    
    Args:
        text: Extracted text from model
        original_image_size: Tuple of (width, height) for context
    
    Returns:
        Confidence score between 0 and 1
    """
    if not text or len(text.strip()) == 0:
        return 0.3  # Low confidence for empty results
    
    # Check for reasonable text patterns
    confidence = 1.0
    
    # Penalize very short results (possible incomplete extraction)
    if len(text.strip()) < 5:
        confidence *= 0.7
    
    # Check for excessive repetition (hallucination marker)
    words = text.split()
    if len(words) > 0:
        unique_words = len(set(words))
        repetition_ratio = unique_words / len(words)
        if repetition_ratio < 0.3:  # More than 70% repetition
            confidence *= 0.5
    
    # Check for nonsensical character sequences
    if has_suspicious_patterns(text):
        confidence *= 0.6
    
    return max(0.0, min(1.0, confidence))


def has_suspicious_patterns(text: str) -> bool:
    """
    Detect suspicious patterns that might indicate hallucination.
    
    Args:
        text: Text to check
    
    Returns:
        True if suspicious patterns are detected
    """
    # Pattern: excessive special characters (suspicious)
    special_char_ratio = sum(1 for c in text if not c.isalnum() and c not in " \n\t-_./()[]{}") / max(len(text), 1)
    if special_char_ratio > 0.3:
        return True
    
    # Pattern: lines that are just noise
    lines = text.split("\n")
    noise_lines = sum(1 for line in lines if re.match(r"^[^a-zA-Z0-9]*$", line.strip()))
    if len(lines) > 5 and noise_lines / len(lines) > 0.5:
        return True
    
    return False


def create_ocr_result(text: str, metadata: Dict[str, Any] = None) -> InferenceResult:
    """
    Create an OCR inference result with confidence checking.
    
    Args:
        text: Extracted text
        metadata: Optional metadata dictionary
    
    Returns:
        InferenceResult with confidence and warnings
    """
    confidence = estimate_ocr_confidence(text)
    warnings = []
    
    if confidence < WARNING_THRESHOLD:
        warnings.append("High uncertainty on text extraction. Verify manually if critical.")
    
    return InferenceResult(
        text=text,
        confidence=confidence,
        has_warnings=len(warnings) > 0,
        warnings=warnings,
        raw_metadata=metadata or {},
    )


def create_description_result(text: str, metadata: Dict[str, Any] = None) -> InferenceResult:
    """
    Create a description inference result.
    
    Args:
        text: Generated description
        metadata: Optional metadata dictionary
    
    Returns:
        InferenceResult
    """
    return InferenceResult(
        text=text,
        confidence=0.95,  # Higher confidence for descriptions
        has_warnings=False,
        warnings=[],
        raw_metadata=metadata or {},
    )


def parse_verification_response(response: str) -> Tuple[bool, float]:
    """
    Parse model response for verification tasks.
    
    Expected format: "YES" or "NO" with optional confidence.
    
    Args:
        response: Model response text
    
    Returns:
        Tuple of (verified: bool, confidence: float)
    """
    response_upper = response.strip().upper()
    
    # Look for YES or NO in the response
    if "YES" in response_upper:
        return True, 0.9
    elif "NO" in response_upper:
        return False, 0.9
    else:
        # Ambiguous response
        return None, 0.3
