"""Deterministic cross-fact relationship classification and comparison engine."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .fact import Fact

# Public relationship states as mandated by assignment specification
CORROBORATED = "CORROBORATED"
CONTRADICTED = "CONTRADICTED"
CONTEXTUALLY_RECONCILED = "CONTEXTUALLY_RECONCILED"
UNCERTAIN = "UNCERTAIN"
INCOMPARABLE = "INCOMPARABLE"

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
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


@dataclass(slots=True, frozen=True)
class FactRelationship:
    """Represents the evaluated relationship between two facts."""

    state: str
    fact_a: Fact
    fact_b: Fact
    explanation: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize relationship to a clean dictionary."""
        return {
            "state": self.state,
            "fact_a_id": self.fact_a.fact_id,
            "fact_b_id": self.fact_b.fact_id,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "fact_a": self.fact_a.to_dict(),
            "fact_b": self.fact_b.to_dict(),
            "metadata": dict(self.metadata),
        }


def _tokens(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric terms excluding stopwords."""
    return {
        tok
        for tok in re.findall(r"[A-Za-z0-9%$₹€£.]+", text.casefold())
        if tok and tok not in STOPWORDS
    }


def _extract_years(fact: Fact) -> set[str]:
    """Extract 4-digit calendar years from fact subject, raw value, and evidence."""
    combined = f"{fact.subject} {fact.raw_value} {fact.evidence_text}"
    return {match.group(1) for match in YEAR_RE.finditer(combined)}


def _subjects_compatible(subject_a: str, subject_b: str) -> bool:
    """Determine whether two subject strings refer to compatible entities or metrics."""
    norm_a = subject_a.strip().casefold()
    norm_b = subject_b.strip().casefold()

    if not norm_a or not norm_b:
        return False

    if norm_a == norm_b or norm_a in norm_b or norm_b in norm_a:
        return True

    tokens_a = _tokens(norm_a)
    tokens_b = _tokens(norm_b)
    return bool(tokens_a & tokens_b)


def _units_compatible(unit_a: str | None, unit_b: str | None) -> bool:
    """Check dimensional unit compatibility (e.g. tonnes vs shipments are incomparable)."""
    if unit_a is None and unit_b is None:
        return True
    if unit_a is None or unit_b is None:
        return True

    u_a = unit_a.strip().casefold()
    u_b = unit_b.strip().casefold()

    if u_a == u_b:
        return True

    # Currency aliases
    currencies = {"currency", "usd", "inr", "eur", "gbp", "dollars", "rupees", "$", "₹", "€", "£"}
    if u_a in currencies and u_b in currencies:
        return True

    # Percentage aliases
    percentages = {"percent", "percentage", "%"}
    if u_a in percentages and u_b in percentages:
        return True

    return False


def compare_facts(fact_a: Fact, fact_b: Fact) -> FactRelationship:
    """Compare two facts deterministically and classify their relationship.

    Relationship states:
        - CORROBORATED: Facts report consistent values for the same subject and period.
        - CONTRADICTED: Facts report conflicting values for the same subject and period.
        - CONTEXTUALLY_RECONCILED: Values differ due to explainable temporal or reporting context.
        - INCOMPARABLE: Facts differ in dimension, unit, or entity.
        - UNCERTAIN: Evidence or validation confidence is insufficient.
    """
    # 1. Evidence Grounding Check
    if fact_a.status != "grounded" or fact_b.status != "grounded":
        return FactRelationship(
            state=UNCERTAIN,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=0.5,
            explanation="One or both candidate facts are not validated as grounded.",
        )

    # 2. Dimensional / Fact Type Check
    if fact_a.fact_type != fact_b.fact_type:
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(f"Incomparable fact types: '{fact_a.fact_type}' vs '{fact_b.fact_type}'."),
        )

    # 3. Unit Compatibility Check
    if not _units_compatible(fact_a.unit, fact_b.unit):
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(f"Incompatible measurement units: '{fact_a.unit}' vs '{fact_b.unit}'."),
        )

    # 4. Entity / Subject Compatibility Check
    if not _subjects_compatible(fact_a.subject, fact_b.subject):
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(
                f"Subjects refer to distinct entities or metrics: "
                f"'{fact_a.subject}' vs '{fact_b.subject}'."
            ),
        )

    # 5. Temporal / Period Context Check
    years_a = _extract_years(fact_a)
    years_b = _extract_years(fact_b)
    has_years = bool(years_a and years_b)
    same_period = has_years and bool(years_a & years_b)
    different_period = has_years and not (years_a & years_b)

    # 6. Value Comparison
    val_a = fact_a.normalized_value
    val_b = fact_b.normalized_value

    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        num_a = float(val_a)
        num_b = float(val_b)
        values_match = math.isclose(num_a, num_b, rel_tol=1e-3, abs_tol=1e-3)

        if values_match:
            period_str = f" in {','.join(sorted(years_a))}" if years_a else ""
            return FactRelationship(
                state=CORROBORATED,
                fact_a=fact_a,
                fact_b=fact_b,
                confidence=1.0,
                explanation=(
                    f"Facts corroborate with matching normalized value {num_a}{period_str}."
                ),
            )

        # Values differ: Check if temporal context explains the difference
        if different_period:
            p_a = ",".join(sorted(years_a))
            p_b = ",".join(sorted(years_b))
            return FactRelationship(
                state=CONTEXTUALLY_RECONCILED,
                fact_a=fact_a,
                fact_b=fact_b,
                confidence=1.0,
                explanation=(
                    f"Values differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
                    f"due to different reporting periods ({p_a} vs {p_b})."
                ),
            )

        if same_period:
            p_str = ",".join(sorted(years_a))
            return FactRelationship(
                state=CONTRADICTED,
                fact_a=fact_a,
                fact_b=fact_b,
                confidence=1.0,
                explanation=(
                    f"Contradicting values ({fact_a.raw_value} vs {fact_b.raw_value}) "
                    f"reported for the same period ({p_str})."
                ),
            )

        # Values differ without explicit period metadata
        return FactRelationship(
            state=UNCERTAIN,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=0.7,
            explanation=(
                f"Values differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
                f"but reporting periods cannot be confirmed."
            ),
        )

    # Fallback for non-numeric (string / date) representations
    if str(val_a).strip().casefold() == str(val_b).strip().casefold():
        return FactRelationship(
            state=CORROBORATED,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"Facts corroborate with identical representation '{val_a}'.",
        )

    if different_period:
        p_a = ",".join(sorted(years_a))
        p_b = ",".join(sorted(years_b))
        return FactRelationship(
            state=CONTEXTUALLY_RECONCILED,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(
                f"Representations differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
                f"across different periods ({p_a} vs {p_b})."
            ),
        )

    return FactRelationship(
        state=CONTRADICTED,
        fact_a=fact_a,
        fact_b=fact_b,
        confidence=1.0,
        explanation=f"Representations contradict: '{fact_a.raw_value}' vs '{fact_b.raw_value}'.",
    )
