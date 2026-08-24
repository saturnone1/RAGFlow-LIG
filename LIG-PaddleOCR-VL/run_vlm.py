"""Start the PaddleOCR-VL VLM backend without a command shell."""

from __future__ import annotations

import os
from pathlib import Path


def positive_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


utilization = float(os.environ.get("PADDLEOCR_VL_GPU_MEMORY_UTILIZATION", "0.60"))
if not 0 < utilization < 1:
    raise ValueError("PADDLEOCR_VL_GPU_MEMORY_UTILIZATION must be between 0 and 1")

config_path = Path("/tmp/lig-vllm-backend.yaml")
config_path.write_text(
    "\n".join(
        [
            f"gpu-memory-utilization: {utilization}",
            f"max-model-len: {positive_int('PADDLEOCR_VL_MAX_MODEL_LEN', 16384)}",
            f"max-num-batched-tokens: {positive_int('PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS', 16384)}",
            f"max-num-seqs: {positive_int('PADDLEOCR_VL_MAX_NUM_SEQS', 8)}",
            f"api-server-count: {positive_int('PADDLEOCR_VL_API_SERVER_COUNT', 1)}",
            "enforce-eager: true",
            "",
        ]
    ),
    encoding="utf-8",
)

os.execvp(
    "paddleocr",
    [
        "paddleocr",
        "genai_server",
        "--model_name",
        "PaddleOCR-VL-1.6-0.9B",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--backend",
        "vllm",
        "--backend_config",
        str(config_path),
    ],
)
