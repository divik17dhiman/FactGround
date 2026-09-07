"""Tests for the PDF ingestion and document representation layer."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from superjoin_fact_knowledge import Document, PDFIngestionError, ingest_pdf


def _write_pdf(path: Path, page_texts: list[str | None]) -> None:
    """Create a deterministic PDF with one page per text entry."""
    pdf = fitz.open()
    for text in page_texts:
        page = pdf.new_page()
        if text is not None:
            page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def test_ingest_pdf_success(tmp_path: Path) -> None:
    """A simple multi-page PDF should be represented with preserved page numbers."""
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf(
        pdf_path,
        [
            "Revenue: INR 100 crore\nGrowth: 12.5%",
            "Employees: 1,250",
        ],
    )

    document = ingest_pdf(pdf_path)

    assert isinstance(document, Document)
    assert len(document.pages) == 2
    assert [page.page_number for page in document.pages] == [1, 2]
    assert document.pages[0].text.startswith("Revenue:")
    assert "100 crore" in document.pages[0].text
    assert "12.5%" in document.pages[0].text
    assert "Employees: 1,250" in document.pages[1].text
    assert "1,250" in document.pages[1].text
    assert document.diagnostics.page_count == 2
    assert document.diagnostics.pages_with_text == 2
    assert document.diagnostics.pages_without_text == 0


def test_ingest_pdf_handles_empty_text_pages(tmp_path: Path) -> None:
    """Pages with no extractable text should remain in the document with diagnostics."""
    pdf_path = tmp_path / "empty-page.pdf"
    _write_pdf(pdf_path, ["Revenue: INR 100 crore", None])

    document = ingest_pdf(pdf_path)

    assert len(document.pages) == 2
    assert document.pages[0].has_extractable_text is True
    assert document.pages[1].has_extractable_text is False
    assert document.pages[1].text == ""
    assert document.pages[1].page_number == 2
    assert document.diagnostics.empty_pages == [2]
    assert document.diagnostics.pages_without_text == 1


def test_ingest_pdf_invalid_input_raises_meaningful_error(tmp_path: Path) -> None:
    """Invalid file inputs should raise a domain-level ingestion error."""
    missing_path = tmp_path / "missing.pdf"
    with pytest.raises(PDFIngestionError, match="does not exist"):
        ingest_pdf(missing_path)

    directory = tmp_path / "not_a_file"
    directory.mkdir()
    with pytest.raises(PDFIngestionError, match="directory"):
        ingest_pdf(directory)

    text_path = tmp_path / "not_a_pdf.txt"
    text_path.write_text("this is not a pdf", encoding="utf-8")
    with pytest.raises(PDFIngestionError, match="PDF"):
        ingest_pdf(text_path)

    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4\nnot actually valid pdf\n")
    with pytest.raises(PDFIngestionError, match="invalid|unreadable|corrupt"):
        ingest_pdf(corrupt_pdf)


def test_document_metadata_is_exposed(tmp_path: Path) -> None:
    """The document should expose page counts and source metadata for later stages."""
    pdf_path = tmp_path / "meta.pdf"
    _write_pdf(pdf_path, ["Page one", "Page two"])

    document = ingest_pdf(pdf_path)

    assert document.source_path == str(pdf_path)
    assert document.source_name == pdf_path.name
    assert document.diagnostics.page_count == 2
    assert document.diagnostics.approximate_character_count > 0
    assert document.source_metadata["file_size_bytes"] > 0
