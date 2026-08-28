import unittest
from pathlib import Path


class DeploymentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = Path(__file__).resolve().parents[2]
        cls.compose = (cls.repository / "LIG-Deployment/docker-compose.lig.yml").read_text(encoding="utf-8")
        cls.launcher = (cls.repository / "LIG-Deployment/lig-ragflow.ps1").read_text(encoding="utf-8")
        cls.airgap_export = (cls.repository / "LIG-Deployment/airgap-export.ps1").read_text(encoding="utf-8")
        cls.airgap_import = (cls.repository / "LIG-Deployment/airgap-import.ps1").read_text(encoding="utf-8")

    def test_database_migration_is_a_one_shot_dependency(self) -> None:
        self.assertIn("ragflow-migrate:", self.compose)
        self.assertIn("- --migrate-only", self.compose)
        self.assertGreaterEqual(self.compose.count("condition: service_completed_successfully"), 4)
        self.assertGreaterEqual(self.compose.count("- --skip-database-initialization"), 4)

    def test_redis_queue_never_evicts_and_has_no_default_memory_cap(self) -> None:
        self.assertIn("- --maxmemory\n      - ${REDIS_MAXMEMORY:-0}", self.compose)
        self.assertIn("- --maxmemory-policy\n      - noeviction", self.compose)

    def test_start_preserves_optional_profiles(self) -> None:
        start_block = self.launcher.split('    "start" {', 1)[1].split('    "paddleocr-start" {', 1)[0]
        self.assertNotIn("--remove-orphans", start_block)
        self.assertIn('Invoke-Compose @("up", "-d")', start_block)

    def test_recovery_test_is_explicit(self) -> None:
        self.assertIn('"recovery-test" { Invoke-RecoveryTest }', self.launcher)
        self.assertIn('Invoke-Docker @("restart", $worker)', self.launcher)
        self.assertIn('Invoke-Docker @("restart", $infinity)', self.launcher)

    def test_airgap_base_archive_excludes_embedding_and_ocr_images(self) -> None:
        base_images = self.airgap_export.split("$images = @(", 1)[1].split(")", 1)[0]
        self.assertNotIn("qwen3-embedding", base_images)
        self.assertNotIn("paddleocr-ko", base_images)
        self.assertNotIn("paddleocr-vl", base_images)
        self.assertIn("[switch]$IncludeEmbedding", self.airgap_export)
        self.assertIn("[switch]$IncludePaddleOcr", self.airgap_export)
        self.assertIn("[switch]$IncludePaddleOcrVl", self.airgap_export)
        self.assertIn('"lig-paddleocr-images-v0.26.4.tar.gz"', self.airgap_export)

    def test_airgap_import_uses_current_format_without_requiring_ocr(self) -> None:
        self.assertIn("bundleFormat = 13", self.airgap_export)
        self.assertIn("$manifest.bundleFormat -ne 13", self.airgap_import)
        required_images = self.airgap_import.split("foreach ($requiredImage in", 1)[1].split(") {", 1)[0]
        self.assertIn("$manifest.uiImage", required_images)
        self.assertIn("$manifest.mcpImage", required_images)
        self.assertNotIn("$manifest.ocrImage", required_images)


if __name__ == "__main__":
    unittest.main()
