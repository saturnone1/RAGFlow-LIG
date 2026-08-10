from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Callable

import requests


def invoke_layout_parsing(
    source_path: Path,
    optional_payload: dict[str, Any],
    upstream_url: str,
    timeout_seconds: float,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Call the official synchronous API and return its RAGFlow-compatible result."""
    encoded = base64.b64encode(source_path.read_bytes()).decode("ascii")
    # Parser options may tune OCR, but they must not replace the uploaded file
    # or make the service fetch an operator-supplied URL.
    payload = {**optional_payload, "file": encoded, "fileType": 0}
    response = post(
        f"{upstream_url.rstrip('/')}/layout-parsing",
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("errorCode", 0) != 0:
        raise RuntimeError(body.get("errorMsg") or "PaddleOCR-VL returned an error")
    result = body.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("PaddleOCR-VL response has no result object")
    return result
