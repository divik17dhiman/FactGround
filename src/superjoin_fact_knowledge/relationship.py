"""Deterministic cross-fact relationship classification and comparison engine."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .fact import Fact, extract_entity_from_subject, extract_period

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

GENERIC_SUBJECT_WORDS = {
    "aggregating",
    "shares",
    "equity",
    "share",
    "value",
    "total",
    "amount",
    "number",
    "size",
    "details",
    "type",
    "million",
    "billion",
    "thousand",
    "crore",
    "lakh",
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


def _get_period(fact: Fact) -> str | None:
    """Retrieve or deterministically extract a reliable reporting period for the fact."""
    if fact.period:
        return fact.period
    combined = f"{fact.subject} {fact.raw_value} {fact.evidence_text}"
    return extract_period(combined)


def _periods_match(p_a: str, p_b: str) -> bool:
    """Check whether two reporting period strings represent the same period."""
    if p_a.casefold() == p_b.casefold():
        return True
    norm_a = p_a.upper().replace("FY", "").strip()
    norm_b = p_b.upper().replace("FY", "").strip()
    return norm_a == norm_b


def _get_scope(fact: Fact) -> str | None:
    """Get the scope/context of a fact from metadata or subject text."""
    if fact.scope:
        return fact.scope
    s_lower = fact.subject.lower()
    if "fresh issue" in s_lower:
        return "Fresh Issue"
    if "offer for sale" in s_lower:
        return "Offer for Sale"
    if "total offer" in s_lower or "offer of equity shares" in s_lower:
        return "Total Offer"
    if "face value" in s_lower:
        return "Face Value"
    return None


def _get_entity(fact: Fact) -> str | None:
    """Get the entity of a fact from metadata or subject text."""
    if fact.entity:
        return fact.entity
    return extract_entity_from_subject(fact.subject)


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
    overlap = tokens_a & tokens_b
    if not overlap:
        return False

    meaningful_overlap = overlap - GENERIC_SUBJECT_WORDS
    return bool(meaningful_overlap)


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
        - INCOMPARABLE: Facts differ in dimension, unit, entity, or scope.
        - UNCERTAIN: Validation is insufficient, or period context is missing.
    """
    # Facts must be grounded in verified evidence before establishing authoritative relationships
    if fact_a.status != "grounded" or fact_b.status != "grounded":
        return FactRelationship(
            state=UNCERTAIN,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=0.5,
            explanation="One or both candidate facts are not validated as grounded.",
        )

    # Dimensional compatibility gate: cannot compare disparate fact types
    if fact_a.fact_type != fact_b.fact_type:
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"Incomparable fact types: '{fact_a.fact_type}' vs '{fact_b.fact_type}'.",
        )

    # Unit compatibility gate
    if not _units_compatible(fact_a.unit, fact_b.unit):
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"Incompatible measurement units: '{fact_a.unit}' vs '{fact_b.unit}'.",
        )

    # Entity boundary gate: distinct named entities must not be conflated
    entity_a = _get_entity(fact_a)
    entity_b = _get_entity(fact_b)
    if entity_a and entity_b and entity_a.casefold() != entity_b.casefold():
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"Facts refer to different entities: '{entity_a}' vs '{entity_b}'.",
        )

    # Scope boundary gate: distinct transactional components must not contradict
    scope_a = _get_scope(fact_a)
    scope_b = _get_scope(fact_b)
    if scope_a and scope_b and scope_a.casefold() != scope_b.casefold():
        return FactRelationship(
            state=INCOMPARABLE,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"The values refer to different scopes: '{scope_a}' and '{scope_b}'.",
        )

    # Subject alignment gate: metrics must refer to compatible domain concepts
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

    # Temporal context evaluation
    period_a = _get_period(fact_a)
    period_b = _get_period(fact_b)
    has_periods = bool(period_a and period_b)
    same_period = has_periods and _periods_match(period_a, period_b)
    different_period = has_periods and not same_period

    # Numerical value comparison and relationship classification
    val_a = fact_a.normalized_value
    val_b = fact_b.normalized_value

    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        num_a = float(val_a)
        num_b = float(val_b)
        values_match = math.isclose(num_a, num_b, rel_tol=1e-3, abs_tol=1e-3)

        if values_match:
            period_str = f" in {period_a}" if period_a else ""
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
            return FactRelationship(
                state=CONTEXTUALLY_RECONCILED,
                fact_a=fact_a,
                fact_b=fact_b,
                confidence=1.0,
                explanation=(
                    f"Values differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
                    f"due to different reporting periods ({period_a} vs {period_b})."
                ),
            )

        if same_period:
            return FactRelationship(
                state=CONTRADICTED,
                fact_a=fact_a,
                fact_b=fact_b,
                confidence=1.0,
                explanation=(
                    f"Contradicting values ({fact_a.raw_value} vs {fact_b.raw_value}) "
                    f"reported for the same period ({period_a})."
                ),
            )

        # Values differ without confirmed reporting periods
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
        period_str = f" in {period_a}" if period_a else ""
        return FactRelationship(
            state=CORROBORATED,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=f"Facts corroborate with identical representation '{val_a}'{period_str}.",
        )

    if different_period:
        return FactRelationship(
            state=CONTEXTUALLY_RECONCILED,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(
                f"Representations differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
                f"across different periods ({period_a} vs {period_b})."
            ),
        )

    if same_period:
        return FactRelationship(
            state=CONTRADICTED,
            fact_a=fact_a,
            fact_b=fact_b,
            confidence=1.0,
            explanation=(
                f"Representations contradict: '{fact_a.raw_value}' vs '{fact_b.raw_value}' "
                f"reported for the same period ({period_a})."
            ),
        )

    return FactRelationship(
        state=UNCERTAIN,
        fact_a=fact_a,
        fact_b=fact_b,
        confidence=0.7,
        explanation=(
            f"Representations differ ({fact_a.raw_value} vs {fact_b.raw_value}) "
            f"but reporting periods cannot be confirmed."
        ),
    )
