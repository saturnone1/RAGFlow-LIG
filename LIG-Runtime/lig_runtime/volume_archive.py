"""Create and restore portable archives for RAGFlow Docker volumes.

This module deliberately uses Python instead of a shell entrypoint so the
air-gapped Windows deployment works where command interpreters are blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def _archive_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def pack(source: Path, archive: Path) -> dict[str, object]:
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive.name}.", suffix=".tmp", dir=archive.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    file_count = 0
    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"symbolic links are not supported: {path}")
                bundle.add(path, arcname=_archive_name(path, source), recursive=False)
                if path.is_file():
                    file_count += 1
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "archive": str(archive),
        "files": file_count,
        "sha256": sha256(archive),
        "bytes": archive.stat().st_size,
    }


def _validated_members(bundle: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = bundle.getmembers()
    for member in members:
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
            raise ValueError(f"unsafe archive member: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise ValueError(f"unsupported archive member: {member.name}")
    return members


def restore(archive: Path, target: Path) -> dict[str, object]:
    archive = archive.resolve(strict=True)
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve(strict=True)
    if target == Path(target.anchor):
        raise ValueError("refusing to restore over a filesystem root")
    with tarfile.open(archive, "r:gz") as bundle:
        members = _validated_members(bundle)
        for child in target.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
        bundle.extractall(target, members=members, filter="data")
    return {
        "archive": str(archive),
        "target": str(target),
        "files": sum(member.isfile() for member in members),
        "sha256": sha256(archive),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("source", type=Path)
    pack_parser.add_argument("archive", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("target", type=Path)
    arguments = parser.parse_args()
    result = (
        pack(arguments.source, arguments.archive)
        if arguments.command == "pack"
        else restore(arguments.archive, arguments.target)
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
