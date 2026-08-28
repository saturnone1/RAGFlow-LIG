from __future__ import annotations

from pathlib import Path

from runtime_patches.contract import checked_target, replace_once

EXPECTED_SHA256 = "d00fdaad3cfcd533f6dcc13f5dd653d7bb8db27bc13dc8b727cafae5247c4907"


def apply_dataset_settings_patch(target_path: Path) -> None:
    target = checked_target(target_path, EXPECTED_SHA256, "api/apps/services/dataset_api_service.py")
    text = target.read_text(encoding="utf-8")
    text = replace_once(text, "import logging\nimport json\n", "import logging\nimport json\nfrom datetime import datetime\n", "dataset datetime import")
    text = replace_once(text, "from api.db.db_models import File\n", "from api.db.db_models import DB, Document, File\n", "dataset DB and Document imports")
    text = replace_once(
        text,
        "from api.db.services.knowledgebase_service import KnowledgebaseService\n",
        "from api.db.services.knowledgebase_service import KnowledgebaseService\nfrom api.db.services.common_service import retry_db_operation\n",
        "dataset transaction retry import",
    )
    text = replace_once(
        text,
        "from common.misc_utils import thread_pool_exec\n",
        "from common.misc_utils import thread_pool_exec\nfrom common.time_utils import current_timestamp, datetime_format\n",
        "dataset timestamp imports",
    )
    text = replace_once(
        text,
        '    if not KnowledgebaseService.update_by_id(kb.id, req):\n'
        '        return False, "Update dataset error.(Database error)"\n\n'
        '    ok, k = KnowledgebaseService.get_by_id(kb.id)\n',
        '    document_update = {}\n'
        '    if "parser_config" in req:\n'
        '        document_update["parser_config"] = req["parser_config"]\n'
        '    if "parser_id" in req and req["parser_id"]:\n'
        '        document_update["parser_id"] = req["parser_id"]\n'
        '    if "pipeline_id" in req:\n'
        '        document_update["pipeline_id"] = req["pipeline_id"]\n'
        '    # Commit the dataset and the document-owned parser settings together.\n'
        '    # Workers therefore never observe a partially applied UI save.\n'
        '    @retry_db_operation\n'
        '    def persist_dataset_settings():\n'
        '        dataset_update = dict(req)\n'
        '        dataset_update["update_time"] = current_timestamp()\n'
        '        dataset_update["update_date"] = datetime_format(datetime.now())\n'
        '        with DB.atomic():\n'
        '            updated = KnowledgebaseService.model.update(dataset_update).where(KnowledgebaseService.model.id == kb.id).execute()\n'
        '            if updated and document_update:\n'
        '                Document.update(document_update).where(Document.kb_id == kb.id).execute()\n'
        '            return updated\n\n'
        '    if not persist_dataset_settings():\n'
        '        return False, "Update dataset error.(Database error)"\n\n'
        '    ok, k = KnowledgebaseService.get_by_id(kb.id)\n',
        "dataset parser configuration propagation",
    )
    target.write_text(text, encoding="utf-8")
