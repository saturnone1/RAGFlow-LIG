"""Optional legacy Office integration tests using msoffcrypto-tool's MIT fixtures.

Set LIG_LEGACY_OFFICE_FIXTURES to the ``tests/inputs`` directory from
https://github.com/nolze/msoffcrypto-tool (validated at commit
6d9e72c58de2cf7df1ab45ac0d74ebedac8c58e3). The binary fixtures are not
duplicated in the air-gap product repository.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest

from lig_runtime.document_password import (
    DocumentPasswordError,
    secure_parser_config,
    validate_document_access,
)

FIXTURE_ROOT = os.environ.get("LIG_LEGACY_OFFICE_FIXTURES")
pytestmark = pytest.mark.skipif(not FIXTURE_ROOT, reason="legacy Office fixture directory is not configured")


@pytest.fixture(autouse=True)
def password_key(monkeypatch):
    monkeypatch.setenv("LIG_DOCUMENT_PASSWORD_KEY", base64.b64encode(bytes(range(32))).decode())
    monkeypatch.setenv("LIG_DOCUMENT_PASSWORD_KEY_ID", "test")


@pytest.mark.parametrize(
    ("filename", "password"),
    [
        ("rc4cryptoapi_password.doc", "Password1234_"),
        ("rc4cryptoapi_password.xls", "Password1234_"),
        ("rc4cryptoapi_password.ppt", "Password1234_"),
        ("xor_password_123456789012345.xls", "123456789012345"),
    ],
)
def test_legacy_office_password_validation(filename, password):
    binary = (Path(FIXTURE_ROOT) / filename).read_bytes()
    config, _ = secure_parser_config({"document_password": password}, filename)
    validate_document_access(filename, binary, config)

    wrong_config, _ = secure_parser_config({"document_password": "incorrect"}, filename)
    with pytest.raises(DocumentPasswordError, match="incorrect|unsupported"):
        validate_document_access(filename, binary, wrong_config)
