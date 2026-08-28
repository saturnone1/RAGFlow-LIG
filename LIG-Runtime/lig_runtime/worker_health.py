"""Container health probe for isolated task executors without a shell."""

from __future__ import annotations

import os
from pathlib import Path


def process_counts(proc_root: Path = Path("/proc")) -> tuple[int, int]:
    python_workers = 0
    go_workers = 0
    for cmdline_path in proc_root.glob("[0-9]*/cmdline"):
        try:
            command = cmdline_path.read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if b"rag/svr/task_executor.py" in command:
            python_workers += 1
        if b"bin/ragflow_server" in command and b"--ingestor" in command:
            go_workers += 1
    return python_workers, go_workers


def main() -> int:
    try:
        expected = int(os.environ.get("TASK_EXECUTOR_WORKERS", "1"))
    except ValueError:
        return 1
    if expected < 1:
        return 1

    scheme = os.environ.get("API_PROXY_SCHEME", "python").lower()
    python_workers, go_workers = process_counts()
    python_ready = scheme not in {"python", "hybrid"} or python_workers >= expected
    go_ready = scheme not in {"go", "hybrid"} or go_workers >= expected
    return 0 if python_ready and go_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
