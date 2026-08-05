"""Tests for the document understanding pipeline (attachments → text → understanding)."""

from __future__ import annotations

import io

from pypdf import PdfWriter
from sqlmodel import Session, select

from app.core.db import engine
from app.core.models import Document
from app.documents.extract import DocKind, detect_kind, extract_text
from app.documents.pipeline import DocumentProcessor


def _docx_bytes(text: str) -> bytes:
    import docx

    document = docx.Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_detect_kind_by_extension_and_type():
    assert detect_kind("report.pdf") is DocKind.pdf
    assert detect_kind("contract.docx") is DocKind.word
    assert detect_kind("scan.png") is DocKind.image
    assert detect_kind("notes.txt") is DocKind.text
    assert detect_kind("photo", "image/jpeg") is DocKind.image


def test_extract_text_from_docx():
    result = extract_text(_docx_bytes("Hello warranty claim"), "contract.docx")
    assert result.kind is DocKind.word
    assert "warranty claim" in result.text
    assert result.needs_vision is False


def test_extract_text_from_plaintext():
    result = extract_text(b"plain body text", "note.txt", "text/plain")
    assert result.kind is DocKind.text
    assert result.text == "plain body text"


def test_scanned_pdf_flags_needs_vision():
    result = extract_text(_blank_pdf_bytes(), "scan.pdf", "application/pdf")
    assert result.kind is DocKind.pdf
    # A blank/scanned PDF has no extractable text → route to a vision model.
    assert result.needs_vision is True


def test_image_flags_needs_vision():
    result = extract_text(b"\x89PNG\r\n", "photo.png", "image/png")
    assert result.kind is DocKind.image
    assert result.needs_vision is True
    assert result.text == ""


def test_processor_persists_document_and_summary():
    with Session(engine) as session:
        processor = DocumentProcessor(session)
        analysis = processor.analyze(
            _docx_bytes("Invoice due 2025-01-15 for account 12345"),
            "invoice.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            source="email:test",
        )
        assert analysis.kind is DocKind.word
        assert analysis.summary  # mock LLM returns a deterministic summary
        assert analysis.file_hash
        assert analysis.stored_document_id is not None

        stored = session.exec(select(Document)).all()
    assert len(stored) == 1
    assert stored[0].source == "email:test"
    assert stored[0].storage_ref is not None
