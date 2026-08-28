import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from lig_runtime.volume_archive import pack, restore


class VolumeArchiveTests(unittest.TestCase):
    def test_round_trip_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            (source / "nested").mkdir()
            (source / "nested" / "한글.txt").write_text("RAGFlow 상태", encoding="utf-8")
            archive = root / "backup.tar.gz"

            packed = pack(source, archive)
            (target / "old").mkdir(parents=True)
            (target / "old" / "stale.txt").write_text("stale", encoding="utf-8")
            restored = restore(archive, target)

            self.assertEqual(packed["sha256"], restored["sha256"])
            self.assertEqual((target / "nested" / "한글.txt").read_text(encoding="utf-8"), "RAGFlow 상태")
            self.assertFalse((target / "old").exists())

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape.txt")
                payload = b"unsafe"
                info.size = len(payload)
                bundle.addfile(info, io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                restore(archive, root / "target")


if __name__ == "__main__":
    unittest.main()
