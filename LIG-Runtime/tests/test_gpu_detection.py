from __future__ import annotations

import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from lig_runtime import gpu_detection


class GpuDetectionTests(unittest.TestCase):
    def test_nvidia_smi_is_invoked_without_a_shell(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="0\n2\n", stderr="")
        with patch.object(gpu_detection.subprocess, "run", return_value=completed) as run:
            self.assertEqual(gpu_detection.nvidia_device_ids(), (0, 2))

        args, kwargs = run.call_args
        self.assertEqual(args[0][0], "nvidia-smi")
        self.assertNotIn("shell", kwargs)

    def test_cuda_requires_provider_and_visible_device(self) -> None:
        onnxruntime = types.SimpleNamespace(get_available_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": onnxruntime}), patch.object(
            gpu_detection, "nvidia_device_ids", return_value=(0,)
        ):
            self.assertTrue(gpu_detection.onnx_cuda_available(0))
            self.assertFalse(gpu_detection.onnx_cuda_available(1))
            self.assertEqual(gpu_detection.onnx_cuda_device_count(), 1)

    def test_cpu_provider_never_reports_cuda(self) -> None:
        onnxruntime = types.SimpleNamespace(get_available_providers=lambda: ["CPUExecutionProvider"])
        with patch.dict(sys.modules, {"onnxruntime": onnxruntime}), patch.object(
            gpu_detection, "nvidia_device_ids", return_value=(0,)
        ):
            self.assertFalse(gpu_detection.onnx_cuda_available(0))
            self.assertEqual(gpu_detection.onnx_cuda_device_count(), 0)


if __name__ == "__main__":
    unittest.main()
