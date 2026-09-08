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
    "as",
    "at",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "than",
    "that",
    "the",
    "their",
    "this",
    "these",
    "those",
    "to",
    "was",
    "were",
    "which",
    "with",
}

VERB_WORDS = {
    "had",
    "has",
    "have",
    "having",
    "was",
    "were",
    "is",
    "are",
    "be",
    "been",
    "rose",
    "rise",
    "rising",
    "risen",
    "grew",
    "grow",
    "growing",
    "grown",
    "fell",
    "fall",
    "falling",
    "fallen",
    "declined",
    "decline",
    "declining",
    "increased",
    "increase",
    "increasing",
    "decreased",
    "decrease",
    "decreasing",
    "reached",
    "reach",
    "reaching",
    "reported",
    "report",
    "reporting",
    "stood",
    "stand",
    "standing",
    "completed",
    "complete",
    "completing",
    "ended",
    "end",
    "ending",
    "recorded",
    "record",
    "recording",
    "posted",
    "post",
    "posting",
    "operated",
    "generated",
    "generate",
    "generating",
    "closed",
    "close",
    "closing",
    "expected",
    "expect",
    "expects",
    "expecting",
    "projected",
    "project",
    "projects",
    "projecting",
    "estimated",
    "estimate",
    "estimates",
    "estimating",
    "anticipated",
    "anticipate",
    "anticipates",
    "anticipating",
    "forecast",
    "forecasted",
    "forecasting",
    "compared",
    "comparing",
    "comprising",
    "comprises",
    "comprised",
    "representing",
    "represents",
    "represented",
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

# Units that are too generic or frequently noise in document extraction
INVALID_UNIT_PATTERNS = {
    "page",
    "pages",
    "section",
    "chapter",
    "ref",
    "figure",
    "table",
    "note",
    "of",
    "to",
    "from",
    "for",
    "and",
    "or",
    "by",
    "in",
    "on",
    "at",
    "a",
    "an",
    "the",
    "as",
    "is",
    "are",
    "be",
    "been",
}

# Known valid unit abbreviations and their normalized form
KNOWN_UNITS = {
    "m": "m",
    "mn": "mn",
    "million": "million",
    "mil": "million",
    "b": "bn",
    "bn": "bn",
    "billion": "billion",
    "bil": "billion",
    "k": "k",
    "thousand": "thousand",
    "th": "thousand",
    "lakh": "lakh",
    "cr": "crore",
    "crore": "crore",
    "sq": "sq",
    "sqft": "sq ft",
    "sq ft": "sq ft",
    "sq m": "sq m",
    "mt": "mt",
    "tonnes": "tonnes",
    "tons": "tons",
    "pcs": "pcs",
    "pieces": "pieces",
    "units": "units",
}

PERIOD_PATTERNS = [
    (
        re.compile(r"\bFY\s*(?:19|20)?(\d{2})\b", re.IGNORECASE),
        lambda m: f"FY20{m.group(1)}",
    ),
    (
        re.compile(r"\bfiscal\s+(?:year\s+)?(?:19|20)?(\d{2})\b", re.IGNORECASE),
        lambda m: f"FY20{m.group(1)}",
    ),
    (
        re.compile(r"\bfinancial\s+year\s+(?:19|20)?(\d{2})\b", re.IGNORECASE),
        lambda m: f"FY20{m.group(1)}",
    ),
    (
        re.compile(r"\b(Q[1-4])\s*(?:of\s+)?(?:FY\s*)?(?:19|20)?(\d{2})\b", re.IGNORECASE),
        lambda m: f"{m.group(1).upper()} FY20{m.group(2)}",
    ),
    (
        re.compile(
            r"\b(?:year|period|months?)\s+ended\s+(?:(?:[A-Za-z]+|\d{1,2},?)\s+)*(20\d{2})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        re.compile(
            r"\bas\s+(?:of|at)\s+(?:(?:[A-Za-z]+|\d{1,2},?)\s+)*(20\d{2})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        re.compile(r"\b(?:in|for|during)\s+((?:19|20)\d{2})\b", re.IGNORECASE),
        lambda m: m.group(1),
    ),
    (
        re.compile(r"\bby\s+((?:19|20)\d{2})\b", re.IGNORECASE),
        lambda m: m.group(1),
    ),
]

EXCLUDE_PERIOD_PATTERNS = [
    re.compile(r"\b(?:Companies\s+)?Act,?\s*(?:19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\bRegulations?,?\s*(?:19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\bRules?,?\s*(?:19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\bCircular,?\s*(?:19|20)\d{2}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:Prospectus\s+)?Dated\s+[A-Za-z]+\s+\d{1,2},?\s*(?:19|20)\d{2}\b",
        re.IGNORECASE,
    ),
    re.compile(r"[A-Z0-9]{5,}(?:19|20)\d{2}[A-Z0-9]*", re.IGNORECASE),
    re.compile(r"\bSection\s+\d+\s+of\s+[^.!?\n]*(?:19|20)\d{2}\b", re.IGNORECASE),
]

SCOPE_PATTERNS = [
    (re.compile(r"\bfresh\s+issue\b", re.IGNORECASE), "Fresh Issue"),
    (re.compile(r"\boffer\s+for\s+sale\b", re.IGNORECASE), "Offer for Sale"),
    (
        re.compile(
            r"\b(?:total\s+offer|offer\s+of\s+equity\s+shares|aggregate\s+offer)\b",
            re.IGNORECASE,
        ),
        "Total Offer",
    ),
    (re.compile(r"\bface\s+value\b", re.IGNORECASE), "Face Value"),
]

SELLING_SHAREHOLDER_RE = re.compile(
    r"\b(?P<name>[A-Z][A-Za-z0-9&.,()\'/-]+(?:\s+[A-Za-z0-9&.,()\'/-]+)*)\s+Selling\s+Shareholder",
    re.IGNORECASE,
)

ENTITY_PREDICATE_RE = re.compile(
    r"\b(?P<entity>Company\s+[A-Za-z0-9]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Logistics|Corp|Inc|Ltd|Limited|Technologies|Holdings|Industries|Capital))\s+(?:reported|recorded|stood\s+at|posted|reached|announced|saw|had|revised\s+to)\b"
)

ENTITY_SUBJECT_RE = re.compile(
    r"\b(?:Company\s+[A-Za-z0-9]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Logistics|Corp|Inc|Ltd|Limited|Technologies|Holdings|Industries|Capital))\b"
)


def clean_text_for_periods(text: str) -> str:
    """Remove regulatory, corporate ID, and header dates that are not reporting periods."""
    cleaned = text
    for ep in EXCLUDE_PERIOD_PATTERNS:
        cleaned = ep.sub(" ", cleaned)
    return cleaned


def extract_period(text: str) -> str | None:
    """Deterministically extract and normalize a reliable reporting period from text."""
    cleaned = clean_text_for_periods(text)
    for pat, formatter in PERIOD_PATTERNS:
        m = pat.search(cleaned)
        if m:
            return formatter(m)
    m_yr = re.search(r"\b((?:19|20)\d{2})\b", cleaned)
    if m_yr and len(cleaned.split()) <= 6:
        return m_yr.group(1)
    return None


QUALIFIER_RE = re.compile(
    r"\b(?P<qual>expected|projected|forecast|forecasted|estimated|anticipated|target|guidance)\b",
    re.IGNORECASE,
)

FORWARD_CONNECTOR_RE = re.compile(
    r"^\s*(?:in|for|during|by|as\s+of|as\s+at|ended|ending|at|of)?\s*[\(\[]?\s*$",
    re.IGNORECASE,
)

BACKWARD_CONNECTOR_RE = re.compile(
    r"^\s*[\)\]]?(?:(?:in|for|during|by|as\s+of|as\s+at)\s+)?(?:was|were|reported|reached|stood\s+at|posted|generated|recorded|to|of|at|is)?\s*$",
    re.IGNORECASE,
)


def find_temporal_spans(text: str) -> list[dict[str, Any]]:
    """Locate non-overlapping reporting period patterns and their exact character spans in text."""
    excluded_mask = [False] * len(text)
    for ep in EXCLUDE_PERIOD_PATTERNS:
        for m in ep.finditer(text):
            for i in range(m.start(), m.end()):
                excluded_mask[i] = True

    spans: list[dict[str, Any]] = []
    for pat, formatter in PERIOD_PATTERNS:
        for m in pat.finditer(text):
            s, e = m.span()
            if any(excluded_mask[i] for i in range(s, e)):
                continue
            spans.append(
                {
                    "start": s,
                    "end": e,
                    "raw": m.group(0),
                    "period": formatter(m),
                }
            )

    # Sort spans by starting position and length descending
    spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered: list[dict[str, Any]] = []
    last_end = -1
    for sp in spans:
        if sp["start"] >= last_end:
            filtered.append(sp)
            last_end = sp["end"]
    return filtered


def associate_local_period(
    sentence: str,
    val_start: int,
    val_end: int,
    all_val_spans: list[tuple[int, int]],
    temporal_spans: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    """Deterministically associate an extracted numeric value with its local temporal context.

    Returns:
        (period, temporal_qualifier)
    """
    boundary_m = list(
        re.finditer(r"[;.]|\b(?:and|but|while|whereas)\b", sentence[:val_start], re.IGNORECASE)
    )
    clause_start = boundary_m[-1].end() if boundary_m else 0
    clause_text = sentence[clause_start:val_start]
    qual_m = QUALIFIER_RE.search(clause_text)
    qualifier = qual_m.group("qual").lower() if qual_m else None

    if not temporal_spans:
        return None, qualifier

    def crosses_other_val(s: int, e: int) -> bool:
        low, high = min(s, e), max(s, e)
        for vs, ve in all_val_spans:
            if (vs, ve) == (val_start, val_end):
                continue
            if vs >= low and ve <= high:
                return True
        return False

    def crosses_sentence_boundary(s: int, e: int) -> bool:
        sub = sentence[min(s, e) : max(s, e)]
        return bool(re.search(r"[;.]", sub))

    candidates: list[dict[str, Any]] = []

    for t in temporal_spans:
        t_start, t_end = t["start"], t["end"]
        p_val = t["period"]

        # 1. Forward attachment: value ... temporal (e.g. '$216 billion in Fiscal 2020')
        if t_start >= val_end:
            if crosses_other_val(val_end, t_start) or crosses_sentence_boundary(val_end, t_start):
                continue
            between = sentence[val_end:t_start]
            if len(between) <= 40 and FORWARD_CONNECTOR_RE.match(between):
                candidates.append(
                    {
                        "period": p_val,
                        "dist": len(between),
                        "direction": "forward",
                    }
                )
        # 2. Backward attachment: temporal ... value (e.g. 'In FY2024, revenue was $120m')
        elif t_end <= val_start:
            if crosses_other_val(t_end, val_start) or crosses_sentence_boundary(t_end, val_start):
                continue
            between = sentence[t_end:val_start]
            if len(between) <= 60 and BACKWARD_CONNECTOR_RE.match(between):
                candidates.append(
                    {
                        "period": p_val,
                        "dist": len(between),
                        "direction": "backward",
                    }
                )

    if not candidates:
        # Fallback: if there is exactly one temporal span and exactly one value in sentence,
        # attach if no sentence boundary separates them
        if len(temporal_spans) == 1 and len(all_val_spans) == 1:
            t = temporal_spans[0]
            if not crosses_sentence_boundary(val_start, t["start"]):
                return t["period"], qualifier
        return None, qualifier

    forward_cands = [c for c in candidates if c["direction"] == "forward"]
    backward_cands = [c for c in candidates if c["direction"] == "backward"]

    if forward_cands:
        best_f = min(forward_cands, key=lambda c: c["dist"])
        return best_f["period"], qualifier

    if backward_cands:
        best_b = min(backward_cands, key=lambda c: c["dist"])
        return best_b["period"], qualifier

    return None, qualifier


def extract_scope_and_entity(
    subject: str = "",
    local_text: str = "",
    full_prefix: str = "",
    page_text: str = "",
) -> tuple[str | None, str | None]:
    """Extract scope and entity context from local text and prefix cues."""
    combined = f"{local_text} {subject}".strip()

    prefix_source = page_text if page_text else full_prefix
    if prefix_source:
        sh_idx = prefix_source.lower().rfind("selling shareholder")
        if sh_idx != -1 and (len(prefix_source) - sh_idx <= 220):
            before_sh = prefix_source[:sh_idx]
            lines = [line.strip() for line in before_sh.split("\n") if line.strip()]
            if lines:
                cand = lines[-1]
                cand = re.sub(
                    r"\b(?:Investor|Individual|Promoter|Corporate)\b",
                    "",
                    cand,
                    flags=re.IGNORECASE,
                ).strip()
                if not cand and len(lines) >= 2:
                    cand = lines[-2]
                cand = re.sub(r"^[0-9.,\s#*-]+", "", cand).strip()
                if cand and not cand.lower().startswith("name of"):
                    return cand, cand

    matches = list(SELLING_SHAREHOLDER_RE.finditer(combined))
    if matches:
        last_m = matches[-1]
        name = last_m.group("name").strip()
        if "\n" in name:
            non_empty = [line_item.strip() for line_item in name.split("\n") if line_item.strip()]
            name = non_empty[-1] if non_empty else ""
        name = re.sub(
            r"\b(?:Investor|Individual|Promoter|Corporate)\b",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()
        name = re.sub(r"^[0-9.,\s#*-]+", "", name).strip()
        if name and not name.lower().startswith("name of"):
            return name, name

    for pat, label in SCOPE_PATTERNS:
        if pat.search(combined):
            return label, None

    if not local_text.strip() and prefix_source:
        if re.search(r"\btotal\s+offer\b", prefix_source, re.IGNORECASE):
            return "Total Offer", None

    m_ent = ENTITY_PREDICATE_RE.search(combined)
    if m_ent:
        entity = m_ent.group("entity").strip()
        return None, entity

    return None, None


def extract_entity_from_subject(subject: str) -> str | None:
    """Extract entity name from subject string if present."""
    m = re.search(r"\b(Company\s+[A-Za-z0-9]+)\b", subject, re.IGNORECASE)
    if m:
        return m.group(1).title()
    m2 = ENTITY_SUBJECT_RE.search(subject)
    if m2:
        return m2.group(0).strip()
    return None


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize fact to a structured dictionary representation."""
        return {
            "fact_id": self.fact_id,
            "subject": self.subject,
            "fact_type": self.fact_type,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "metric": self.metric,
            "evidence": self.evidence_text,
            "page": self.page_number,
            "document": self.document_name,
            "document_id": self.document_id,
            "confidence": self.confidence,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @property
    def scope(self) -> str | None:
        """Convenience property for context scope from metadata."""
        return self.metadata.get("scope")

    @property
    def entity(self) -> str | None:
        """Convenience property for entity from metadata."""
        return self.metadata.get("entity")

    @property
    def period(self) -> str | None:
        """Convenience property for reporting period from metadata."""
        return self.metadata.get("period")

    @property
    def temporal_qualifier(self) -> str | None:
        """Convenience property for temporal qualifier (e.g. expected, projected) from metadata."""
        return self.metadata.get("temporal_qualifier")


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


def _deduplicate_adjacent_words(text: str) -> str:
    """Remove consecutive repeated words to avoid 'Fiscal Fiscal' or 'March March'."""
    words = text.split()
    deduped = []
    for word in words:
        if not deduped or word.lower() != deduped[-1].lower():
            deduped.append(word)
    return " ".join(deduped)


def _words(text: str) -> list[str]:
    """Tokenize lowercase words from a text fragment."""
    return re.findall(r"[A-Za-z][A-Za-z0-9&/.-]*", text)


TEMPORAL_WORDS = {
    "fiscal",
    "fy",
    "quarter",
    "quarterly",
    "year",
    "years",
    "annual",
    "annually",
    "period",
    "month",
    "months",
    "date",
    "ended",
    *(m.lower() for m in MONTHS),
}

CURRENCY_SCALE_WORDS = {
    "usd",
    "inr",
    "eur",
    "gbp",
    "dollar",
    "dollars",
    "rupee",
    "rupees",
    "million",
    "billion",
    "thousand",
    "crore",
    "lakh",
    "k",
    "m",
    "bn",
    "percent",
    "percentage",
}


def _has_substantive_subject(text: str) -> bool:
    """Check whether a text fragment contains at least one substantive subject word."""
    words = _words(text)
    if not words:
        return False
    for w in words:
        wl = w.lower()
        if (
            wl not in STOPWORDS
            and wl not in VERB_WORDS
            and wl not in TEMPORAL_WORDS
            and wl not in CURRENCY_SCALE_WORDS
            and not any(ch.isdigit() for ch in wl)
        ):
            return True
    return False


def _subject_context(prefix: str) -> str:
    """Prefer the text segment nearest the extracted value when deriving a subject."""
    segments = SUBJECT_BOUNDARY_RE.split(prefix)
    if not segments:
        return prefix
    return segments[-1]


def _derive_subject(prefix: str) -> str:
    """Extract a subject from the text immediately before a value match.

    Prefers meaningful content words, deduplicates adjacent repetitions,
    and limits to 2-3 meaningful tokens for clarity.
    """
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

    # Avoid truncation: use last 2-3 tokens, but deduplicate adjacent repetitions
    if len(filtered) <= 2:
        subject_text = " ".join(filtered)
    else:
        subject_text = " ".join(filtered[-3:])

    # Remove adjacent duplicate words (handles "Fiscal Fiscal", "March March", etc.)
    subject_text = _deduplicate_adjacent_words(subject_text)

    return _strip_trailing_punctuation(subject_text)


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


def _is_valid_quantity_unit(unit: str) -> bool:
    """Check if a unit string is likely a valid measurement unit and not noise.

    Filters out common document artifacts (page numbers, section references, etc.)
    and single-letter fragments that are likely truncation artifacts.
    """
    if not unit:
        return False

    unit_lower = unit.lower().strip()

    # Filter known invalid patterns
    if unit_lower in INVALID_UNIT_PATTERNS:
        return False

    # Filter very short noise (single chars or pairs that are truncations)
    if len(unit) <= 2 and unit_lower not in KNOWN_UNITS:
        return False

    # Accept known valid units
    if unit_lower in KNOWN_UNITS:
        return True

    # Accept longer units (likely real measurement units)
    if len(unit) >= 3:
        return True

    return False


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

    # 1. Collect all numeric value spans in the sentence
    all_val_spans: list[tuple[int, int]] = []
    for cm in CURRENCY_RE.finditer(text):
        all_val_spans.append(cm.span())
    for pm in PERCENT_RE.finditer(text):
        all_val_spans.append(pm.span())
    for qm in QUANTITY_RE.finditer(text):
        if _is_valid_quantity_unit(_strip_trailing_punctuation(qm.group("unit").strip())):
            all_val_spans.append(qm.span())

    # 2. Extract deterministic temporal spans
    temporal_spans = find_temporal_spans(text)

    last_end = 0
    prev_currency_subject: str | None = None
    prev_currency_scope: str | None = None
    prev_currency_entity: str | None = None

    for currency_match in CURRENCY_RE.finditer(text):
        subject, raw_value = _extract_subject_and_value(text, currency_match)
        local_text = text[last_end : currency_match.start()].strip()
        last_end = currency_match.end()

        # Local temporal context association
        period, qualifier = associate_local_period(
            text, currency_match.start(), currency_match.end(), all_val_spans, temporal_spans
        )

        page_idx = page.text.find(currency_match.group(0))
        page_prefix = page.text[:page_idx] if page_idx != -1 else ""
        scope, entity = extract_scope_and_entity(
            subject=subject,
            local_text=local_text,
            full_prefix=text[: currency_match.start()],
            page_text=page_prefix,
        )

        if prev_currency_subject and not _has_substantive_subject(local_text):
            subject = prev_currency_subject
            if not scope and prev_currency_scope:
                scope = prev_currency_scope
            if not entity and prev_currency_entity:
                entity = prev_currency_entity
        else:
            prev_currency_subject = subject
            prev_currency_scope = scope
            prev_currency_entity = entity

        normalized = _normalize_currency(
            currency_match.group("value"), currency_match.group("scale")
        )
        meta: dict[str, Any] = {
            "currency_symbol": currency_match.group("symbol") or currency_match.group("name")
        }
        if period:
            meta["period"] = period
        if qualifier:
            meta["temporal_qualifier"] = qualifier
        if scope:
            meta["scope"] = scope
        if entity:
            meta["entity"] = entity

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
                metadata=meta,
            )
        )

    last_end = 0
    prev_percent_subject: str | None = None
    prev_percent_scope: str | None = None
    prev_percent_entity: str | None = None

    for percent_match in PERCENT_RE.finditer(text):
        subject, raw_value = _extract_subject_and_value(text, percent_match)
        local_text = text[last_end : percent_match.start()].strip()
        last_end = percent_match.end()

        # Local temporal context association
        period, qualifier = associate_local_period(
            text, percent_match.start(), percent_match.end(), all_val_spans, temporal_spans
        )

        scope, entity = extract_scope_and_entity(
            subject=subject,
            local_text=local_text,
            full_prefix=text[: percent_match.start()],
        )

        if prev_percent_subject and not _has_substantive_subject(local_text):
            subject = prev_percent_subject
            if not scope and prev_percent_scope:
                scope = prev_percent_scope
            if not entity and prev_percent_entity:
                entity = prev_percent_entity
        else:
            prev_percent_subject = subject
            prev_percent_scope = scope
            prev_percent_entity = entity

        normalized = float(_normalize_number(percent_match.group("value")))
        meta: dict[str, Any] = {}
        if period:
            meta["period"] = period
        if qualifier:
            meta["temporal_qualifier"] = qualifier
        if scope:
            meta["scope"] = scope
        if entity:
            meta["entity"] = entity

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
                metadata=meta,
            )
        )

    last_end = 0
    for quantity_match in QUANTITY_RE.finditer(text):
        subject = _strip_trailing_punctuation(quantity_match.group("subject").strip())
        subject = _derive_subject(subject)
        raw_value = quantity_match.group("value")
        unit = _strip_trailing_punctuation(quantity_match.group("unit").strip())

        # Skip quantities with invalid or noisy units
        if not _is_valid_quantity_unit(unit):
            continue

        local_text = text[last_end : quantity_match.start()].strip()
        last_end = quantity_match.end()

        # Local temporal context association
        period, qualifier = associate_local_period(
            text, quantity_match.start(), quantity_match.end(), all_val_spans, temporal_spans
        )

        scope, entity = extract_scope_and_entity(
            subject=subject,
            local_text=local_text,
            full_prefix=text[: quantity_match.start()],
        )

        normalized = _normalize_number(raw_value)
        meta: dict[str, Any] = {}
        if period:
            meta["period"] = period
        if qualifier:
            meta["temporal_qualifier"] = qualifier
        if scope:
            meta["scope"] = scope
        if entity:
            meta["entity"] = entity

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
                metadata=meta,
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
