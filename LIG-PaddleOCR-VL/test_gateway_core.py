from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from gateway_core import invoke_layout_parsing


class PaddleOcrVlGatewayCoreTests(unittest.TestCase):
    def test_official_response_is_reduced_to_result_object(self) -> None:
        response = MagicMock()
        expected = {"layoutParsingResults": [{"prunedResult": {"parsing_res_list": []}}]}
        response.json.return_value = {"errorCode": 0, "result": expected}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source.pdf")
            source.write_bytes(b"pdf")
            post = MagicMock(return_value=response)
            result = invoke_layout_parsing(
                source,
                {"formatBlockContent": True, "file": "https://invalid.example/file.pdf", "fileType": 1},
                "http://paddleocr-vl-api:8080/",
                30,
                post=post,
            )

        self.assertEqual(result, expected)
        call = post.call_args
        self.assertEqual(call.args[0], "http://paddleocr-vl-api:8080/layout-parsing")
        self.assertEqual(call.kwargs["json"]["fileType"], 0)
        self.assertEqual(base64.b64decode(call.kwargs["json"]["file"]), b"pdf")
        self.assertEqual(call.kwargs["json"]["fileType"], 0)
        self.assertTrue(call.kwargs["json"]["formatBlockContent"])

    def test_upstream_error_is_reported(self) -> None:
        response = MagicMock()
        response.json.return_value = {"errorCode": 500, "errorMsg": "model failed"}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "source.pdf")
            source.write_bytes(b"pdf")
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                invoke_layout_parsing(source, {}, "http://upstream", 30, post=MagicMock(return_value=response))


if __name__ == "__main__":
    unittest.main()
