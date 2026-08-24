param(
    [string]$RagFlowImage = "lig/ragflow-ui:v0.26.4-4",
    [string]$PaddleOcrImage = "lig/paddleocr-ko:v0.26.4-4",
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
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

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
from lig_runtime.resource_control import adaptive_pdf_task_page_size
from deepdoc.parser.paddleocr_parser import PaddleOCRConfig, PaddleOCRParser
from api.db.joint_services.tenant_model_service import _replace_profile_reference

os.environ["ADAPTIVE_PDF_TASK_PAGE_SIZE"] = "false"
assert adaptive_pdf_task_page_size(40) == 40


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

direct_writer = PdfWriter()
direct_writer.add_blank_page(width=612, height=792)
direct_writer.add_blank_page(width=400, height=600)
direct_pdf = io.BytesIO()
direct_writer.write(direct_pdf)
direct_pdf_bytes = direct_pdf.getvalue()
assert PaddleOCRParser._is_pdf_data(direct_pdf_bytes)
assert PaddleOCRParser._is_pdf_data(b"scanner-prefix\n" + direct_pdf_bytes)
assert not PaddleOCRParser._is_pdf_data(b"\x89PNG\r\n\x1a\nimage")

direct_calls = []

class DirectResponse:
    status_code = 200
    text = ""

    def __init__(self, page_width):
        self.page_width = page_width

    def json(self):
        return {
            "errorCode": 0,
            "result": {
                "layoutParsingResults": [
                    {"prunedResult": {"parsing_res_list": [{"block_content": str(self.page_width)}]}}
                ],
                "ocrResults": [],
            },
        }


def direct_post(url, json, headers, timeout):
    image_bytes = base64.b64decode(json["file"])
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert json["fileType"] == 1
    from PIL import Image
    with Image.open(io.BytesIO(image_bytes)) as rendered:
        width = rendered.width
    direct_calls.append((url, width, timeout))
    return DirectResponse(width)


direct_parser = PaddleOCRParser(
    base_url="http://remote.example/layout-parsing",
    access_token="test",
    api_mode="direct-image",
    direct_workers=2,
    direct_render_dpi=96,
)
direct_config = PaddleOCRConfig.from_dict({
    "base_url": direct_parser.base_url,
    "access_token": "test",
    "algorithm": "PP-StructureV3",
    "api_mode": "direct-image",
    "direct_workers": 2,
    "direct_render_dpi": 96,
    "request_timeout": 60,
})
with patch("deepdoc.parser.paddleocr_parser.requests.post", direct_post):
    direct_result = direct_parser._send_direct_images(direct_pdf_bytes, direct_config, None)
assert len(direct_calls) == 2
direct_widths = [int(entry["prunedResult"]["parsing_res_list"][0]["block_content"]) for entry in direct_result["layoutParsingResults"]]
assert len(direct_widths) == 2 and direct_widths[0] > direct_widths[1]

old_profile = "paddleocr-from-env@paddleocr-from-env(1)@PaddleOCR"
new_profile = "paddleocr-from-env@paddleocr-from-env@PaddleOCR"
replaced, replaced_count = _replace_profile_reference(
    {"layout_recognize": old_profile, "nested": [old_profile, {"keep": "value"}]},
    old_profile,
    new_profile,
)
assert replaced_count == 2
assert replaced["layout_recognize"] == new_profile
assert replaced["nested"][0] == new_profile

required_patches = {
    "/ragflow/api/apps/__init__.py": ("max_content_length or None", "body_timeout or None", "Bearer credential is not a JWT"),
    "/ragflow/admin/server/admin_server.py": ("max_content_length or None",),
    "/ragflow/api/db/services/task_service.py": ("PDF_TASK_PAGE_SIZE", "PADDLEOCR_TASK_PAGE_SIZE", "encrypted_pdf_page_count", "adaptive_pdf_task_page_size"),
    "/ragflow/deepdoc/parser/paddleocr_parser.py": ("_slice_pdf_data", "from_page", "iter_lines", "requests.delete(poll_url", "cached_pdf_outlines", "self.__images__(data_bytes", "page_to - page_from", '"PaddleOCR-VL-1.6": _VL_FIELD_MAPPING', "direct_render_dpi", '"renderDpi": str(config.direct_render_dpi)', "def _is_pdf_data", 'payload["fileType"] = 1'),
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
    "/ragflow/api/db/joint_services/tenant_model_service.py": ("ensure_paddleocr_vl_from_env", "paddleocr-vl-from-env", "PADDLEOCR_VL_ACCESS_TOKEN", "get_by_provider_id_and_instance_name", "Do not overwrite", "_migrate_profile_references", "_ocr_endpoint_available", "Retired duplicate bundled"),
    "/ragflow/rag/llm/ocr_model.py": ("paddleocr_api_mode", "PADDLEOCR_API_MODE", "paddleocr_direct_workers", "paddleocr_direct_render_dpi", "_apply_dataset_overrides"),
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
from pathlib import Path

sys.path.insert(0, "/opt/lig-paddleocr")
import app

assert app.DETECTION_MODEL_PATH.name == "ch_PP-OCRv5_det_mobile.onnx"
assert app.RECOGNITION_MODEL_PATH.name == "korean_PP-OCRv5_rec_mobile.onnx"
assert any(0xAC00 <= ord(character) <= 0xD7A3 for character in app.recognition_characters)
assert app.DEFAULT_RENDER_DPI == 144
assert app._pdf_render_scale(1000, 1000, 144) == 2.0
assert app._pdf_render_scale(1000, 1000, 216) == 3.0
assert app.MAX_UPLOAD_BYTES == 0
assert app.MAX_PDF_PAGES == 0
assert any(rule.rule == "/api/v2/ocr/jobs/<job_id>" and "DELETE" in rule.methods for rule in app.app.url_map.iter_rules())
assert app.OcrJobCanceled
assert app.DEVICE == "cpu"
assert all(providers[0] == "CPUExecutionProvider" for providers in app.OCR_SESSION_PROVIDERS.values())
app_source = Path(app.__file__).read_text(encoding="utf-8")
assert 'PADDLEOCR_DEVICE' in app_source
assert 'CUDAExecutionProvider' in app_source
for marker in ("ensure_paddleocr_vl_from_env", "APIToken.create", "RAGFLOW_MCP_HOST_API_KEY"):
    assert marker in app_source, f"missing PaddleOCR provisioning marker: {marker}"
scale = app._pdf_render_scale(app.MAX_PAGE_PIXELS, 2, 144)
assert scale < 1.0
assert app.MAX_PAGE_PIXELS * 2 * scale * scale <= app.MAX_PAGE_PIXELS + 1
print("PaddleOCR Korean model and PDF pixel-scaling checks passed.")
'@
Invoke-ContainerPython -Image $PaddleOcrImage -Program $ocrProgram -Environment @(
    "PADDLEOCR_INTERNAL_TOKEN=build-verification-token"
)

Invoke-Docker @("run", "--rm", "--entrypoint", "dotnet", $McpImage, "--list-runtimes")
Write-Host "CPU image verification passed."
