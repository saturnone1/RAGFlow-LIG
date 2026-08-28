from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lig_runtime import worker_health


class WorkerHealthTests(unittest.TestCase):
    def test_process_counts_python_and_go_workers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            commands = [
                b"python\0rag/svr/task_executor.py\0-i\0worker_0\0",
                b"python\0rag/svr/task_executor.py\0-i\0worker_1\0",
                b"bin/ragflow_server\0--ingestor\0",
            ]
            for process_id, command in enumerate(commands, start=100):
                process_directory = proc_root / str(process_id)
                process_directory.mkdir()
                (process_directory / "cmdline").write_bytes(command)

            self.assertEqual(worker_health.process_counts(proc_root), (2, 1))

    @patch("lig_runtime.worker_health.process_counts", return_value=(2, 0))
    def test_python_mode_requires_configured_worker_count(self, _counts) -> None:
        with patch.dict(os.environ, {"API_PROXY_SCHEME": "python", "TASK_EXECUTOR_WORKERS": "3"}, clear=False):
            self.assertEqual(worker_health.main(), 1)

        with patch.dict(os.environ, {"API_PROXY_SCHEME": "python", "TASK_EXECUTOR_WORKERS": "2"}, clear=False):
            self.assertEqual(worker_health.main(), 0)

    @patch("lig_runtime.worker_health.process_counts", return_value=(0, 3))
    def test_go_mode_accepts_go_ingestors(self, _counts) -> None:
        with patch.dict(os.environ, {"API_PROXY_SCHEME": "go", "TASK_EXECUTOR_WORKERS": "3"}, clear=False):
            self.assertEqual(worker_health.main(), 0)

    @patch("lig_runtime.worker_health.process_counts", return_value=(3, 2))
    def test_hybrid_mode_requires_both_worker_families(self, _counts) -> None:
        with patch.dict(os.environ, {"API_PROXY_SCHEME": "hybrid", "TASK_EXECUTOR_WORKERS": "3"}, clear=False):
            self.assertEqual(worker_health.main(), 1)


if __name__ == "__main__":
    unittest.main()
