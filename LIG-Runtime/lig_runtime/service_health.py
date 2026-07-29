from __future__ import annotations

import os
import sys
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380").rstrip("/")
    try:
        with urlopen(f"{base_url}/api/v1/system/ping", timeout=10) as response:
            return 0 if response.status == 200 and response.read(16).strip() == b"pong" else 1
    except (URLError, TimeoutError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
