#!/usr/bin/env python3
"""Apply the narrowly scoped LIG runtime patch to RAGFlow v0.26.4."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from runtime_patches.dataset_settings import apply_dataset_settings_patch
from runtime_patches.offline_team_membership import apply_offline_team_membership_patch

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
EXPECTED_NAIVE_PARSER_SHA256 = "99a168e1713321f64f3fb8b1834c1f76f549804f540d08002f5b8aa92bc40bcf"
EXPECTED_PICTURE_PARSER_SHA256 = "2e67f314adb4375d613345d2e6ba19d4079feaf78027b8a713d5c2183d4dc553"
EXPECTED_REFACTORED_CHUNK_SERVICE_SHA256 = "c2fc8e3da4f88214b08893ca02793a6984db4ce3b38cd30e4631f5c4b45648c2"
EXPECTED_EMAIL_PARSER_SHA256 = "bb301146d2225e3cf47b32e80b3b6058ca549973ab4903947cf9e2576ca1bcad"
EXPECTED_REDIS_CONN_SHA256 = "aaa61fde04ab654da5dfb519cebde91e60436081185e4a1a07d38ed187596489"
EXPECTED_TENANT_MODEL_SERVICE_SHA256 = "26352a0b1b4244c316691d8f02e5131e932ffe87c8c60ee3c4674ca0c9f6d33e"
EXPECTED_API_APP_SHA256 = "a69fbdf8fd18cedde60fcd0245e558ebef8198039aad532576d28a7f7726ba27"
EXPECTED_ADMIN_SERVER_SHA256 = "399040a01af13adf69d49eb444d62fe508ae212cf8d095f620c12f37e09bb1f5"
EXPECTED_EMBEDDING_SERVICE_SHA256 = "7937e5de77f8badc953fb476b0f81e986532a9d8f8da17de10818182ec9a3ea2"
EXPECTED_DATAFLOW_SERVICE_SHA256 = "b6c0b874a555d27cce7989a93644b1cb171575d3b895d4b246d85baececc7e62"
EXPECTED_OCR_MODEL_SHA256 = "9901a48f98423fc5a765985595dbc31cd246b5f76869eac9603d74c3e559b627"
EXPECTED_INFINITY_CONN_SHA256 = "85cb001ff451960331731785fa7d13e69c1017b37f2f967dee77e65523b76baa"
EXPECTED_INFINITY_CONN_BASE_SHA256 = "d3a1dfd788ab657c82a5711cb4a6e0e4c9c6c605e4451b6283473c72ddd5cfde"
EXPECTED_DOCUMENT_SERVICE_SHA256 = "02cf6c5e9a1732d7ee5bb2fb094cb8661bdab31aa2ee5fee5876003cc77734b5"
EXPECTED_TASK_EXECUTOR_LIMITER_SHA256 = "9d71b0c22e56b5c7e6b333a80aa83ce9de844f3c0a5ef4e65755660b67d54354"
EXPECTED_SETTINGS_SHA256 = "c81b2b13f2a19a01892a9208cb5df3753f5845616b6655eec6c71f5dca741610"
EXPECTED_DEEPDOC_OCR_SHA256 = "a4b1c380046584124edacb1d14c2c11fe293e843c0ae32bbe3e3a8a26b8474e3"
EXPECTED_DB_MODELS_SHA256 = "26d9734b0b249c207e887d40bbe2734235e5d66c1805c9be5f05743605daced4"
OLD_TIMEOUT = "headers={\"Content-Type\": \"application/json\"}, timeout=30)"
NEW_TIMEOUT = (
    'headers={"Content-Type": "application/json"}, '
    'timeout=float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")))'
)
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
    if len(sys.argv) != 34:
        raise SystemExit(
            "usage: apply-runtime-patches.py <embedding_model.py> "
            "<paddleocr_parser.py> <task_executor.py> <document_api.py> "
            "<document_api_service.py> <file_service.py> <task_service.py> "
            "<pipeline_parser.py> <pdf_chunk_metadata.py> <chunk_api.py> <file_utils.py> "
            "<refactored_chunk_builder.py> <refactored_task_handler.py> <naive.py> "
            "<picture.py> <refactored_chunk_service.py> <email.py> "
            "<redis_conn.py> <tenant_model_service.py> <api_apps_init.py> <admin_server.py> "
            "<embedding_service.py> <dataflow_service.py> <ocr_model.py> "
            "<infinity_conn.py> <infinity_conn_base.py> <document_service.py> "
            "<task_executor_limiter.py> <settings.py> <deepdoc_ocr.py> "
            "<db_models.py> <dataset_api_service.py> <tenant_api.py>"
        )

    embedding_target = Path(sys.argv[1])
    source = normalized_source(embedding_target)
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != EXPECTED_EMBEDDING_SHA256:
        raise SystemExit(
            "Unsupported RAGFlow embedding_model.py: "
            f"expected {EXPECTED_EMBEDDING_SHA256}, got {actual_sha256}"
        )

    text = source.decode("utf-8")
    if text.count(OLD_TIMEOUT) != 2:
        raise SystemExit("Expected exactly two HuggingFace embedding timeout sites")

    text = text.replace(OLD_TIMEOUT, NEW_TIMEOUT)
    text = replace_once(text, "import threading\n", "import threading\nimport time\n", "embedding retry time import")
    text = replace_once(
        text,
        '        self.base_url = base_url or "http://127.0.0.1:8080"\n\n'
        "    def encode(self, texts: list):\n",
        '        self.base_url = base_url or "http://127.0.0.1:8080"\n\n'
        "    def _request(self, payload, max_retries=None):\n"
        "        if max_retries is None:\n"
        '            max_retries = max(0, int(os.environ.get("HUGGINGFACE_EMBEDDING_MAX_RETRIES", "0")))\n'
        "        attempt = 0\n"
        "        while True:\n"
        "            try:\n"
        "                response = requests.post(\n"
        '                    f"{self.base_url}/embed",\n'
        "                    json=payload,\n"
        '                    headers={"Content-Type": "application/json"},\n'
        '                    timeout=float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")),\n'
        "                )\n"
        "                if response.status_code not in (408, 429) and response.status_code < 500:\n"
        "                    return response\n"
        '                detail = f"HTTP {response.status_code}"\n'
        "                if max_retries and attempt >= max_retries:\n"
        "                    return response\n"
        "            except requests.RequestException as error:\n"
        "                detail = str(error)\n"
        "                if max_retries and attempt >= max_retries:\n"
        '                    raise ModelException(f"Embedding service unavailable after retries: {error}", retryable=True) from error\n'
        "            attempt += 1\n"
        "            delay = min(30, 2 ** min(attempt - 1, 5))\n"
        '            logger.warning("Embedding service unavailable (%s); retrying in %ss", detail, delay)\n'
        "            time.sleep(delay)\n\n"
        "    def encode(self, texts: list):\n",
        "resilient HuggingFace embedding request",
    )
    text = replace_once(
        text,
        '        response = requests.post(f"{self.base_url}/embed", json={"inputs": texts}, headers={"Content-Type": "application/json"}, timeout=float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")))\n',
        '        response = self._request({"inputs": texts})\n',
        "HuggingFace document embedding retry",
    )
    text = replace_once(
        text,
        '        response = requests.post(f"{self.base_url}/embed", json={"inputs": text}, headers={"Content-Type": "application/json"}, timeout=float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")))\n',
        '        query_retries = max(0, int(os.environ.get("HUGGINGFACE_EMBEDDING_QUERY_MAX_RETRIES", "3")))\n'
        '        response = self._request({"inputs": text}, query_retries)\n',
        "HuggingFace query embedding retry",
    )
    embedding_target.write_text(text, encoding="utf-8")

    paddleocr_target = Path(sys.argv[2])
    source = normalized_source(paddleocr_target)
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
    text = replace_once(
        text,
        '        "PaddleOCR-VL": _VL_FIELD_MAPPING,\n'
        '        "PP-OCRv5": _VL_FIELD_MAPPING,\n',
        '        "PaddleOCR-VL": _VL_FIELD_MAPPING,\n'
        '        "PaddleOCR-VL-1.6": _VL_FIELD_MAPPING,\n'
        '        "PP-OCRv5": _VL_FIELD_MAPPING,\n',
        "PaddleOCR-VL-1.6 option forwarding",
    )
    text = replace_once(
        text,
        "from PIL import Image\n",
        "from PIL import Image\nfrom pypdf import PdfReader, PdfWriter\n",
        "PaddleOCR PDF page slicing imports",
    )
    text = replace_once(
        text,
        "import json\nimport logging\nimport os\nimport re\nimport tempfile\nimport time\n",
        "import base64\nimport hashlib\nimport json\nimport logging\nimport os\nimport re\nimport tempfile\nimport threading\nimport time\nfrom concurrent.futures import ThreadPoolExecutor\n",
        "PaddleOCR outline cache imports",
    )
    text = replace_once(
        text,
        "    request_timeout: int = 600\n"
        "    prettify_markdown: bool = True\n",
        '    api_mode: Literal["auto", "job", "direct-image"] = "auto"\n'
        "    direct_workers: int = 8\n"
        "    direct_render_dpi: int = 144\n"
        "    request_timeout: int = 600\n"
        "    prettify_markdown: bool = True\n",
        "PaddleOCR API mode configuration",
    )
    text = replace_once(
        text,
        "        if not self.access_token:\n"
        "            return False, \"[PaddleOCR] Access token not configured\"\n\n"
        "        return True, \"\"\n",
        "        if not self.base_url:\n"
        "            return False, \"[PaddleOCR] Base URL not configured\"\n\n"
        "        return True, \"\"\n",
        "optional PaddleOCR access token",
    )
    text = replace_once(
        text,
        "        algorithm = cfg.get(\"algorithm\", \"PaddleOCR-VL\")\n\n"
        "        # Validate algorithm\n",
        "        algorithm = cfg.get(\"algorithm\", \"PaddleOCR-VL\")\n"
        "        api_mode = cfg.get(\"api_mode\", \"auto\")\n"
        "        if api_mode not in {\"auto\", \"job\", \"direct-image\"}:\n"
        "            raise ValueError(f\"Unsupported PaddleOCR API mode: {api_mode}\")\n"
        "        try:\n"
        "            cfg[\"direct_workers\"] = max(1, int(cfg.get(\"direct_workers\", 8)))\n"
        "        except (TypeError, ValueError):\n"
        "            raise ValueError(\"PaddleOCR direct_workers must be a positive integer\")\n"
        "        try:\n"
        "            cfg[\"direct_render_dpi\"] = int(cfg.get(\"direct_render_dpi\", 144))\n"
        "            if cfg[\"direct_render_dpi\"] < 1:\n"
        "                raise ValueError\n"
        "        except (TypeError, ValueError):\n"
        "            raise ValueError(\"PaddleOCR direct_render_dpi must be a positive integer\")\n\n"
        "        # Validate algorithm\n",
        "PaddleOCR API mode validation",
    )
    text = replace_once(
        text,
        "        request_timeout: int = 600,\n"
        "    ):\n"
        '        """Initialize PaddleOCR parser."""\n',
        '        api_mode: Literal["auto", "job", "direct-image"] = "auto",\n'
        "        direct_workers: int = 8,\n"
        "        direct_render_dpi: int = 144,\n"
        "        request_timeout: int = 600,\n"
        "    ):\n"
        '        """Initialize PaddleOCR parser."""\n',
        "PaddleOCR parser API mode parameters",
    )
    text = replace_once(
        text,
        "        self.algorithm = algorithm\n"
        "        self.request_timeout = request_timeout\n",
        "        self.algorithm = algorithm\n"
        "        self.api_mode = api_mode\n"
        "        self.direct_workers = max(1, int(direct_workers))\n"
        "        self.direct_render_dpi = int(direct_render_dpi)\n"
        "        if self.direct_render_dpi < 1:\n"
        "            raise ValueError(\"PaddleOCR direct_render_dpi must be a positive integer\")\n"
        "        self.request_timeout = request_timeout\n",
        "PaddleOCR parser API mode state",
    )
    config_anchor = '            "request_timeout": request_timeout if request_timeout is not None else self.request_timeout,\n'
    if text.count(config_anchor) != 2:
        raise SystemExit("Expected PDF and image PaddleOCR request configuration sites")
    text = text.replace(
        config_anchor,
        '            "api_mode": kwargs.get("api_mode", self.api_mode),\n'
        '            "direct_workers": kwargs.get("direct_workers", self.direct_workers),\n'
        '            "direct_render_dpi": kwargs.get("direct_render_dpi", self.direct_render_dpi),\n'
        + config_anchor,
    )
    text = replace_once(
        text,
        "    def _send_request(self, data: bytes, config: PaddleOCRConfig, callback: Optional[Callable[[float, str], None]]) -> dict[str, Any]:\n"
        '        """Send request to PaddleOCR async Job API (submit → poll → fetch)."""\n'
        "        optional_payload = self._build_payload(data, self.file_type, config)\n",
        "    def _resolved_api_mode(self, config: PaddleOCRConfig) -> str:\n"
        '        if config.api_mode not in {"auto", "job", "direct-image"}:\n'
        '            raise ValueError(f"Unsupported PaddleOCR API mode: {config.api_mode}")\n'
        '        if config.api_mode != "auto":\n'
        "            return config.api_mode\n"
        '        host = requests.utils.urlparse(config.base_url).hostname or ""\n'
        '        return "job" if host in {"paddleocr", "paddleocr-vl", "127.0.0.1", "localhost"} else "direct-image"\n\n'
        "    @staticmethod\n"
        "    def _is_pdf_data(data: bytes) -> bool:\n"
        "        if b\"%PDF-\" in data[:1024]:\n"
        "            return True\n"
        "        image_signatures = (b\"\\xff\\xd8\\xff\", b\"\\x89PNG\\r\\n\\x1a\\n\", b\"GIF87a\", b\"GIF89a\", b\"II*\\x00\", b\"MM\\x00*\", b\"BM\")\n"
        "        if data.startswith(image_signatures) or (data.startswith(b\"RIFF\") and data[8:12] == b\"WEBP\"):\n"
        "            return False\n"
        "        try:\n"
        "            return bool(PdfReader(BytesIO(data), strict=False).pages)\n"
        "        except Exception:\n"
        "            return False\n\n"
        "    def _send_direct_images(self, data: bytes, config: PaddleOCRConfig, callback: Optional[Callable[[float, str], None]]) -> dict[str, Any]:\n"
        "        headers = {\"Client-Platform\": \"ragflow\"}\n"
        "        if config.access_token:\n"
        '            headers["Authorization"] = f"Bearer {config.access_token}"\n'
        "        completed = 0\n"
        "        progress_lock = threading.Lock()\n\n"
        "        def submit(index_and_image, total_pages):\n"
        "            nonlocal completed\n"
        "            index, image = index_and_image\n"
        "            output = BytesIO()\n"
        '            image.convert("RGB").save(output, format="JPEG", quality=92)\n'
        "            payload = self._build_payload(output.getvalue(), 1, config)\n"
        '            payload["file"] = base64.b64encode(output.getvalue()).decode("ascii")\n'
        '            payload["fileType"] = 1\n'
        "            response = requests.post(config.base_url, json=payload, headers=headers, timeout=config.request_timeout)\n"
        "            if response.status_code != 200:\n"
        '                raise RuntimeError(f"[PaddleOCR] direct page {index + 1} failed: HTTP {response.status_code} {response.text[:200]}")\n'
        "            body = response.json()\n"
        "            if body.get(\"errorCode\") not in (None, 0):\n"
        '                raise RuntimeError(f"[PaddleOCR] direct page {index + 1} failed: {body.get(\'errorMsg\')}")\n'
        "            with progress_lock:\n"
        "                completed += 1\n"
        "                if callback:\n"
        '                    callback(0.1 + 0.6 * completed / total_pages, f"[PaddleOCR] direct pages: {completed}/{total_pages}")\n'
        "            return index, body.get(\"result\", body)\n\n"
        "        page_results = []\n"
        "        if self._is_pdf_data(data):\n"
        "            render_dpi = config.direct_render_dpi\n"
        "            with pdfplumber.open(BytesIO(data)) as pdf:\n"
        "                total_pages = len(pdf.pages)\n"
        "                if total_pages < 1:\n"
        "                    raise ValueError(\"[PaddleOCR] PDF contains no pages\")\n"
        "                workers = min(config.direct_workers, total_pages)\n"
        "                for start in range(0, total_pages, workers):\n"
        "                    stop = min(start + workers, total_pages)\n"
        "                    images = [pdf.pages[index].to_image(resolution=render_dpi, antialias=True).original for index in range(start, stop)]\n"
        "                    try:\n"
        "                        indexed = list(zip(range(start, stop), images))\n"
        "                        with ThreadPoolExecutor(max_workers=len(indexed), thread_name_prefix=\"paddleocr-direct\") as executor:\n"
        "                            page_results.extend(executor.map(lambda item: submit(item, total_pages), indexed))\n"
        "                    finally:\n"
        "                        for image in images:\n"
        "                            image.close()\n"
        "        else:\n"
        "            with Image.open(BytesIO(data)) as image:\n"
        '                page_image = image.convert("RGB").copy()\n'
        "            try:\n"
        "                page_results.append(submit((0, page_image), 1))\n"
        "            finally:\n"
        "                page_image.close()\n"
        "        page_results.sort(key=lambda item: item[0])\n"
        "        combined = {\"layoutParsingResults\": [], \"ocrResults\": []}\n"
        "        for _, result in page_results:\n"
        "            combined[\"layoutParsingResults\"].extend(result.get(\"layoutParsingResults\", []))\n"
        "            combined[\"ocrResults\"].extend(result.get(\"ocrResults\", []))\n"
        "        return combined\n\n"
        "    def _send_request(self, data: bytes, config: PaddleOCRConfig, callback: Optional[Callable[[float, str], None]]) -> dict[str, Any]:\n"
        '        """Send a local Job API request or page images to a direct PaddleX API."""\n'
        "        mode = self._resolved_api_mode(config)\n"
        '        self.logger.info("[PaddleOCR] API mode=%s endpoint=%s", mode, config.base_url)\n'
        '        if mode == "direct-image":\n'
        "            return self._send_direct_images(data, config, callback)\n"
        "        optional_payload = self._build_payload(data, self.file_type, config)\n",
        "PaddleOCR direct-image adapter",
    )
    text = replace_once(
        text,
        '            form_data = {\n'
        '                "model": config.algorithm,\n'
        '                "optionalPayload": json.dumps(optional_payload),\n'
        '            }\n',
        '            form_data = {\n'
        '                "model": config.algorithm,\n'
        '                "renderDpi": str(config.direct_render_dpi),\n'
        '                "optionalPayload": json.dumps(optional_payload),\n'
        '            }\n',
        "PaddleOCR Job API render DPI forwarding",
    )
    text = replace_once(
        text,
        "from deepdoc.parser.utils import extract_pdf_outlines\n",
        "from deepdoc.parser.utils import extract_pdf_outlines\n\n\n"
        "_OUTLINE_CACHE_LOCK = threading.Lock()\n"
        "_OUTLINE_CACHE: dict[str, list] = {}\n\n\n"
        "def cached_pdf_outlines(source):\n"
        '    """Extract PDF outlines once per document instead of once per page-range task.\n\n'
        "    pypdf resolves every outline entry with a linear scan over the page list, so\n"
        "    a long document costs O(outlines x pages) each time. The result depends only\n"
        "    on the bytes and is an immutable list of tuples, so it is safe to share.\n"
        '    """\n'
        "    if not isinstance(source, (bytes, bytearray)):\n"
        "        return extract_pdf_outlines(source)\n"
        "    key = hashlib.sha256(source).hexdigest()\n"
        "    with _OUTLINE_CACHE_LOCK:\n"
        "        cached = _OUTLINE_CACHE.get(key)\n"
        "    if cached is not None:\n"
        "        return cached\n"
        "    outlines = extract_pdf_outlines(source)\n"
        "    with _OUTLINE_CACHE_LOCK:\n"
        "        # Tasks run one document at a time, so a single entry is all that hits.\n"
        "        _OUTLINE_CACHE.clear()\n"
        "        _OUTLINE_CACHE[key] = outlines\n"
        "    return outlines\n",
        "PaddleOCR outline cache helper",
    )
    text = replace_once(
        text,
        "        self.outlines = extract_pdf_outlines(binary if binary is not None else filepath)\n",
        "        self.outlines = cached_pdf_outlines(binary if binary is not None else filepath)\n",
        "PaddleOCR cached outline lookup",
    )
    text = replace_once(
        text,
        "        callback: Optional[Callable[[float, str], None]] = None,\n"
        "        *,\n"
        '        parse_method: str = "raw",\n',
        "        callback: Optional[Callable[[float, str], None]] = None,\n"
        "        *,\n"
        "        from_page: int = 0,\n"
        "        to_page: int = MAXIMUM_PAGE_NUMBER,\n"
        '        parse_method: str = "raw",\n',
        "PaddleOCR parse page range parameters",
    )
    text = replace_once(
        text,
        "        data_bytes = self._prepare_file_data(filepath, binary)\n\n"
        "        # Generate page images for cropping functionality\n"
        "        input_source = filepath if binary is None else binary\n",
        "        data_bytes = self._prepare_file_data(filepath, binary)\n"
        "        data_bytes = self._slice_pdf_data(data_bytes, from_page, to_page)\n\n"
        "        # Generate page images for cropping functionality. Feeding the sliced\n"
        "        # range keeps this off the full document: otherwise every page-range\n"
        "        # task of a large PDF re-parses the whole file to render a few pages.\n",
        "PaddleOCR task page slicing",
    )
    text = replace_once(
        text,
        "            self.__images__(input_source, callback=callback)\n",
        "            self.__images__(data_bytes, page_from=from_page, page_to=to_page, callback=callback)\n",
        "PaddleOCR task page images",
    )
    text = replace_once(
        text,
        '        """Generate page images from PDF for cropping."""\n'
        "        self.page_from = page_from\n",
        '        """Generate page images from PDF for cropping.\n\n'
        "        fnm holds only the pages of the current task, so it is indexed from 0\n"
        "        while page_from stays the absolute page number the position tags need.\n"
        '        """\n'
        "        self.page_from = page_from\n",
        "PaddleOCR sliced page image docstring",
    )
    text = replace_once(
        text,
        "                self.page_images = [p.to_image(resolution=72, antialias=True).original for i, p in enumerate(self.pdf.pages[page_from:page_to])]\n",
        "                self.page_images = [p.to_image(resolution=72, antialias=True).original for p in self.pdf.pages[: page_to - page_from]]\n",
        "PaddleOCR sliced page image indexing",
    )
    text = replace_once(
        text,
        "        return source_path.read_bytes()\n\n"
        "    def _build_payload",
        "        return source_path.read_bytes()\n\n"
        "    @staticmethod\n"
        "    def _slice_pdf_data(data: bytes, from_page: int, to_page: int) -> bytes:\n"
        "        reader = PdfReader(BytesIO(data), strict=False)\n"
        "        page_count = len(reader.pages)\n"
        "        start = max(0, int(from_page))\n"
        "        stop = min(page_count, max(start, int(to_page)))\n"
        "        if start >= stop:\n"
        '            raise ValueError(f"[PaddleOCR] empty PDF page range: {start}..{stop}")\n'
        "        if start == 0 and stop == page_count:\n"
        "            return data\n\n"
        "        writer = PdfWriter()\n"
        "        for page_number in range(start, stop):\n"
        "            writer.add_page(reader.pages[page_number])\n"
        "        output = BytesIO()\n"
        "        writer.write(output)\n"
        "        return output.getvalue()\n\n"
        "    def _build_payload",
        "PaddleOCR PDF slicing helper",
    )
    text = replace_once(
        text,
        "            result_resp = requests.get(result_json_url, timeout=_remaining())\n"
        "            result_resp.raise_for_status()\n",
        "            result_resp = requests.get(result_json_url, timeout=_remaining(), stream=True)\n"
        "            result_resp.raise_for_status()\n",
        "streaming PaddleOCR result download",
    )
    text = replace_once(
        text,
        "        jsonl_lines = result_resp.text.strip().split(\"\\n\")\n"
        "        jsonl_data = []\n"
        "        for line in jsonl_lines:\n"
        "            line = line.strip()\n"
        "            if line:\n"
        "                try:\n"
        "                    jsonl_data.append(json.loads(line))\n"
        "                except ValueError as exc:\n"
        "                    raise RuntimeError(f\"[PaddleOCR] result JSONL parse error: {exc}\")\n",
        "        jsonl_data = []\n"
        "        try:\n"
        "            for raw_line in result_resp.iter_lines(decode_unicode=True):\n"
        "                line = (raw_line or \"\").strip()\n"
        "                if line:\n"
        "                    jsonl_data.append(json.loads(line))\n"
        "        except ValueError as exc:\n"
        "            raise RuntimeError(f\"[PaddleOCR] result JSONL parse error: {exc}\") from exc\n"
        "        finally:\n"
        "            result_resp.close()\n",
        "incremental PaddleOCR JSONL parsing",
    )
    text = replace_once(
        text,
        "        while True:\n"
        "            if time.monotonic() >= deadline:\n",
        "        while True:\n"
        "            if callback:\n"
        "                try:\n"
        "                    callback(None, \"\")\n"
        "                except BaseException:\n"
        "                    try:\n"
        "                        requests.delete(poll_url, headers=headers, timeout=5)\n"
        "                    except requests.RequestException as cancel_error:\n"
        "                        self.logger.warning(f\"[PaddleOCR] failed to cancel remote job {job_id}: {cancel_error}\")\n"
        "                    raise\n"
        "            if time.monotonic() >= deadline:\n",
        "PaddleOCR cooperative cancellation polling",
    )
    text = replace_once(
        text,
        '            elif state == "failed":\n',
        '            elif state in {"canceled", "cancelled"}:\n'
        '                raise RuntimeError(f"[PaddleOCR] job {job_id} was canceled")\n'
        '            elif state == "failed":\n',
        "PaddleOCR canceled job state",
    )
    paddleocr_target.write_text(text, encoding="utf-8")

    task_executor_target = Path(sys.argv[3])
    source = normalized_source(task_executor_target)
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
        "    @timeout(60)\n"
        "    def batch_encode(txts):\n",
        '    @timeout(float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")))\n'
        "    def batch_encode(txts):\n",
        "legacy document embedding timeout",
    )
    text = replace_once(
        text,
        "            @timeout(60)\n"
        "            def batch_encode(txts):\n",
        '            @timeout(float(os.environ.get("HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS", "300")))\n'
        "            def batch_encode(txts):\n",
        "legacy enrichment embedding timeout",
    )
    text = replace_once(
        text,
        '    if task["size"] > settings.DOC_MAXIMUM_SIZE:\n',
        '    document_max_bytes = int(os.environ.get("LIG_DOCUMENT_MAX_BYTES", "0"))\n'
        '    if document_max_bytes > 0 and task["size"] > document_max_bytes:\n',
        "optional legacy executor document-size limit",
    )
    text = replace_once(
        text,
        '        set_progress(task["id"], prog=-1, msg="File size exceeds( <= %dMb )" % (int(settings.DOC_MAXIMUM_SIZE / 1024 / 1024)))\n'
        '        get_recording_context().record("file_size_exceeded", True)\n'
        "        return []\n",
        '        get_recording_context().record("file_size_exceeded", True)\n'
        '        raise ValueError("File size exceeds configured LIG_DOCUMENT_MAX_BYTES (%dMb)" % (int(document_max_bytes / 1024 / 1024)))\n',
        "legacy executor oversized-file failure",
    )
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
        "            ret = PipelineOperationLogService.record_pipeline_operation(\n"
        "                document_id=task[\"doc_id\"], pipeline_id=\"\", task_type=pipeline_task_type, task_id=task_id, referred_document_id=referred_document_id\n"
        "            )\n"
        "            get_recording_context().save_func_return_value(\"PipelineOperationLogService.record_pipeline_operation\", ret)\n",
        "            try:\n"
        "                ret = PipelineOperationLogService.record_pipeline_operation(\n"
        "                    document_id=task[\"doc_id\"], pipeline_id=\"\", task_type=pipeline_task_type, task_id=task_id, referred_document_id=referred_document_id\n"
        "                )\n"
        "                get_recording_context().save_func_return_value(\"PipelineOperationLogService.record_pipeline_operation\", ret)\n"
        "            except Exception:\n"
        "                logging.exception(\"Failed to record pipeline operation for task %s\", task_id)\n",
        "task lease cleanup survives operation logging failure",
    )
    text = replace_once(
        text,
        '            logging.info(f"GraphRAG task result for task {task}:\\n{result}")',
        '            logging.info(f"GraphRAG task result for task {task.get(\'id\', \'\')}:\\n{result}")',
        "GraphRAG task log secret redaction",
    )
    text = replace_once(
        text,
        "from common.constants import PAGERANK_FLD, TAG_FLD, SVR_CONSUMER_GROUP_NAME\n",
        "from common.constants import PAGERANK_FLD, TAG_FLD, SVR_CONSUMER_GROUP_NAME, TaskStatus\n",
        "task executor cancellation status import",
    )
    text = replace_once(
        text,
        'WORKER_HEARTBEAT_TIMEOUT = int(os.environ.get("WORKER_HEARTBEAT_TIMEOUT", "120"))\n'
        "stop_event = threading.Event()\n",
        'WORKER_HEARTBEAT_TIMEOUT = int(os.environ.get("WORKER_HEARTBEAT_TIMEOUT", "120"))\n'
        'TASK_LEASE_SECONDS = int(os.environ.get("TASK_LEASE_SECONDS", "180"))\n'
        'TASK_LEASE_REFRESH_SECONDS = max(5, min(60, TASK_LEASE_SECONDS // 3))\n'
        'TASK_CANCEL_GRACE_SECONDS = max(1.0, float(os.environ.get("TASK_CANCEL_GRACE_SECONDS", "5")))\n'
        'TASK_CANCEL_POLL_SECONDS = max(0.25, float(os.environ.get("TASK_CANCEL_POLL_SECONDS", "1")))\n'
        'TASK_PENDING_CLAIM_IDLE_SECONDS = max(\n'
        '    float(WORKER_HEARTBEAT_TIMEOUT) * 2,\n'
        '    float(os.environ.get("TASK_PENDING_CLAIM_IDLE_SECONDS", "300")),\n'
        ')\n'
        "stop_event = threading.Event()\n",
        "task lease configuration",
    )
    text = replace_once(
        text,
        "        except StopIteration:\n"
        "            for svr_queue_name in svr_queue_names:\n"
        "                redis_msg = REDIS_CONN.queue_consumer(svr_queue_name, SVR_CONSUMER_GROUP_NAME, CONSUMER_NAME)\n"
        "                if redis_msg:\n"
        "                    break\n",
        "        except StopIteration:\n"
        "            redis_msg = REDIS_CONN.claim_stale_message(\n"
        "                svr_queue_names,\n"
        "                SVR_CONSUMER_GROUP_NAME,\n"
        "                CONSUMER_NAME,\n"
        "                int(TASK_PENDING_CLAIM_IDLE_SECONDS * 1000),\n"
        "            )\n"
        "            for svr_queue_name in svr_queue_names:\n"
        "                if redis_msg:\n"
        "                    break\n"
        "                redis_msg = REDIS_CONN.queue_consumer(svr_queue_name, SVR_CONSUMER_GROUP_NAME, CONSUMER_NAME)\n"
        "                if redis_msg:\n"
        "                    break\n",
        "stale pending-message recovery before new work",
    )
    if text.count("        return None, None\n") != 4:
        raise SystemExit("Expected four task collector empty returns")
    text = text.replace("        return None, None\n", "        return None, None, None\n", 3)
    text = replace_once(
        text,
        "    canceled = False\n"
        "    if msg.get(\"doc_id\", \"\") in [GRAPH_RAPTOR_FAKE_DOC_ID, CANVAS_DEBUG_DOC_ID]:\n",
        "    if has_canceled(msg[\"id\"]):\n"
        "        DONE_TASKS += 1\n"
        "        logging.info(\"Acknowledging canceled pending task %s before lease acquisition\", msg[\"id\"])\n"
        "        redis_msg.ack()\n"
        "        return redis_msg, None, None\n\n"
        "    task_lease = RedisDistributedLock(\n"
        "        f\"task_lease:{msg['id']}\", timeout=TASK_LEASE_SECONDS, blocking_timeout=0\n"
        "    )\n"
        "    try:\n"
        "        lease_acquired = task_lease.acquire()\n"
        "    except Exception:\n"
        "        logging.exception(\"Failed to acquire task lease for %s\", msg['id'])\n"
        "        lease_acquired = False\n"
        "    if not lease_acquired:\n"
        "        logging.info(\"Task %s is already running; leaving the message pending\", msg['id'])\n"
        "        return redis_msg, None, None\n\n"
        "    canceled = False\n"
        "    if msg.get(\"doc_id\", \"\") in [GRAPH_RAPTOR_FAKE_DOC_ID, CANVAS_DEBUG_DOC_ID]:\n",
        "task lease acquisition before retry accounting",
    )
    text = replace_once(
        text,
        "        redis_msg.ack()\n"
        "        return None, None\n\n"
        "    task_type = msg.get(\"task_type\", \"\")\n",
        "        redis_msg.ack()\n"
        "        task_lease.release()\n"
        "        return redis_msg, None, None\n\n"
        "    task_type = msg.get(\"task_type\", \"\")\n",
        "release lease for terminal queue messages",
    )
    text = replace_once(
        text,
        "        FAILED_TASKS += 1\n"
        "        logging.warning(f\"collect task {msg['id']} {state}\")\n",
        "        if canceled:\n"
        "            DONE_TASKS += 1\n"
        "        logging.warning(f\"collect task {msg['id']} {state}\")\n",
        "terminal queue messages do not inflate failure metrics",
    )
    text = replace_once(
        text,
        "    return redis_msg, task\n\n\n"
        "async def get_storage_binary(bucket, name):\n",
        "    return redis_msg, task, task_lease\n\n\n"
        "async def get_storage_binary(bucket, name):\n",
        "return acquired task lease",
    )
    text = replace_once(
        text,
        "async def handle_task():\n"
        "    global DONE_TASKS, FAILED_TASKS\n"
        "    redis_msg, task = await collect()\n",
        "async def _refresh_task_lease(task_lease, task_id):\n"
        "    while True:\n"
        "        await asyncio.sleep(TASK_LEASE_REFRESH_SECONDS)\n"
        "        if not task_lease.refresh():\n"
        "            logging.warning(\"Task lease refresh failed for %s; will retry\", task_id)\n\n\n"
        "async def _watch_canceled_tasks():\n"
        "    canceled_since = {}\n"
        "    while True:\n"
        "        active_task_ids = set(CURRENT_TASKS)\n"
        "        now = time.monotonic()\n"
        "        for task_id in active_task_ids:\n"
        "            if not has_canceled(task_id):\n"
        "                canceled_since.pop(task_id, None)\n"
        "                continue\n"
        "            first_seen = canceled_since.setdefault(task_id, now)\n"
        "            if now - first_seen >= TASK_CANCEL_GRACE_SECONDS:\n"
        "                logging.error(\n"
        "                    \"Task %s ignored cancellation for %.1fs; restarting isolated executor process\",\n"
        "                    task_id,\n"
        "                    now - first_seen,\n"
        "                )\n"
        "                os._exit(75)\n"
        "        for task_id in set(canceled_since) - active_task_ids:\n"
        "            canceled_since.pop(task_id, None)\n"
        "        await asyncio.sleep(TASK_CANCEL_POLL_SECONDS)\n\n\n"
        "async def handle_task():\n"
        "    global DONE_TASKS, FAILED_TASKS\n"
        "    redis_msg, task, task_lease = await collect()\n",
        "task lease heartbeat",
    )
    text = replace_once(
        text,
        "    except TaskCanceledException as e:\n"
        "        DONE_TASKS += 1\n"
        "        CURRENT_TASKS.pop(task_id, None)\n"
        "        logging.info(f\"handle_task canceled for task {task_id}: {getattr(e, 'msg', str(e))}\")\n",
        "    except TaskCanceledException as e:\n"
        "        DONE_TASKS += 1\n"
        "        CURRENT_TASKS.pop(task_id, None)\n"
        "        try:\n"
        "            document_tasks = list(TaskService.query(doc_id=task[\"doc_id\"]))\n"
        "            has_new_run = any(\n"
        "                (document_task.progress or 0) < 1 and not has_canceled(document_task.id)\n"
        "                for document_task in document_tasks\n"
        "            )\n"
        "            if not has_new_run:\n"
        "                DocumentService.update_by_id(\n"
        "                    task[\"doc_id\"], {\"run\": TaskStatus.CANCEL.value, \"progress\": -1}\n"
        "                )\n"
        "        except Exception:\n"
        "            logging.exception(\"Failed to converge canceled document state for task %s\", task_id)\n"
        "        logging.info(f\"handle_task canceled for task {task_id}: {getattr(e, 'msg', str(e))}\")\n",
        "canceled task document state convergence",
    )
    text = replace_once(
        text,
        "    if not task:\n"
        "        await asyncio.sleep(5)\n"
        "        return\n",
        "    if not task:\n"
        "        # Clean terminal messages inherited from dead consumers promptly.\n"
        "        await asyncio.sleep(0.05 if redis_msg else 5)\n"
        "        return\n",
        "fast terminal pending-message cleanup",
    )
    text = replace_once(
        text,
        "    task_id = task[\"id\"]\n"
        "    try:\n",
        "    task_id = task[\"id\"]\n"
        "    lease_refresh_task = asyncio.create_task(_refresh_task_lease(task_lease, task_id))\n"
        "    try:\n",
        "start task lease heartbeat",
    )
    text = replace_once(
        text,
        "    redis_msg.ack()\n\n\n"
        "async def get_server_ip() -> str:\n",
        "    lease_refresh_task.cancel()\n"
        "    await asyncio.gather(lease_refresh_task, return_exceptions=True)\n"
        "    try:\n"
        "        task_lease.release()\n"
        "    finally:\n"
        "        redis_msg.ack()\n\n\n"
        "async def get_server_ip() -> str:\n",
        "release task lease before acknowledging",
    )
    text = replace_once(
        text,
        "    report_task = asyncio.create_task(report_status())\n"
        "    tasks = []\n",
        "    report_task = asyncio.create_task(report_status())\n"
        "    cancel_watchdog_task = asyncio.create_task(_watch_canceled_tasks())\n"
        "    tasks = []\n",
        "start task cancellation watchdog",
    )
    text = replace_once(
        text,
        "        report_task.cancel()\n"
        "        await asyncio.gather(report_task, return_exceptions=True)\n",
        "        report_task.cancel()\n"
        "        cancel_watchdog_task.cancel()\n"
        "        await asyncio.gather(report_task, cancel_watchdog_task, return_exceptions=True)\n",
        "cancel watchdog shutdown",
    )
    task_executor_target.write_text(text, encoding="utf-8")

    document_api_target = checked_target(Path(sys.argv[4]), EXPECTED_DOCUMENT_API_SHA256, "document_api.py")
    text = document_api_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pathlib import Path\n",
        "from pathlib import Path\n\n"
        "from lig_runtime.document_compatibility import DocumentCompatibilityError, validate_parser_compatibility\n"
        "from lig_runtime.document_password import (\n"
        "    DocumentPasswordError,\n"
        "    normalize_document_password_for_binary,\n"
        "    sanitize_document_response,\n"
        "    secure_parser_config,\n"
        ")\n",
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
        "            req[\"parser_config\"], document_password_changed = secure_parser_config(\n"
        "                req[\"parser_config\"], doc.name\n"
        "            )\n"
        "            if document_password_changed:\n"
        "                bucket, storage_name = File2DocumentService.get_storage_address(doc_id=doc.id)\n"
        "                binary = await thread_pool_exec(settings.STORAGE_IMPL.get, bucket, storage_name)\n"
        "                req[\"parser_config\"] = normalize_document_password_for_binary(\n"
        "                    doc.name, binary, req[\"parser_config\"]\n"
        "                )\n"
        "                document_password_changed = req[\"parser_config\"] != old_parser_config\n"
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
        "import logging\n\n"
        "from lig_runtime.document_password import preserve_document_password_state, sanitize_document_response\n",
        "document response sanitizer import",
    )
    text = replace_once(
        text,
        '        req["parser_config"] = get_parser_config(req["chunk_method"], req.get("parser_config"))\n'
        '        DocumentService.update_parser_config(doc.id, req["parser_config"])\n',
        '        req["parser_config"] = get_parser_config(req["chunk_method"], req.get("parser_config"))\n'
        '        req["parser_config"] = preserve_document_password_state(doc.parser_config, req["parser_config"])\n'
        '        DocumentService.update_parser_config(doc.id, req["parser_config"])\n',
        "preserve document password across chunk-method changes",
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
        "from lig_runtime.document_password import is_encrypted_pdf, normalize_document_password_for_binary, secure_parser_config\n",
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
        "                    file_parser_config = normalize_document_password_for_binary(\n"
        "                        doc.name, blob, file_parser_config\n"
        "                    )\n"
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
        "                file_parser_config = normalize_document_password_for_binary(\n"
        "                    filename, blob, file_parser_config\n"
        "                )\n"
        "                if filetype == FileType.PDF.value and not is_encrypted_pdf(blob):\n"
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
        "from common.misc_utils import get_uuid\n",
        "from common.misc_utils import get_uuid\n"
        "from common.parser_config_utils import normalize_layout_recognizer\n"
        "from lig_runtime.resource_control import adaptive_pdf_task_page_size\n",
        "task service layout recognizer import",
    )
    text = replace_once(
        text,
        "TASK_MAX_LOG_LENGTH = int(os.environ.get(\"TASK_MAX_LOG_LENGTH\", 3000))  # TEXT MAX is 64 KiB bytes!\n",
        "TASK_MAX_LOG_LENGTH = int(os.environ.get(\"TASK_MAX_LOG_LENGTH\", \"262144\"))\n"
        "TASK_MAX_CRASH_RETRIES = int(os.environ.get(\"TASK_MAX_CRASH_RETRIES\", \"0\"))\n",
        "configurable crash retry policy",
    )
    text = replace_once(
        text,
        "            cls.model.retry_count,\n"
        "            Document.kb_id,\n",
        "            cls.model.retry_count,\n"
        "            cls.model.progress,\n"
        "            Document.kb_id,\n",
        "completed task progress selection",
    )
    text = replace_once(
        text,
        "        doc = docs[0]\n\n"
        "        msg = f\"\\n{datetime.now().strftime('%H:%M:%S')} Task has been received.\"\n",
        "        doc = docs[0]\n"
        "        if doc[\"progress\"] >= 1:\n"
        "            return None\n\n"
        "        msg = f\"\\n{datetime.now().strftime('%H:%M:%S')} Task has been received.\"\n",
        "completed task duplicate suppression",
    )
    text = replace_once(
        text,
        "        if doc[\"retry_count\"] >= 3:\n"
        "            msg = \"\\nERROR: Task is abandoned after 3 times attempts.\"\n"
        "            prog = -1\n",
        "        if TASK_MAX_CRASH_RETRIES > 0 and doc[\"retry_count\"] >= TASK_MAX_CRASH_RETRIES:\n"
        "            msg = f\"\\nERROR: Task is abandoned after {TASK_MAX_CRASH_RETRIES} crash retries.\"\n"
        "            prog = -1\n",
        "unlimited default crash recovery",
    )
    text = replace_once(
        text,
        "        if docs[0][\"retry_count\"] >= 3:\n",
        "        if TASK_MAX_CRASH_RETRIES > 0 and docs[0][\"retry_count\"] >= TASK_MAX_CRASH_RETRIES:\n",
        "configurable crash retry enforcement",
    )
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
        '        page_size = doc["parser_config"].get("task_page_size") or 12\n',
        '        page_size = max(1, int(doc["parser_config"].get("task_page_size") or os.environ.get("PDF_TASK_PAGE_SIZE", "40")))\n',
        "global PDF task page size default",
    )
    text = replace_once(
        text,
        '        if doc["parser_id"] == "paper":\n'
        '            page_size = doc["parser_config"].get("task_page_size") or 22\n'
        '        if doc["parser_id"] in ["one", "knowledge_graph"] or doc["parser_config"].get("toc_extraction", False):\n'
        '            page_size = MAXIMUM_TASK_PAGE_NUMBER\n',
        '        if doc["parser_id"] == "paper":\n'
        '            page_size = max(1, int(doc["parser_config"].get("task_page_size") or os.environ.get("PDF_TASK_PAGE_SIZE", "40")))\n'
        '        if doc["parser_id"] in ["one", "knowledge_graph"] or doc["parser_config"].get("toc_extraction", False):\n'
        '            page_size = MAXIMUM_TASK_PAGE_NUMBER\n'
        '        layout_recognizer, _ = normalize_layout_recognizer(doc["parser_config"].get("layout_recognize", "DeepDOC"))\n'
        '        if layout_recognizer == "PaddleOCR":\n'
        '            paddleocr_page_size = max(1, int(os.environ.get("PADDLEOCR_TASK_PAGE_SIZE", "40")))\n'
        '            page_size = min(page_size, paddleocr_page_size)\n'
        '        page_size = adaptive_pdf_task_page_size(page_size)\n',
        "PaddleOCR task page size application",
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
    text = replace_once(
        text,
        '                return get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR) or ensure_paddleocr_from_env(tenant_id)\n',
        '                return ensure_paddleocr_from_env(tenant_id) or get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR)\n',
        "deterministic default PaddleOCR profile",
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
    text = replace_once(
        text,
        "    if blob_len == 0:\n"
        "        return blob\n\n"
        "    def try_open(data):\n",
        "    if blob_len == 0:\n"
        "        return blob\n"
        "    if blob_len > MAX_BLOB_SIZE_PDF:\n"
        "        return blob\n\n"
        "    def try_open(data):\n",
        "large PDF early repair bypass",
    )
    text = replace_once(
        text,
        "    if try_open(blob):\n"
        "        return blob\n\n"
        "    if blob_len > MAX_BLOB_SIZE_PDF:\n"
        "        return blob\n\n"
        "    repaired = repair_pdf_with_ghostscript(blob)\n",
        "    if try_open(blob):\n"
        "        return blob\n\n"
        "    repaired = repair_pdf_with_ghostscript(blob)\n",
        "remove late large PDF repair bypass",
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
        "from common.constants import ParserType\n",
        "from common.constants import ParserType\n"
        "from common.exceptions import TaskCanceledException\n",
        "refactored chunk cancellation import",
    )
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
    text = replace_once(
        text,
        "    except Exception as e:\n"
        "        ctx.progress_cb(-1, msg=\"Internal server error while chunking: %s\" % str(e).replace(\"'\", \"\"))\n"
        "        logging.exception(\"Chunking {}/{} got exception\".format(ctx.location, ctx.name))\n",
        "    except TaskCanceledException:\n"
        "        raise\n"
        "    except Exception as e:\n"
        "        ctx.progress_cb(-1, msg=\"Internal server error while chunking: %s\" % str(e).replace(\"'\", \"\"))\n"
        "        logging.exception(\"Chunking {}/{} got exception\".format(ctx.location, ctx.name))\n",
        "refactored chunk cancellation passthrough",
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

    naive_parser_target = checked_target(Path(sys.argv[14]), EXPECTED_NAIVE_PARSER_SHA256, "rag/app/naive.py")
    text = naive_parser_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        for embed_filename, embed_bytes in embeds:\n"
        "            try:\n",
        "        for embed_filename, embed_bytes in embeds:\n"
        "            if not re.search(r\"\\.(docx|pdf|csv|xlsx?|txt|py|js|java|c|cpp|h|php|go|ts|sh|cs|kt|sql|md|markdown|mdx|json|html?|doc|pptx?)$\", embed_filename, re.IGNORECASE):\n"
        "                logging.debug(\"Skipping unsupported embedded stream: %s\", embed_filename)\n"
        "                continue\n"
        "            try:\n",
        "skip unsupported embedded streams",
    )
    text = replace_once(
        text,
        "    sections, tables = pdf_parser(filename if not binary else binary, from_page=from_page, to_page=to_page, callback=callback)\n\n"
        "    tables = vision_figure_parser_pdf_wrapper(\n",
        "    sections, tables = pdf_parser(filename if not binary else binary, from_page=from_page, to_page=to_page, callback=callback)\n\n"
        "    if not sections and not tables:\n"
        "        if callback:\n"
        "            callback(0.3, \"[DeepDoc] no OCR sections found; trying embedded PDF text.\")\n"
        "        fallback_kwargs = dict(kwargs)\n"
        "        fallback_kwargs.pop(\"layout_recognizer\", None)\n"
        "        try:\n"
        "            plain_sections, plain_tables, plain_parser = by_plaintext(\n"
        "                filename=filename,\n"
        "                binary=binary,\n"
        "                from_page=from_page,\n"
        "                to_page=to_page,\n"
        "                callback=callback,\n"
        "                layout_recognizer=\"Plain Text\",\n"
        "                **fallback_kwargs,\n"
        "            )\n"
        "            if plain_sections or plain_tables:\n"
        "                if callback:\n"
        "                    callback(0.4, \"[DeepDoc] fallback succeeded with embedded PDF text.\")\n"
        "                return plain_sections, plain_tables, plain_parser\n"
        "        except Exception as exc:\n"
        "            logging.warning(\"Embedded PDF text fallback after DeepDoc failed: %s\", exc)\n\n"
        "    tables = vision_figure_parser_pdf_wrapper(\n",
        "DeepDoc empty-result fallback",
    )
    text = replace_once(
        text,
        "    pdf_parser = None\n"
        "    if tenant_id:\n"
        "        if not paddleocr_llm_name:\n"
        "            try:\n"
        '                paddleocr_llm_name = get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR) or ensure_paddleocr_from_env(tenant_id)\n'
        "            except Exception as e:  # best-effort fallback\n"
        '                logging.warning(f"fallback to env paddleocr: {e}")\n\n'
        "        if paddleocr_llm_name:\n"
        "            try:\n"
        "                ocr_model_config = get_model_config_from_provider_instance(tenant_id, LLMType.OCR, paddleocr_llm_name)\n"
        "                ocr_model = LLMBundle(tenant_id=tenant_id, model_config=ocr_model_config, lang=lang)\n"
        "                pdf_parser = ocr_model.mdl\n"
        "                sections, tables = pdf_parser.parse_pdf(\n"
        "                    filepath=filename,\n"
        "                    binary=binary,\n"
        "                    callback=callback,\n"
        "                    parse_method=parse_method,\n"
        "                    **kwargs,\n"
        "                )\n"
        "                return sections, tables, pdf_parser\n"
        "            except Exception as e:\n"
        '                logging.error(f"Failed to parse pdf via LLMBundle PaddleOCR ({paddleocr_llm_name}): {e}")\n\n'
        "        return None, None, None\n\n"
        "    if callback:\n"
        '        callback(-1, "PaddleOCR not found.")\n'
        "    return None, None, None\n",
        "    def fallback(reason: str):\n"
        '        logging.warning("PaddleOCR could not build PDF sections; continuing with fallback parsers: %s", reason)\n'
        "        if callback:\n"
        '            callback(0.15, f"[PaddleOCR] {reason}; trying embedded PDF text.")\n\n'
        "        fallback_kwargs = dict(kwargs)\n"
        '        fallback_kwargs.pop("layout_recognizer", None)\n'
        '        fallback_kwargs.pop("parse_method", None)\n'
        '        fallback_kwargs.pop("paddleocr_llm_name", None)\n\n'
        "        try:\n"
        "            sections, tables, parser = by_plaintext(\n"
        "                filename=filename,\n"
        "                binary=binary,\n"
        "                from_page=from_page,\n"
        "                to_page=to_page,\n"
        "                callback=callback,\n"
        '                layout_recognizer="Plain Text",\n'
        "                **fallback_kwargs,\n"
        "            )\n"
        "            if sections or tables:\n"
        "                if callback:\n"
        '                    callback(0.3, "[PaddleOCR] fallback succeeded with embedded PDF text.")\n'
        "                return sections, tables, parser\n"
        "        except Exception as exc:\n"
        '            logging.warning("Embedded PDF text fallback failed: %s", exc)\n\n'
        "        if callback:\n"
        '            callback(0.3, "[PaddleOCR] no embedded text found; continuing with DeepDoc.")\n'
        "        try:\n"
        "            return by_deepdoc(\n"
        "                filename=filename,\n"
        "                binary=binary,\n"
        "                from_page=from_page,\n"
        "                to_page=to_page,\n"
        "                lang=lang,\n"
        "                callback=callback,\n"
        "                pdf_cls=pdf_cls,\n"
        "                **fallback_kwargs,\n"
        "            )\n"
        "        except Exception as exc:\n"
        '            logging.warning("DeepDoc fallback after PaddleOCR failed: %s", exc)\n'
        "            if callback:\n"
        '                callback(0.4, f"[PaddleOCR] all PDF parsers returned no content: {exc}")\n'
        "            return [], [], None\n\n"
        "    explicit_paddleocr_model = bool(paddleocr_llm_name)\n"
        "    pdf_parser = None\n"
        "    if tenant_id:\n"
        "        if not paddleocr_llm_name:\n"
        "            try:\n"
        '                paddleocr_llm_name = ensure_paddleocr_from_env(tenant_id) or get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR)\n'
        "            except Exception as e:  # best-effort fallback\n"
        '                logging.warning(f"fallback to env paddleocr: {e}")\n\n'
        "        if paddleocr_llm_name:\n"
        "            try:\n"
        "                ocr_model_config = get_model_config_from_provider_instance(tenant_id, LLMType.OCR, paddleocr_llm_name)\n"
        "                ocr_model = LLMBundle(tenant_id=tenant_id, model_config=ocr_model_config, lang=lang)\n"
        "                pdf_parser = ocr_model.mdl\n"
        "                sections, tables = pdf_parser.parse_pdf(\n"
        "                    filepath=filename,\n"
        "                    binary=binary,\n"
        "                    callback=callback,\n"
        "                    from_page=from_page,\n"
        "                    to_page=to_page,\n"
        "                    parse_method=parse_method,\n"
        "                    **kwargs,\n"
        "                )\n"
        "                if sections or tables:\n"
        "                    return sections, tables, pdf_parser\n"
        '                return fallback("the OCR result contained no text sections")\n'
        "            except Exception as e:\n"
        '                logging.error(f"Failed to parse pdf via LLMBundle PaddleOCR ({paddleocr_llm_name}): {e}")\n'
        "                if explicit_paddleocr_model:\n"
        '                    raise RuntimeError(f"Configured PaddleOCR model {paddleocr_llm_name!r} is unavailable: {e}") from e\n'
        '                return fallback(f"request failed: {e}")\n\n'
        '        return fallback("no PaddleOCR model is configured")\n\n'
        '    return fallback("tenant information is unavailable")\n',
        "PaddleOCR PDF fallback chain",
    )
    naive_parser_target.write_text(text, encoding="utf-8")

    picture_parser_target = checked_target(Path(sys.argv[15]), EXPECTED_PICTURE_PARSER_SHA256, "rag/app/picture.py")
    text = picture_parser_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '            paddleocr_llm_name = get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR) or ensure_paddleocr_from_env(tenant_id)\n',
        '            paddleocr_llm_name = ensure_paddleocr_from_env(tenant_id) or get_first_provider_model_name(tenant_id, "PaddleOCR", LLMType.OCR)\n',
        "PaddleOCR image current environment model precedence",
    )
    text = replace_once(
        text,
        "        # Try PaddleOCR if configured as layout_recognize\n"
        "        txt = _try_paddleocr_image(filename, binary, tenant_id, parser_config, callback)\n\n"
        "        if not txt:\n",
        "        # Try PaddleOCR if configured as layout_recognize\n"
        "        paddleocr_selected = _is_paddleocr_selected(parser_config)\n"
        "        txt = _try_paddleocr_image(filename, binary, tenant_id, parser_config, callback)\n\n"
        "        if not txt and not paddleocr_selected:\n",
        "selected PaddleOCR fallback ownership",
    )
    text = replace_once(
        text,
        "            # Fallback to local deepdoc OCR\n"
        "            bxs = ocr(np.array(img))\n"
        '            txt = "\\n".join([t[0] for _, t in bxs if t[0]])\n',
        "            # Fallback to local deepdoc OCR\n"
        "            txt = _try_local_ocr_text(img)\n",
        "nonblocking local image OCR",
    )
    text = replace_once(
        text,
        '        callback(0.4, "Finish OCR: (%s ...)" % txt[:12])\n',
        '        if txt:\n'
        '            ocr_engine = "PaddleOCR" if paddleocr_selected else "local DeepDoc OCR"\n'
        '            callback(0.4, f"Finish {ocr_engine}: ({txt[:12]} ...)")\n'
        '        elif paddleocr_selected:\n'
        '            callback(0.4, "PaddleOCR produced no text; continuing with the CV LLM fallback.")\n',
        "accurate image OCR progress",
    )
    text = replace_once(
        text,
        "\n\ndef _try_paddleocr_image(filename, binary, tenant_id, parser_config, callback):\n",
        "\n\ndef _is_paddleocr_selected(parser_config):\n"
        '    layout_recognize = parser_config.get("layout_recognize", "")\n'
        "    if not layout_recognize:\n"
        "        return False\n"
        "    layout_recognizer, _ = normalize_layout_recognizer(layout_recognize)\n"
        '    return layout_recognizer == "PaddleOCR"\n\n\n'
        "def _try_paddleocr_image(filename, binary, tenant_id, parser_config, callback):\n",
        "PaddleOCR selection helper",
    )
    text = replace_once(
        text,
        "        if not paddleocr_llm_name:\n"
        '            return ""\n',
        "        if not paddleocr_llm_name:\n"
        '            callback(0.2, "PaddleOCR is selected but no model is configured; continuing with fallback processing.")\n'
        '            return ""\n',
        "missing PaddleOCR model progress",
    )
    text = replace_once(
        text,
        '            logging.warning("[PaddleOCR] parse_image not available, falling back to local OCR")\n'
        '            return ""\n',
        '            logging.warning("[PaddleOCR] parse_image is unavailable; continuing with fallback processing")\n'
        '            callback(0.2, "PaddleOCR image parsing is unavailable; continuing with fallback processing.")\n'
        '            return ""\n',
        "unavailable PaddleOCR image parser progress",
    )
    text = replace_once(
        text,
        '        logging.warning(f"[PaddleOCR] image parsing failed, falling back to local OCR: {e}")\n',
        '        logging.exception("[PaddleOCR] image parsing failed")\n'
        '        callback(0.2, f"PaddleOCR failed; continuing with fallback processing: {e}")\n'
        '        return ""\n',
        "PaddleOCR image failure progress",
    )
    text = replace_once(
        text,
        "        except Exception as e:\n"
        "            callback(prog=-1, msg=str(e))\n\n"
        "    return []\n",
        "        except Exception as e:\n"
        '            logging.warning("CV LLM image description failed; preserving OCR fallback: %s", e)\n'
        "            if not txt and paddleocr_selected:\n"
        '                callback(0.6, "CV LLM fallback unavailable; continuing with local DeepDoc OCR.")\n'
        "                txt = _try_local_ocr_text(img)\n"
        "            if txt:\n"
        '                callback(0.8, f"Using OCR text after CV LLM fallback: ({txt[:12]} ...)")\n'
        "                tokenize(doc, txt, eng, language=lang)\n"
        "            else:\n"
        '                callback(0.8, "No OCR text was recognized; creating an image chunk using its file name.")\n'
        "                tokenize(doc, filename, eng, language=lang)\n"
        "            return attach_media_context([doc], 0, image_ctx)\n\n"
        "    return []\n",
        "nonblocking image OCR fallback",
    )
    text = replace_once(
        text,
        "\n\ndef _is_paddleocr_selected(parser_config):\n",
        "\n\ndef _try_local_ocr_text(image):\n"
        "    try:\n"
        "        boxes = ocr(np.array(image))\n"
        '        return "\\n".join([text[0] for _, text in boxes if text[0]])\n'
        "    except Exception:\n"
        '        logging.exception("Local DeepDoc image OCR failed; continuing with fallback processing")\n'
        '        return ""\n\n\n'
        "def _is_paddleocr_selected(parser_config):\n",
        "local image OCR fallback helper",
    )
    picture_parser_target.write_text(text, encoding="utf-8")

    chunk_service_target = checked_target(
        Path(sys.argv[16]), EXPECTED_REFACTORED_CHUNK_SERVICE_SHA256, "task_executor_refactor/chunk_service.py"
    )
    text = chunk_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import logging\n",
        "import logging\nimport os\n",
        "refactored executor environment import",
    )
    text = replace_once(
        text,
        "        if ctx.size > settings.DOC_MAXIMUM_SIZE:\n",
        '        document_max_bytes = int(os.environ.get("LIG_DOCUMENT_MAX_BYTES", "0"))\n'
        "        if document_max_bytes > 0 and ctx.size > document_max_bytes:\n",
        "optional refactored executor document-size limit",
    )
    text = replace_once(
        text,
        '            self._progress(prog=-1, msg="File size exceeds( <= %dMb )" % (int(settings.DOC_MAXIMUM_SIZE / 1024 / 1024)))\n'
        '            self._task_context.recording_context.record("file_size_exceeded", True)\n'
        "            return []\n",
        '            self._task_context.recording_context.record("file_size_exceeded", True)\n'
        '            raise ValueError("File size exceeds configured LIG_DOCUMENT_MAX_BYTES (%dMb)" % (int(document_max_bytes / 1024 / 1024)))\n',
        "refactored executor oversized-file failure",
    )
    chunk_service_target.write_text(text, encoding="utf-8")

    email_parser_target = checked_target(Path(sys.argv[17]), EXPECTED_EMAIL_PARSER_SHA256, "rag/app/email.py")
    text = email_parser_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    parser_config = kwargs.get(\n"
        "        \"parser_config\",\n"
        "        {\"chunk_token_num\": 512, \"delimiter\": \"\\n!?。；！？\", \"layout_recognize\": \"DeepDOC\"},\n"
        "    )\n",
        "    parser_config = {\n"
        "        \"chunk_token_num\": 512,\n"
        "        \"delimiter\": \"\\n!?。；！？\",\n"
        "        \"layout_recognize\": \"DeepDOC\",\n"
        "        **(kwargs.get(\"parser_config\") or {}),\n"
        "    }\n",
        "email parser defaults",
    )
    email_parser_target.write_text(text, encoding="utf-8")

    redis_conn_target = checked_target(Path(sys.argv[18]), EXPECTED_REDIS_CONN_SHA256, "rag/utils/redis_conn.py")
    text = redis_conn_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    def get_pending_msg(self, queue, group_name):\n",
        "    def claim_stale_message(self, queue_names, group_name, consumer_name, min_idle_time_ms):\n"
        "        \"\"\"Claim one message abandoned by an inactive or replaced consumer.\"\"\"\n"
        "        for queue_name in queue_names:\n"
        "            try:\n"
        "                group_info = self.REDIS.xinfo_groups(queue_name)\n"
        "                if not any(gi[\"name\"] == group_name for gi in group_info):\n"
        "                    continue\n"
        "                claimed = self.REDIS.xautoclaim(\n"
        "                    queue_name, group_name, consumer_name, min_idle_time_ms,\n"
        "                    start_id=\"0-0\", count=1,\n"
        "                )\n"
        "                messages = claimed[1] if len(claimed) > 1 else []\n"
        "                if not messages:\n"
        "                    continue\n"
        "                msg_id, payload = messages[0]\n"
        "                logging.warning(\n"
        "                    \"Claimed stale queue message %s from %s for consumer %s\",\n"
        "                    msg_id, queue_name, consumer_name,\n"
        "                )\n"
        "                return RedisMsg(self.REDIS, queue_name, group_name, msg_id, payload)\n"
        "            except Exception as e:\n"
        "                if \"no such key\" not in str(e).lower():\n"
        "                    logging.warning(\n"
        "                        \"RedisDB.claim_stale_message %s got exception: %s\", queue_name, e\n"
        "                    )\n"
        "                    self.__open__()\n"
        "        return None\n\n"
        "    def get_pending_msg(self, queue, group_name):\n",
        "stale consumer message recovery",
    )
    text = replace_once(
        text,
        "    def release(self):\n"
        "        REDIS_CONN.delete_if_equal(self.lock_key, self.lock_value)\n",
        "    def refresh(self):\n"
        "        try:\n"
        "            return bool(self.lock.reacquire())\n"
        "        except Exception:\n"
        "            logging.exception(\"Failed to refresh Redis lock %s\", self.lock_key)\n"
        "            return False\n\n"
        "    def release(self):\n"
        "        REDIS_CONN.delete_if_equal(self.lock_key, self.lock_value)\n",
        "renewable task lease support",
    )
    redis_conn_target.write_text(text, encoding="utf-8")

    tenant_model_target = checked_target(
        Path(sys.argv[19]),
        EXPECTED_TENANT_MODEL_SERVICE_SHA256,
        "api/db/joint_services/tenant_model_service.py",
    )
    text = tenant_model_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import logging\nimport os\nimport enum\nimport json\n",
        "import logging\nimport os\nimport enum\nimport json\nimport time\nfrom urllib.parse import urlsplit\n\nimport requests\n",
        "PaddleOCR profile health imports",
    )
    text = replace_once(
        text,
        "from api.db.services.tenant_llm_service import TenantService\n",
        "from api.db.db_models import DB, Document, Knowledgebase\n"
        "from api.db.services.tenant_llm_service import TenantService\n",
        "PaddleOCR profile migration models",
    )
    text = replace_once(
        text,
        "def _ensure_ocr_provider_from_env(tenant_id: str, provider_name: str, model_name: str, config: dict | None) -> str | None:\n",
        "_OCR_ENDPOINT_HEALTH_CACHE: dict[str, tuple[float, bool]] = {}\n\n\n"
        "def _ocr_endpoint_available(base_url: str, cache_seconds: float = 5.0) -> bool:\n"
        "    now = time.monotonic()\n"
        "    cached = _OCR_ENDPOINT_HEALTH_CACHE.get(base_url)\n"
        "    if cached and now - cached[0] < cache_seconds:\n"
        "        return cached[1]\n"
        "    parts = urlsplit(base_url)\n"
        "    if not parts.scheme or not parts.netloc:\n"
        "        available = False\n"
        "    else:\n"
        "        health_url = f\"{parts.scheme}://{parts.netloc}/health\"\n"
        "        try:\n"
        "            response = requests.get(health_url, timeout=1.0)\n"
        "            available = response.ok and response.json().get(\"status\") == \"ok\"\n"
        "        except (requests.RequestException, ValueError, TypeError):\n"
        "            available = False\n"
        "    _OCR_ENDPOINT_HEALTH_CACHE[base_url] = (now, available)\n"
        "    return available\n\n\n"
        "def _set_ocr_profile_status(provider_obj, instance_name: str, active: bool) -> bool:\n"
        "    instance_obj = TenantModelInstanceService.get_by_provider_id_and_instance_name(provider_obj.id, instance_name)\n"
        "    if not instance_obj:\n"
        "        return False\n"
        "    desired = ActiveStatusEnum.ACTIVE.value if active else ActiveStatusEnum.INACTIVE.value\n"
        "    changed = False\n"
        "    if instance_obj.status != desired:\n"
        "        TenantModelInstanceService.update_by_id(instance_obj.id, {\"status\": desired})\n"
        "        changed = True\n"
        "    models = TenantModelService.get_models_by_instance_id(instance_obj.id)\n"
        "    changed_models = [model.id for model in models if model.status != desired]\n"
        "    if changed_models:\n"
        "        TenantModelService.batch_update_model_status(changed_models, desired)\n"
        "        changed = True\n"
        "    return changed\n\n\n"
        "def _replace_profile_reference(value, old_name: str, new_name: str):\n"
        "    if isinstance(value, dict):\n"
        "        replaced = {}\n"
        "        changed = 0\n"
        "        for key, item in value.items():\n"
        "            new_item, item_changed = _replace_profile_reference(item, old_name, new_name)\n"
        "            replaced[key] = new_item\n"
        "            changed += item_changed\n"
        "        return replaced, changed\n"
        "    if isinstance(value, list):\n"
        "        replaced = []\n"
        "        changed = 0\n"
        "        for item in value:\n"
        "            new_item, item_changed = _replace_profile_reference(item, old_name, new_name)\n"
        "            replaced.append(new_item)\n"
        "            changed += item_changed\n"
        "        return replaced, changed\n"
        "    if isinstance(value, str):\n"
        "        occurrences = value.count(old_name)\n"
        "        return value.replace(old_name, new_name), occurrences\n"
        "    return value, 0\n\n\n"
        "def _migrate_profile_references(tenant_id: str, provider_name: str, old_instance_name: str, canonical_instance_name: str, model_name: str) -> int:\n"
        "    old_composite = f\"{model_name}@{old_instance_name}@{provider_name}\"\n"
        "    new_composite = f\"{model_name}@{canonical_instance_name}@{provider_name}\"\n"
        "    changed = 0\n"
        "    knowledgebases = list(Knowledgebase.select().where(Knowledgebase.tenant_id == tenant_id))\n"
        "    kb_ids = [kb.id for kb in knowledgebases]\n"
        "    documents = list(Document.select().where(Document.kb_id.in_(kb_ids))) if kb_ids else []\n"
        "    with DB.atomic():\n"
        "        for record in [*knowledgebases, *documents]:\n"
        "            parser_config, count = _replace_profile_reference(record.parser_config or {}, old_composite, new_composite)\n"
        "            if not count:\n"
        "                continue\n"
        "            record.parser_config = parser_config\n"
        "            record.save(only=[record.__class__.parser_config])\n"
        "            changed += count\n"
        "    return changed\n\n\n"
        "def _ensure_ocr_provider_from_env(tenant_id: str, provider_name: str, model_name: str, config: dict | None) -> str | None:\n",
        "PaddleOCR profile lifecycle and reference migration helpers",
    )
    text = replace_once(
        text,
        "def get_tenant_default_model_by_type(tenant_id: str, model_type: str | enum.Enum):\n",
        "def ensure_paddleocr_vl_from_env(tenant_id: str) -> str | None:\n"
        '    if os.environ.get("PADDLEOCR_VL_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:\n'
        "        return None\n"
        "    base_url = os.environ.get(\"PADDLEOCR_VL_BASE_URL\")\n"
        "    access_token = os.environ.get(\"PADDLEOCR_VL_ACCESS_TOKEN\")\n"
        "    if not base_url or not access_token:\n"
        "        return None\n"
        "    config = dict(PADDLEOCR_DEFAULT_CONFIG)\n"
        '    config["PADDLEOCR_BASE_URL"] = base_url\n'
        '    config["PADDLEOCR_ACCESS_TOKEN"] = access_token\n'
        '    config["PADDLEOCR_ALGORITHM"] = os.environ.get("PADDLEOCR_VL_MODEL", "PaddleOCR-VL-1.6")\n'
        "    model = _ensure_ocr_provider_from_env(\n"
        "        tenant_id,\n"
        '        "PaddleOCR",\n'
        '        "paddleocr-vl-from-env",\n'
        "        config,\n"
        "    )\n"
        "    provider_obj = TenantModelProviderService.get_by_tenant_id_and_provider_name(tenant_id, \"PaddleOCR\")\n"
        "    available = _ocr_endpoint_available(base_url)\n"
        "    if provider_obj and _set_ocr_profile_status(provider_obj, \"paddleocr-vl-from-env\", available):\n"
        "        logging.info(\"PaddleOCR-VL bundled profile is now %s for tenant %s\", \"active\" if available else \"inactive\", tenant_id)\n"
        "    return model if available else None\n\n\n"
        "def get_tenant_default_model_by_type(tenant_id: str, model_type: str | enum.Enum):\n",
        "environment-managed PaddleOCR-VL provider",
    )
    text = replace_once(
        text,
        "    api_key = json.dumps(config)\n"
        "    instance_obj = TenantModelInstanceService.get_by_provider_id_and_api_key(provider_obj.id, api_key)\n"
        "    if not instance_obj:\n"
        "        instance_obj = TenantModelInstanceService.create_instance(\n"
        "            provider_id=provider_obj.id,\n"
        "            instance_name=model_name,\n"
        "            api_key=api_key,\n"
        "            extra=\"{}\",\n"
        "        )\n\n",
        "    api_key = json.dumps(config)\n"
        "    instance_obj = TenantModelInstanceService.get_by_provider_id_and_instance_name(provider_obj.id, model_name)\n"
        "    if not instance_obj:\n"
        "        TenantModelInstanceService.create_instance(\n"
        "            provider_id=provider_obj.id,\n"
        "            instance_name=model_name,\n"
        "            api_key=api_key,\n"
        "            extra=\"{}\",\n"
        "        )\n"
        "        instance_obj = TenantModelInstanceService.get_by_provider_id_and_instance_name(provider_obj.id, model_name)\n"
        "        if not instance_obj:\n"
        "            raise RuntimeError(f\"Failed to create {provider_name} model instance for tenant {tenant_id}\")\n"
        "    # Existing instances may have been edited in the UI. Do not overwrite\n"
        "    # their shared database configuration from one container's environment.\n"
        "    # Retire only legacy auto-suffixed copies that are semantically identical\n"
        "    # to the canonical bundled profile. Rewrite dataset and document references\n"
        "    # transactionally before disabling the duplicate rows.\n"
        "    if model_name in {\"paddleocr-from-env\", \"paddleocr-vl-from-env\"}:\n"
        "        try:\n"
        "            canonical_config = json.loads(instance_obj.api_key)\n"
        "        except (TypeError, ValueError, json.JSONDecodeError):\n"
        "            canonical_config = None\n"
        "        if canonical_config is not None:\n"
        "            duplicate_prefix = f\"{model_name}(\"\n"
        "            for candidate in TenantModelInstanceService.get_all_by_provider_id(provider_obj.id):\n"
        "                suffix = candidate.instance_name[len(duplicate_prefix):-1] if (\n"
        "                    candidate.instance_name.startswith(duplicate_prefix)\n"
        "                    and candidate.instance_name.endswith(\")\")\n"
        "                ) else \"\"\n"
        "                if not suffix.isdigit():\n"
        "                    continue\n"
        "                try:\n"
        "                    candidate_config = json.loads(candidate.api_key)\n"
        "                except (TypeError, ValueError, json.JSONDecodeError):\n"
        "                    continue\n"
        "                canonical_url = str(canonical_config.get(\"PADDLEOCR_BASE_URL\", \"\")).rstrip(\"/\")\n"
        "                candidate_url = str(candidate_config.get(\"PADDLEOCR_BASE_URL\", \"\")).rstrip(\"/\")\n"
        "                if candidate_url != canonical_url or candidate_config.get(\"PADDLEOCR_ALGORITHM\") != canonical_config.get(\"PADDLEOCR_ALGORITHM\"):\n"
        "                    continue\n"
        "                migrated = _migrate_profile_references(\n"
        "                    tenant_id, provider_name, candidate.instance_name, instance_obj.instance_name, model_name\n"
        "                )\n"
        "                duplicate_models = TenantModelService.get_models_by_instance_id(candidate.id)\n"
        "                model_ids_to_disable = [\n"
        "                    duplicate.id for duplicate in duplicate_models\n"
        "                    if duplicate.status != ActiveStatusEnum.INACTIVE.value\n"
        "                ]\n"
        "                status_changed = candidate.status != ActiveStatusEnum.INACTIVE.value or bool(model_ids_to_disable)\n"
        "                if candidate.status != ActiveStatusEnum.INACTIVE.value:\n"
        "                    TenantModelInstanceService.update_by_id(\n"
        "                        candidate.id, {\"status\": ActiveStatusEnum.INACTIVE.value}\n"
        "                    )\n"
        "                if model_ids_to_disable:\n"
        "                    TenantModelService.batch_update_model_status(\n"
        "                        model_ids_to_disable, ActiveStatusEnum.INACTIVE.value\n"
        "                    )\n"
        "                if migrated or status_changed:\n"
        "                    logging.info(\n"
        "                        \"Retired duplicate bundled %s model instance %s for tenant %s; migrated references=%d\",\n"
        "                        provider_name, candidate.instance_name, tenant_id, migrated,\n"
        "                    )\n\n",
        "environment-managed OCR provider creation only",
    )
    text = replace_once(
        text,
        "def ensure_paddleocr_from_env(tenant_id: str) -> str | None:\n"
        "    return _ensure_ocr_provider_from_env(\n"
        "        tenant_id,\n"
        '        "PaddleOCR",\n'
        '        "paddleocr-from-env",\n'
        "        _collect_env_config(PADDLEOCR_ENV_KEYS, PADDLEOCR_DEFAULT_CONFIG),\n"
        "    )\n",
        "def ensure_paddleocr_from_env(tenant_id: str) -> str | None:\n"
        "    # Model-list refresh calls this entry point. Provision both bundled\n"
        "    # profiles as separate instances so normal OCR, VL, and user-created\n"
        "    # remote endpoints never collapse into one profile.\n"
        "    normal_model = _ensure_ocr_provider_from_env(\n"
        "        tenant_id,\n"
        '        "PaddleOCR",\n'
        '        "paddleocr-from-env",\n'
        "        _collect_env_config(PADDLEOCR_ENV_KEYS, PADDLEOCR_DEFAULT_CONFIG),\n"
        "    )\n"
        "    ensure_paddleocr_vl_from_env(tenant_id)\n"
        "    return normal_model\n",
        "separate bundled PaddleOCR profiles",
    )
    tenant_model_target.write_text(text, encoding="utf-8")

    api_app_target = checked_target(Path(sys.argv[20]), EXPECTED_API_APP_SHA256, "api/apps/__init__.py")
    text = api_app_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'app.config["BODY_TIMEOUT"] = int(os.environ.get("QUART_BODY_TIMEOUT", 600))\n',
        'body_timeout = int(os.environ.get("QUART_BODY_TIMEOUT", "0"))\n'
        'app.config["BODY_TIMEOUT"] = body_timeout or None\n',
        "unlimited slow upload body timeout support",
    )
    text = replace_once(
        text,
        'app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 1024 * 1024 * 1024))\n',
        'max_content_length = int(os.environ.get("MAX_CONTENT_LENGTH", "0"))\n'
        'app.config["MAX_CONTENT_LENGTH"] = max_content_length or None\n',
        "unlimited HTTP document upload support",
    )
    text = replace_once(
        text,
        '        except Exception as e_jwt:\n'
        '            logging.warning(f"load_user from jwt got exception {e_jwt}")\n',
        '        except Exception as e_jwt:\n'
        '            if auth_token.count(".") == 2:\n'
        '                logging.warning(f"load_user from jwt got exception {e_jwt}")\n'
        '            else:\n'
        '                logging.debug("Bearer credential is not a JWT; trying API token authentication")\n',
        "quiet expected API-token authentication fallback",
    )
    api_app_target.write_text(text, encoding="utf-8")

    admin_server_target = checked_target(Path(sys.argv[21]), EXPECTED_ADMIN_SERVER_SHA256, "admin/server/admin_server.py")
    text = admin_server_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 1024 * 1024 * 1024))\n',
        '    max_content_length = int(os.environ.get("MAX_CONTENT_LENGTH", "0"))\n'
        '    app.config["MAX_CONTENT_LENGTH"] = max_content_length or None\n',
        "unlimited admin upload support",
    )
    admin_server_target.write_text(text, encoding="utf-8")

    embedding_service_target = checked_target(
        Path(sys.argv[22]),
        EXPECTED_EMBEDDING_SERVICE_SHA256,
        "rag/svr/task_executor_refactor/embedding_service.py",
    )
    text = embedding_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from typing import Any, Dict, List, Tuple\n",
        "import asyncio\nfrom typing import Any, Dict, List, Tuple\n",
        "refactored embedding asyncio import",
    )
    # The upstream loop awaits each batch in turn, so the embedding backend never
    # sees more than one request and cannot group them into a forward pass.
    # Dispatch them together and let embed_limiter bound what is in flight.
    text = replace_once(
        text,
        "        # Batch encode contents using EmbeddingUtils\n"
        "        vects_batches = []\n"
        "        for i in range(0, len(contents), self._embedding_batch_size):\n"
        "            batch = contents[i : i + self._embedding_batch_size]\n"
        "            async with self._task_context.embed_limiter:\n"
        "                vts, c = await thread_pool_exec(\n"
        "                    self._batch_encode_wrapper,\n"
        "                    [truncate(t, embedding_model.max_length - 10) for t in batch],\n"
        "                    embedding_model,\n"
        "                )\n"
        "            vects_batches.append(vts)\n"
        "            tk_count += c\n"
        "            if self._task_context.progress_cb:\n"
        '                self._task_context.progress_cb(prog=0.7 + 0.2 * (i + 1) / len(contents), msg="")\n',
        "        # Batch encode contents using EmbeddingUtils. Batches are dispatched\n"
        "        # together so the backend can group them into one forward pass;\n"
        "        # embed_limiter bounds how many are actually in flight, and at 1 this\n"
        "        # behaves exactly like the sequential loop it replaces.\n"
        "        embedded = 0\n\n"
        "        async def encode_at(start: int):\n"
        "            nonlocal embedded\n"
        "            batch = contents[start : start + self._embedding_batch_size]\n"
        "            async with self._task_context.embed_limiter:\n"
        "                vts, c = await thread_pool_exec(\n"
        "                    self._batch_encode_wrapper,\n"
        "                    [truncate(t, embedding_model.max_length - 10) for t in batch],\n"
        "                    embedding_model,\n"
        "                )\n"
        "            embedded += len(batch)\n"
        "            if self._task_context.progress_cb:\n"
        '                self._task_context.progress_cb(prog=0.7 + 0.2 * embedded / len(contents), msg="")\n'
        "            return vts, c\n\n"
        "        # Let the first failure propagate rather than collecting exceptions:\n"
        "        # gather marks the siblings' exceptions retrieved on its own, and the\n"
        "        # encode itself runs in a thread pool that a cancellation cannot\n"
        "        # interrupt, so waiting for them only delays unwinding past the\n"
        "        # cancellation grace period.\n"
        "        results = await asyncio.gather(*[encode_at(start) for start in range(0, len(contents), self._embedding_batch_size)])\n"
        "        vects_batches = [vts for vts, _ in results]\n"
        "        tk_count += sum(c for _, c in results)\n",
        "concurrent refactored embedding batches",
    )
    embedding_service_target.write_text(text, encoding="utf-8")

    # embed_limiter shared MAX_CONCURRENT_CHUNK_BUILDERS with the parser limiter,
    # so embedding concurrency could not be raised without shrinking the memory
    # budget that sizes OCR page batches.
    limiter_target = checked_target(
        Path(sys.argv[28]),
        EXPECTED_TASK_EXECUTOR_LIMITER_SHA256,
        "rag/svr/task_executor_limiter.py",
    )
    text = limiter_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'MAX_CONCURRENT_MINIO = int(os.environ.get("MAX_CONCURRENT_MINIO", "10"))\n',
        'MAX_CONCURRENT_MINIO = int(os.environ.get("MAX_CONCURRENT_MINIO", "10"))\n'
        "# Parser concurrency and embedding concurrency pull in opposite directions: the\n"
        "# first divides the memory budget for page batching, the second decides how many\n"
        "# requests the embedding backend can group into one forward pass. Defaulting to\n"
        "# the parser value keeps the previous behaviour when this is not set.\n"
        'MAX_CONCURRENT_EMBEDDERS = int(os.environ.get("MAX_CONCURRENT_EMBEDDERS", str(MAX_CONCURRENT_CHUNK_BUILDERS)))\n',
        "embedding concurrency setting",
    )
    text = replace_once(
        text,
        "embed_limiter = LoopLocalSemaphore(MAX_CONCURRENT_CHUNK_BUILDERS)\n",
        "embed_limiter = LoopLocalSemaphore(MAX_CONCURRENT_EMBEDDERS)\n",
        "embedding limiter decoupling",
    )
    limiter_target.write_text(text, encoding="utf-8")

    dataflow_service_target = checked_target(
        Path(sys.argv[23]),
        EXPECTED_DATAFLOW_SERVICE_SHA256,
        "rag/svr/task_executor_refactor/dataflow_service.py",
    )
    text = dataflow_service_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    @timeout(60)\n"
        "    async def _embed_chunks(self, chunks: List[Dict], token_consumption: int) -> Tuple[Optional[List[Dict]], int]:\n",
        "    async def _embed_chunks(self, chunks: List[Dict], token_consumption: int) -> Tuple[Optional[List[Dict]], int]:\n",
        "dataflow aggregate embedding timeout removal",
    )
    dataflow_service_target.write_text(text, encoding="utf-8")

    ocr_model_target = checked_target(Path(sys.argv[24]), EXPECTED_OCR_MODEL_SHA256, "rag/llm/ocr_model.py")
    text = ocr_model_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        self.paddleocr_algorithm = _resolve_config(\"paddleocr_algorithm\", \"PADDLEOCR_ALGORITHM\", \"PaddleOCR-VL\")\n"
        "        self.paddleocr_access_token = _resolve_config(\"paddleocr_access_token\", \"PADDLEOCR_ACCESS_TOKEN\", None)\n",
        "        self.paddleocr_algorithm = _resolve_config(\"paddleocr_algorithm\", \"PADDLEOCR_ALGORITHM\", \"PaddleOCR-VL\")\n"
        "        self.paddleocr_access_token = _resolve_config(\"paddleocr_access_token\", \"PADDLEOCR_ACCESS_TOKEN\", None)\n"
        "        self.paddleocr_api_mode = _resolve_config(\"paddleocr_api_mode\", \"PADDLEOCR_API_MODE\", \"auto\")\n"
        "        self.paddleocr_direct_workers = int(_resolve_config(\"paddleocr_direct_workers\", \"PADDLEOCR_DIRECT_WORKERS\", 8))\n"
        "        self.paddleocr_direct_render_dpi = int(_resolve_config(\"paddleocr_direct_render_dpi\", \"PADDLEOCR_DIRECT_RENDER_DPI\", 144))\n",
        "database-managed PaddleOCR execution settings",
    )
    text = replace_once(
        text,
        "            algorithm=self.paddleocr_algorithm,\n"
        "        )\n",
        "            algorithm=self.paddleocr_algorithm,\n"
        "            api_mode=self.paddleocr_api_mode,\n"
        "            direct_workers=self.paddleocr_direct_workers,\n"
        "            direct_render_dpi=self.paddleocr_direct_render_dpi,\n"
        "        )\n",
        "PaddleOCR execution settings forwarding",
    )
    text = replace_once(
        text,
        "    def parse_pdf(self, filepath: str, binary=None, callback=None, parse_method: str = \"raw\", **kwargs):\n"
        "        ok, reason = self.check_available()\n"
        "        if not ok:\n"
        "            raise RuntimeError(f\"PaddleOCR server not accessible: {reason}\")\n",
        "    @staticmethod\n"
        "    def _apply_dataset_overrides(kwargs: dict) -> dict:\n"
        "        # Dataset settings are stored with paddleocr_* names, while the\n"
        "        # parser accepts generic names. Translate them for every task so\n"
        "        # all executor containers consume the shared DB value.\n"
        "        resolved = dict(kwargs)\n"
        "        for source, target in {\n"
        "            \"paddleocr_api_url\": \"base_url\",\n"
        "            \"paddleocr_base_url\": \"base_url\",\n"
        "            \"paddleocr_access_token\": \"access_token\",\n"
        "            \"paddleocr_algorithm\": \"algorithm\",\n"
        "            \"paddleocr_api_mode\": \"api_mode\",\n"
        "            \"paddleocr_direct_workers\": \"direct_workers\",\n"
        "            \"paddleocr_direct_render_dpi\": \"direct_render_dpi\",\n"
        "        }.items():\n"
        "            if source in resolved and resolved[source] not in (None, \"\"):\n"
        "                resolved[target] = resolved.pop(source)\n"
        "        return resolved\n\n"
        "    def parse_pdf(self, filepath: str, binary=None, callback=None, parse_method: str = \"raw\", **kwargs):\n"
        "        kwargs = self._apply_dataset_overrides(kwargs)\n"
        "        ok, reason = self.check_available()\n"
        "        if not ok:\n"
        "            raise RuntimeError(f\"PaddleOCR server not accessible: {reason}\")\n",
        "dataset PaddleOCR override translation",
    )
    text = replace_once(
        text,
        "    def parse_image(self, filepath: str, binary=None, callback=None, **kwargs) -> str:\n"
        "        ok, reason = self.check_available()\n"
        "        if not ok:\n"
        "            raise RuntimeError(f\"PaddleOCR server not accessible: {reason}\")\n",
        "    def parse_image(self, filepath: str, binary=None, callback=None, **kwargs) -> str:\n"
        "        kwargs = self._apply_dataset_overrides(kwargs)\n"
        "        ok, reason = self.check_available()\n"
        "        if not ok:\n"
        "            raise RuntimeError(f\"PaddleOCR server not accessible: {reason}\")\n",
        "dataset PaddleOCR image override translation",
    )
    ocr_model_target.write_text(text, encoding="utf-8")

    # Infinity returns a table handle without contacting the server, so "does this
    # table exist" must be answered from list_tables() instead of from whether
    # get_table() raises. Otherwise every index_exist() guard reports True for a
    # missing table and the failure surfaces later as "Table ... doesn't exist".
    infinity_conn_target = checked_target(
        Path(sys.argv[25]),
        EXPECTED_INFINITY_CONN_SHA256,
        "rag/utils/infinity_conn.py",
    )
    text = infinity_conn_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "            try:\n"
        "                table_instance = db_instance.get_table(table_name)\n"
        "            except InfinityException as e:\n"
        "                # src/common/status.cppm, kTableNotExist = 3022\n"
        "                if e.error_code != ErrorCode.TABLE_NOT_EXIST:\n"
        "                    raise\n"
        "                vector_size = 0\n",
        "            if table_name not in db_instance.list_tables().table_names:\n"
        "                vector_size = 0\n",
        "infinity insert table existence check",
    )
    text = replace_once(
        text,
        "                # Fallback: Create table with base schema (shouldn't normally happen as init_kb() creates it)\n"
        '                self.logger.debug(f"Fallback: Creating table {table_name} with base schema, parser_id: {parser_id}")\n'
        "                self.create_idx(index_name, knowledgebase_id, vector_size, parser_id)\n"
        "                table_instance = db_instance.get_table(table_name)\n",
        "                # init_kb() normally creates the table before any insert reaches here.\n"
        '                self.logger.warning(f"Creating missing table {table_name} with base schema, parser_id: {parser_id}")\n'
        "                self.create_idx(index_name, knowledgebase_id, vector_size, parser_id)\n"
        "            table_instance = db_instance.get_table(table_name)\n",
        "infinity insert missing table creation",
    )
    infinity_conn_target.write_text(text, encoding="utf-8")

    infinity_conn_base_target = checked_target(
        Path(sys.argv[26]),
        EXPECTED_INFINITY_CONN_BASE_SHA256,
        "common/doc_store/infinity_conn_base.py",
    )
    text = infinity_conn_base_target.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "            db_instance = inf_conn.get_database(self.dbName)\n"
        "            _ = db_instance.get_table(table_name)\n"
        "            return True\n"
        "        except Exception as e:\n"
        '            self.logger.warning(f"INFINITY indexExist {str(e)}")\n',
        "            db_instance = inf_conn.get_database(self.dbName)\n"
        "            return table_name in db_instance.list_tables().table_names\n"
        "        except Exception as e:\n"
        '            self.logger.warning(f"INFINITY index_exist {str(e)}")\n',
        "infinity index_exist table listing",
    )
    infinity_conn_base_target.write_text(text, encoding="utf-8")

    # A document split into many page-range tasks aggregates every task log into
    # one TEXT column. Past 64 KiB the whole row update fails, which froze both
    # the log and the progress percentage for the rest of the run.
    document_service_target = checked_target(
        Path(sys.argv[27]),
        EXPECTED_DOCUMENT_SERVICE_SHA256,
        "api/db/services/document_service.py",
    )
    text = document_service_target.read_text(encoding="utf-8")
    text = replace_once(text, "import logging\n", "import logging\nimport os\n", "document log limit environment import")
    text = replace_once(
        text,
        "from rag.nlp import search\n"
        "from rag.utils.redis_conn import REDIS_CONN\n",
        "from rag.nlp import search\n"
        "from rag.utils.redis_conn import REDIS_CONN\n\n"
        "# The LIG schema migrates progress logs to LONGTEXT. Keep a configurable\n"
        "# recent tail so the UI remains responsive without the old 64 KiB ceiling.\n"
        'DOC_PROGRESS_MSG_MAX_BYTES = int(os.environ.get("DOC_PROGRESS_MSG_MAX_BYTES", "4194304"))\n\n\n'
        "def trim_tail_by_bytes(text: str, max_bytes: int) -> str:\n"
        '    """Keep the most recent whole lines of text that fit in max_bytes of UTF-8."""\n'
        '    encoded = text.encode("utf-8")\n'
        "    if len(encoded) <= max_bytes:\n"
        "        return text\n"
        "    tail = encoded[-max_bytes:]\n"
        '    # "\\n" is ASCII, so cutting after one lands on a character boundary.\n'
        '    newline = tail.find(b"\\n")\n'
        "    if newline >= 0:\n"
        "        tail = tail[newline + 1 :]\n"
        '    return tail.decode("utf-8", errors="ignore")\n',
        "document progress message trimming helper",
    )
    text = replace_once(
        text,
        "                if msg:\n"
        '                    info["progress_msg"] = msg\n',
        "                if msg:\n"
        "                    progress_msg = msg\n",
        "document progress message split assignment",
    )
    text = replace_once(
        text,
        '                        info["progress_msg"] += "\\n%d tasks are ahead in the queue..." % queue_ahead\n',
        '                        progress_msg += "\\n%d tasks are ahead in the queue..." % queue_ahead\n',
        "document progress message split append",
    )
    text = replace_once(
        text,
        '                    info["progress_msg"] = "%d tasks are ahead in the queue..." % queue_ahead\n',
        '                    progress_msg = "%d tasks are ahead in the queue..." % queue_ahead\n',
        "document progress message split fallback",
    )
    text = replace_once(
        text,
        "                (cls.model.update(info).where((cls.model.id == d[\"id\"]) & ((cls.model.run.is_null(True)) | (cls.model.run != TaskStatus.CANCEL.value))).execute())\n"
        "            except Exception as e:\n"
        "                if str(e).find(\"'0'\") < 0:\n"
        '                    logging.exception("fetch task exception")\n',
        "                not_canceled = (cls.model.run.is_null(True)) | (cls.model.run != TaskStatus.CANCEL.value)\n"
        '                cls.model.update(info).where((cls.model.id == d["id"]) & not_canceled).execute()\n'
        "                # progress_msg concatenates every task's log, so a document split\n"
        "                # into many page-range tasks produces megabytes of text against a\n"
        "                # 64 KiB TEXT column. Write it separately from the progress fields\n"
        "                # and trim it, so an oversized log can never stall progress.\n"
        "                try:\n"
        '                    cls.model.update(progress_msg=trim_tail_by_bytes(progress_msg, DOC_PROGRESS_MSG_MAX_BYTES)).where((cls.model.id == d["id"]) & not_canceled).execute()\n'
        "                except Exception:\n"
        '                    logging.exception("update progress_msg failed for document %s", d["id"])\n'
        "            except Exception as e:\n"
        "                if str(e).find(\"'0'\") < 0:\n"
        '                    logging.exception("update document progress failed for %s: %s", d["id"], e)\n',
        "document progress and log split write",
    )
    document_service_target.write_text(text, encoding="utf-8")

    settings_target = checked_target(Path(sys.argv[29]), EXPECTED_SETTINGS_SHA256, "common/settings.py")
    text = settings_target.read_text(encoding="utf-8")
    text = replace_once(text, "from common.misc_utils import pip_install_torch\n", "", "settings torch helper import")
    text = replace_once(
        text,
        "def check_and_install_torch():\n"
        "    global PARALLEL_DEVICES\n"
        "    try:\n"
        "        pip_install_torch()\n"
        "        import torch.cuda\n\n"
        "        PARALLEL_DEVICES = torch.cuda.device_count()\n"
        "        logging.info(f\"found {PARALLEL_DEVICES} gpus\")\n"
        "    except Exception:\n"
        "        logging.info(\"can't import package 'torch'\")\n",
        "def check_and_install_torch():\n"
        "    global PARALLEL_DEVICES\n"
        "    from lig_runtime.gpu_detection import onnx_cuda_device_count\n\n"
        "    PARALLEL_DEVICES = onnx_cuda_device_count()\n"
        "    logging.info(\"found %s ONNX CUDA device(s)\", PARALLEL_DEVICES)\n",
        "settings ONNX GPU detection",
    )
    settings_target.write_text(text, encoding="utf-8")

    deepdoc_ocr_target = checked_target(Path(sys.argv[30]), EXPECTED_DEEPDOC_OCR_SHA256, "deepdoc/vision/ocr.py")
    text = deepdoc_ocr_target.read_text(encoding="utf-8")
    text = replace_once(text, "from common.misc_utils import pip_install_torch\n", "from lig_runtime.gpu_detection import onnx_cuda_available\n", "DeepDOC torch helper import")
    text = replace_once(
        text,
        "    def cuda_is_available():\n"
        "        try:\n"
        "            pip_install_torch()\n"
        "            import torch\n\n"
        "            target_id = 0 if device_id is None else device_id\n"
        "            if torch.cuda.is_available() and torch.cuda.device_count() > target_id:\n"
        "                return True\n"
        "        except Exception:\n"
        "            return False\n"
        "        return False\n",
        "    def cuda_is_available():\n"
        "        target_id = 0 if device_id is None else device_id\n"
        "        return onnx_cuda_available(target_id)\n",
        "DeepDOC ONNX GPU detection",
    )
    text = replace_once(
        text,
        '        gpu_mem_limit_mb = int(os.environ.get("OCR_GPU_MEM_LIMIT_MB", "2048"))\n'
        '        arena_strategy = os.environ.get("OCR_ARENA_EXTEND_STRATEGY", "kNextPowerOfTwo")\n'
        "        provider_device_id = 0 if device_id is None else device_id\n"
        "        cuda_provider_options = {\n"
        '            "device_id": provider_device_id,  # Use specific GPU\n'
        '            "gpu_mem_limit": max(gpu_mem_limit_mb, 0) * 1024 * 1024,\n'
        '            "arena_extend_strategy": arena_strategy,  # gpu memory allocation strategy\n'
        "        }\n",
        '        gpu_mem_limit_mb = int(os.environ.get("OCR_GPU_MEM_LIMIT_MB", "0"))\n'
        '        arena_strategy = os.environ.get("OCR_ARENA_EXTEND_STRATEGY", "kNextPowerOfTwo")\n'
        "        provider_device_id = 0 if device_id is None else device_id\n"
        "        cuda_provider_options = {\n"
        '            "device_id": provider_device_id,\n'
        '            "arena_extend_strategy": arena_strategy,\n'
        "        }\n"
        "        if gpu_mem_limit_mb > 0:\n"
        '            cuda_provider_options["gpu_mem_limit"] = gpu_mem_limit_mb * 1024 * 1024\n',
        "optional DeepDOC GPU memory cap",
    )
    text = replace_once(
        text,
        "        logging.info(f\"load_model {model_file_path} uses GPU (device {provider_device_id}, gpu_mem_limit={cuda_provider_options['gpu_mem_limit']}, arena_strategy={arena_strategy})\")\n",
        "        logging.info(f\"load_model {model_file_path} uses GPU (device {provider_device_id}, gpu_mem_limit={cuda_provider_options.get('gpu_mem_limit', 'unlimited')}, arena_strategy={arena_strategy})\")\n",
        "DeepDOC optional GPU memory logging",
    )
    deepdoc_ocr_target.write_text(text, encoding="utf-8")

    db_models_target = checked_target(Path(sys.argv[31]), EXPECTED_DB_MODELS_SHA256, "api/db/db_models.py")
    text = db_models_target.read_text(encoding="utf-8")
    text = text.replace(
        '    progress_msg = TextField(null=True, help_text="process message", default="")\n',
        '    progress_msg = LongTextField(null=True, help_text="process message", default="")\n',
    )
    if text.count('progress_msg = LongTextField(null=True, help_text="process message", default="")') != 3:
        raise SystemExit("Expected Document, Task, and PipelineOperationLog progress_msg fields")
    text = replace_once(
        text,
        '    alter_db_add_column(migrator, "task", "chunk_ids", LongTextField(null=True, help_text="chunk ids", default=""))\n',
        '    alter_db_add_column(migrator, "task", "chunk_ids", LongTextField(null=True, help_text="chunk ids", default=""))\n'
        '    alter_db_column_type(migrator, "document", "progress_msg", LongTextField(null=True, help_text="process message", default=""))\n'
        '    alter_db_column_type(migrator, "task", "progress_msg", LongTextField(null=True, help_text="process message", default=""))\n'
        '    alter_db_column_type(migrator, "pipeline_operation_log", "progress_msg", LongTextField(null=True, help_text="process message", default=""))\n',
        "progress log LONGTEXT migration",
    )
    db_models_target.write_text(text, encoding="utf-8")

    apply_dataset_settings_patch(Path(sys.argv[32]))
    apply_offline_team_membership_patch(Path(sys.argv[33]))


def checked_target(path: Path, expected_sha256: str, label: str) -> Path:
    source = normalized_source(path)
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SystemExit(f"Unsupported RAGFlow {label}: expected {expected_sha256}, got {actual_sha256}")
    return path


def normalized_source(path: Path) -> bytes:
    """Hash Git text identically on Windows and Linux without weakening pinning."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one {label} site")
    return text.replace(old, new)


if __name__ == "__main__":
    main()
