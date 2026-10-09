"""
Launcher for the PhishGuard API and dashboard.
Prints the real status of each component, then starts the FastAPI server with Uvicorn.
"""

import sys
import socket

# Ensure UTF-8 encoding for Windows standard output safety
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import uvicorn
from component_status import component_registry


def find_available_port(start_port: int = 8000, max_tries: int = 10) -> int:
    """Finds an available open TCP port starting from start_port."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start_port


def print_component_status(port: int):
    print("=" * 70)
    print("  PhishGuard AI - phishing website analysis (development build)")
    print("=" * 70)
    for comp in component_registry():
        print(f"  [{comp['status']:<15}] {comp['name']}")
    print("-" * 70)
    print("  No trained detection model is available yet; scans return no verdict.")
    print(f"  Dashboard UI:  http://127.0.0.1:{port}")
    print(f"  REST API docs: http://127.0.0.1:{port}/docs")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    target_port = find_available_port(8000, 20)
    print_component_status(target_port)
    uvicorn.run("api:app", host="127.0.0.1", port=target_port, reload=False)
