#!/usr/bin/env python3
"""Apply the narrowly scoped LIG runtime patch to RAGFlow v0.26.4."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


EXPECTED_EMBEDDING_SHA256 = "b844aec1bd2bc49bb54e55beb7d6273a7da6cbd5cfe15b3e96fd7882e0b3e4eb"
EXPECTED_PADDLEOCR_SHA256 = "94b735a444ee81a03bcd7bd996851a7e3759ee95e14e0b8d838a5d59f68e6704"
EXPECTED_TASK_EXECUTOR_SHA256 = "389f45143dc98e3882545fdea8b18b1c4537e597448ae5b72cfed41a0305511a"
OLD_TIMEOUT = "headers={\"Content-Type\": \"application/json\"}, timeout=30)"
NEW_TIMEOUT = "headers={\"Content-Type\": \"application/json\"}, timeout=60)"
PADDLEOCR_PROGRESS_REPLACEMENTS = {
    'callback(0.9, f"[PaddleOCR] done, sections: {len(sections)}")':
        'callback(0.78, f"[PaddleOCR] done, sections: {len(sections)}")',
    'callback(1.0, f"[PaddleOCR] done, tables: {len(tables)}")':
        'callback(0.79, f"[PaddleOCR] done, tables: {len(tables)}")',
}
OLD_EMBEDDING_PROGRESS = (
    'callback(prog=0.7 + 0.2 * (i + 1) / len(cnts), msg="")'
)
NEW_EMBEDDING_PROGRESS = (
    "callback("
    "prog=0.7 + 0.2 * min(i + settings.EMBEDDING_BATCH_SIZE, len(cnts)) / len(cnts), "
    'msg="")'
)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: apply-runtime-patches.py <embedding_model.py> "
            "<paddleocr_parser.py> <task_executor.py>"
        )

    embedding_target = Path(sys.argv[1])
    source = embedding_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_EMBEDDING_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow embedding_model.py: "
            f"expected {EXPECTED_EMBEDDING_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    if text.count(OLD_TIMEOUT) != 2:
        raise SystemExit("Expected exactly two HuggingFace embedding timeout sites")

    embedding_target.write_text(
        text.replace(OLD_TIMEOUT, NEW_TIMEOUT), encoding="utf-8"
    )

    paddleocr_target = Path(sys.argv[2])
    source = paddleocr_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_PADDLEOCR_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow paddleocr_parser.py: "
            f"expected {EXPECTED_PADDLEOCR_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    for old_progress, new_progress in PADDLEOCR_PROGRESS_REPLACEMENTS.items():
        if text.count(old_progress) != 1:
            raise SystemExit(
                "Expected exactly one PaddleOCR terminal progress callback: "
                f"{old_progress}"
            )
        text = text.replace(old_progress, new_progress)
    paddleocr_target.write_text(text, encoding="utf-8")

    task_executor_target = Path(sys.argv[3])
    source = task_executor_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_TASK_EXECUTOR_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow task_executor.py: "
            f"expected {EXPECTED_TASK_EXECUTOR_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    if text.count(OLD_EMBEDDING_PROGRESS) != 1:
        raise SystemExit("Expected exactly one embedding progress calculation")
    task_executor_target.write_text(
        text.replace(OLD_EMBEDDING_PROGRESS, NEW_EMBEDDING_PROGRESS),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
