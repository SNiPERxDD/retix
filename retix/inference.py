"""
Core vision inference engine using MLX-VLM.
Handles model loading, caching, and inference execution.
"""

import time
import sys
import importlib
from pathlib import Path
from typing import Optional, Tuple, Any
import json

from PIL import Image

from retix.config import (
    MODEL_NAME,
    CACHE_DIR,
    DEFAULT_TEMPERATURE,
    MAX_TOKENS,
    TASK_TOKEN_LIMITS,
    ensure_cache_dir,
)
from retix.guardrails import InferenceResult, create_ocr_result, create_description_result
from retix.path_utils import resolve_image_path
from retix.image_preprocessing import downscale_image, cleanup_downscaled

# Lazy imports - don't import at module level to avoid dependency issues
mlx_vlm = None
mx = None
_import_error = None

QWEN3_VL_REGISTRY_KEYS = ("qwen3_vl",)
QWEN3_MODEL_TYPE_KEYS = ("qwen3_vl", "qwen3-vl", "qwen3vl")
QWEN3_MODULE_ALIASES = ("qwen3_vl",)
QWEN2_VL_MODULE_NAMES = ("qwen2_5_vl", "qwen2_vl", "qwen2vl")
QWEN2_VL_CLASS_NAMES = ("Model", "Qwen2VLModel", "Qwen2VisionModel")
REGISTRY_ATTRIBUTE_NAMES = ("MODEL_MAPPING", "MODEL_REGISTRY", "MODEL_CLASSES")


def _resolve_mlx_model_module(models_module: Any, module_name: str) -> Optional[Any]:
    """Resolve an MLX-VLM model module from attributes or dynamic import."""
    module_object = getattr(models_module, module_name, None)
    if module_object is not None:
        return module_object

    try:
        return importlib.import_module(f"mlx_vlm.models.{module_name}")
    except Exception:
        return None


def _find_qwen2_fallback_module_name(models_module: Any) -> Optional[str]:
    """Find the most compatible fallback module name for Qwen3 model types."""
    for module_name in QWEN2_VL_MODULE_NAMES:
        if _resolve_mlx_model_module(models_module, module_name) is not None:
            return module_name
    return None


def _find_qwen2_fallback(models_module: Any) -> Optional[Any]:
    """Find a Qwen2-VL fallback class or module inside mlx_vlm.models."""
    for module_name in QWEN2_VL_MODULE_NAMES:
        candidate_module = _resolve_mlx_model_module(models_module, module_name)
        if candidate_module is None:
            continue

        for class_name in QWEN2_VL_CLASS_NAMES:
            candidate_class = getattr(candidate_module, class_name, None)
            if candidate_class is not None:
                return candidate_class

    for class_name in QWEN2_VL_CLASS_NAMES:
        candidate_class = getattr(models_module, class_name, None)
        if candidate_class is not None:
            return candidate_class

    return None


def _inject_qwen3_registry_support(models_module: Any) -> bool:
    """Inject a Qwen3-VL registry alias when the installed MLX-VLM build lacks one."""
    fallback_model = _find_qwen2_fallback(models_module)
    if fallback_model is None:
        return False

    injected = False
    for registry_name in REGISTRY_ATTRIBUTE_NAMES:
        registry = getattr(models_module, registry_name, None)
        if not isinstance(registry, dict):
            continue

        for registry_key in QWEN3_VL_REGISTRY_KEYS:
            if registry_key not in registry:
                registry[registry_key] = fallback_model
                injected = True

    if not hasattr(models_module, "qwen3_vl"):
        fallback_module = None
        for module_name in QWEN2_VL_MODULE_NAMES:
            fallback_module = getattr(models_module, module_name, None)
            if fallback_module is not None:
                break

        setattr(models_module, "qwen3_vl", fallback_module or fallback_model)
        injected = True

    return injected


def _inject_qwen3_model_remapping(utils_module: Any, models_module: Any) -> bool:
    """Inject Qwen3 model-type remapping used by mlx_vlm.utils.get_model_and_args."""
    model_remapping = getattr(utils_module, "MODEL_REMAPPING", None)
    if not isinstance(model_remapping, dict):
        return False

    fallback_module_name = _find_qwen2_fallback_module_name(models_module)
    if fallback_module_name is None:
        return False

    injected = False
    for model_type_key in QWEN3_MODEL_TYPE_KEYS:
        if model_remapping.get(model_type_key) != fallback_module_name:
            model_remapping[model_type_key] = fallback_module_name
            injected = True

    fallback_module_object = getattr(models_module, fallback_module_name, None)
    if fallback_module_object is None:
        fallback_module_object = _resolve_mlx_model_module(
            models_module, fallback_module_name
        )

    if fallback_module_object is not None:
        for module_alias in QWEN3_MODULE_ALIASES:
            module_alias_key = f"mlx_vlm.models.{module_alias}"
            if module_alias_key not in sys.modules:
                sys.modules[module_alias_key] = fallback_module_object
                injected = True

    return injected


def _ensure_mlx_loaded() -> bool:
    """
    Lazy-load MLX-VLM dependencies.
    Must be called at runtime, not at module import time.
    
    Returns:
        True if successfully loaded, False if in mock mode or unavailable
    """
    global mlx_vlm, mx, _import_error
    
    if mlx_vlm is not None:
        return True  # Already loaded
    
    try:
        import mlx.core
        import mlx_vlm as mlx_vlm_module
        from mlx_vlm import models as mlx_models
        from mlx_vlm import utils as mlx_utils

        registry_injected = _inject_qwen3_registry_support(mlx_models)
        remapping_injected = _inject_qwen3_model_remapping(mlx_utils, mlx_models)
        if registry_injected or remapping_injected:
            sys.stderr.write("[FIX] Injected qwen3_vl compatibility mapping into mlx_vlm\n")
            sys.stderr.flush()
        
        mx = mlx.core
        mlx_vlm = mlx_vlm_module
        return True
    except Exception as e:
        _import_error = str(e)
        return False


class VisionEngine:
    """
    Core vision inference engine using MLX-VLM.
    Manages model loading, caching, and inference execution.
    """
    
    def __init__(self, model_name: str = MODEL_NAME, cache_dir: Optional[Path] = None, use_mock: bool = False):
        """
        Initialize the vision engine.
        
        Args:
            model_name: HuggingFace model identifier
            cache_dir: Directory for model caching. Defaults to ~/.cache/retix/
            use_mock: If True, use mock responses for testing (when MLX not available)
        
        Raises:
            ImportError: If mlx_vlm is not installed and use_mock is False
        """
        if mlx_vlm is None and not use_mock:
            raise ImportError(
                "MLX-VLM is not installed. Install with: pip install mlx-vlm"
            )
        
        self.model_name = model_name
        self.cache_dir = cache_dir or ensure_cache_dir()
        self.model = None
        self.processor = None
        self._load_start_time = None
        self.use_mock = use_mock or (mlx_vlm is None)
    
    def load_model(self) -> Tuple[Any, Any]:
        """
        Load the vision model and processor.
        
        Uses caching to avoid reloading. Logs to stderr to avoid interfering with output.
        
        Returns:
            Tuple of (model, processor) or (None, None) if using mock mode
        
        Raises:
            RuntimeError: If model loading fails (when not in mock mode)
        """
        if self.model is not None and self.processor is not None:
            return self.model, self.processor
        
        # In mock mode, return None tuple
        if self.use_mock:
            sys.stderr.write(f"[MOCK MODE] Model would be loaded: {self.model_name}\n")
            sys.stderr.flush()
            return None, None
        
        # Try to load real MLX-VLM
        if not _ensure_mlx_loaded():
            if not self.use_mock:
                self.use_mock = True
                sys.stderr.write(f"[WARNING] MLX not available, using mock mode\n")
                sys.stderr.flush()
            return None, None
        
        self._load_start_time = time.time()
        
        try:
            sys.stderr.write(f"Loading model: {self.model_name}\n")
            sys.stderr.flush()
            
            # Load model using MLX-VLM
            self.model, self.processor = mlx_vlm.load(self.model_name)
            
            load_time = time.time() - self._load_start_time
            sys.stderr.write(f"Model loaded in {load_time:.2f}s\n")
            sys.stderr.flush()
            
            return self.model, self.processor
        
        except Exception as e:
            sys.stderr.write(f"Error loading model: {str(e)}\n")
            sys.stderr.flush()
            raise RuntimeError(f"Failed to load vision model: {str(e)}") from e
    
    def run_inference(
        self,
        image_path: str,
        prompt: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
    ) -> InferenceResult:
        """
        Run inference on an image with a given prompt.
        
        Args:
            image_path: Path to the image file
            prompt: Text prompt for the model
            temperature: Sampling temperature (enforced to 0 for determinism)
            max_tokens: Maximum tokens to generate
        
        Returns:
            InferenceResult with model output and metadata
        
        Raises:
            FileNotFoundError: If image doesn't exist
            RuntimeError: If inference fails
        """
        # Resolve and validate image path
        resolved_path = resolve_image_path(image_path)
        
        # Auto-downscale high-resolution images (Pareto optimized)
        optimized_path = downscale_image(str(resolved_path), verbose=True)
        is_downscaled = optimized_path != str(resolved_path)
        
        # Load model if not already loaded
        model, processor = self.load_model()
        
        # Enforce temperature = 0 for deterministic results
        temperature = 0.0
        
        # Mock mode for testing without real GPU
        if self.use_mock:
            inference_start = time.time()
            sys.stderr.write(f"[MOCK] Generating response for: {resolved_path.name}\n")
            sys.stderr.flush()
            
            # Generate realistic mock output based on image
            mock_output = self._generate_mock_response(resolved_path, "UI description")
            
            inference_time = time.time() - inference_start
            sys.stderr.write(f"[MOCK] Response generated in {inference_time:.2f}s\n")
            sys.stderr.flush()
            
            metadata = {
                "image_path": str(resolved_path),
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "inference_time_ms": int(inference_time * 1000),
                "mode": "mock",
            }
            
            result = create_description_result(mock_output, metadata)
            return result
        
        try:
            inference_start = time.time()
            
            sys.stderr.write(f"Running inference on: {resolved_path.name}\n")
            sys.stderr.flush()
            
            # Ensure MLX is loaded
            if not _ensure_mlx_loaded():
                raise RuntimeError("MLX-VLM not available and not in mock mode")
            
            # Load the image (using optimized/downscaled path)
            image = Image.open(optimized_path).convert("RGB")
            
            # Prepare message in chat format for Qwen3-VL
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            
            # Apply chat template to get the formatted prompt
            formatted_prompt = processor.apply_chat_template(
                messages, 
                add_generation_prompt=True
            )
            
            # Run generation using MLX-VLM
            generation_result = mlx_vlm.generate(
                model=model,
                processor=processor,
                image=image,
                prompt=formatted_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                verbose=False
            )
            
            # Extract text from GenerationResult
            output_text = generation_result.text
            
            inference_time = time.time() - inference_start
            sys.stderr.write(f"Inference completed in {inference_time:.2f}s\n")
            sys.stderr.flush()
            
            # Get downscaled dimensions if applicable
            orig_dims = None
            downscaled_dims = None
            if is_downscaled:
                orig_img = Image.open(resolved_path)
                downscaled_img = Image.open(optimized_path)
                orig_dims = (orig_img.width, orig_img.height)
                downscaled_dims = (downscaled_img.width, downscaled_img.height)
                sys.stderr.write(
                    f"[OPTIMIZE] Resolution: {orig_dims[0]}x{orig_dims[1]} → {downscaled_dims[0]}x{downscaled_dims[1]}\n"
                )
                sys.stderr.flush()
            
            # Create result with metadata
            metadata = {
                "image_path": str(resolved_path),
                "optimized_path": optimized_path if is_downscaled else None,
                "original_resolution": orig_dims,
                "downscaled_resolution": downscaled_dims,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "inference_time_ms": int(inference_time * 1000),
                "prompt_tokens": generation_result.prompt_tokens,
                "generation_tokens": generation_result.generation_tokens,
                "prompt_tps": generation_result.prompt_tps,
                "generation_tps": generation_result.generation_tps,
            }
            
            result = create_description_result(output_text, metadata)
            
            # Clean up downscaled temp file if we created one
            if is_downscaled:
                cleanup_downscaled(optimized_path)
            
            return result
        
        except Exception as e:
            # Clean up downscaled temp file if we created one
            if is_downscaled:
                cleanup_downscaled(optimized_path)
            sys.stderr.write(f"Inference error: {str(e)}\n")
            sys.stderr.flush()
            raise RuntimeError(f"Inference failed: {str(e)}") from e
    
    def _generate_mock_response(self, image_path: Path, task_type: str) -> str:
        """Generate a realistic mock response for testing."""
        filename = image_path.name
        
        if task_type == "UI description":
            return (
                f"This is a user interface screenshot from '{filename}'. "
                "The interface contains a login form with the following elements:\n\n"
                "1. A header text that reads 'Login Form'\n"
                "2. An email input field labeled 'Email:'\n"
                "3. A password input field labeled 'Password:'\n"
                "4. A green button labeled 'Login' centered at the bottom\n\n"
                "The layout is clean and simple, using a white background with blue input borders. "
                "The login button is prominently displayed and appears clickable. "
                "Overall, this appears to be a standard web or application login interface."
            )
        elif task_type == "OCR":
            return "Login Form\nEmail:\nPassword:\nLogin"
        elif task_type == "verify":
            return "YES"
        else:
            return f"Mock response for {task_type} on {filename}"
    
    def run_ocr(
        self,
        image_path: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = None,
    ) -> InferenceResult:
        """
        Run OCR (text extraction) on an image.
        
        Args:
            image_path: Path to the image file
            temperature: Sampling temperature (enforced to 0)
            max_tokens: Maximum tokens to generate (uses task-specific default if None)
        
        Returns:
            InferenceResult with extracted text and confidence
        """
        # Use task-specific token limit
        if max_tokens is None:
            max_tokens = TASK_TOKEN_LIMITS.get("ocr", 256)
        
        ocr_prompt = (
            "Extract all visible text from this image. "
            "Return only the text content in a structured format, "
            "one line per text element."
        )
        
        if self.use_mock:
            # Mock OCR response
            sys.stderr.write("[MOCK] Extracting text via OCR\n")
            sys.stderr.flush()
            resolved_path = resolve_image_path(image_path)
            mock_output = self._generate_mock_response(resolved_path, "OCR")
            ocr_result = create_ocr_result(mock_output, {"image_path": str(resolved_path), "mode": "mock"})
            return ocr_result
        
        result = self.run_inference(
            image_path=image_path,
            prompt=ocr_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Re-evaluate confidence for OCR task
        ocr_result = create_ocr_result(result.text, result.raw_metadata)
        return ocr_result
    
    def verify_claim(
        self,
        image_path: str,
        claim: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = None,
    ) -> Tuple[Optional[bool], float]:
        """
        Verify if a claim is true about an image (boolean check).
        
        Args:
            image_path: Path to the image file
            claim: Claim to verify (e.g., "the button is red")
            temperature: Sampling temperature (enforced to 0)
            max_tokens: Maximum tokens (limited for boolean response, uses task-specific default if None)
        
        Returns:
            Tuple of (is_true: bool or None, confidence: float)
        """
        # Use task-specific token limit
        if max_tokens is None:
            max_tokens = TASK_TOKEN_LIMITS.get("verify", 10)
        
        verify_prompt = f"Is this true about the image: {claim}? Answer YES or NO only."
        
        if self.use_mock:
            # Mock verification
            sys.stderr.write(f"[MOCK] Verifying claim: {claim}\n")
            sys.stderr.flush()
            
            # Simple mock logic: if claim mentions known elements, return YES
            claim_lower = claim.lower()
            if "login" in claim_lower or "button" in claim_lower:
                return True, 0.85
            elif "red" in claim_lower or "missing" in claim_lower:
                return False, 0.85
            else:
                return None, 0.5
        
        result = self.run_inference(
            image_path=image_path,
            prompt=verify_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Parse YES/NO response
        response_upper = result.text.strip().upper()
        if "YES" in response_upper:
            return True, result.confidence
        elif "NO" in response_upper:
            return False, result.confidence
        else:
            return None, 0.3


# Global singleton instance
_engine_instance: Optional[VisionEngine] = None


def _resolve_default_model_name() -> str:
    """Resolve default model from configuration with safe fallback."""
    try:
        from retix.project_config import load_config

        config = load_config()
        configured_model = config.get("model")
        if isinstance(configured_model, str) and configured_model.strip():
            return configured_model.strip()
    except Exception:
        pass
    return MODEL_NAME


def get_vision_engine(model_name: Optional[str] = None, use_mock: bool = False) -> VisionEngine:
    """
    Get or create the global vision engine instance.
    
    Args:
        model_name: Model to load. If omitted, resolves from RETIX config.
        use_mock: If True, use mock mode for testing without GPU
    
    Returns:
        VisionEngine instance
    """
    global _engine_instance

    resolved_model_name = model_name or _resolve_default_model_name()
    
    # Auto-enable mock if MLX is not available AND not explicitly disabled
    auto_mock = use_mock or not _ensure_mlx_loaded()
    
    if _engine_instance is None or _engine_instance.model_name != resolved_model_name:
        _engine_instance = VisionEngine(model_name=resolved_model_name, use_mock=auto_mock)
    
    return _engine_instance


def reset_engine() -> None:
    """Reset the global engine instance."""
    global _engine_instance
    _engine_instance = None
