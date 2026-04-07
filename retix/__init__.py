"""RETIX package root.

RETIX provides local vision capabilities for autonomous coding agents.
"""

__version__ = "1.2.6"
__author__ = "Vision Team"
__license__ = "MIT"

from retix.inference import VisionEngine, get_vision_engine
from retix.daemon_server import DaemonServer, DaemonClient

__all__ = [
    "VisionEngine",
    "get_vision_engine",
    "DaemonServer",
    "DaemonClient",
]
