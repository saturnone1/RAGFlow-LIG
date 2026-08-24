"""Start the PaddleOCR-VL layout pipeline without a command shell."""

from __future__ import annotations

import os


device = os.environ.get("PADDLEOCR_VL_PIPELINE_DEVICE", "cpu").strip().lower()
if device != "cpu":
    raise ValueError("PADDLEOCR_VL_PIPELINE_DEVICE must be cpu in this image")

os.execvp(
    "paddlex",
    [
        "paddlex",
        "--serve",
        "--pipeline",
        "/home/paddleocr/pipeline_config_vllm.yaml",
        "--device",
        device,
    ],
)
