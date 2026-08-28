from __future__ import annotations

import hashlib
from pathlib import Path


def checked_target(path: Path, expected_sha256: str, label: str) -> Path:
    source = path.read_bytes().replace(b"\r\n", b"\n")
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SystemExit(f"Unsupported RAGFlow {label}: expected {expected_sha256}, got {actual_sha256}")
    return path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one {label} site")
    return text.replace(old, new)
