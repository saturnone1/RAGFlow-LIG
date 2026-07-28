"""Password-protected PDF handling for the LIG runtime overlay."""

from __future__ import annotations

import os
from base64 import b64decode, b64encode
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pypdf import PdfReader, PdfWriter
from pypdf._encryption import PasswordType

PASSWORD_INPUT_FIELD = "pdf_password"
PASSWORD_CLEAR_FIELD = "clear_pdf_password"
PASSWORD_STORAGE_FIELD = "_lig_pdf_password_v1"
PASSWORD_STATUS_FIELD = "pdf_password_configured"
MAX_PASSWORD_BYTES = 1024
_KEY_ENV = "LIG_PDF_PASSWORD_KEY"
_AAD = b"lig-ragflow/pdf-password/v1"
_DECRYPT_CACHE_LIMIT = 128 * 1024 * 1024
_DECRYPT_CACHE_ITEM_LIMIT = 64 * 1024 * 1024
_decrypt_cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_decrypt_cache_size = 0
_decrypt_cache_lock = Lock()


class PdfPasswordError(ValueError):
    """A user-correctable PDF password configuration error."""


def _key() -> bytes:
    encoded = os.environ.get(_KEY_ENV, "").strip()
    if not encoded:
        raise RuntimeError(f"{_KEY_ENV} is required for password-protected PDF support.")
    try:
        key = b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError(f"{_KEY_ENV} must be a base64-encoded 32-byte key.") from exc
    if len(key) != 32:
        raise RuntimeError(f"{_KEY_ENV} must decode to exactly 32 bytes.")
    return key


def _is_pdf(filename: str) -> bool:
    return Path(filename).suffix.lower() == ".pdf"


def _validate_password(password: object) -> str:
    if not isinstance(password, str):
        raise PdfPasswordError("The PDF password must be a string.")
    if not password:
        raise PdfPasswordError("The PDF password cannot be empty.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PdfPasswordError(f"The PDF password must be at most {MAX_PASSWORD_BYTES} UTF-8 bytes.")
    return password


def _seal(password: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, password.encode("utf-8"), _AAD)
    return "v1:" + b64encode(nonce + ciphertext).decode("ascii")


def _unseal(token: object) -> str:
    if not isinstance(token, str) or not token.startswith("v1:"):
        raise PdfPasswordError("The saved PDF password has an unsupported format.")
    try:
        payload = b64decode(token[3:], validate=True)
        if len(payload) < 29:
            raise ValueError("encrypted payload is too short")
        plaintext = AESGCM(_key()).decrypt(payload[:12], payload[12:], _AAD)
        return plaintext.decode("utf-8")
    except (ValueError, UnicodeDecodeError, InvalidTag) as exc:
        raise PdfPasswordError("The saved PDF password could not be decrypted.") from exc


def secure_parser_config(parser_config: dict | None, filename: str) -> tuple[dict, bool]:
    """Replace a submitted plaintext password with an authenticated ciphertext."""
    config = deepcopy(parser_config or {})
    extension = config.get("ext")
    extension = extension if isinstance(extension, dict) else {}
    extension.pop(PASSWORD_STORAGE_FIELD, None)

    supplied = PASSWORD_INPUT_FIELD in config or PASSWORD_INPUT_FIELD in extension
    clear = bool(config.pop(PASSWORD_CLEAR_FIELD, False) or extension.pop(PASSWORD_CLEAR_FIELD, False))
    extension.pop(PASSWORD_CLEAR_FIELD, None)
    password = config.pop(PASSWORD_INPUT_FIELD, extension.pop(PASSWORD_INPUT_FIELD, None))
    if isinstance(config.get("ext"), dict):
        config["ext"] = extension

    if not supplied and not clear:
        return config, False
    if not _is_pdf(filename):
        raise PdfPasswordError("A PDF password can only be assigned to a .pdf document.")
    if clear or password is None:
        config[PASSWORD_STORAGE_FIELD] = None
        return config, True

    config[PASSWORD_STORAGE_FIELD] = _seal(_validate_password(password))
    return config, True


def sanitize_parser_config(parser_config: object) -> object:
    """Remove private ciphertext and expose only a harmless configured flag."""
    if not isinstance(parser_config, dict):
        return parser_config
    config = deepcopy(parser_config)
    configured = bool(config.pop(PASSWORD_STORAGE_FIELD, None))
    extension = config.get("ext")
    if isinstance(extension, dict):
        extension.pop(PASSWORD_INPUT_FIELD, None)
        extension.pop(PASSWORD_CLEAR_FIELD, None)
        extension.pop(PASSWORD_STORAGE_FIELD, None)
    config[PASSWORD_STATUS_FIELD] = configured
    return config


def sanitize_document_response(document: dict) -> dict:
    sanitized = dict(document)
    if "parser_config" in sanitized:
        sanitized["parser_config"] = sanitize_parser_config(sanitized["parser_config"])
    return sanitized


def _decrypt_result(binary: bytes, password: str) -> tuple[PdfReader, PasswordType, bool]:
    empty_reader = PdfReader(BytesIO(binary), strict=False)
    try:
        empty_result = empty_reader.decrypt("")
    except Exception:  # noqa: BLE001 - pypdf exposes several backend-specific failures.
        empty_result = PasswordType.NOT_DECRYPTED

    reader = PdfReader(BytesIO(binary), strict=False)
    try:
        result = reader.decrypt(password)
    except Exception as exc:
        raise PdfPasswordError("The PDF password is incorrect or the encryption is unsupported.") from exc
    return reader, PasswordType(result), PasswordType(empty_result) != PasswordType.NOT_DECRYPTED


def _open_encrypted_pdf(filename: str, binary: bytes, parser_config: dict) -> PdfReader | None:
    if not _is_pdf(filename):
        return None
    try:
        reader = PdfReader(BytesIO(binary), strict=False)
    except Exception:  # noqa: BLE001 - malformed PDFs must fall through to the existing parser error path.
        return None
    if not reader.is_encrypted:
        return None

    token = parser_config.get(PASSWORD_STORAGE_FIELD)
    if not token:
        raise PdfPasswordError("This PDF is password protected. Enter its password and try again.")
    reader, result, permissions_only = _decrypt_result(binary, _unseal(token))
    if result == PasswordType.NOT_DECRYPTED:
        raise PdfPasswordError("The PDF password is incorrect.")
    if permissions_only and result != PasswordType.OWNER_PASSWORD:
        raise PdfPasswordError("This PDF has permission restrictions. Enter the owner (permissions) password.")
    return reader


def validate_pdf_access(filename: str, binary: bytes, parser_config: dict | None) -> None:
    """Fail an upload early when an encrypted PDF lacks a usable password."""
    _open_encrypted_pdf(filename, binary, parser_config or {})


def encrypted_pdf_page_count(filename: str, binary: bytes, parser_config: dict | None) -> int | None:
    """Count pages for encrypted PDFs before RAGFlow splits work into tasks."""
    reader = _open_encrypted_pdf(filename, binary, parser_config or {})
    return len(reader.pages) if reader is not None else None


def _cache_key(binary: bytes, token: object) -> tuple[str, str] | None:
    if not isinstance(token, str) or len(binary) > _DECRYPT_CACHE_ITEM_LIMIT:
        return None
    return sha256(binary).hexdigest(), token


def _cached_plaintext(key: tuple[str, str] | None) -> bytes | None:
    if key is None:
        return None
    with _decrypt_cache_lock:
        value = _decrypt_cache.get(key)
        if value is not None:
            _decrypt_cache.move_to_end(key)
        return value


def _cache_plaintext(key: tuple[str, str] | None, value: bytes) -> None:
    global _decrypt_cache_size
    if key is None or len(value) > _DECRYPT_CACHE_ITEM_LIMIT:
        return
    with _decrypt_cache_lock:
        previous = _decrypt_cache.pop(key, None)
        if previous is not None:
            _decrypt_cache_size -= len(previous)
        _decrypt_cache[key] = value
        _decrypt_cache_size += len(value)
        while _decrypt_cache_size > _DECRYPT_CACHE_LIMIT and _decrypt_cache:
            _, evicted = _decrypt_cache.popitem(last=False)
            _decrypt_cache_size -= len(evicted)


def prepare_pdf_for_parsing(filename: str, binary: bytes, parser_config: dict | None) -> tuple[bytes, dict]:
    """Return plaintext PDF bytes and a parser config without private fields."""
    config = deepcopy(parser_config or {})
    cache_key = _cache_key(binary, config.get(PASSWORD_STORAGE_FIELD)) if _is_pdf(filename) else None
    cached = _cached_plaintext(cache_key)
    if cached is not None:
        config.pop(PASSWORD_STORAGE_FIELD, None)
        return cached, config
    reader = _open_encrypted_pdf(filename, binary, config)
    config.pop(PASSWORD_STORAGE_FIELD, None)
    extension = config.get("ext")
    if isinstance(extension, dict):
        extension.pop(PASSWORD_INPUT_FIELD, None)
        extension.pop(PASSWORD_CLEAR_FIELD, None)
    if reader is None:
        return binary, config

    output = BytesIO()
    PdfWriter(clone_from=reader).write(output)
    plaintext = output.getvalue()
    _cache_plaintext(cache_key, plaintext)
    return plaintext, config
