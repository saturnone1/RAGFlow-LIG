"""Authoritative file-extension and chunk-parser compatibility contract."""

from __future__ import annotations

from pathlib import Path


class DocumentCompatibilityError(ValueError):
    """The selected parser cannot consume the uploaded document format."""


TEXT_EXTENSIONS = frozenset({"txt", "py", "js", "java", "c", "cpp", "h", "php", "go", "ts", "sh", "cs", "kt", "sql"})
MARKUP_EXTENSIONS = frozenset({"md", "markdown", "mdx"})
IMAGE_EXTENSIONS = frozenset(
    {"jpg", "jpeg", "png", "tif", "gif", "webp", "avif", "apng", "ico", "icon", "pcx", "tga", "psd"}
)
VIDEO_EXTENSIONS = frozenset({"mp4", "mov", "avi", "flv", "mpeg", "mpg", "webm", "wmv", "3gp", "3gpp", "mkv"})
AUDIO_EXTENSIONS = frozenset({"da", "wave", "wav", "mp3", "aac", "flac", "ogg", "aiff", "au", "midi", "wma", "realaudio", "vqf", "oggvorbis", "ape"})

NAIVE_EXTENSIONS = frozenset(
    {"doc", "docx", "pdf", "csv", "xls", "xlsx", "html", "htm", "epub", "json", "jsonl", "ldjson"}
) | TEXT_EXTENSIONS | MARKUP_EXTENSIONS

# HWP/HWPX are converted to parser-ready UTF-8 text by document_password.py.
TEXT_TRANSFORM_EXTENSIONS = frozenset({"hwp", "hwpx"})

PARSER_EXTENSIONS: dict[str, frozenset[str]] = {
    "naive": NAIVE_EXTENSIONS,
    "knowledge_graph": NAIVE_EXTENSIONS,
    "tag": frozenset({"xls", "xlsx", "txt", "csv"}),
    "book": frozenset({"doc", "docx", "pdf", "txt", "htm", "html"}),
    "laws": frozenset({"doc", "docx", "pdf", "txt", "md", "markdown", "mdx", "htm", "html"}),
    "manual": frozenset({"doc", "docx", "pdf"}),
    "paper": frozenset({"pdf"}),
    "presentation": frozenset({"ppt", "pptx", "pdf"}),
    "table": frozenset({"xls", "xlsx", "txt", "csv"}),
    "qa": frozenset({"xls", "xlsx", "txt", "csv", "pdf", "md", "markdown", "mdx", "docx"}),
    "one": frozenset({"doc", "docx", "pdf", "xls", "xlsx", "txt", "md", "markdown", "mdx", "htm", "html"}),
    "resume": frozenset({"pdf", "docx", "txt"}),
    "picture": IMAGE_EXTENSIONS | VIDEO_EXTENSIONS,
    "audio": AUDIO_EXTENSIONS,
    "email": frozenset({"eml"}),
}

RECOMMENDED_PARSER: dict[str, str] = {
    **{extension: "picture" for extension in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS},
    **{extension: "audio" for extension in AUDIO_EXTENSIONS},
    "eml": "email",
    "ppt": "presentation",
    "pptx": "presentation",
    "csv": "table",
    "xls": "table",
    "xlsx": "table",
}

CONVERSION_GUIDANCE: dict[str, str] = {
    "msg": "Export the message as EML.",
    "rtf": "Save the document as DOCX, PDF, or TXT.",
    "wps": "Save the document as DOCX or PDF.",
    "pages": "Export the document as DOCX or PDF.",
    "numbers": "Export the spreadsheet as XLSX or CSV.",
    "key": "Export the presentation as PPTX or PDF.",
    "yml": "Save the content as TXT or Markdown.",
    "yaml": "Save the content as TXT or Markdown.",
    "xml": "Save the content as TXT, HTML, or JSON.",
    "ini": "Save the content as TXT.",
    "hlp": "Export the help document as HTML, PDF, or TXT.",
    "alac": "Convert the audio to WAV, FLAC, or MP3.",
    "wavpack": "Convert the audio to WAV, FLAC, or MP3.",
    "wv": "Convert the audio to WAV, FLAC, or MP3.",
    "vorbis": "Convert the audio to WAV, FLAC, or MP3.",
    "opus": "Convert the audio to WAV, FLAC, or MP3.",
    "svg": "Export the image as PNG or JPEG.",
    "cdr": "Export the image as PNG or JPEG.",
    "dxf": "Export the drawing as PDF or PNG.",
    "ai": "Export the artwork as PDF or PNG.",
    "raw": "Develop the image and export it as PNG or JPEG.",
}


def document_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def parser_extension(filename: str) -> str:
    extension = document_extension(filename)
    return "txt" if extension in TEXT_TRANSFORM_EXTENSIONS else extension


def compatible_parsers(filename: str) -> tuple[str, ...]:
    extension = parser_extension(filename)
    return tuple(sorted(parser for parser, extensions in PARSER_EXTENSIONS.items() if extension in extensions))


def recommended_parser(filename: str) -> str | None:
    original_extension = document_extension(filename)
    if original_extension in TEXT_TRANSFORM_EXTENSIONS:
        return "naive"
    recommendation = RECOMMENDED_PARSER.get(original_extension)
    if recommendation:
        return recommendation
    parsers = compatible_parsers(filename)
    return "naive" if "naive" in parsers else (parsers[0] if parsers else None)


def validate_parser_compatibility(filename: str, parser_id: str | None) -> None:
    """Reject a document before storage when its effective parser cannot read it."""
    parser = (parser_id or "naive").lower()
    extension = document_extension(filename)
    effective_extension = parser_extension(filename)
    supported = PARSER_EXTENSIONS.get(parser)
    if supported is not None and effective_extension in supported:
        return

    parsers = compatible_parsers(filename)
    recommendation = recommended_parser(filename)
    if recommendation:
        guidance = f" Select the '{recommendation}' chunk method."
    else:
        guidance = " " + CONVERSION_GUIDANCE.get(extension, "Convert the file to PDF, DOCX, TXT, or another supported format.")
    parser_list = ", ".join(parsers) if parsers else "none"
    raise DocumentCompatibilityError(
        f".{extension or '(none)'} files cannot be chunked with the '{parser}' method."
        f" Compatible methods: {parser_list}.{guidance}"
    )
