"""Deterministic fact model and extraction utilities for Phase 2."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .document import Document, Page

STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "with",
}

VERB_WORDS = {
    "had",
    "has",
    "have",
    "was",
    "were",
    "is",
    "are",
    "rose",
    "grew",
    "fell",
    "declined",
    "increased",
    "reached",
    "reported",
    "stood",
    "completed",
    "ended",
    "recorded",
    "posted",
    "operated",
    "generated",
    "closed",
}

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"(?P<value>\d[\d,]*(?:\.\d+)?)%")
CURRENCY_RE = re.compile(
    r"(?:(?P<symbol>[$€£¥₹])|(?P<name>USD|INR|EUR|GBP|JPY|AUD|CAD|CNY|dollar|dollars|rupee|rupees))"
    r"\s*(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<scale>million|billion|thousand|lakh|crore|m|bn|k)?",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"(?P<value>(?:"
    + "|".join(MONTHS)
    + r")\s+\d{4}|FY\d{2,4}|Q[1-4](?:\s+of\s+)?\d{4}|(?:19|20)\d{2})",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Fact:
    """Deterministic, provenance-preserving representation of a structured fact."""

    fact_id: str
    subject: str
    fact_type: str
    raw_value: str
    normalized_value: float | int | str | None
    unit: str | None = None
    metric: str | None = None
    evidence_text: str = ""
    page_number: int = 0
    document_id: str = ""
    document_name: str = ""
    confidence: float = 1.0
    status: str = "extracted"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        subject: str,
        fact_type: str,
        raw_value: str,
        normalized_value: float | int | str | None,
        unit: str | None,
        evidence_text: str,
        page_number: int,
        document_id: str,
        document_name: str,
        confidence: float = 1.0,
        status: str = "extracted",
        metric: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Fact:
        """Create a fact with a stable generated identifier."""
        return cls(
            fact_id=uuid.uuid4().hex,
            subject=subject.strip(),
            fact_type=fact_type,
            raw_value=raw_value.strip(),
            normalized_value=normalized_value,
            unit=unit,
            metric=metric,
            evidence_text=evidence_text.strip(),
            page_number=page_number,
            document_id=document_id,
            document_name=document_name,
            confidence=confidence,
            status=status,
            metadata=metadata or {},
        )


def _normalize_number(raw: str) -> float:
    """Turn a number string into a float."""
    cleaned = raw.replace(",", "")
    return float(cleaned)


def _strip_trailing_punctuation(value: str) -> str:
    """Remove common punctuation to keep subject names readable."""
    return value.strip().rstrip(".,;:!?()[]{}\"'")


def _words(text: str) -> list[str]:
    """Tokenize lowercase words from a text fragment."""
    return re.findall(r"[A-Za-z][A-Za-z0-9&/.-]*", text)


def _derive_subject(prefix: str) -> str:
    """Extract a subject from the text immediately before a value match."""
    tokens = _words(prefix)
    if not tokens:
        return "unknown"

    filtered = [
        token
        for token in tokens
        if token.lower() not in STOPWORDS and token.lower() not in VERB_WORDS
    ]
    if not filtered:
        filtered = tokens

    if len(filtered) <= 2:
        return _strip_trailing_punctuation(" ".join(filtered))

    return _strip_trailing_punctuation(" ".join(filtered[-2:]))


def _extract_subject_and_value(sentence: str, match: re.Match[str]) -> tuple[str, str]:
    """Return a subject phrase and raw value from a sentence-level match."""
    prefix = sentence[: match.start()]
    subject = _derive_subject(prefix)
    raw_value = match.group(0)
    return subject, raw_value


def _normalize_currency(raw_value: str, scale: str | None) -> float:
    """Normalize numeric values that include a currency scale such as million or crore."""
    number = _normalize_number(raw_value)

    scale_map = {
        "k": 1_000.0,
        "thousand": 1_000.0,
        "lakh": 100_000.0,
        "crore": 10_000_000.0,
        "m": 1_000_000.0,
        "million": 1_000_000.0,
        "bn": 1_000_000_000.0,
        "billion": 1_000_000_000.0,
    }

    multiplier = scale_map.get((scale or "").lower(), 1.0)
    return number * multiplier


def _sentence_fact_candidates(sentence: str, page: Page, document: Document) -> list[Fact]:
    """Generate fact candidates from one sentence using lightweight deterministic parsing."""
    candidates: list[Fact] = []
    text = sentence.strip()
    if not text:
        return candidates

    currency_match = CURRENCY_RE.search(text)
    if currency_match:
        subject, raw_value = _extract_subject_and_value(text, currency_match)
        normalized = _normalize_currency(
            currency_match.group("value"), currency_match.group("scale")
        )
        candidates.append(
            Fact.create(
                subject=subject,
                fact_type="currency",
                raw_value=f"{currency_match.group(0).strip()}",
                normalized_value=normalized,
                unit="currency",
                metric="currency_value",
                evidence_text=text,
                page_number=page.page_number,
                document_id=document.document_id,
                document_name=document.source_name,
                metadata={
                    "currency_symbol": currency_match.group("symbol")
                    or currency_match.group("name")
                },
            )
        )

    percent_match = PERCENT_RE.search(text)
    if percent_match:
        subject, raw_value = _extract_subject_and_value(text, percent_match)
        normalized = float(_normalize_number(percent_match.group("value")))
        candidates.append(
            Fact.create(
                subject=subject,
                fact_type="percentage",
                raw_value=percent_match.group(0),
                normalized_value=normalized,
                unit="percent",
                metric="percentage",
                evidence_text=text,
                page_number=page.page_number,
                document_id=document.document_id,
                document_name=document.source_name,
            )
        )

    quantity_pattern = re.compile(
        r"(?P<subject>[^.!?]*?)(?:had|with|reported|reached|posted|recorded|saw|operated|generated|of|at|on)\s+"
        r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>[A-Za-z][A-Za-z/.-]{0,25})",
        re.IGNORECASE,
    )
    quantity_match = quantity_pattern.search(text)
    if quantity_match:
        subject = _strip_trailing_punctuation(quantity_match.group("subject").strip())
        subject = _derive_subject(subject)
        raw_value = quantity_match.group("value")
        unit = _strip_trailing_punctuation(quantity_match.group("unit").strip())
        normalized = _normalize_number(raw_value)
        if not re.fullmatch(r"page|pages|page\s*\d+", unit, flags=re.IGNORECASE):
            candidates.append(
                Fact.create(
                    subject=subject,
                    fact_type="quantity",
                    raw_value=raw_value,
                    normalized_value=normalized,
                    unit=unit,
                    metric="quantity",
                    evidence_text=text,
                    page_number=page.page_number,
                    document_id=document.document_id,
                    document_name=document.source_name,
                )
            )

    date_match = DATE_RE.search(text)
    if date_match:
        subject = _extract_subject_and_value(text, date_match)[0]
        value = date_match.group("value")
        candidates.append(
            Fact.create(
                subject=subject,
                fact_type="date",
                raw_value=value,
                normalized_value=value,
                unit=None,
                metric="date",
                evidence_text=text,
                page_number=page.page_number,
                document_id=document.document_id,
                document_name=document.source_name,
            )
        )

    return candidates


def _sentence_chunks(text: str) -> list[str]:
    """Split page text into sentences with simple deterministic boundaries."""
    if not text.strip():
        return []
    sections = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in sections if part.strip()]


def extract_facts(document: Document) -> list[Fact]:
    """Extract a small deterministic set of general facts from a domain-document model."""
    facts: list[Fact] = []

    for page in document.pages:
        if not page.has_extractable_text:
            continue

        for sentence in _sentence_chunks(page.text):
            sentence_facts = _sentence_fact_candidates(sentence, page, document)
            facts.extend(sentence_facts)

    return facts
