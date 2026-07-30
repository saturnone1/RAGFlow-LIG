"""Resource-aware admission helpers for document ingestion."""

from __future__ import annotations

import os
from pathlib import Path


def available_memory_bytes() -> int:
    """Return the tightest host/cgroup memory availability visible to this process."""
    candidates: list[int] = []
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            name, value = line.split(":", 1)
            values[name] = int(value.strip().split()[0]) * 1024
        if values.get("MemAvailable", 0) > 0:
            candidates.append(values["MemAvailable"])
    except (OSError, ValueError, KeyError):
        pass

    try:
        limit_text = Path("/sys/fs/cgroup/memory.max").read_text(encoding="ascii").strip()
        if limit_text != "max":
            limit = int(limit_text)
            current = int(Path("/sys/fs/cgroup/memory.current").read_text(encoding="ascii").strip())
            candidates.append(max(0, limit - current))
    except (OSError, ValueError):
        pass

    try:
        limit = int(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes").read_text(encoding="ascii").strip())
        current = int(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes").read_text(encoding="ascii").strip())
        if 0 < limit < 2**60:
            candidates.append(max(0, limit - current))
    except (OSError, ValueError):
        pass

    return min(candidates) if candidates else 2**63 - 1


def adaptive_pdf_task_page_size(configured_max: int) -> int:
    """Choose a non-rejecting PDF task size from current memory and parser concurrency."""
    configured_max = max(1, int(configured_max))
    workers = max(1, int(os.environ.get("TASK_EXECUTOR_WORKERS", "1")))
    parser_concurrency = max(1, int(os.environ.get("MAX_CONCURRENT_CHUNK_BUILDERS", "1")))
    estimated_page_bytes = max(
        1,
        int(os.environ.get("LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE", str(96 * 1024 * 1024))),
    )
    reserve_bytes = max(
        0,
        int(os.environ.get("LIG_INGESTION_MEMORY_RESERVE_BYTES", str(1024 * 1024 * 1024))),
    )
    memory_percent = min(100, max(1, int(os.environ.get("LIG_INGESTION_MEMORY_PERCENT", "25"))))
    available = max(0, available_memory_bytes() - reserve_bytes) * memory_percent // 100
    per_parser = available // (workers * parser_concurrency)
    memory_pages = max(1, per_parser // estimated_page_bytes)
    return min(configured_max, memory_pages)
