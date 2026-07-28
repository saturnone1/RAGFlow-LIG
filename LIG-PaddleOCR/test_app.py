from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app as ocr_app


class OcrJobLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        with ocr_app.jobs_lock:
            ocr_app.jobs.clear()

    def tearDown(self) -> None:
        with ocr_app.jobs_lock:
            ocr_app.jobs.clear()

    def test_cleanup_only_expires_terminal_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            running_file = Path(directory, "running.jsonl")
            done_file = Path(directory, "done.jsonl")
            running_file.touch()
            done_file.touch()
            expired = time.time() - ocr_app.JOB_TTL_SECONDS - 1
            with ocr_app.jobs_lock:
                ocr_app.jobs.update(
                    running={"state": "running", "updated_at": expired, "result_path": str(running_file)},
                    done={"state": "done", "updated_at": expired, "result_path": str(done_file)},
                )

            ocr_app._cleanup_jobs()

            self.assertIn("running", ocr_app.jobs)
            self.assertTrue(running_file.exists())
            self.assertNotIn("done", ocr_app.jobs)
            self.assertFalse(done_file.exists())

    def test_restart_cleanup_removes_all_orphan_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            orphan = Path(directory, "recent.source")
            orphan.touch()
            with patch.object(ocr_app, "JOB_DIRECTORY", Path(directory)):
                ocr_app._cleanup_job_files_at_startup()
            self.assertFalse(orphan.exists())

    def test_page_pixel_limit_rejects_decompression_bombs(self) -> None:
        ocr_app._validate_page_pixels(1000, 1000)
        with self.assertRaisesRegex(ValueError, "pixel OCR limit"):
            ocr_app._validate_page_pixels(ocr_app.MAX_PAGE_PIXELS, 2)


if __name__ == "__main__":
    unittest.main()
