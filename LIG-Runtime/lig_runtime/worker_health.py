"""Container health probe for isolated task executors without a shell."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    for cmdline_path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            command = cmdline_path.read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if b"rag/svr/task_executor.py" in command:
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
