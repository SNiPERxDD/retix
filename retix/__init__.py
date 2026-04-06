"""RETIX package root.

RETIX provides local vision capabilities for autonomous coding agents.
"""

__version__ = "1.2.0"
__author__ = "Vision Team"
__license__ = "MIT"

from retix.inference import VisionEngine, get_vision_engine
from retix.skill_generator import ensure_skill_exists
from retix.daemon_server import DaemonServer, DaemonClient

__all__ = [
    "VisionEngine",
    "get_vision_engine",
    "ensure_skill_exists",
    "DaemonServer",
    "DaemonClient",
]
