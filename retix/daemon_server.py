"""
Daemon mode for retix.
Keeps the model in memory for sub-500ms response times on subsequent requests.
Uses Unix sockets for communication between CLI client and daemon server.
"""

import socket
import json
import sys
import time
import os
import signal
import gc
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess

from retix.config import (
    SOCKET_FILE,
    PID_FILE,
    SOCKET_DIR,
    DAEMON_SHUTDOWN_TIMEOUT_SEC,
    ensure_socket_dir,
)
from retix.inference import get_vision_engine


class DaemonServer:
    """
    Background daemon that keeps the vision model in memory.
    Communicates with CLI client via Unix socket.
    """
    
    def __init__(self, socket_path: Path = SOCKET_FILE):
        """
        Initialize daemon server.
        
        Args:
            socket_path: Path to the Unix socket
        """
        self.socket_path = socket_path
        self.engine = None
        self.running = False
    
    def start(self) -> None:
        """
        Start the daemon server.
        Binds to Unix socket and enters request loop.
        """
        ensure_socket_dir()
        
        # Remove old socket if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        # Create Unix domain socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(self.socket_path))
        
        # Set socket permissions to 600 (owner read/write only) for security
        # Prevents other users from snooping on screenshots in multi-user setups
        os.chmod(str(self.socket_path), 0o600)
        
        sock.listen(1)
        
        # Write PID file
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))
        
        self.running = True
        sys.stderr.write(f"Daemon started. Socket: {self.socket_path}\n")
        sys.stderr.flush()
        
        # Pre-load the model
        sys.stderr.write("Pre-loading vision model...\n")
        sys.stderr.flush()
        self.engine = get_vision_engine()
        self.engine.load_model()
        
        # Handle signals
        signal.signal(signal.SIGTERM, lambda s, f: self.shutdown())
        signal.signal(signal.SIGINT, lambda s, f: self.shutdown())
        
        try:
            while self.running:
                try:
                    connection, client_address = sock.accept()
                    self._handle_connection(connection)
                except KeyboardInterrupt:
                    break
        finally:
            sock.close()
            self.socket_path.unlink(missing_ok=True)
            PID_FILE.unlink(missing_ok=True)
    
    def _handle_connection(self, connection: socket.socket) -> None:
        """
        Handle a single client request.
        
        Args:
            connection: Socket connection from client
        """
        try:
            data = connection.recv(8192).decode("utf-8")
            request = json.loads(data)
            
            response = self._process_request(request)
            
            connection.sendall(json.dumps(response).encode("utf-8"))
        except Exception as e:
            sys.stderr.write(f"Error handling connection: {str(e)}\n")
            sys.stderr.flush()
            connection.sendall(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            connection.close()
            self._clear_runtime_cache()

    def _clear_runtime_cache(self) -> None:
        """Release MLX and Python-managed memory after each request."""
        try:
            import mlx.core as mx

            metal_backend = getattr(mx, "metal", None)
            if metal_backend is not None and hasattr(metal_backend, "clear_cache"):
                metal_backend.clear_cache()
        except Exception:
            pass

        gc.collect()
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a client request.
        
        Args:
            request: Request dictionary with 'command' and parameters
        
        Returns:
            Response dictionary
        """
        command = request.get("command")
        
        if command == "describe":
            image_path = request.get("image_path")
            prompt = request.get("prompt")
            result = self.engine.run_inference(image_path, prompt)
            return {
                "success": True,
                "output": result.text,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "metadata": result.raw_metadata,
            }
        
        elif command == "ocr":
            image_path = request.get("image_path")
            result = self.engine.run_ocr(image_path)
            return {
                "success": True,
                "output": result.text,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "metadata": result.raw_metadata,
            }
        
        elif command == "verify":
            image_path = request.get("image_path")
            claim = request.get("claim")
            verified, confidence = self.engine.verify_claim(image_path, claim)
            return {
                "success": True,
                "verified": verified,
                "confidence": confidence,
            }
        
        else:
            return {"success": False, "error": f"Unknown command: {command}"}
    
    def shutdown(self) -> None:
        """Gracefully shutdown the daemon."""
        sys.stderr.write("Shutting down daemon...\n")
        sys.stderr.flush()
        self.engine = None
        gc.collect()
        self.running = False


class DaemonClient:
    """
    Client for communicating with the vision daemon.
    """
    
    def __init__(self, socket_path: Path = SOCKET_FILE):
        """
        Initialize daemon client.
        
        Args:
            socket_path: Path to the Unix socket
        """
        self.socket_path = socket_path
    
    def is_running(self) -> bool:
        """
        Check if daemon is running.
        Handles stale socket files that can occur when daemon crashes or macOS sleeps.
        
        Returns:
            True if daemon socket is accessible and responsive
        """
        if not self.socket_path.exists():
            return False
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)  # 1 second timeout to quickly detect stale sockets
            sock.connect(str(self.socket_path))
            sock.close()
            return True
        except (socket.error, ConnectionRefusedError, socket.timeout):
            # Socket file exists but daemon is not responding (stale socket)
            # Clean it up so a new daemon can be started fresh
            try:
                self.socket_path.unlink()
            except Exception:
                pass
            return False
    
    def send_request(self, request: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """
        Send a request to the daemon.
        
        Args:
            request: Request dictionary
            timeout: Socket timeout in seconds
        
        Returns:
            Response dictionary
        
        Raises:
            ConnectionError: If daemon is not running
        """
        if not self.is_running():
            raise ConnectionError("Vision daemon is not running. Start with: retix daemon start")
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(str(self.socket_path))
            
            # Send request
            sock.sendall(json.dumps(request).encode("utf-8"))
            
            # Receive response
            response_data = sock.recv(65536).decode("utf-8")
            sock.close()
            
            return json.loads(response_data)
        
        except socket.timeout:
            raise ConnectionError("Daemon request timed out")
        except Exception as e:
            raise ConnectionError(f"Daemon communication error: {str(e)}") from e


def start_daemon_background() -> None:
    """Start the daemon as a background process (detached)."""
    # Use subprocess to start daemon in background
    subprocess.Popen(
        [sys.executable, "-m", "retix.daemon_server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent process
    )
    
    # Wait a moment for daemon to start
    time.sleep(1)


def stop_daemon() -> None:
    """Stop the running daemon with deterministic cleanup."""
    if not PID_FILE.exists():
        SOCKET_FILE.unlink(missing_ok=True)
        return

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        SOCKET_FILE.unlink(missing_ok=True)
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        SOCKET_FILE.unlink(missing_ok=True)
        return

    deadline = time.time() + DAEMON_SHUTDOWN_TIMEOUT_SEC
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
            time.sleep(0.2)
        except ProcessLookupError:
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    PID_FILE.unlink(missing_ok=True)
    SOCKET_FILE.unlink(missing_ok=True)


def get_daemon_status() -> Dict[str, Any]:
    """Get daemon status."""
    client = DaemonClient()
    
    if client.is_running():
        return {
            "status": "running",
            "socket": str(SOCKET_FILE),
            "pid_file": str(PID_FILE),
        }
    else:
        return {
            "status": "stopped",
            "socket": str(SOCKET_FILE),
        }


# Entry point for daemon subprocess
if __name__ == "__main__":
    server = DaemonServer()
    server.start()
