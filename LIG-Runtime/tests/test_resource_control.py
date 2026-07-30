import os
import unittest
from unittest.mock import patch

from lig_runtime.resource_control import adaptive_pdf_task_page_size


class AdaptivePageSizeTests(unittest.TestCase):
    def test_never_rejects_low_memory(self):
        environment = {
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=512 * 1024**2):
                self.assertEqual(adaptive_pdf_task_page_size(12), 1)

    def test_uses_available_memory_but_respects_configured_max(self):
        environment = {
            "TASK_EXECUTOR_WORKERS": "2",
            "MAX_CONCURRENT_CHUNK_BUILDERS": "1",
            "LIG_INGESTION_MEMORY_RESERVE_BYTES": str(1024**3),
            "LIG_INGESTION_MEMORY_PERCENT": "100",
            "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE": str(100 * 1024**2),
        }
        with patch.dict(os.environ, environment, clear=False):
            with patch("lig_runtime.resource_control.available_memory_bytes", return_value=5 * 1024**3):
                self.assertEqual(adaptive_pdf_task_page_size(12), 12)
                self.assertEqual(adaptive_pdf_task_page_size(30), 20)


if __name__ == "__main__":
    unittest.main()
