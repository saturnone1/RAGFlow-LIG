from __future__ import annotations

import base64
import hashlib
import io
import zlib
from zipfile import ZIP_STORED, ZipFile

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pypdf import PdfReader, PdfWriter

from lig_runtime.document_password import (
    LEGACY_STORAGE_FIELD,
    PASSWORD_CLEAR_FIELD,
    PASSWORD_INPUT_FIELD,
    PASSWORD_STATUS_FIELD,
    PASSWORD_STORAGE_FIELD,
    DocumentPasswordError,
    encrypted_pdf_page_count,
    prepare_document_for_parsing,
    sanitize_parser_config,
    secure_parser_config,
    validate_document_access,
)


@pytest.fixture(autouse=True)
def password_key(monkeypatch):
    encoded = base64.b64encode(bytes(range(32))).decode("ascii")
    monkeypatch.setenv("LIG_DOCUMENT_PASSWORD_KEY", encoded)
    monkeypatch.setenv("LIG_PDF_PASSWORD_KEY", encoded)


def encrypted_pdf(user_password: str, owner_password: str | None = None, algorithm: str = "AES-256") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt(user_password, owner_password, algorithm=algorithm)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def encrypted_office_zip(password: str) -> bytes:
    pytest.importorskip("msoffcrypto")
    pytest.importorskip("docx")
    from docx import Document
    from msoffcrypto.format.ooxml import OOXMLFile
    document = Document()
    document.add_paragraph("RAG-LIG Office test")
    plain = io.BytesIO()
    document.save(plain)
    encrypted = io.BytesIO()
    OOXMLFile(io.BytesIO(plain.getvalue())).encrypt(password, encrypted)
    return encrypted.getvalue()


def hwpx_document(password: str | None) -> bytes:
    section = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hs:sec xmlns:hs="urn:hancom:section" xmlns:hp="urn:hancom:paragraph">'
        '<hp:p><hp:run><hp:t>암호화 HWPX 본문</hp:t></hp:run></hp:p>'
        '<hp:p><hp:run><hp:t>두 번째 문단</hp:t></hp:run></hp:p>'
        "</hs:sec>"
    ).encode()
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_STORED) as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        if password is None:
            archive.writestr("Contents/section0.xml", section)
            archive.writestr(
                "META-INF/manifest.xml",
                '<?xml version="1.0"?><manifest xmlns="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>',
            )
        else:
            salt = bytes(range(16))
            iv = bytes(range(16, 32))
            start_key = hashlib.sha256(password.encode()).digest()
            key = hashlib.pbkdf2_hmac("sha1", start_key, salt, 1024, dklen=32)
            compressor = zlib.compressobj(level=6, wbits=-15)
            compressed = compressor.compress(section) + compressor.flush()
            padded = compressed + bytes((-len(compressed)) % 16)
            encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
            ciphertext = encryptor.update(padded) + encryptor.finalize()
            archive.writestr("Contents/section0.xml", ciphertext)
            checksum = base64.b64encode(hashlib.sha256(section[:1024]).digest()).decode()
            manifest = f'''<?xml version="1.0"?>
                <odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
                  <odf:file-entry full-path="Contents/section0.xml" media-type="application/xml" size="{len(section)}">
                    <odf:encryption-data checksum-type="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0#sha256-1k" checksum="{checksum}">
                      <odf:algorithm algorithm-name="http://www.w3.org/2001/04/xmlenc#aes256-cbc" initialisation-vector="{base64.b64encode(iv).decode()}"/>
                      <odf:key-derivation key-derivation-name="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0#pbkdf2" key-size="32" iteration-count="1024" salt="{base64.b64encode(salt).decode()}"/>
                      <odf:start-key-generation start-key-generation-name="http://www.w3.org/2000/09/xmldsig#sha256" key-size="32"/>
                    </odf:encryption-data>
                  </odf:file-entry>
                </odf:manifest>'''
            archive.writestr("META-INF/manifest.xml", manifest)
    return output.getvalue()


def secured(filename: str, password: str) -> dict:
    config, changed = secure_parser_config({PASSWORD_INPUT_FIELD: password}, filename)
    assert changed is True
    assert PASSWORD_INPUT_FIELD not in config
    assert password not in config[PASSWORD_STORAGE_FIELD]
    return config


def test_document_open_password_is_sealed_and_pdf_is_decrypted():
    encrypted = encrypted_pdf("열기-암호", "소유자-암호")
    config = secured("secure.pdf", "열기-암호")
    validate_document_access("secure.pdf", encrypted, config)
    assert encrypted_pdf_page_count("secure.pdf", encrypted, config) == 1

    name, plaintext, parser_config = prepare_document_for_parsing("secure.pdf", encrypted, config)
    assert name == "secure.pdf"
    assert PdfReader(io.BytesIO(plaintext)).is_encrypted is False
    assert PASSWORD_STORAGE_FIELD not in parser_config


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-128", "AES-256"])
def test_common_pdf_algorithms(algorithm):
    encrypted = encrypted_pdf("open-password", "owner-password", algorithm)
    name, plaintext, _ = prepare_document_for_parsing("secure.pdf", encrypted, secured("secure.pdf", "open-password"))
    assert name == "secure.pdf"
    assert PdfReader(io.BytesIO(plaintext)).is_encrypted is False


def test_pdf_wrong_missing_and_permissions_only_passwords():
    encrypted = encrypted_pdf("correct")
    with pytest.raises(DocumentPasswordError, match="incorrect"):
        validate_document_access("secure.pdf", encrypted, secured("secure.pdf", "wrong"))
    with pytest.raises(DocumentPasswordError, match="password protected"):
        validate_document_access("secure.pdf", encrypted, {})

    restricted = encrypted_pdf("", "owner-password")
    with pytest.raises(DocumentPasswordError, match="owner"):
        validate_document_access("restricted.pdf", restricted, secured("restricted.pdf", "not-owner"))
    validate_document_access("restricted.pdf", restricted, secured("restricted.pdf", "owner-password"))


@pytest.mark.parametrize("extension", ["docx", "xlsx", "pptx"])
def test_modern_office_password_decryption(extension):
    encrypted = encrypted_office_zip("office-password")
    name, plaintext, parser_config = prepare_document_for_parsing(
        f"secure.{extension}", encrypted, secured(f"secure.{extension}", "office-password")
    )
    assert name == f"secure.{extension}"
    assert plaintext.startswith(b"PK")
    assert PASSWORD_STORAGE_FIELD not in parser_config


def test_office_wrong_or_missing_password():
    encrypted = encrypted_office_zip("office-password")
    with pytest.raises(DocumentPasswordError, match="password protected"):
        validate_document_access("secure.docx", encrypted, {})
    with pytest.raises(DocumentPasswordError, match="incorrect"):
        validate_document_access("secure.docx", encrypted, secured("secure.docx", "wrong"))


def test_encrypted_and_plain_hwpx_are_extracted_to_text():
    encrypted = hwpx_document("hwpx-password")
    name, plaintext, parser_config = prepare_document_for_parsing(
        "secure.hwpx", encrypted, secured("secure.hwpx", "hwpx-password")
    )
    assert name == "secure.hwpx.txt"
    assert plaintext.decode() == "암호화 HWPX 본문\n두 번째 문단"
    assert PASSWORD_STORAGE_FIELD not in parser_config

    plain_name, plain_text, _ = prepare_document_for_parsing("plain.hwpx", hwpx_document(None), {})
    assert plain_name == "plain.hwpx.txt"
    assert plain_text.decode() == "암호화 HWPX 본문\n두 번째 문단"


def test_hwpx_wrong_or_missing_password():
    encrypted = hwpx_document("correct")
    with pytest.raises(DocumentPasswordError, match="password protected"):
        validate_document_access("secure.hwpx", encrypted, {})
    with pytest.raises(DocumentPasswordError, match="incorrect"):
        validate_document_access("secure.hwpx", encrypted, secured("secure.hwpx", "wrong"))


def test_status_redaction_clear_and_legacy_storage_migration():
    config = secured("secure.docx", "secret")
    sanitized = sanitize_parser_config(config)
    assert PASSWORD_STORAGE_FIELD not in sanitized
    assert sanitized[PASSWORD_STATUS_FIELD] is True

    cleared, changed = secure_parser_config({**config, PASSWORD_CLEAR_FIELD: True}, "secure.docx")
    assert changed is True
    assert cleared[PASSWORD_STORAGE_FIELD] is None

    legacy = {LEGACY_STORAGE_FIELD: config[PASSWORD_STORAGE_FIELD]}
    migrated, changed = secure_parser_config(legacy, "secure.pdf")
    assert changed is False
    assert LEGACY_STORAGE_FIELD not in migrated
    assert migrated[PASSWORD_STORAGE_FIELD] == config[PASSWORD_STORAGE_FIELD]

    duplicated, changed = secure_parser_config(
        {
            PASSWORD_STORAGE_FIELD: config[PASSWORD_STORAGE_FIELD],
            LEGACY_STORAGE_FIELD: "stale-legacy-token",
        },
        "secure.pdf",
    )
    assert changed is False
    assert LEGACY_STORAGE_FIELD not in duplicated
    assert duplicated[PASSWORD_STORAGE_FIELD] == config[PASSWORD_STORAGE_FIELD]


def test_password_rejected_for_unrelated_file_type_and_plain_office_is_unchanged():
    with pytest.raises(DocumentPasswordError, match="supported"):
        secure_parser_config({PASSWORD_INPUT_FIELD: "secret"}, "notes.txt")

    plain = io.BytesIO()
    with ZipFile(plain, "w") as archive:
        archive.writestr("word/document.xml", "plain")
    name, binary, config = prepare_document_for_parsing("plain.docx", plain.getvalue(), {})
    assert name == "plain.docx"
    assert binary == plain.getvalue()
    assert PASSWORD_STATUS_FIELD not in config
