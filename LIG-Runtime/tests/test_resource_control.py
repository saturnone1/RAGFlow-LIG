import os
import unittest
from unittest.mock import patch

from lig_runtime.resource_control import adaptive_pdf_task_page_size


class AdaptivePageSizeTests(unittest.TestCase):
    def test_defaults_to_exact_configured_page_size(self):
        with patch.dict(os.environ, {"ADAPTIVE_PDF_TASK_PAGE_SIZE": "false"}, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=1):
                self.assertEqual(adaptive_pdf_task_page_size(40), 40)

    def test_never_rejects_low_memory(self):
        environment = {
            "ADAPTIVE_PDF_TASK_PAGE_SIZE": "true",
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=512 * 1024**2):
                self.assertEqual(adaptive_pdf_task_page_size(12), 1)

    def test_uses_available_memory_but_respects_configured_max(self):
        environment = {
            "ADAPTIVE_PDF_TASK_PAGE_SIZE": "true",
            "TASK_EXECUTOR_WORKERS": "2",
            "MAX_CONCURRENT_TASKS": "1",
            "MAX_CONCURRENT_CHUNK_BUILDERS": "1",
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
            "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE": str(100 * 1024**2),
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=5 * 1024**3):
                self.assertEqual(adaptive_pdf_task_page_size(12), 12)
                self.assertEqual(adaptive_pdf_task_page_size(30), 20)

    def test_task_slots_cap_parser_concurrency(self):
        environment = {
            "ADAPTIVE_PDF_TASK_PAGE_SIZE": "true",
            "TASK_EXECUTOR_WORKERS": "3",
            "MAX_CONCURRENT_TASKS": "1",
            "MAX_CONCURRENT_CHUNK_BUILDERS": "3",
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
            "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE": str(100 * 1024**2),
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=5 * 1024**3):
                self.assertEqual(adaptive_pdf_task_page_size(12), 12)

    def test_worker_and_per_worker_parser_slots_multiply(self):
        environment = {
            "ADAPTIVE_PDF_TASK_PAGE_SIZE": "true",
            "TASK_EXECUTOR_WORKERS": "3",
            "MAX_CONCURRENT_TASKS": "3",
            "MAX_CONCURRENT_CHUNK_BUILDERS": "3",
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
            "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE": str(100 * 1024**2),
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=5 * 1024**3):
                self.assertEqual(adaptive_pdf_task_page_size(12), 4)


if __name__ == "__main__":
    unittest.main()
