from __future__ import annotations

from base64 import b64encode
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from lig_runtime.pdf_password import (
    PASSWORD_INPUT_FIELD,
    PASSWORD_STATUS_FIELD,
    PASSWORD_STORAGE_FIELD,
    PdfPasswordError,
    encrypted_pdf_page_count,
    prepare_pdf_for_parsing,
    sanitize_parser_config,
    secure_parser_config,
    validate_pdf_access,
)


@pytest.fixture(autouse=True)
def password_key(monkeypatch):
    monkeypatch.setenv("LIG_PDF_PASSWORD_KEY", b64encode(bytes(range(32))).decode("ascii"))


def encrypted_pdf(user_password: str, owner_password: str | None = None, algorithm: str = "AES-256") -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt(user_password, owner_password, algorithm=algorithm)
    writer.write(output)
    return output.getvalue()


def test_document_open_password_is_sealed_and_decrypted():
    encrypted = encrypted_pdf("열기-암호", "소유자-암호")
    config, changed = secure_parser_config({PASSWORD_INPUT_FIELD: "열기-암호"}, "secure.pdf")

    assert changed is True
    assert PASSWORD_INPUT_FIELD not in config
    assert "열기-암호" not in config[PASSWORD_STORAGE_FIELD]
    validate_pdf_access("secure.pdf", encrypted, config)
    assert encrypted_pdf_page_count("secure.pdf", encrypted, config) == 1

    plaintext, parser_config = prepare_pdf_for_parsing("secure.pdf", encrypted, config)
    assert PdfReader(BytesIO(plaintext)).is_encrypted is False
    assert len(PdfReader(BytesIO(plaintext)).pages) == 1
    assert PASSWORD_STORAGE_FIELD not in parser_config


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-128", "AES-256"])
def test_common_acrobat_encryption_algorithms(algorithm):
    encrypted = encrypted_pdf("open-password", "owner-password", algorithm)
    config, _ = secure_parser_config({PASSWORD_INPUT_FIELD: "open-password"}, "secure.pdf")

    plaintext, _ = prepare_pdf_for_parsing("secure.pdf", encrypted, config)
    assert PdfReader(BytesIO(plaintext)).is_encrypted is False


def test_wrong_or_missing_password_has_actionable_error():
    encrypted = encrypted_pdf("correct")
    wrong, _ = secure_parser_config({PASSWORD_INPUT_FIELD: "wrong"}, "secure.pdf")

    with pytest.raises(PdfPasswordError, match="incorrect"):
        validate_pdf_access("secure.pdf", encrypted, wrong)
    with pytest.raises(PdfPasswordError, match="password protected"):
        validate_pdf_access("secure.pdf", encrypted, {})


def test_permissions_only_pdf_requires_owner_password():
    encrypted = encrypted_pdf("", "owner-password")
    user_config, _ = secure_parser_config({PASSWORD_INPUT_FIELD: "not-owner"}, "restricted.pdf")
    owner_config, _ = secure_parser_config({PASSWORD_INPUT_FIELD: "owner-password"}, "restricted.pdf")

    with pytest.raises(PdfPasswordError):
        validate_pdf_access("restricted.pdf", encrypted, user_config)
    validate_pdf_access("restricted.pdf", encrypted, owner_config)


def test_private_ciphertext_is_not_returned_by_api_sanitizer():
    config, _ = secure_parser_config({PASSWORD_INPUT_FIELD: "secret"}, "secure.pdf")
    sanitized = sanitize_parser_config(config)

    assert PASSWORD_STORAGE_FIELD not in sanitized
    assert sanitized[PASSWORD_STATUS_FIELD] is True
    assert "secret" not in repr(sanitized)


def test_plain_pdf_and_non_pdf_are_unchanged():
    plain = encrypted_pdf("")
    # Re-write after decrypting the empty user password to obtain a truly plain PDF.
    reader = PdfReader(BytesIO(plain))
    reader.decrypt("")
    output = BytesIO()
    PdfWriter(clone_from=reader).write(output)
    plain = output.getvalue()

    returned, config = prepare_pdf_for_parsing("plain.pdf", plain, {"chunk_token_num": 128})
    assert returned == plain
    assert config == {"chunk_token_num": 128}

    returned, config = prepare_pdf_for_parsing("notes.txt", b"hello", {})
    assert returned == b"hello"
    assert config == {}
