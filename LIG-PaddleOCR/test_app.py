from __future__ import annotations

import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as ocr_app


class OcrJobLifecycleTests(unittest.TestCase):
    def test_cpu_sessions_report_their_actual_provider(self) -> None:
        self.assertTrue(ocr_app.OCR_SESSION_PROVIDERS)
        self.assertTrue(
            all(
                providers[0] == "CPUExecutionProvider"
                for providers in ocr_app.OCR_SESSION_PROVIDERS.values()
            )
        )

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

    def test_large_image_is_scaled_to_the_current_memory_budget(self) -> None:
        from PIL import Image

        image = Image.new("RGB", (2000, 1000))
        with patch.object(ocr_app, "_page_pixel_budget", return_value=500_000):
            fitted = ocr_app._fit_image_to_memory(image, 1024 * 1024 * 1024)
        try:
            self.assertLessEqual(fitted.width * fitted.height, 500_000)
        finally:
            fitted.close()
            image.close()

    def test_memory_budget_adapts_without_rejecting_a_page(self) -> None:
        budget = ocr_app._page_pixel_budget(
            ocr_app.MIN_FREE_BYTES + ocr_app.OCR_BYTES_PER_PIXEL * 2_000_000
        )
        self.assertEqual(budget, min(ocr_app.MAX_PAGE_PIXELS, 2_000_000 // ocr_app.JOB_WORKERS))

    def test_memory_wait_stops_when_job_is_canceled(self) -> None:
        cancel_event = threading.Event()
        cancel_event.set()
        with self.assertRaisesRegex(ocr_app.OcrJobCanceled, "canceled"):
            ocr_app._wait_for_memory(cancel_event)

    def test_cancel_endpoint_signals_running_job(self) -> None:
        cancel_event = threading.Event()
        future = MagicMock()
        future.cancel.return_value = False
        with ocr_app.jobs_lock:
            ocr_app.jobs["running-job"] = {
                "state": "running",
                "created_at": time.time(),
                "updated_at": time.time(),
                "cancel_event": cancel_event,
                "future": future,
            }

        async def cancel() -> tuple[int, dict]:
            client = ocr_app.app.test_client()
            response = await client.delete(
                "/api/v2/ocr/jobs/running-job",
                headers={"Authorization": f"Bearer {ocr_app.INTERNAL_TOKEN}"},
            )
            return response.status_code, await response.get_json()

        status, payload = asyncio.run(cancel())
        self.assertEqual(status, 202)
        self.assertEqual(payload["data"]["state"], "canceling")
        self.assertTrue(cancel_event.is_set())

    def test_pdf_render_scale_does_not_double_scale_or_reject_large_pages(self) -> None:
        self.assertEqual(ocr_app._pdf_render_scale(1000, 1000), ocr_app.RENDER_SCALE)
        scale = ocr_app._pdf_render_scale(
            ocr_app.MAX_PAGE_PIXELS,
            2,
            ocr_app.MIN_FREE_BYTES + ocr_app.OCR_BYTES_PER_PIXEL * ocr_app.MAX_PAGE_PIXELS,
        )
        self.assertLess(scale, 1.0)
        self.assertLessEqual(ocr_app.MAX_PAGE_PIXELS * 2 * scale * scale, ocr_app.MAX_PAGE_PIXELS + 1)
        with self.assertRaisesRegex(ValueError, "dimensions must be positive"):
            ocr_app._pdf_render_scale(0, 1000)


if __name__ == "__main__":
    unittest.main()
