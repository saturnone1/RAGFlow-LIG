from __future__ import annotations

import unittest

import adapter


class PrepareEmbedPayloadTest(unittest.TestCase):
    def test_adds_instruction_to_query_string(self) -> None:
        result = adapter.prepare_embed_payload({"inputs": "MIL-STD-2525C란?"})

        self.assertTrue(result["inputs"].startswith("Instruct: "))
        self.assertTrue(result["inputs"].endswith("Query: MIL-STD-2525C란?"))

    def test_leaves_document_batch_unchanged(self) -> None:
        payload = {"inputs": ["첫 번째 문서", "second document"]}

        self.assertIs(adapter.prepare_embed_payload(payload), payload)

    def test_rejects_non_string_inputs(self) -> None:
        with self.assertRaises(ValueError):
            adapter.prepare_embed_payload({"inputs": ["valid", 3]})


if __name__ == "__main__":
    unittest.main()
