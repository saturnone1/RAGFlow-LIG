"""GPU capability checks shared by the LIG RAGFlow runtime.

The checks intentionally avoid importing or installing PyTorch. RAGFlow's OCR
paths use ONNX Runtime, so CUDA is usable only when both its CUDA provider and
an NVIDIA device exposed to the container are present.
"""

from __future__ import annotations

import logging
import subprocess


def nvidia_device_ids() -> tuple[int, ...]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader,nounits"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logging.info("NVIDIA device detection unavailable: %s", error)
        return ()

    if result.returncode != 0:
        logging.info("nvidia-smi returned %s: %s", result.returncode, result.stderr.strip())
        return ()

    device_ids = []
    for line in result.stdout.splitlines():
        try:
            device_ids.append(int(line.strip()))
        except ValueError:
            continue
    return tuple(device_ids)


def onnx_cuda_available(device_id: int = 0) -> bool:
    try:
        import onnxruntime as ort
    except ImportError:
        return False
    return "CUDAExecutionProvider" in ort.get_available_providers() and device_id in nvidia_device_ids()


def onnx_cuda_device_count() -> int:
    try:
        import onnxruntime as ort
    except ImportError:
        return 0
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return 0
    return len(nvidia_device_ids())
