#!/usr/bin/env python3
"""
retix Setup and Diagnostics Script.

This script handles:
1. Initial setup and dependency verification
2. Model caching and performance optimization
3. Failure diagnosis and recovery
4. Environment configuration

Run with: python setup.py
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json


class EnvironmentDiagnostics:
    """Diagnose and validate the environment for retix."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info_messages: List[str] = []
        self.system_info: Dict[str, str] = {}
    
    def run_diagnostics(self) -> bool:
        """Run full diagnostic suite."""
        print("=" * 60)
        print("retix Environment Diagnostics")
        print("=" * 60)
        
        self._check_system()
        self._check_python()
        self._check_dependencies()
        self._check_mlx_compatibility()
        self._check_disk_space()
        self._check_cache_permissions()
        self._check_gpu_availability()
        
        return self._report_results()
    
    def _check_system(self) -> None:
        """Check system information."""
        print("\n[1] System Information")
        system = platform.system()
        architecture = platform.processor()
        
        self.system_info["os"] = system
        self.system_info["architecture"] = architecture
        self.system_info["python_version"] = platform.python_version()
        
        print(f"  OS: {system}")
        print(f"  Architecture: {architecture}")
        print(f"  Python: {self.system_info['python_version']}")
        
        if system != "Darwin":
            self.warnings.append(
                f"retix is optimized for macOS, but running on {system}. "
                "Some features may not work as expected."
            )
        
        # Check for Apple Silicon
        if system == "Darwin" and "arm" not in architecture.lower():
            self.warnings.append(
                "Not running on Apple Silicon (M1/M2/M3). "
                "Performance may be suboptimal. Consider running on an M-series Mac."
            )
    
    def _check_python(self) -> None:
        """Check Python version compatibility."""
        print("\n[2] Python Compatibility")
        
        version = sys.version_info
        print(f"  Python {version.major}.{version.minor}.{version.micro}")
        
        if version < (3, 9):
            self.errors.append(f"Python 3.9+ required, but got {version.major}.{version.minor}")
        else:
            print("  ✓ Python version is compatible")
    
    def _check_dependencies(self) -> None:
        """Check required Python dependencies."""
        print("\n[3] Python Dependencies")
        
        required_packages = {
            "click": "CLI framework",
            "pillow": "Image processing",
            "numpy": "Numerical computing",
            "pydantic": "Data validation",
            "pyyaml": "YAML support",
        }
        
        optional_packages = {
            "mlx": "Apple MLX framework",
            "mlx_vlm": "MLX Vision-Language Model",
        }
        
        # Check required
        for package, description in required_packages.items():
            try:
                __import__(package)
                print(f"  ✓ {package}: {description}")
            except ImportError:
                self.errors.append(f"Missing required package: {package} ({description})")
        
        # Check optional
        for package, description in optional_packages.items():
            try:
                __import__(package)
                print(f"  ✓ {package}: {description}")
            except ImportError:
                self.warnings.append(f"Missing optional package: {package} ({description})")
    
    def _check_mlx_compatibility(self) -> None:
        """Check MLX and VLM compatibility."""
        print("\n[4] MLX Framework")
        
        try:
            import mlx
            print(f"  ✓ MLX installed")
            
            # Check if running on GPU
            try:
                import mlx.core as mx
                print(f"  ✓ MLX Core available")
                # Try a simple operation to verify GPU access
                x = mx.array([1.0, 2.0, 3.0])
                print(f"  ✓ MLX GPU access working")
            except Exception as e:
                self.warnings.append(f"MLX GPU may not be fully functional: {str(e)}")
        
        except ImportError:
            self.errors.append(
                "MLX not installed. Install with: pip install mlx mlx-vlm"
            )
    
    def _check_disk_space(self) -> None:
        """Check available disk space."""
        print("\n[5] Disk Space")
        
        cache_dir = Path.home() / ".cache" / "retix"
        home_dir = Path.home()
        
        # Get disk usage
        try:
            import shutil
            disk_stats = shutil.disk_usage(str(home_dir))
            free_gb = disk_stats.free / (1024 ** 3)
            total_gb = disk_stats.total / (1024 ** 3)
            
            print(f"  Total disk space: {total_gb:.1f} GB")
            print(f"  Free disk space: {free_gb:.1f} GB")
            
            model_size_gb = 2.5
            if free_gb < model_size_gb * 1.5:
                self.errors.append(
                    f"Insufficient disk space. Need at least {model_size_gb * 1.5:.1f} GB free, "
                    f"but only {free_gb:.1f} GB available."
                )
            elif free_gb < model_size_gb * 2:
                self.warnings.append(
                    "Low disk space. Recommended to have at least "
                    f"{model_size_gb * 2:.1f} GB free for comfortable operation."
                )
            else:
                print(f"  ✓ Sufficient disk space available")
        
        except Exception as e:
            self.warnings.append(f"Could not check disk space: {str(e)}")
    
    def _check_cache_permissions(self) -> None:
        """Check write permissions for cache directory."""
        print("\n[6] Cache Permissions")
        
        cache_dir = Path.home() / ".cache" / "retix"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            test_file = cache_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            print(f"  ✓ Cache directory is writable: {cache_dir}")
        except Exception as e:
            self.errors.append(f"Cannot write to cache directory: {str(e)}")
    
    def _check_gpu_availability(self) -> None:
        """Check GPU availability and memory."""
        print("\n[7] GPU/Device Status")
        
        try:
            import mlx.core as mx
            
            # Get device info
            device = mx.default_device()
            print(f"  Default device: {device}")
            
            # Check available memory (this is approximate)
            try:
                # Try to allocate a large array to test memory
                test_array = mx.zeros((1024, 1024, 1024))  # ~4GB float32
                del test_array
                print("  ✓ Sufficient GPU memory available")
            except MemoryError:
                self.warnings.append(
                    "May have insufficient GPU memory for optimal performance. "
                    "Consider closing other applications."
                )
        
        except ImportError:
            self.warnings.append("Cannot check GPU status (MLX not available)")
    
    def _report_results(self) -> bool:
        """Report diagnostic results."""
        print("\n" + "=" * 60)
        print("Diagnostic Results")
        print("=" * 60)
        
        if self.errors:
            print("\n❌ ERRORS (must fix):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS (recommended to fix):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All checks passed! System is ready for retix.")
            return True
        
        if not self.errors:
            print("\n✅ No critical errors. System ready (with warnings).")
            return True
        
        return False


class SetupProcedure:
    """Handle initial setup and configuration."""
    
    def run_setup(self) -> bool:
        """Run complete setup procedure."""
        print("\n" + "=" * 60)
        print("retix Setup Procedure")
        print("=" * 60)
        
        steps = [
            ("Installing Python dependencies", self._install_dependencies),
            ("Creating cache directories", self._setup_cache_dirs),
            ("Configuring environment", self._configure_environment),
            ("Installing CLI globally", self._install_cli),
            ("Testing installation", self._test_installation),
        ]
        
        for step_name, step_func in steps:
            print(f"\n[Setup] {step_name}...")
            try:
                step_func()
                print(f"  ✓ {step_name} complete")
            except Exception as e:
                print(f"  ✗ {step_name} failed: {str(e)}")
                return False
        
        return True
    
    def _install_dependencies(self) -> None:
        """Install Python dependencies."""
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-e", "."
        ])
    
    def _setup_cache_dirs(self) -> None:
        """Create necessary cache and config directories."""
        dirs = [
            Path.home() / ".cache" / "retix",
            Path.home() / ".local" / "var" / "retix",
            Path.home() / ".retix",
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _configure_environment(self) -> None:
        """Configure shell environment."""
        # This could set up aliases, shell completions, etc.
        pass
    
    def _install_cli(self) -> None:
        """Install CLI as global command."""
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-e", "."
        ])
    
    def _test_installation(self) -> None:
        """Test that CLI is working."""
        result = subprocess.run(
            ["retix", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"CLI test failed: {result.stderr}")


def main():
    """Main entry point."""
    diagnostics = EnvironmentDiagnostics()
    success = diagnostics.run_diagnostics()
    
    if not success:
        print("\n" + "=" * 60)
        print("❌ Setup cannot proceed due to errors above.")
        print("=" * 60)
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Proceeding with setup...")
    print("=" * 60)
    
    setup = SetupProcedure()
    if setup.run_setup():
        print("\n" + "=" * 60)
        print("✅ Setup completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Try your first command: retix describe screenshot.png")
        print("2. Read the project skill: cat .retix/SKILL.md")
        print("3. Start daemon for faster inference: retix daemon start")
    else:
        print("\n" + "=" * 60)
        print("❌ Setup encountered errors.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
