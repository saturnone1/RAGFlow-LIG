from __future__ import annotations

import pytest

from lig_runtime.document_compatibility import (
    DocumentCompatibilityError,
    compatible_parsers,
    recommended_parser,
    validate_parser_compatibility,
)


@pytest.mark.parametrize(
    ("filename", "parser"),
    [
        ("report.pdf", "naive"),
        ("sheet.xlsx", "table"),
        ("slides.pptx", "presentation"),
        ("source.go", "naive"),
        ("mail.eml", "email"),
        ("scan.png", "picture"),
        ("voice.wav", "audio"),
        ("document.hwp", "naive"),
        ("document.hwpx", "table"),
    ],
)
def test_compatible_parser_matrix(filename, parser):
    validate_parser_compatibility(filename, parser)


@pytest.mark.parametrize(
    ("filename", "parser", "recommendation"),
    [
        ("slides.pptx", "naive", "presentation"),
        ("message.msg", "email", None),
        ("legacy.rtf", "naive", None),
        ("drawing.svg", "picture", None),
        ("manual.pdf", "table", "naive"),
    ],
)
def test_incompatible_parser_has_actionable_error(filename, parser, recommendation):
    with pytest.raises(DocumentCompatibilityError, match="cannot be chunked") as caught:
        validate_parser_compatibility(filename, parser)
    if recommendation:
        assert f"'{recommendation}'" in str(caught.value)


def test_recommendations_and_compatible_parser_list_are_deterministic():
    assert recommended_parser("data.csv") == "table"
    assert recommended_parser("security.HWPX") == "naive"
    assert "naive" in compatible_parsers("README.md")
    assert compatible_parsers("unsupported.rtf") == ()


def test_tag_parser_does_not_accept_naive_only_formats():
    validate_parser_compatibility("tags.csv", "tag")
    with pytest.raises(DocumentCompatibilityError):
        validate_parser_compatibility("report.pdf", "tag")
