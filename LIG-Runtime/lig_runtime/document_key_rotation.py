"""Audit and rewrap stored document passwords after a key rotation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable

from lig_runtime.document_password import (
    PASSWORD_STORAGE_FIELD,
    DocumentPasswordError,
    _keyring,
    rewrap_parser_config,
)


def keyring_fingerprint() -> dict[str, object]:
    active_id, keys = _keyring()
    digest = hashlib.sha256()
    for key_id, key in sorted(keys.items()):
        digest.update(key_id.encode("ascii") + b"\0" + key)
    return {
        "active_key_id": active_id,
        "configured_key_ids": sorted(keys),
        "fingerprint": digest.hexdigest(),
    }


def audit_configs(configs: Iterable[tuple[str, dict | None]]) -> tuple[list[tuple[str, dict]], list[str]]:
    changed: list[tuple[str, dict]] = []
    errors: list[str] = []
    for document_id, config in configs:
        try:
            rewrapped, was_changed = rewrap_parser_config(config)
            if was_changed:
                changed.append((document_id, rewrapped))
        except (DocumentPasswordError, RuntimeError) as exc:
            errors.append(f"{document_id}: {exc}")
    return changed, errors


def _database_configs():
    from api.db.db_models import Document

    rows = Document.select(Document.id, Document.parser_config).iterator()
    return ((row.id, row.parser_config or {}) for row in rows)


def _audit_database_configs() -> tuple[int, int, list[str]]:
    candidates = 0
    error_count = 0
    reported_errors: list[str] = []
    for document_id, config in _database_configs():
        try:
            _, changed = rewrap_parser_config(config)
        except (DocumentPasswordError, RuntimeError) as exc:
            error_count += 1
            if len(reported_errors) < 100:
                reported_errors.append(f"{document_id}: {exc}")
            continue
        if changed:
            candidates += 1
    return candidates, error_count, reported_errors


def _apply_document_ids(document_ids: list[str]) -> int:
    from api.db.db_models import DB, Document

    applied = 0
    with DB.atomic():
        for document_id in document_ids:
            row = (
                Document.select(Document.id, Document.parser_config)
                .where(Document.id == document_id)
                .for_update()
                .get_or_none()
            )
            if row is None:
                raise RuntimeError(f"Document {document_id} disappeared during key rotation.")
            config, changed = rewrap_parser_config(row.parser_config or {})
            if not changed:
                continue
            updated = Document.update(parser_config=config).where(Document.id == document_id).execute()
            if updated != 1:
                raise RuntimeError(f"Document {document_id} disappeared during key rotation.")
            applied += 1
    return applied


def _apply_database_configs(batch_size: int) -> int:
    applied = 0
    pending_ids: list[str] = []
    for document_id, config in _database_configs():
        _, changed = rewrap_parser_config(config)
        if not changed:
            continue
        pending_ids.append(document_id)
        if len(pending_ids) >= batch_size:
            applied += _apply_document_ids(pending_ids)
            pending_ids.clear()
    if pending_ids:
        applied += _apply_document_ids(pending_ids)
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist rewrapped tokens. The default is an audit-only dry run.")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--fingerprint", action="store_true", help="Print only the non-secret keyring fingerprint.")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000:
        parser.error("--batch-size must be between 1 and 1000")

    fingerprint = keyring_fingerprint()
    if args.fingerprint:
        print(json.dumps(fingerprint, sort_keys=True))
        return 0

    from common import settings

    settings.init_settings()
    candidates, error_count, errors = _audit_database_configs()
    if error_count:
        print(
            json.dumps(
                {
                    **fingerprint,
                    "status": "failed",
                    "error_count": error_count,
                    "errors": errors,
                    "rewrap_candidates": candidates,
                }
            )
        )
        return 2
    applied = _apply_database_configs(args.batch_size) if args.apply else 0
    print(
        json.dumps(
            {
                **fingerprint,
                "status": "complete" if args.apply else "dry-run",
                "rewrap_candidates": candidates,
                "rewrapped": applied,
                "storage_field": PASSWORD_STORAGE_FIELD,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
