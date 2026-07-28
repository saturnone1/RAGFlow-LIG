#!/usr/bin/env python3
"""Apply the narrowly scoped LIG runtime patch to RAGFlow v0.26.4."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

EXPECTED_EMBEDDING_SHA256 = "b844aec1bd2bc49bb54e55beb7d6273a7da6cbd5cfe15b3e96fd7882e0b3e4eb"
EXPECTED_PADDLEOCR_SHA256 = "94b735a444ee81a03bcd7bd996851a7e3759ee95e14e0b8d838a5d59f68e6704"
EXPECTED_TASK_EXECUTOR_SHA256 = "389f45143dc98e3882545fdea8b18b1c4537e597448ae5b72cfed41a0305511a"
EXPECTED_DOCUMENT_API_SHA256 = "b26f0a7dea5ea8b0a3a7a5e66be81f79d3dbf61c5d3fdcc4404fa493cf7ed67e"
EXPECTED_DOCUMENT_API_SERVICE_SHA256 = "60260d6bbdc8821adb484166a1a42ce656bcd794ec02bad9c7bfbf699d0b5e4d"
EXPECTED_FILE_SERVICE_SHA256 = "993d0a442318192d7090d5771753aa04467abaa84af92a3c77b1c4134621afab"
EXPECTED_TASK_SERVICE_SHA256 = "32003df60fd2335a713894bbd91cdd885c0162b803a04d115ac4713c9fafb611"
EXPECTED_PIPELINE_PARSER_SHA256 = "8696d52e5fc38003062d2e70e71fcd84c12521cb18204a8565f325637bea6328"
EXPECTED_PDF_CHUNK_METADATA_SHA256 = "3f204ed52fb787bee0b11f216b2cb9ef78953648aa3ffab008efa9147f039c8e"
EXPECTED_CHUNK_API_SHA256 = "f5da126149457c6c256169914c3012bc587be9ac3f2c11beb5987b3063bc12db"
EXPECTED_FILE_UTILS_SHA256 = "6d4d5fbe0e249b0e491b746b2b6351833a583f8acd21dda2c9099620ab5a294a"
EXPECTED_REFACTORED_CHUNK_BUILDER_SHA256 = "0d76ff4d212dd1fa3c6be999177c12f9c6ac8579510c7d7807bdf458e6715b04"
EXPECTED_REFACTORED_TASK_HANDLER_SHA256 = "a0b7b5e1e70c0d21bb35320e83ebc49650d099838958b92399b1c3b10bba6e7d"
OLD_TIMEOUT = "headers={\"Content-Type\": \"application/json\"}, timeout=30)"
NEW_TIMEOUT = "headers={\"Content-Type\": \"application/json\"}, timeout=60)"
PADDLEOCR_PROGRESS_REPLACEMENTS = {
    'callback(0.9, f"[PaddleOCR] done, sections: {len(sections)}")':
        'callback(0.78, f"[PaddleOCR] done, sections: {len(sections)}")',
    'callback(1.0, f"[PaddleOCR] done, tables: {len(tables)}")':
        'callback(0.79, f"[PaddleOCR] done, tables: {len(tables)}")',
}
OLD_EMBEDDING_PROGRESS = (
    'callback(prog=0.7 + 0.2 * (i + 1) / len(cnts), msg="")'
)
NEW_EMBEDDING_PROGRESS = (
    "callback("
    "prog=0.7 + 0.2 * min(i + settings.EMBEDDING_BATCH_SIZE, len(cnts)) / len(cnts), "
    'msg="")'
)


def main() -> None:
    if len(sys.argv) != 14:
        raise SystemExit(
            "usage: apply-runtime-patches.py <embedding_model.py> "
            "<paddleocr_parser.py> <task_executor.py> <document_api.py> "
            "<document_api_service.py> <file_service.py> <task_service.py> "
            "<pipeline_parser.py> <pdf_chunk_metadata.py> <chunk_api.py> <file_utils.py> "
            "<refactored_chunk_builder.py> <refactored_task_handler.py>"
        )

    embedding_target = Path(sys.argv[1])
    source = embedding_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_EMBEDDING_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow embedding_model.py: "
            f"expected {EXPECTED_EMBEDDING_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    if text.count(OLD_TIMEOUT) != 2:
        raise SystemExit("Expected exactly two HuggingFace embedding timeout sites")

    embedding_target.write_text(
        text.replace(OLD_TIMEOUT, NEW_TIMEOUT), encoding="utf-8"
    )

    paddleocr_target = Path(sys.argv[2])
    source = paddleocr_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_PADDLEOCR_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow paddleocr_parser.py: "
            f"expected {EXPECTED_PADDLEOCR_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    for old_progress, new_progress in PADDLEOCR_PROGRESS_REPLACEMENTS.items():
        if text.count(old_progress) != 1:
            raise SystemExit(
                "Expected exactly one PaddleOCR terminal progress callback: "
                f"{old_progress}"
            )
        text = text.replace(old_progress, new_progress)
    paddleocr_target.write_text(text, encoding="utf-8")

    task_executor_target = Path(sys.argv[3])
    source = task_executor_target.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_TASK_EXECUTOR_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow task_executor.py: "
            f"expected {EXPECTED_TASK_EXECUTOR_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    if text.count(OLD_EMBEDDING_PROGRESS) != 1:
        raise SystemExit("Expected exactly one embedding progress calculation")
    text = text.replace(OLD_EMBEDDING_PROGRESS, NEW_EMBEDDING_PROGRESS)
    text = replace_once(
        text,
        "    # Record chunk configuration for comparison\n",
        "    from lig_runtime.document_password import DocumentPasswordError, prepare_document_for_parsing\n\n"
        "    try:\n"
        "        parser_filename, binary, parser_config_for_chunk = prepare_document_for_parsing(\n"
        "            task[\"name\"], binary, parser_config_for_chunk\n"
        "        )\n"
        "    except DocumentPasswordError as exc:\n"
        "        progress_callback(-1, str(exc))\n"
        "        raise\n\n"
        "    # Record chunk configuration for comparison\n",
        "document decryption before chunking",
    )
    text = replace_once(
        text,
        "                task[\"name\"],\n"
        "                binary=binary,\n",
        "                parser_filename,\n"
        "                binary=binary,\n",
        "prepared parser filename",
    )
    text = replace_once(
        text,
        '        logging.info(f"handle_task done for task {json.dumps(task)}")',
        '        logging.info(f"handle_task done for task {task_id}, doc id:{task.get(\'doc_id\', \'\')}")',
        "task completion log secret redaction",
    )
    text = replace_once(
        text,
        '        logging.exception(f"handle_task got exception for task {json.dumps(task)}")',
        '        logging.exception(f"handle_task got exception for task {task_id}, doc id:{task.get(\'doc_id\', \'\')}")',
        "task failure log secret redaction",
    )
    text = replace_once(
        text,
        '            logging.info(f"GraphRAG task result for task {task}:\\n{result}")',
        '            logging.info(f"GraphRAG task result for task {task.get(\'id\', \'\')}:\\n{result}")',
        "GraphRAG task log secret redaction",
    )
    task_executor_target.write_text(text, encoding="utf-8")

    document_api_target = checked_target(Path(sys.argv[4]), EXPECTED_DOCUMENT_API_SHA256, "document_api.py")
    text = document_api_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pathlib import Path\n",
        "from pathlib import Path\n\n"
        "from lig_runtime.document_compatibility import DocumentCompatibilityError, validate_parser_compatibility\n"
        "from lig_runtime.document_password import DocumentPasswordError, sanitize_document_response, secure_parser_config\n",
        "document API password import",
    )
    text = replace_once(
        text,
        "    # All validations passed, now perform all updates\n",
        "    effective_pipeline_id = req.get(\"pipeline_id\", doc.pipeline_id)\n"
        "    if not effective_pipeline_id and any(field in req for field in (\"name\", \"chunk_method\", \"parser_id\")):\n"
        "        try:\n"
        "            validate_parser_compatibility(\n"
        "                req.get(\"name\", doc.name),\n"
        "                req.get(\"chunk_method\") or req.get(\"parser_id\") or doc.parser_id,\n"
        "            )\n"
        "        except DocumentCompatibilityError as exc:\n"
        "            return get_error_data_result(message=str(exc), code=RetCode.ARGUMENT_ERROR)\n\n"
        "    # All validations passed, now perform all updates\n",
        "validate document parser compatibility before update",
    )
    text = replace_once(
        text,
        "    parser_config_template_group_changed = False\n",
        "    parser_config_template_group_changed = False\n"
        "    document_password_changed = False\n",
        "document password change tracking",
    )
    text = replace_once(
        text,
        "        req[\"parser_config\"].update(update_doc_req.parser_config.ext)\n"
        "        parser_config_template_group_touched = _normalize_parser_config_compilation_template_group_ids(req[\"parser_config\"])\n",
        "        req[\"parser_config\"].update(update_doc_req.parser_config.ext)\n"
        "        try:\n"
        "            req[\"parser_config\"], document_password_changed = secure_parser_config(req[\"parser_config\"], doc.name)\n"
        "        except DocumentPasswordError as exc:\n"
        "            return get_error_data_result(message=str(exc), code=RetCode.ARGUMENT_ERROR)\n"
        "        parser_config_template_group_touched = _normalize_parser_config_compilation_template_group_ids(req[\"parser_config\"])\n",
        "secure updated document password",
    )
    text = replace_once(
        text,
        "        if parser_config_template_group_changed and doc.parser_id.lower() == req[\"chunk_method\"].lower():\n",
        "        if (parser_config_template_group_changed or document_password_changed) and doc.parser_id.lower() == req[\"chunk_method\"].lower():\n",
        "reset after password update with chunk method",
    )
    text = replace_once(
        text,
        "    elif parser_config_template_group_changed:\n",
        "    elif parser_config_template_group_changed or document_password_changed:\n",
        "reset after password update",
    )
    text = replace_once(
        text,
        "    err, files = await thread_pool_exec(\n"
        "        FileService.upload_document,\n",
        "    document_passwords = None\n"
        "    raw_document_passwords = form.get(\"document_passwords\")\n"
        "    if raw_document_passwords:\n"
        "        try:\n"
        "            document_passwords = json.loads(raw_document_passwords)\n"
        "        except (json.JSONDecodeError, TypeError):\n"
        "            return get_error_data_result(message=\"document_passwords must be a JSON array.\", code=RetCode.ARGUMENT_ERROR)\n"
        "        if not isinstance(document_passwords, list) or len(document_passwords) != len(file_objs) or any(password is not None and not isinstance(password, str) for password in document_passwords):\n"
        "            return get_error_data_result(message=\"document_passwords must contain one string or null for each uploaded file.\", code=RetCode.ARGUMENT_ERROR)\n\n"
        "    err, files = await thread_pool_exec(\n"
        "        FileService.upload_document,\n",
        "parse per-file document passwords",
    )
    text = replace_once(
        text,
        "        parser_config_override=parser_config_override,\n"
        "    )\n",
        "        parser_config_override=parser_config_override,\n"
        "        document_passwords=document_passwords,\n"
        "    )\n",
        "pass document passwords to upload service",
    )
    text = replace_once(
        text,
        "        doc_data = files\n",
        "        doc_data = [sanitize_document_response(doc) for doc in files]\n",
        "sanitize raw upload response",
    )
    text = replace_once(
        text,
        "    return get_result(data=doc.to_dict())\n",
        "    return get_result(data=sanitize_document_response(doc.to_dict()))\n",
        "sanitize metadata update response",
    )
    document_api_target.write_text(text, encoding="utf-8")

    document_api_service_target = checked_target(Path(sys.argv[5]), EXPECTED_DOCUMENT_API_SERVICE_SHA256, "document_api_service.py")
    text = document_api_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import logging\n",
        "import logging\n\nfrom lig_runtime.document_password import sanitize_document_response\n",
        "document response sanitizer import",
    )
    text = replace_once(
        text,
        "    return renamed_doc\n\n\ndef map_doc_keys_with_run_status",
        "    return sanitize_document_response(renamed_doc)\n\n\ndef map_doc_keys_with_run_status",
        "sanitize mapped document response",
    )
    text = replace_once(
        text,
        "    renamed_doc = _process_run_mapping(renamed_doc, run_status)\n"
        "    return renamed_doc\n",
        "    renamed_doc = _process_run_mapping(renamed_doc, run_status)\n"
        "    return sanitize_document_response(renamed_doc)\n",
        "sanitize mapped upload response",
    )
    document_api_service_target.write_text(text, encoding="utf-8")

    file_service_target = checked_target(Path(sys.argv[6]), EXPECTED_FILE_SERVICE_SHA256, "file_service.py")
    text = file_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import logging\n",
        "import logging\n\n"
        "from lig_runtime.document_compatibility import validate_parser_compatibility\n"
        "from lig_runtime.document_password import secure_parser_config, validate_document_access\n",
        "file service document password import",
    )
    text = replace_once(
        text,
        '    def upload_document(self, kb, file_objs, user_id, src="local", parent_path: str | None = None, parser_config_override: dict | None = None):',
        '    def upload_document(self, kb, file_objs, user_id, src="local", parent_path: str | None = None, parser_config_override: dict | None = None, document_passwords: list[str | None] | None = None):',
        "upload service password argument",
    )
    text = replace_once(
        text,
        "        err, files = [], []\n"
        "        for file in file_objs:\n",
        "        err, files = [], []\n"
        "        for file_index, file in enumerate(file_objs):\n"
        "            file_parser_config = merged_parser_config\n"
        "            if document_passwords and document_passwords[file_index]:\n"
        "                file_parser_config, _ = secure_parser_config(\n"
        "                    {**merged_parser_config, \"document_password\": document_passwords[file_index]}, file.filename\n"
        "                )\n",
        "per-file secured document password configuration",
    )
    text = replace_once(
        text,
        "            if e:\n"
        "                try:\n"
        "                    if str(doc.kb_id) != str(kb.id):\n",
        "            if e:\n"
        "                old_blob = None\n"
        "                storage_updated = False\n"
        "                try:\n"
        "                    if str(doc.kb_id) != str(kb.id):\n",
        "existing document atomic update state",
    )
    text = replace_once(
        text,
        "                        continue\n"
        "                    blob = file.read()\n"
        "                    # Connector-supplied fingerprint (e.g. xxhash128(S3 ETag))\n",
        "                        continue\n"
        "                    storage_location = doc.location\n"
        "                    existing_parser_config = {**base_parser_config, **(doc.parser_config or {})}\n"
        "                    if parser_config_override and isinstance(parser_config_override, dict):\n"
        "                        existing_parser_config.update(parser_config_override)\n"
        "                    submitted_password = (\n"
        "                        document_passwords[file_index]\n"
        "                        if document_passwords and document_passwords[file_index]\n"
        "                        else None\n"
        "                    )\n"
        "                    if submitted_password:\n"
        "                        existing_parser_config[\"document_password\"] = submitted_password\n"
        "                    file_parser_config, _ = secure_parser_config(existing_parser_config, doc.name)\n"
        "                    if not doc.pipeline_id:\n"
        "                        validate_parser_compatibility(doc.name, doc.parser_id)\n"
        "                    blob = file.read()\n"
        "                    validate_document_access(doc.name, blob, file_parser_config)\n"
        "                    # Connector-supplied fingerprint (e.g. xxhash128(S3 ETag))\n",
        "existing document validation before replacement",
    )
    text = replace_once(
        text,
        "                    old_hash = doc.content_hash or \"\"\n"
        "                    settings.STORAGE_IMPL.put(kb.id, doc.location, blob, kb.tenant_id)\n"
        "                    doc.size = len(blob)\n"
        "                    doc.content_hash = new_hash\n"
        "                    doc = doc.to_dict()\n"
        "                    DocumentService.update_by_id(doc[\"id\"], doc)\n"
        "                    if new_hash != old_hash:\n"
        "                        files.append((doc, blob))\n"
        "                except Exception as exc:\n"
        "                    logging.exception(f\"Failed to update document {doc_id}: {exc}\")\n",
        "                    old_hash = doc.content_hash or \"\"\n"
        "                    config_changed = file_parser_config != (doc.parser_config or {})\n"
        "                    if new_hash == old_hash and not config_changed:\n"
        "                        continue\n"
        "                    old_blob = settings.STORAGE_IMPL.get(kb.id, storage_location)\n"
        "                    settings.STORAGE_IMPL.put(kb.id, storage_location, blob, kb.tenant_id)\n"
        "                    storage_updated = True\n"
        "                    doc.size = len(blob)\n"
        "                    doc.content_hash = new_hash\n"
        "                    doc.parser_config = file_parser_config\n"
        "                    doc = doc.to_dict()\n"
        "                    if not DocumentService.update_by_id(doc[\"id\"], doc):\n"
        "                        raise RuntimeError(\"Failed to persist the updated document metadata.\")\n"
        "                    files.append((doc, blob))\n"
        "                except Exception as exc:\n"
        "                    if storage_updated and old_blob is not None:\n"
        "                        try:\n"
        "                            settings.STORAGE_IMPL.put(kb.id, storage_location, old_blob, kb.tenant_id)\n"
        "                        except Exception:\n"
        "                            logging.exception(\"Failed to restore document storage after update failure\")\n"
        "                    logging.exception(f\"Failed to update document {doc_id}: {exc}\")\n",
        "atomic existing document replacement",
    )
    text = replace_once(
        text,
        "                blob = file.read()\n"
        "                if filetype == FileType.PDF.value:\n"
        "                    blob = read_potential_broken_pdf(blob)\n",
        "                blob = file.read()\n"
        "                parser_id = self.get_parser(filetype, filename, kb.parser_id)\n"
        "                if not kb.pipeline_id:\n"
        "                    validate_parser_compatibility(filename, parser_id)\n"
        "                validate_document_access(filename, blob, file_parser_config)\n"
        "                if filetype == FileType.PDF.value:\n"
        "                    blob = read_potential_broken_pdf(blob)\n",
        "validate password-protected document upload",
    )
    text = replace_once(
        text,
        '                    "parser_config": merged_parser_config,\n',
        '                    "parser_config": file_parser_config,\n',
        "store per-file password configuration",
    )
    text = replace_once(
        text,
        '                    "parser_id": self.get_parser(filetype, filename, kb.parser_id),\n',
        '                    "parser_id": parser_id,\n',
        "reuse validated parser id",
    )
    file_service_target.write_text(text, encoding="utf-8")

    task_service_target = checked_target(Path(sys.argv[7]), EXPECTED_TASK_SERVICE_SHA256, "task_service.py")
    text = task_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        file_bin = settings.STORAGE_IMPL.get(bucket, name)\n"
        "        pages = PdfParser.total_page_number(doc[\"name\"], file_bin)\n",
        "        file_bin = settings.STORAGE_IMPL.get(bucket, name)\n"
        "        from lig_runtime.document_password import encrypted_pdf_page_count\n\n"
        "        pages = encrypted_pdf_page_count(doc[\"name\"], file_bin, doc.get(\"parser_config\"))\n"
        "        if pages is None:\n"
        "            pages = PdfParser.total_page_number(doc[\"name\"], file_bin)\n",
        "encrypted PDF task page count",
    )
    text = replace_once(
        text,
        "    elif doc[\"parser_id\"] == \"table\":\n"
        "        file_bin = settings.STORAGE_IMPL.get(bucket, name)\n"
        "        rn = RAGFlowExcelParser.row_number(doc[\"name\"], file_bin)\n",
        "    elif doc[\"parser_id\"] == \"table\":\n"
        "        file_bin = settings.STORAGE_IMPL.get(bucket, name)\n"
        "        from lig_runtime.document_password import prepare_document_for_parsing\n\n"
        "        prepared_name, file_bin, _ = prepare_document_for_parsing(\n"
        "            doc[\"name\"], file_bin, doc.get(\"parser_config\")\n"
        "        )\n"
        "        rn = RAGFlowExcelParser.row_number(prepared_name, file_bin)\n",
        "encrypted table task row count",
    )
    task_service_target.write_text(text, encoding="utf-8")

    pipeline_parser_target = checked_target(Path(sys.argv[8]), EXPECTED_PIPELINE_PARSER_SHA256, "pipeline parser.py")
    text = pipeline_parser_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        if self._canvas._doc_id:\n"
        "            b, n = File2DocumentService.get_storage_address(doc_id=self._canvas._doc_id)\n"
        "            blob = settings.STORAGE_IMPL.get(b, n)\n"
        "        else:\n",
        "        if self._canvas._doc_id:\n"
        "            b, n = File2DocumentService.get_storage_address(doc_id=self._canvas._doc_id)\n"
        "            blob = settings.STORAGE_IMPL.get(b, n)\n"
        "            from api.db.services.document_service import DocumentService\n"
        "            from lig_runtime.document_password import prepare_document_for_parsing\n\n"
        "            found, document = DocumentService.get_by_id(self._canvas._doc_id)\n"
        "            if found:\n"
        "                name, blob, _ = prepare_document_for_parsing(name, blob, document.parser_config)\n"
        "        else:\n",
        "pipeline document decryption",
    )
    text = replace_once(
        text,
        "            if from_upstream.name.split(\".\")[-1].lower() not in conf.get(\"suffix\", []):\n",
        "            if name.split(\".\")[-1].lower() not in conf.get(\"suffix\", []):\n",
        "prepared pipeline filename selection",
    )
    pipeline_parser_target.write_text(text, encoding="utf-8")

    pdf_chunk_metadata_target = checked_target(Path(sys.argv[9]), EXPECTED_PDF_CHUNK_METADATA_SHA256, "pdf_chunk_metadata.py")
    text = pdf_chunk_metadata_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        bucket, name = File2DocumentService.get_storage_address(doc_id=canvas._doc_id)\n"
        "        return settings.STORAGE_IMPL.get(bucket, name)\n",
        "        bucket, name = File2DocumentService.get_storage_address(doc_id=canvas._doc_id)\n"
        "        blob = settings.STORAGE_IMPL.get(bucket, name)\n"
        "        from api.db.services.document_service import DocumentService\n"
        "        from lig_runtime.document_password import prepare_document_for_parsing\n\n"
        "        found, document = DocumentService.get_by_id(canvas._doc_id)\n"
        "        if found:\n"
        "            _, blob, _ = prepare_document_for_parsing(document.name, blob, document.parser_config)\n"
        "        return blob\n",
        "pipeline PDF preview decryption",
    )
    pdf_chunk_metadata_target.write_text(text, encoding="utf-8")

    chunk_api_target = checked_target(Path(sys.argv[10]), EXPECTED_CHUNK_API_SHA256, "chunk_api.py")
    text = chunk_api_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import logging\n",
        "import logging\n\nfrom lig_runtime.document_password import sanitize_document_response\n",
        "chunk API document sanitizer import",
    )
    text = replace_once(
        text,
        "    return renamed_doc\n\n\ndef _get_query_id_list",
        "    return sanitize_document_response(renamed_doc)\n\n\ndef _get_query_id_list",
        "sanitize chunk API document response",
    )
    chunk_api_target.write_text(text, encoding="utf-8")

    file_utils_target = checked_target(Path(sys.argv[11]), EXPECTED_FILE_UTILS_SHA256, "file_utils.py")
    text = file_utils_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "|html|sql|epub)$",
        "|html|sql|epub|hwp|hwpx)$",
        "HWP and HWPX upload extensions",
    )
    file_utils_target.write_text(text, encoding="utf-8")

    refactored_chunk_builder_target = checked_target(
        Path(sys.argv[12]),
        EXPECTED_REFACTORED_CHUNK_BUILDER_SHA256,
        "task_executor_refactor/chunk_builder.py",
    )
    text = refactored_chunk_builder_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    try:\n"
        "        # Merge table parser config\n"
        "        parser_config = merge_table_parser_config_from_kb(ctx.raw_task)\n\n"
        "        async with ctx.chunk_limiter:\n",
        "    try:\n"
        "        # Merge table parser config and prepare protected documents before parsing.\n"
        "        parser_config = merge_table_parser_config_from_kb(ctx.raw_task)\n"
        "        from lig_runtime.document_password import prepare_document_for_parsing\n\n"
        "        parser_filename, binary, parser_config = prepare_document_for_parsing(\n"
        "            ctx.name, binary, parser_config\n"
        "        )\n\n"
        "        async with ctx.chunk_limiter:\n",
        "refactored executor document decryption",
    )
    text = replace_once(
        text,
        "                ctx.name,\n"
        "                binary=binary,\n",
        "                parser_filename,\n"
        "                binary=binary,\n",
        "refactored executor prepared parser filename",
    )
    refactored_chunk_builder_target.write_text(text, encoding="utf-8")

    refactored_task_handler_target = checked_target(
        Path(sys.argv[13]),
        EXPECTED_REFACTORED_TASK_HANDLER_SHA256,
        "task_executor_refactor/task_handler.py",
    )
    text = refactored_task_handler_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '                logging.info(f"GraphRAG task result for task {ctx.raw_task}:\\n{result}")',
        '                logging.info(f"GraphRAG task result for task {ctx.id}:\\n{result}")',
        "refactored GraphRAG task log secret redaction",
    )
    refactored_task_handler_target.write_text(text, encoding="utf-8")


def checked_target(path: Path, expected_sha256: str, label: str) -> Path:
    source = path.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SystemExit(f"Unsupported RAGFlow {label}: expected {expected_sha256}, got {actual_sha256}")
    return path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one {label} site")
    return text.replace(old, new)


if __name__ == "__main__":
    main()
