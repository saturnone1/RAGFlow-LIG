from __future__ import annotations

import os
import socket
import sys
from urllib.error import URLError
from urllib.request import urlopen


def api_ready(base_url: str) -> bool:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/v1/system/ping", timeout=10) as response:
            return response.status == 200 and response.read(16).strip() == b"pong"
    except (URLError, TimeoutError, OSError):
        return False


def tcp_ready(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


def main() -> int:
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")
    mcp_host = os.getenv("RAGFLOW_MCP_HEALTH_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("RAGFLOW_MCP_PORT", "9382"))
    return 0 if api_ready(base_url) and tcp_ready(mcp_host, mcp_port) else 1


if __name__ == "__main__":
    sys.exit(main())
