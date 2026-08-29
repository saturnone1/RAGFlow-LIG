from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from runtime_patches.dataset_settings import EXPECTED_SHA256, apply_dataset_settings_patch
from runtime_patches.offline_team_membership import (
    EXPECTED_SHA256 as EXPECTED_TEAM_SHA256,
    apply_offline_team_membership_patch,
)


class RuntimePatchContractTests(unittest.TestCase):
    def test_dataset_settings_patch_is_atomic_and_compiles(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        source_path = repository / "RAGFlow/api/apps/services/dataset_api_service.py"
        text = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), EXPECTED_SHA256)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source_path.name
            target.write_text(text, encoding="utf-8", newline="\n")
            apply_dataset_settings_patch(target)
            patched = target.read_text(encoding="utf-8")

        compile(patched, str(source_path), "exec")
        self.assertIn("with DB.atomic():", patched)
        self.assertIn("Document.update(document_update)", patched)
        self.assertNotIn("KnowledgebaseService.update_by_id(kb.id, req)", patched)

    def test_hash_pin_accepts_windows_line_endings_only(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        source_path = repository / "RAGFlow/api/apps/services/dataset_api_service.py"
        text = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source_path.name
            target.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
            apply_dataset_settings_patch(target)
            patched = target.read_text(encoding="utf-8")
        self.assertIn("with DB.atomic():", patched)

    def test_offline_team_membership_adds_registered_user_directly(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        source_path = repository / "RAGFlow/api/apps/restful_apis/tenant_api.py"
        text = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), EXPECTED_TEAM_SHA256)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / source_path.name
            target.write_text(text, encoding="utf-8", newline="\n")
            apply_offline_team_membership_patch(target)
            patched = target.read_text(encoding="utf-8")

        compile(patched, str(source_path), "exec")
        self.assertIn('role=UserTenantRole.NORMAL', patched)
        self.assertIn('membership.role == UserTenantRole.NORMAL', patched)
        self.assertIn('with DB.lock(f"team_member:{lock_digest[:52]}", timeout=10):', patched)
        self.assertIn('message="Registered active user not found."', patched)
        self.assertNotIn("send_invite_email", patched)
        self.assertNotIn("UserTenantRole.INVITE,", patched)


if __name__ == "__main__":
    unittest.main()
