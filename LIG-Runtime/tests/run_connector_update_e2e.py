"""Exercise connector replacement and compensating storage rollback in a live container."""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

from common import settings
from werkzeug.datastructures import FileStorage


def upload_file(document_id: str, filename: str, payload: bytes) -> FileStorage:
    file = FileStorage(stream=BytesIO(payload), filename=filename)
    file.id = document_id
    return file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_id")
    parser.add_argument("document_id")
    parser.add_argument("updated_file", type=Path)
    parser.add_argument("rollback_file", type=Path)
    parser.add_argument("password")
    args = parser.parse_args()

    settings.init_settings()
    from api.db.services.document_service import DocumentService
    from api.db.services.file_service import FileService
    from api.db.services.knowledgebase_service import KnowledgebaseService

    found, kb = KnowledgebaseService.get_by_id(args.dataset_id)
    if not found:
        raise RuntimeError("E2E dataset was not found.")
    found, original_doc = DocumentService.get_by_id(args.document_id)
    if not found:
        raise RuntimeError("E2E document was not found.")

    updated_payload = args.updated_file.read_bytes()
    errors, documents = FileService.upload_document(
        kb,
        [upload_file(args.document_id, original_doc.name, updated_payload)],
        kb.tenant_id,
        src="connector-e2e",
        document_passwords=[args.password],
    )
    if errors or len(documents) != 1:
        raise RuntimeError(f"Connector replacement failed: {errors}")

    found, updated_doc = DocumentService.get_by_id(args.document_id)
    if not found:
        raise RuntimeError("Updated E2E document disappeared.")
    stored_after_update = settings.STORAGE_IMPL.get(kb.id, updated_doc.location)
    if stored_after_update != updated_payload:
        raise RuntimeError("Connector replacement did not update object storage.")
    successful_hash = updated_doc.content_hash
    successful_config = dict(updated_doc.parser_config or {})

    rollback_payload = args.rollback_file.read_bytes()
    original_update_method = DocumentService.update_by_id
    try:
        DocumentService.update_by_id = staticmethod(lambda *_args, **_kwargs: False)
        rollback_errors, rollback_documents = FileService.upload_document(
            kb,
            [upload_file(args.document_id, updated_doc.name, rollback_payload)],
            kb.tenant_id,
            src="connector-e2e",
            document_passwords=[args.password],
        )
    finally:
        DocumentService.update_by_id = original_update_method

    if not rollback_errors or rollback_documents:
        raise RuntimeError("Forced metadata failure did not fail the connector replacement.")
    stored_after_rollback = settings.STORAGE_IMPL.get(kb.id, updated_doc.location)
    if stored_after_rollback != updated_payload:
        raise RuntimeError("Object storage was not restored after metadata failure.")
    found, rolled_back_doc = DocumentService.get_by_id(args.document_id)
    if not found or rolled_back_doc.content_hash != successful_hash or dict(rolled_back_doc.parser_config or {}) != successful_config:
        raise RuntimeError("Document metadata changed despite the forced update failure.")

    print(
        json.dumps(
            {
                "status": "passed",
                "connector_update": True,
                "storage_rollback": True,
                "password_config_preserved": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
