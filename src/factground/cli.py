"""Command-line interface for FactGround."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .ingestion import PDFIngestionError
from .knowledge import QueryResult
from .workflow import build_knowledge_base, query


def _format_text_result(result: QueryResult) -> str:
    """Format query result for terminal display."""
    lines = [
        "=" * 64,
        f"Query:  {result.query}",
        f"Status: {result.status} (Grounded: {'Yes' if result.is_grounded else 'No'})",
    ]
    if result.explanation:
        lines.append(f"Score / Match Reasons: {result.explanation}")
    lines.append("=" * 64)

    if result.answer_text:
        lines.append(f"Answer: {result.answer_text}")
    else:
        lines.append("Answer: [No unambiguous grounded answer found]")

    lines.append("-" * 64)

    if result.matches:
        lines.append(f"Candidate Facts Found ({len(result.matches)}):")
        for idx, match in enumerate(result.matches, start=1):
            fact = match.fact
            lines.append(f"  [{idx}] {fact.subject} -> {fact.raw_value} (Page {fact.page_number})")
            lines.append(f"      Document:   {fact.document_name}")
            if fact.normalized_value is not None:
                lines.append(f"      Normalized: {fact.normalized_value} {fact.unit or ''}".strip())
            lines.append(f'      Evidence:   "{fact.evidence_text}"')
            lines.append(f"      Status:     {fact.status} (Score: {match.score:.1f})")
    else:
        lines.append("No matching facts found in knowledge base.")

    lines.append("=" * 64)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for CLI execution."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="factground",
        description="Extract, ground, and query facts from documents.",
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        metavar="PDF",
        help="Path(s) to one or more PDF files to ingest.",
    )
    parser.add_argument(
        "-q",
        "--query",
        required=True,
        metavar="QUERY",
        help="Natural language or keyword query string.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured JSON to stdout.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum candidate matches to return (default: 5).",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Include ungrounded/review facts in matching.",
    )

    args = parser.parse_args(argv)

    try:
        kb = build_knowledge_base(args.pdf_paths)
        result = query(
            kb,
            args.query,
            limit=args.limit,
            include_needs_review=args.include_review,
        )

        if args.json_output:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(_format_text_result(result))

        return 0

    except (PDFIngestionError, ValueError, FileNotFoundError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
