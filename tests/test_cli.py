"""Tests for the superjoin command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf as fitz
import pytest

from superjoin_fact_knowledge.cli import main


def _create_test_pdf(path: Path, text: str) -> Path:
    """Helper to create a single-page PDF with text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def test_cli_help_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "usage: superjoin" in captured.out


def test_cli_query_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = _create_test_pdf(
        tmp_path / "test_report.pdf",
        "Total revenue reached $42.0 million in FY2024.",
    )

    exit_code = main([str(pdf_path), "-q", "Total revenue"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Query:  Total revenue" in captured.out
    assert "Status: answer_found" in captured.out
    assert "Total revenue was $42.0 million" in captured.out
    assert "test_report.pdf" in captured.out


def test_cli_query_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = _create_test_pdf(
        tmp_path / "test_report.pdf",
        "Operating profit was $15.5 million in FY2024.",
    )

    exit_code = main([str(pdf_path), "-q", "Operating profit", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["query"] == "Operating profit"
    assert data["status"] == "answer_found"
    assert data["is_grounded"] is True
    assert "$15.5 million" in data["answer"]
    assert len(data["evidence"]) >= 1
    assert data["evidence"][0]["document"] == "test_report.pdf"


def test_cli_missing_file_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "does_not_exist.pdf"), "-q", "test"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error:" in captured.err


def test_cli_missing_query_flag_fails() -> None:
    with pytest.raises(SystemExit):
        main(["dummy.pdf"])
