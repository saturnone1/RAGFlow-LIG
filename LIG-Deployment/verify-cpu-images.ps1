param(
    [string]$RagFlowImage = "lig/ragflow-ui:v0.26.4-3",
    [string]$PaddleOcrImage = "lig/paddleocr-ko:v0.26.4-3",
    [string]$McpImage = "lig/ragflow-mcp:v0.26.4-3"
)

$ErrorActionPreference = "Stop"

function Invoke-Docker([string[]]$Arguments) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & $dockerExecutable @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        throw "docker failed with exit code $dockerExitCode"
    }
}

function Invoke-ContainerPython([string]$Image, [string]$Program, [string[]]$Environment = @()) {
    $encodedProgram = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Program))
    $arguments = @("run", "--rm")
    foreach ($entry in $Environment) {
        $arguments += @("--env", $entry)
    }
    $arguments += @(
        "--entrypoint", "/ragflow/.venv/bin/python",
        $Image,
        "-c", "import base64; exec(base64.b64decode('$encodedProgram'))"
    )
    Invoke-Docker $arguments
}

foreach ($image in @($RagFlowImage, $PaddleOcrImage, $McpImage)) {
    Invoke-Docker @("image", "inspect", "--format", "{{.Id}}", $image)
}

$runtimeProgram = @'
import base64
import io
import os
import sys
from pathlib import Path

os.environ["LIG_DOCUMENT_PASSWORD_KEY"] = base64.b64encode(bytes(range(32))).decode("ascii")
sys.path.insert(0, "/ragflow")

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from lig_runtime.document_password import (
    PASSWORD_INPUT_FIELD,
    PASSWORD_STATUS_FIELD,
    PASSWORD_STORAGE_FIELD,
    normalize_document_password_for_binary,
    prepare_document_for_parsing,
    preserve_document_password_state,
    secure_parser_config,
)


def pdf_bytes(password=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (LIG encrypted PDF content) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    if password is not None:
        writer.encrypt(password, "owner-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


config, changed = secure_parser_config({PASSWORD_INPUT_FIELD: "open-password"}, "secure.pdf")
assert changed and PASSWORD_STORAGE_FIELD in config
assert "open-password" not in repr(config)

_, decrypted, public_config = prepare_document_for_parsing("secure.pdf", pdf_bytes("open-password"), config)
reader = PdfReader(io.BytesIO(decrypted))
assert not reader.is_encrypted
assert "LIG encrypted PDF content" in reader.pages[0].extract_text()
assert PASSWORD_STORAGE_FIELD not in public_config

plain_config = normalize_document_password_for_binary("plain.pdf", pdf_bytes(), config)
assert PASSWORD_STORAGE_FIELD not in plain_config
assert PASSWORD_STATUS_FIELD not in plain_config

new_parser_config = preserve_document_password_state(config, {"layout_recognize": "PaddleOCR"})
assert new_parser_config[PASSWORD_STORAGE_FIELD] == config[PASSWORD_STORAGE_FIELD]
assert new_parser_config["layout_recognize"] == "PaddleOCR"

required_patches = {
    "/ragflow/api/apps/__init__.py": ("max_content_length or None", "body_timeout or None"),
    "/ragflow/admin/server/admin_server.py": ("max_content_length or None",),
    "/ragflow/api/db/services/task_service.py": ("PADDLEOCR_TASK_PAGE_SIZE", "encrypted_pdf_page_count", "adaptive_pdf_task_page_size"),
    "/ragflow/deepdoc/parser/paddleocr_parser.py": ("_slice_pdf_data", "from_page", "iter_lines", "requests.delete(poll_url", "cached_pdf_outlines", "self.__images__(data_bytes", "page_to - page_from"),
    "/ragflow/rag/utils/infinity_conn.py": ("list_tables().table_names",),
    "/ragflow/common/doc_store/infinity_conn_base.py": ("return table_name in db_instance.list_tables().table_names",),
    "/ragflow/api/db/services/document_service.py": ("DOC_PROGRESS_MSG_MAX_BYTES", "def trim_tail_by_bytes", "update progress_msg failed for document"),
    "/ragflow/rag/app/naive.py": ("fallback succeeded with embedded PDF text", "continuing with DeepDoc"),
    "/ragflow/rag/app/picture.py": ("creating an image chunk using its file name", "_try_local_ocr_text"),
    "/ragflow/rag/svr/task_executor.py": ("prepare_document_for_parsing", "parser_filename", "task_lease", "_watch_canceled_tasks", "before lease acquisition", "TASK_PENDING_CLAIM_IDLE_SECONDS", "claim_stale_message", "canceled for task", "TaskStatus.CANCEL.value", "LIG_DOCUMENT_MAX_BYTES"),
    "/ragflow/rag/utils/redis_conn.py": ("def claim_stale_message", "xautoclaim", "def refresh(self):"),
    "/ragflow/rag/svr/task_executor_refactor/chunk_builder.py": ("prepare_document_for_parsing", "except TaskCanceledException"),
    "/ragflow/rag/svr/task_executor_refactor/embedding_service.py": ("import asyncio", "async def encode_at", "asyncio.gather"),
    "/ragflow/rag/svr/task_executor_limiter.py": ("MAX_CONCURRENT_EMBEDDERS", "LoopLocalSemaphore(MAX_CONCURRENT_EMBEDDERS)"),
    "/ragflow/rag/svr/task_executor_refactor/dataflow_service.py": ("async def _embed_chunks",),
    "/ragflow/api/db/joint_services/tenant_model_service.py": ("for env_instance in TenantModelInstanceService", "get_by_provider_id_and_instance_name"),
    "/ragflow/rag/llm/ocr_model.py": ("env_managed", "return os.environ[env_key]"),
}
for filename, markers in required_patches.items():
    source = Path(filename).read_text(encoding="utf-8")
    for marker in markers:
        assert marker in source, f"missing runtime patch marker {marker!r} in {filename}"

import msoffcrypto  # noqa: F401
import olefile  # noqa: F401
from lig_runtime import service_health

assert callable(service_health.api_ready)
assert callable(service_health.tcp_ready)

print("RAGFlow runtime password, parser fallback, and packaged dependency checks passed.")
'@
Invoke-ContainerPython -Image $RagFlowImage -Program $runtimeProgram

$ocrProgram = @'
import sys

sys.path.insert(0, "/opt/lig-paddleocr")
import app

assert app.DETECTION_MODEL_PATH.name == "ch_PP-OCRv5_det_mobile.onnx"
assert app.RECOGNITION_MODEL_PATH.name == "korean_PP-OCRv5_rec_mobile.onnx"
assert any(0xAC00 <= ord(character) <= 0xD7A3 for character in app.recognition_characters)
assert app._pdf_render_scale(1000, 1000) == app.RENDER_SCALE
assert app.MAX_UPLOAD_BYTES == 0
assert app.MAX_PDF_PAGES == 0
assert any(rule.rule == "/api/v2/ocr/jobs/<job_id>" and "DELETE" in rule.methods for rule in app.app.url_map.iter_rules())
assert app.OcrJobCanceled
assert all(providers[0] == "CPUExecutionProvider" for providers in app.OCR_SESSION_PROVIDERS.values())
scale = app._pdf_render_scale(app.MAX_PAGE_PIXELS, 2)
assert scale < 1.0
assert app.MAX_PAGE_PIXELS * 2 * scale * scale <= app.MAX_PAGE_PIXELS + 1
print("PaddleOCR Korean model and PDF pixel-scaling checks passed.")
'@
Invoke-ContainerPython -Image $PaddleOcrImage -Program $ocrProgram -Environment @(
    "PADDLEOCR_INTERNAL_TOKEN=build-verification-token"
)

Invoke-Docker @("run", "--rm", "--entrypoint", "/bin/sh", $McpImage, "-c", "test -r /app/LigRagFlowMcp.dll")
Invoke-Docker @("run", "--rm", "--entrypoint", "dotnet", $McpImage, "--list-runtimes")
Write-Host "CPU image verification passed."
