"""Password-protected document handling for the LIG runtime overlay."""

from __future__ import annotations

import os
import re
import struct
import zlib
from base64 import b64decode, b64encode
from collections import OrderedDict
from copy import deepcopy
from hashlib import pbkdf2_hmac, sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from threading import Lock
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pypdf import PdfReader, PdfWriter
from pypdf._encryption import PasswordType

PASSWORD_INPUT_FIELD = "document_password"
PASSWORD_CLEAR_FIELD = "clear_document_password"
PASSWORD_STORAGE_FIELD = "_lig_document_password_v2"
PASSWORD_STATUS_FIELD = "document_password_configured"

# Existing deployed PDF records are an external data contract. They are read and
# migrated when updated, but are never exposed through an API response.
LEGACY_INPUT_FIELD = "pdf_password"
LEGACY_CLEAR_FIELD = "clear_pdf_password"
LEGACY_STORAGE_FIELD = "_lig_pdf_password_v1"
LEGACY_STATUS_FIELD = "pdf_password_configured"

MAX_PASSWORD_BYTES = 1024
SUPPORTED_PASSWORD_EXTENSIONS = frozenset(
    {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".hwp", ".hwpx"}
)
OFFICE_EXTENSIONS = frozenset({".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"})
HANCOM_EXTENSIONS = frozenset({".hwp", ".hwpx"})

_KEY_ENV = "LIG_DOCUMENT_PASSWORD_KEY"
_LEGACY_KEY_ENV = "LIG_PDF_PASSWORD_KEY"
_AAD = b"lig-ragflow/document-password/v2"
_LEGACY_AAD = b"lig-ragflow/pdf-password/v1"
_DECRYPT_CACHE_LIMIT = 128 * 1024 * 1024
_DECRYPT_CACHE_ITEM_LIMIT = 64 * 1024 * 1024
_MAX_HWPX_ENTRY_SIZE = 256 * 1024 * 1024
_MANIFEST_NS = "{urn:oasis:names:tc:opendocument:xmlns:manifest:1.0}"
_HWP_SIGNATURE = b"HWP Document File"
_HWP_PARA_TEXT_TAG = 67

_decrypt_cache: OrderedDict[tuple[str, str], tuple[str, bytes]] = OrderedDict()
_decrypt_cache_size = 0
_decrypt_cache_lock = Lock()


class DocumentPasswordError(ValueError):
    """A user-correctable document password or format error."""


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _key_from_environment(name: str) -> bytes | None:
    encoded = os.environ.get(name, "").strip()
    if not encoded:
        return None
    try:
        key = b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a base64-encoded 32-byte key.") from exc
    if len(key) != 32:
        raise RuntimeError(f"{name} must decode to exactly 32 bytes.")
    return key


def _key() -> bytes:
    key = _key_from_environment(_KEY_ENV)
    if key is None:
        raise RuntimeError(f"{_KEY_ENV} is required for password-protected document support.")
    return key


def _legacy_key() -> bytes:
    key = _key_from_environment(_LEGACY_KEY_ENV) or _key_from_environment(_KEY_ENV)
    if key is None:
        raise RuntimeError(f"{_KEY_ENV} is required to read saved PDF passwords.")
    return key


def _validate_password(password: object) -> str:
    if not isinstance(password, str):
        raise DocumentPasswordError("The document password must be a string.")
    if not password:
        raise DocumentPasswordError("The document password cannot be empty.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise DocumentPasswordError(f"The document password must be at most {MAX_PASSWORD_BYTES} UTF-8 bytes.")
    return password


def _seal(password: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, password.encode("utf-8"), _AAD)
    return "v2:" + b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_sealed_payload(token: object, prefix: str, key: bytes, aad: bytes) -> str:
    if not isinstance(token, str) or not token.startswith(prefix):
        raise DocumentPasswordError("The saved document password has an unsupported format.")
    try:
        payload = b64decode(token[len(prefix) :], validate=True)
        if len(payload) < 29:
            raise ValueError("encrypted payload is too short")
        plaintext = AESGCM(key).decrypt(payload[:12], payload[12:], aad)
        return plaintext.decode("utf-8")
    except (ValueError, UnicodeDecodeError, InvalidTag) as exc:
        raise DocumentPasswordError("The saved document password could not be decrypted.") from exc


def _unseal(token: object) -> str:
    if isinstance(token, str) and token.startswith("v1:"):
        return _decrypt_sealed_payload(token, "v1:", _legacy_key(), _LEGACY_AAD)
    return _decrypt_sealed_payload(token, "v2:", _key(), _AAD)


def _pop_private_fields(config: dict) -> tuple[object, bool, bool]:
    extension = config.get("ext")
    extension = extension if isinstance(extension, dict) else {}
    supplied = any(field in config or field in extension for field in (PASSWORD_INPUT_FIELD, LEGACY_INPUT_FIELD))
    clear = False
    for field in (PASSWORD_CLEAR_FIELD, LEGACY_CLEAR_FIELD):
        clear = bool(config.pop(field, False) or extension.pop(field, False)) or clear
    password = None
    for field in (PASSWORD_INPUT_FIELD, LEGACY_INPUT_FIELD):
        value = config.pop(field, extension.pop(field, None))
        if value is not None:
            password = value
    extension.pop(PASSWORD_STORAGE_FIELD, None)
    extension.pop(LEGACY_STORAGE_FIELD, None)
    if isinstance(config.get("ext"), dict):
        config["ext"] = extension
    return password, supplied, clear


def secure_parser_config(parser_config: dict | None, filename: str) -> tuple[dict, bool]:
    """Replace a submitted plaintext password with authenticated ciphertext."""
    config = deepcopy(parser_config or {})
    password, supplied, clear = _pop_private_fields(config)
    current = config.pop(PASSWORD_STORAGE_FIELD, None)
    legacy = config.pop(LEGACY_STORAGE_FIELD, None)
    existing = current or legacy
    if not supplied and not clear:
        if existing:
            config[PASSWORD_STORAGE_FIELD] = existing
        return config, False
    if _extension(filename) not in SUPPORTED_PASSWORD_EXTENSIONS:
        raise DocumentPasswordError(
            "Passwords are supported for PDF, Word, Excel, PowerPoint, HWP, and HWPX documents only."
        )
    if clear or password is None:
        config[PASSWORD_STORAGE_FIELD] = None
        return config, True
    config[PASSWORD_STORAGE_FIELD] = _seal(_validate_password(password))
    return config, True


def sanitize_parser_config(parser_config: object) -> object:
    """Remove private password material and expose only a harmless status flag."""
    if not isinstance(parser_config, dict):
        return parser_config
    config = deepcopy(parser_config)
    configured = bool(config.pop(PASSWORD_STORAGE_FIELD, None) or config.pop(LEGACY_STORAGE_FIELD, None))
    for field in (
        PASSWORD_INPUT_FIELD,
        PASSWORD_CLEAR_FIELD,
        PASSWORD_STORAGE_FIELD,
        LEGACY_INPUT_FIELD,
        LEGACY_CLEAR_FIELD,
        LEGACY_STORAGE_FIELD,
        LEGACY_STATUS_FIELD,
    ):
        config.pop(field, None)
    extension = config.get("ext")
    if isinstance(extension, dict):
        for field in (
            PASSWORD_INPUT_FIELD,
            PASSWORD_CLEAR_FIELD,
            PASSWORD_STORAGE_FIELD,
            LEGACY_INPUT_FIELD,
            LEGACY_CLEAR_FIELD,
            LEGACY_STORAGE_FIELD,
        ):
            extension.pop(field, None)
    config[PASSWORD_STATUS_FIELD] = configured
    return config


def sanitize_document_response(document: dict) -> dict:
    sanitized = dict(document)
    if "parser_config" in sanitized:
        sanitized["parser_config"] = sanitize_parser_config(sanitized["parser_config"])
    return sanitized


def _password_token(config: dict) -> object:
    return config.get(PASSWORD_STORAGE_FIELD) or config.get(LEGACY_STORAGE_FIELD)


def _required_password(filename: str, config: dict) -> str:
    token = _password_token(config)
    if not token:
        raise DocumentPasswordError(f"{Path(filename).suffix.upper()[1:]} document is password protected. Enter its password and try again.")
    return _unseal(token)


def _open_encrypted_pdf(filename: str, binary: bytes, config: dict) -> PdfReader | None:
    if _extension(filename) != ".pdf":
        return None
    try:
        reader = PdfReader(BytesIO(binary), strict=False)
    except Exception:  # noqa: BLE001 - malformed PDFs belong to the existing parser path.
        return None
    if not reader.is_encrypted:
        return None

    password = _required_password(filename, config)
    empty_reader = PdfReader(BytesIO(binary), strict=False)
    try:
        empty_result = PasswordType(empty_reader.decrypt(""))
    except Exception:  # noqa: BLE001 - backend-specific pypdf failures.
        empty_result = PasswordType.NOT_DECRYPTED
    try:
        result = PasswordType(reader.decrypt(password))
    except Exception as exc:
        raise DocumentPasswordError("The PDF password is incorrect or the encryption is unsupported.") from exc
    if empty_result != PasswordType.NOT_DECRYPTED and result != PasswordType.OWNER_PASSWORD:
        raise DocumentPasswordError("This PDF has permission restrictions. Enter the owner (permissions) password.")
    if result == PasswordType.NOT_DECRYPTED:
        raise DocumentPasswordError("The PDF password is incorrect.")
    return reader


def _prepare_pdf(filename: str, binary: bytes, config: dict) -> bytes:
    reader = _open_encrypted_pdf(filename, binary, config)
    if reader is None:
        return binary
    output = BytesIO()
    PdfWriter(clone_from=reader).write(output)
    return output.getvalue()


def _office_file(binary: bytes):
    try:
        import msoffcrypto
        from msoffcrypto.exceptions import FileFormatError
    except ImportError as exc:
        raise RuntimeError("msoffcrypto-tool is required for password-protected Office documents.") from exc
    try:
        return msoffcrypto.OfficeFile(BytesIO(binary))
    except FileFormatError:
        return None


def _prepare_office(filename: str, binary: bytes, config: dict) -> bytes:
    office_file = _office_file(binary)
    if office_file is None or not office_file.is_encrypted():
        return binary
    password = _required_password(filename, config)
    try:
        office_file.load_key(password=password, verify_password=True)
        output = BytesIO()
        office_file.decrypt(output)
        return output.getvalue()
    except Exception as exc:
        message = str(exc).lower()
        if "irm" in message or "rights" in message or "certificate" in message:
            raise DocumentPasswordError("Microsoft IRM/MIP protected documents are not supported.") from exc
        raise DocumentPasswordError("The Office document password is incorrect or its encryption is unsupported.") from exc


def _safe_hwpx_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise DocumentPasswordError("The HWPX manifest contains an unsafe entry path.")
    return path.as_posix()


def _limited_raw_deflate(data: bytes, expected_size: int) -> bytes:
    if expected_size < 0 or expected_size > _MAX_HWPX_ENTRY_SIZE:
        raise DocumentPasswordError("An encrypted HWPX entry is too large to process safely.")
    inflater = zlib.decompressobj(-15)
    try:
        plain = inflater.decompress(data, expected_size + 1)
        if len(plain) <= expected_size:
            plain += inflater.flush(expected_size + 1 - len(plain))
    except zlib.error as exc:
        raise DocumentPasswordError("The HWPX password is incorrect.") from exc
    if len(plain) > expected_size or len(plain) > _MAX_HWPX_ENTRY_SIZE or not inflater.eof:
        raise DocumentPasswordError("The encrypted HWPX entry has an invalid expanded size.")
    return plain


def _decode_manifest_value(element: ElementTree.Element, name: str) -> bytes:
    try:
        return b64decode(element.attrib[name], validate=True)
    except (KeyError, ValueError) as exc:
        raise DocumentPasswordError(f"The HWPX encryption manifest has an invalid {name} value.") from exc


def _decrypt_hwpx_entries(archive: ZipFile, password: str | None) -> dict[str, bytes]:
    try:
        manifest = ElementTree.fromstring(archive.read("META-INF/manifest.xml"))
    except (KeyError, ElementTree.ParseError) as exc:
        raise DocumentPasswordError("The HWPX encryption manifest is missing or invalid.") from exc

    encrypted_entries = []
    for entry in manifest.findall(f"{_MANIFEST_NS}file-entry"):
        encryption = entry.find(f"{_MANIFEST_NS}encryption-data")
        if encryption is not None:
            encrypted_entries.append((entry, encryption))
    if not encrypted_entries:
        return {}
    if password is None:
        raise DocumentPasswordError("HWPX document is password protected. Enter its password and try again.")

    start_key = sha256(password.encode("utf-8")).digest()
    decrypted: dict[str, bytes] = {}
    total_expected_size = 0
    for entry, encryption in encrypted_entries:
        algorithm = encryption.find(f"{_MANIFEST_NS}algorithm")
        derivation = encryption.find(f"{_MANIFEST_NS}key-derivation")
        start_generation = encryption.find(f"{_MANIFEST_NS}start-key-generation")
        if algorithm is None or derivation is None or start_generation is None:
            raise DocumentPasswordError("The HWPX encryption manifest is incomplete.")
        if algorithm.attrib.get("algorithm-name") != "http://www.w3.org/2001/04/xmlenc#aes256-cbc":
            raise DocumentPasswordError("This HWPX encryption algorithm is not supported.")
        if derivation.attrib.get("key-derivation-name") != f"{_MANIFEST_NS[1:-1]}#pbkdf2":
            raise DocumentPasswordError("This HWPX key derivation algorithm is not supported.")
        if start_generation.attrib.get("start-key-generation-name") != "http://www.w3.org/2000/09/xmldsig#sha256":
            raise DocumentPasswordError("This HWPX password hash algorithm is not supported.")
        try:
            key_size = int(derivation.attrib["key-size"])
            iterations = int(derivation.attrib["iteration-count"])
            expected_size = int(entry.attrib["size"])
        except (KeyError, ValueError) as exc:
            raise DocumentPasswordError("The HWPX encryption parameters are invalid.") from exc
        if key_size != 32 or not 1 <= iterations <= 10_000_000:
            raise DocumentPasswordError("The HWPX encryption parameters are outside the supported range.")
        total_expected_size += expected_size
        if total_expected_size > _MAX_HWPX_ENTRY_SIZE:
            raise DocumentPasswordError("The encrypted HWPX body is too large to process safely.")

        path = _safe_hwpx_path(entry.attrib.get("full-path", ""))
        salt = _decode_manifest_value(derivation, "salt")
        iv = _decode_manifest_value(algorithm, "initialisation-vector")
        if len(iv) != 16:
            raise DocumentPasswordError("The HWPX encryption manifest has an invalid IV.")
        key = pbkdf2_hmac("sha1", start_key, salt, iterations, dklen=key_size)
        try:
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            compressed = decryptor.update(archive.read(path)) + decryptor.finalize()
        except (KeyError, ValueError) as exc:
            raise DocumentPasswordError("The encrypted HWPX payload is invalid.") from exc
        plain = _limited_raw_deflate(compressed, expected_size)
        checksum = _decode_manifest_value(encryption, "checksum")
        if encryption.attrib.get("checksum-type") != f"{_MANIFEST_NS[1:-1]}#sha256-1k" or sha256(plain[:1024]).digest() != checksum:
            raise DocumentPasswordError("The HWPX password is incorrect or the document is damaged.")
        decrypted[path] = plain
    return decrypted


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _extract_hwpx_text(archive: ZipFile, decrypted: dict[str, bytes]) -> bytes:
    section_names = sorted(
        (name for name in archive.namelist() if re.fullmatch(r"Contents/section\d+\.xml", name, re.IGNORECASE)),
        key=lambda name: int(re.search(r"\d+", name).group()),
    )
    if not section_names:
        raise DocumentPasswordError("The HWPX document contains no body sections.")
    output: list[str] = []
    total_size = 0
    for name in section_names:
        if name in decrypted:
            payload = decrypted[name]
        else:
            info = archive.getinfo(name)
            if info.file_size > _MAX_HWPX_ENTRY_SIZE:
                raise DocumentPasswordError("An HWPX body section is too large to process safely.")
            payload = archive.read(info)
        total_size += len(payload)
        if total_size > _MAX_HWPX_ENTRY_SIZE:
            raise DocumentPasswordError("The HWPX body is too large to process safely.")
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise DocumentPasswordError("The HWPX body XML is invalid.") from exc
        for element in root.iter():
            local = _local_name(element.tag)
            if local == "t" and element.text:
                output.append(element.text)
            elif local in {"p", "tr"} and output and output[-1] != "\n":
                output.append("\n")
            elif local == "tc" and output and output[-1] not in {"\n", "\t"}:
                output.append("\t")
    text = "".join(output)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise DocumentPasswordError("No text could be extracted from the HWPX document.")
    return text.encode("utf-8")


def _prepare_hwpx(filename: str, binary: bytes, config: dict) -> tuple[str, bytes]:
    try:
        with ZipFile(BytesIO(binary)) as archive:
            password = _unseal(_password_token(config)) if _password_token(config) else None
            decrypted = _decrypt_hwpx_entries(archive, password)
            return f"{filename}.txt", _extract_hwpx_text(archive, decrypted)
    except BadZipFile as exc:
        raise DocumentPasswordError("The HWPX file is not a valid ZIP document package.") from exc


def _read_hwp_header(binary: bytes) -> tuple[object, bytes, int]:
    ole = None
    try:
        import olefile
        ole = olefile.OleFileIO(BytesIO(binary))
        header = ole.openstream("FileHeader").read()
    except Exception as exc:
        if ole is not None:
            ole.close()
        raise DocumentPasswordError("The HWP file is not a valid HWP 5 document.") from exc
    if not header.startswith(_HWP_SIGNATURE) or len(header) < 40:
        ole.close()
        raise DocumentPasswordError("Only HWP 5 documents are supported.")
    return ole, header, struct.unpack_from("<I", header, 36)[0]


def _clean_hwp_text(payload: bytes) -> str:
    if len(payload) % 2:
        payload = payload[:-1]
    units = list(struct.unpack(f"<{len(payload) // 2}H", payload))
    output: list[str] = []
    index = 0
    extended_controls = set(range(1, 9)) | {11, 12, 14, 15, 16, 17, 18, 21, 22, 23}
    while index < len(units):
        code = units[index]
        if code in extended_controls:
            index += 8
            continue
        if code == 9:
            output.append("\t")
        elif code in {10, 13}:
            output.append("\n")
        elif code >= 32:
            output.append(chr(code))
        index += 1
    return "".join(output)


def _extract_hwp_text(ole, compressed: bool) -> bytes:
    sections = []
    for path in ole.listdir(streams=True, storages=False):
        joined = "/".join(path)
        match = re.fullmatch(r"BodyText/Section(\d+)", joined, re.IGNORECASE)
        if match:
            sections.append((int(match.group(1)), joined))
    sections.sort()
    output: list[str] = []
    expanded_size = 0
    for _, path in sections:
        if ole.get_size(path) > _MAX_HWPX_ENTRY_SIZE:
            raise DocumentPasswordError("An HWP body section is too large to process safely.")
        data = ole.openstream(path).read()
        if compressed:
            inflater = zlib.decompressobj(-15)
            try:
                remaining = _MAX_HWPX_ENTRY_SIZE - expanded_size
                data = inflater.decompress(data, remaining + 1)
                if len(data) <= remaining:
                    data += inflater.flush(remaining + 1 - len(data))
            except zlib.error as exc:
                raise DocumentPasswordError("The compressed HWP body is damaged.") from exc
            if len(data) > remaining or not inflater.eof:
                raise DocumentPasswordError("The expanded HWP body is too large or damaged.")
        expanded_size += len(data)
        if expanded_size > _MAX_HWPX_ENTRY_SIZE:
            raise DocumentPasswordError("The HWP body is too large to process safely.")
        offset = 0
        while offset + 4 <= len(data):
            header = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            tag = header & 0x3FF
            size = (header >> 20) & 0xFFF
            if size == 0xFFF:
                if offset + 4 > len(data):
                    raise DocumentPasswordError("The HWP body contains a truncated record.")
                size = struct.unpack_from("<I", data, offset)[0]
                offset += 4
            if offset + size > len(data):
                raise DocumentPasswordError("The HWP body contains an invalid record size.")
            if tag == _HWP_PARA_TEXT_TAG:
                text = _clean_hwp_text(data[offset : offset + size]).strip()
                if text:
                    output.append(text)
            offset += size
    text = "\n".join(output).strip()
    if not text:
        raise DocumentPasswordError("No text could be extracted from the HWP document.")
    return text.encode("utf-8")


def _prepare_hwp(filename: str, binary: bytes, config: dict) -> tuple[str, bytes]:
    ole, _, properties = _read_hwp_header(binary)
    try:
        if properties & (1 << 2):
            raise DocumentPasswordError("HWP distribution documents are permission-protected and are not processed.")
        if properties & (1 << 8):
            raise DocumentPasswordError("Certificate-encrypted HWP documents are not supported.")
        if properties & (1 << 1):
            if not _password_token(config):
                raise DocumentPasswordError("HWP document is password protected. Enter its password and try again.")
            raise DocumentPasswordError(
                "Password-encrypted binary HWP is not supported by the verified open runtime. Save it as HWPX or DOCX and upload it again."
            )
        return f"{filename}.txt", _extract_hwp_text(ole, bool(properties & 1))
    finally:
        ole.close()


def _cache_key(binary: bytes, token: object, extension: str) -> tuple[str, str] | None:
    if len(binary) > _DECRYPT_CACHE_ITEM_LIMIT:
        return None
    token_value = token if isinstance(token, str) else "plain"
    return sha256(binary).hexdigest(), f"{extension}:{token_value}"


def _cached_plaintext(key: tuple[str, str] | None) -> tuple[str, bytes] | None:
    if key is None:
        return None
    with _decrypt_cache_lock:
        value = _decrypt_cache.get(key)
        if value is not None:
            _decrypt_cache.move_to_end(key)
        return value


def _cache_plaintext(key: tuple[str, str] | None, filename: str, value: bytes) -> None:
    global _decrypt_cache_size
    if key is None or len(value) > _DECRYPT_CACHE_ITEM_LIMIT:
        return
    with _decrypt_cache_lock:
        previous = _decrypt_cache.pop(key, None)
        if previous is not None:
            _decrypt_cache_size -= len(previous[1])
        _decrypt_cache[key] = (filename, value)
        _decrypt_cache_size += len(value)
        while _decrypt_cache_size > _DECRYPT_CACHE_LIMIT and _decrypt_cache:
            _, (_, evicted) = _decrypt_cache.popitem(last=False)
            _decrypt_cache_size -= len(evicted)


def _public_parser_config(config: dict) -> dict:
    config.pop(PASSWORD_STORAGE_FIELD, None)
    config.pop(LEGACY_STORAGE_FIELD, None)
    extension = config.get("ext")
    if isinstance(extension, dict):
        for field in (PASSWORD_INPUT_FIELD, PASSWORD_CLEAR_FIELD, LEGACY_INPUT_FIELD, LEGACY_CLEAR_FIELD):
            extension.pop(field, None)
    return config


def prepare_document_for_parsing(filename: str, binary: bytes, parser_config: dict | None) -> tuple[str, bytes, dict]:
    """Return parser-ready bytes/name and a config without private fields."""
    config = deepcopy(parser_config or {})
    extension = _extension(filename)
    key = _cache_key(binary, _password_token(config), extension) if extension in SUPPORTED_PASSWORD_EXTENSIONS else None
    cached = _cached_plaintext(key)
    if cached is not None:
        cached_name, cached_binary = cached
        return cached_name, cached_binary, _public_parser_config(config)

    prepared_name = filename
    prepared_binary = binary
    if extension == ".pdf":
        prepared_binary = _prepare_pdf(filename, binary, config)
    elif extension in OFFICE_EXTENSIONS:
        prepared_binary = _prepare_office(filename, binary, config)
    elif extension == ".hwpx":
        prepared_name, prepared_binary = _prepare_hwpx(filename, binary, config)
    elif extension == ".hwp":
        prepared_name, prepared_binary = _prepare_hwp(filename, binary, config)

    _cache_plaintext(key, prepared_name, prepared_binary)
    return prepared_name, prepared_binary, _public_parser_config(config)


def validate_document_access(filename: str, binary: bytes, parser_config: dict | None) -> None:
    """Fail an upload early when an encrypted or Hancom document cannot be parsed."""
    if _extension(filename) in SUPPORTED_PASSWORD_EXTENSIONS:
        prepare_document_for_parsing(filename, binary, parser_config)


def encrypted_pdf_page_count(filename: str, binary: bytes, parser_config: dict | None) -> int | None:
    """Count encrypted PDF pages before RAGFlow splits work into tasks."""
    reader = _open_encrypted_pdf(filename, binary, parser_config or {})
    return len(reader.pages) if reader is not None else None
