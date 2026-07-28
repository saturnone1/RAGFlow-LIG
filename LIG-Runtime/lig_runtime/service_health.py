from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380").rstrip("/")
    request = Request(f"{base_url}/api/v1/system/status")
    api_key = os.getenv("RAGFLOW_MCP_HOST_API_KEY", "")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen(request, timeout=10) as response:
            if response.status != 200:
                return 1
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return 1
    code = payload.get("code", -1) if isinstance(payload, dict) else -1
    try:
        if int(code) != 0:
            return 1
    except (TypeError, ValueError):
        return 1
    data = payload.get("data", {})
    dependencies = ("database", "doc_engine", "redis", "storage")
    return 0 if all(data.get(name, {}).get("status") == "green" for name in dependencies) else 1


if __name__ == "__main__":
    sys.exit(main())
