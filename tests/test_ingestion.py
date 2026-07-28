from pathlib import Path

import pytest

from app.services.ingestion import (
    UnsupportedDocumentError,
    load_document,
    load_uploaded_document,
)


def test_load_markdown_preserves_path_and_content(tmp_path: Path) -> None:
    source = tmp_path / "Project Notes.md"
    source.write_text("# API\n\nBuilt a FastAPI service.", encoding="utf-8")

    document = load_document(source)

    assert document.source_path == str(source)
    assert document.source_id.startswith("project-notes-")
    assert "FastAPI service" in document.content


def test_loader_rejects_unsupported_type(tmp_path: Path) -> None:
    source = tmp_path / "resume.csv"
    source.write_text("skill,Python", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentError, match="Unsupported document type"):
        load_document(source)


def test_uploaded_text_document_is_loaded_without_disk_write() -> None:
    document = load_uploaded_document(
        "Project Notes.md",
        b"# API\n\nBuilt a FastAPI service.",
    )

    assert document.source_path == "Project Notes.md"
    assert document.source_id.startswith("project-notes-")
    assert "FastAPI service" in document.content


def test_uploaded_text_must_be_utf8() -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        load_uploaded_document("notes.txt", b"\xff")
