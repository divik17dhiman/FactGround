"""Deterministic fact model and extraction utilities for Phase 2."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field, replace
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
QUANTITY_RE = re.compile(
    r"(?P<subject>[^.!?]*?)(?:had|with|reported|reached|posted|recorded|saw|operated|generated|of|at|on)\s+"
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>[A-Za-z][A-Za-z/.-]{0,25})",
    re.IGNORECASE,
)
SUBJECT_BOUNDARY_RE = re.compile(r"\b(?:and|or|but)\b|[;:]", re.IGNORECASE)


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


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace to make validation comparisons resilient."""
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    """Tokenize lowercase words from a text fragment."""
    return re.findall(r"[A-Za-z][A-Za-z0-9&/.-]*", text)


def _subject_context(prefix: str) -> str:
    """Prefer the text segment nearest the extracted value when deriving a subject."""
    segments = SUBJECT_BOUNDARY_RE.split(prefix)
    if not segments:
        return prefix
    return segments[-1]


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
    prefix = _subject_context(sentence[: match.start()])
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


def _expected_normalized_value(fact: Fact) -> float | str | None:
    """Derive the canonical normalized value implied by a fact's raw text."""
    raw_value = fact.raw_value.strip()

    if fact.fact_type == "currency":
        currency_match = CURRENCY_RE.fullmatch(raw_value)
        if currency_match is None:
            return None
        return _normalize_currency(currency_match.group("value"), currency_match.group("scale"))

    if fact.fact_type == "percentage":
        percent_match = PERCENT_RE.fullmatch(raw_value)
        if percent_match is None:
            return None
        return _normalize_number(percent_match.group("value"))

    if fact.fact_type == "quantity":
        number_match = NUMBER_RE.fullmatch(raw_value)
        if number_match is None:
            return None
        return _normalize_number(number_match.group(0))

    if fact.fact_type == "date":
        return raw_value

    return None


def _fact_evidence_mentions_raw_value(fact: Fact) -> bool:
    """Check whether the evidence text contains the extracted value or a safe equivalent."""
    evidence = _normalize_whitespace(fact.evidence_text).casefold()
    if not evidence:
        return False

    raw_value = _normalize_whitespace(fact.raw_value).casefold()
    if raw_value and raw_value in evidence:
        return True

    compact_raw = raw_value.replace(" ", "")
    compact_evidence = evidence.replace(" ", "")
    if compact_raw and compact_raw in compact_evidence:
        return True

    if fact.fact_type == "currency":
        currency_match = CURRENCY_RE.fullmatch(fact.raw_value.strip())
        if currency_match is not None:
            value = currency_match.group("value").casefold()
            value_no_commas = value.replace(",", "")
            currency_tokens = [
                currency_match.group("symbol"),
                currency_match.group("name"),
                currency_match.group("scale"),
            ]
            if value in evidence or value_no_commas in compact_evidence:
                return True
            for token in currency_tokens:
                if token and token.casefold() in evidence:
                    return True

    if fact.fact_type == "percentage":
        percent_value = fact.raw_value.strip().rstrip("%")
        if percent_value and percent_value.casefold() in evidence:
            return True
        if percent_value and f"{percent_value}%".casefold() in evidence:
            return True
        if percent_value and f"{percent_value} percent".casefold() in evidence:
            return True

    if fact.fact_type == "quantity":
        quantity_value = fact.raw_value.strip().replace(",", "")
        if quantity_value and quantity_value.casefold() in compact_evidence:
            return True

    return False


def validate_fact(fact: Fact, document: Document) -> Fact:
    """Validate evidence grounding for a fact against its source document."""
    validation_issues: list[str] = []

    if not fact.document_id.strip():
        validation_issues.append("missing_document_id")
    if not fact.document_name.strip():
        validation_issues.append("missing_document_name")

    page_numbers = {page.page_number for page in document.pages}
    if fact.page_number not in page_numbers:
        validation_issues.append("invalid_page_number")

    if not fact.evidence_text.strip():
        validation_issues.append("missing_evidence")
    elif not _fact_evidence_mentions_raw_value(fact):
        validation_issues.append("evidence_missing_raw_value")

    expected_value = _expected_normalized_value(fact)
    if expected_value is not None:
        if fact.normalized_value is None:
            validation_issues.append("missing_normalized_value")
        elif isinstance(expected_value, float):
            if not isinstance(fact.normalized_value, (int, float)) or not math.isclose(
                float(fact.normalized_value), expected_value, rel_tol=1e-9, abs_tol=1e-9
            ):
                validation_issues.append("normalized_value_mismatch")
        elif str(fact.normalized_value).strip() != expected_value:
            validation_issues.append("normalized_value_mismatch")

    metadata = dict(fact.metadata)
    metadata["validation_issues"] = validation_issues
    metadata["is_grounded"] = not validation_issues

    return replace(
        fact,
        confidence=fact.confidence if not validation_issues else min(fact.confidence, 0.5),
        status="grounded" if not validation_issues else "needs_review",
        metadata=metadata,
    )


def validate_facts(facts: list[Fact], document: Document) -> list[Fact]:
    """Validate a batch of facts against one document."""
    return [validate_fact(fact, document) for fact in facts]


def _sentence_fact_candidates(sentence: str, page: Page, document: Document) -> list[Fact]:
    """Generate fact candidates from one sentence using lightweight deterministic parsing."""
    candidates: list[Fact] = []
    text = sentence.strip()
    if not text:
        return candidates

    for currency_match in CURRENCY_RE.finditer(text):
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

    for percent_match in PERCENT_RE.finditer(text):
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

    for quantity_match in QUANTITY_RE.finditer(text):
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

    for date_match in DATE_RE.finditer(text):
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
