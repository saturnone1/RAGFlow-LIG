"""Resource-aware admission helpers for document ingestion."""

from __future__ import annotations

import logging
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
    adaptive_enabled = os.environ.get("ADAPTIVE_PDF_TASK_PAGE_SIZE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not adaptive_enabled:
        logging.info("PDF task page size %s (fixed; adaptive sizing disabled)", configured_max)
        return configured_max
    workers = max(1, int(os.environ.get("TASK_EXECUTOR_WORKERS", "1")))
    task_concurrency = max(1, int(os.environ.get("MAX_CONCURRENT_TASKS", "1")))
    chunk_concurrency = max(1, int(os.environ.get("MAX_CONCURRENT_CHUNK_BUILDERS", "1")))
    # A worker cannot run more parsers than either its task slots or its chunk
    # slots. Using the chunk limit alone overestimates memory pressure whenever
    # MAX_CONCURRENT_TASKS is lower and needlessly shrinks PDF page ranges.
    parser_concurrency = min(task_concurrency, chunk_concurrency)
    estimated_page_bytes = max(
        1,
        int(os.environ.get("LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE", str(96 * 1024 * 1024))),
    )
    reserve_bytes = max(
        0,
        int(os.environ.get("LIG_INGESTION_MEMORY_RESERVE_BYTES", str(1024 * 1024 * 1024))),
    )
    memory_percent = min(100, max(1, int(os.environ.get("LIG_INGESTION_MEMORY_PERCENT", "25"))))
    visible_bytes = available_memory_bytes()
    available = max(0, visible_bytes - reserve_bytes) * memory_percent // 100
    per_parser = available // (workers * parser_concurrency)
    memory_pages = max(1, per_parser // estimated_page_bytes)
    chosen = min(configured_max, memory_pages)
    # Whichever of the two bounds wins decides the page batch, and the memory
    # one moves with whatever else is resident. Without this line there is no
    # way to tell a configured limit from a memory-starved one after the fact.
    logging.info(
        "PDF task page size %s (configured max %s, memory allows %s; "
        "visible %.1f GiB, reserve %.1f GiB, %s%% budget, %s worker(s) x %s parser(s))",
        chosen,
        configured_max,
        memory_pages,
        visible_bytes / 1024**3,
        reserve_bytes / 1024**3,
        memory_percent,
        workers,
        parser_concurrency,
    )
    return chosen
