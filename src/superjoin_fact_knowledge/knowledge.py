"""In-memory knowledge base and deterministic query helpers for grounded facts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from .fact import Fact

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

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


@dataclass(slots=True, frozen=True)
class QueryMatch:
    """A ranked candidate fact returned from a knowledge query."""

    fact: Fact
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class QueryResult:
    """Structured output for a deterministic knowledge query."""

    query: str
    status: str
    matches: tuple[QueryMatch, ...]
    review_matches: tuple[QueryMatch, ...] = ()
    answer_text: str | None = None
    explanation: str = ""


def _clone_fact(fact: Fact) -> Fact:
    """Create a defensive copy so the knowledge base cannot be mutated indirectly."""
    return replace(fact, metadata=dict(fact.metadata))


def _normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase text for deterministic matching."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _tokens(text: str) -> set[str]:
    """Tokenize text into comparable lowercase terms."""
    return {
        token
        for token in re.findall(r"[A-Za-z0-9%$₹€£.]+", text.casefold())
        if token and token not in STOPWORDS
    }


def _years_from_text(text: str) -> set[str]:
    """Extract calendar-style years from a piece of text."""
    return {match.group(1) for match in YEAR_RE.finditer(text)}


def _fact_search_text(fact: Fact) -> str:
    """Build a compact search string from the stable fact fields."""
    metadata_values = " ".join(str(value) for value in fact.metadata.values() if value is not None)
    parts = [
        fact.subject,
        fact.fact_type,
        fact.metric or "",
        fact.unit or "",
        fact.raw_value,
        fact.evidence_text,
        metadata_values,
    ]
    return " ".join(part for part in parts if part)


def _fact_years(fact: Fact) -> set[str]:
    """Collect all year-like values represented by a fact."""
    return _years_from_text(_fact_search_text(fact))


def _format_answer(fact: Fact) -> str:
    """Turn a selected fact into a short grounded answer string."""
    subject = fact.subject.strip()
    subject_text = subject[:1].upper() + subject[1:] if subject else "The fact"

    if fact.fact_type == "quantity" and fact.unit:
        return f"{subject_text} was {fact.raw_value} {fact.unit}."

    if fact.fact_type == "date":
        return f"{subject_text} was {fact.raw_value}."

    return f"{subject_text} was {fact.raw_value}."


def _score_fact(fact: Fact, query: str) -> tuple[float, tuple[str, ...]]:
    """Compute a transparent relevance score for a fact and query."""
    normalized_query = _normalize_text(query)
    query_tokens = _tokens(query)
    fact_tokens = _tokens(_fact_search_text(fact))
    reasons: list[str] = []
    score = 0.0

    if not normalized_query:
        return score, tuple(reasons)

    subject = _normalize_text(fact.subject)
    if subject:
        if subject == normalized_query:
            score += 10.0
            reasons.append("subject_exact_match")
        elif subject in normalized_query or normalized_query in subject:
            score += 6.0
            reasons.append("subject_phrase_match")

    subject_tokens = _tokens(fact.subject)
    shared_subject_tokens = query_tokens & subject_tokens
    if shared_subject_tokens:
        score += 3.0 * len(shared_subject_tokens)
        reasons.append(f"subject_token_overlap:{','.join(sorted(shared_subject_tokens))}")

    shared_tokens = query_tokens & fact_tokens
    if shared_tokens:
        score += 1.5 * len(shared_tokens)
        reasons.append(f"context_overlap:{','.join(sorted(shared_tokens))}")

    query_years = _years_from_text(query)
    fact_years = _fact_years(fact)
    if query_years and fact_years:
        shared_years = query_years & fact_years
        if shared_years:
            score += 8.0 + 2.0 * (len(shared_years) - 1)
            reasons.append(f"year_match:{','.join(sorted(shared_years))}")
        else:
            reasons.append("year_mismatch")

    fact_type_tokens = {fact.fact_type.casefold()}
    if fact.fact_type == "percentage":
        fact_type_tokens.update({"percent", "percentage", "margin", "rate"})
    elif fact.fact_type == "currency":
        fact_type_tokens.update({"currency", "monetary", "amount", "value"})
    elif fact.fact_type == "quantity":
        fact_type_tokens.update({"quantity", "count", "total", "number"})
    elif fact.fact_type == "date":
        fact_type_tokens.update({"date", "year", "quarter", "period", "fiscal"})

    fact_type_shared = query_tokens & fact_type_tokens
    if fact_type_shared:
        score += 4.0
        reasons.append(f"fact_type_match:{','.join(sorted(fact_type_shared))}")

    unit_tokens = _tokens(fact.unit or "")
    unit_shared = query_tokens & unit_tokens
    if unit_shared:
        score += 2.0 * len(unit_shared)
        reasons.append(f"unit_match:{','.join(sorted(unit_shared))}")

    if fact.status == "grounded":
        score += 0.5
        reasons.append("grounded_fact")
    elif fact.status == "needs_review":
        reasons.append("needs_review_fact")

    return score, tuple(reasons)


def _rank_facts(facts: Iterable[Fact], query: str) -> list[QueryMatch]:
    """Score and sort facts deterministically."""
    ranked: list[tuple[float, int, QueryMatch]] = []

    for index, fact in enumerate(facts):
        score, reasons = _score_fact(fact, query)
        ranked.append((score, index, QueryMatch(fact=fact, score=score, reasons=reasons)))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2].fact.fact_id))
    return [match for _, _, match in ranked]


def _best_grounded_match(matches: tuple[QueryMatch, ...]) -> QueryMatch | None:
    """Return the top grounded match when it is unambiguous."""
    if not matches:
        return None
    if len(matches) == 1 and matches[0].score > 0:
        return matches[0]
    if matches[0].score > 0 and matches[0].score > matches[1].score:
        return matches[0]
    return None


@dataclass(slots=True, frozen=True)
class KnowledgeBase:
    """Immutable in-memory store of validated facts."""

    facts: tuple[Fact, ...] = ()

    @classmethod
    def empty(cls) -> KnowledgeBase:
        """Create an empty knowledge base."""
        return cls()

    @classmethod
    def from_facts(cls, facts: Iterable[Fact]) -> KnowledgeBase:
        """Create a knowledge base from an iterable of facts."""
        return cls(tuple(_clone_fact(fact) for fact in facts))

    def add_fact(self, fact: Fact) -> KnowledgeBase:
        """Return a new knowledge base with one additional fact."""
        return KnowledgeBase(self.facts + (_clone_fact(fact),))

    def add_facts(self, facts: Iterable[Fact]) -> KnowledgeBase:
        """Return a new knowledge base with multiple additional facts."""
        return KnowledgeBase(self.facts + tuple(_clone_fact(fact) for fact in facts))

    def grounded_facts(self) -> tuple[Fact, ...]:
        """Return the grounded facts currently stored in the knowledge base."""
        return tuple(fact for fact in self.facts if fact.status == "grounded")

    def review_facts(self) -> tuple[Fact, ...]:
        """Return the facts currently marked for review."""
        return tuple(fact for fact in self.facts if fact.status != "grounded")

    def query(
        self,
        query: str,
        *,
        limit: int = 5,
        include_needs_review: bool = False,
    ) -> QueryResult:
        """Query the knowledge base using deterministic, explainable matching."""
        return query_facts(
            self,
            query,
            limit=limit,
            include_needs_review=include_needs_review,
        )


def query_facts(
    knowledge_base: KnowledgeBase,
    query: str,
    *,
    limit: int = 5,
    include_needs_review: bool = False,
) -> QueryResult:
    """Query grounded facts and preserve their provenance in a structured result."""
    grounded_candidates = _rank_facts(knowledge_base.grounded_facts(), query)
    review_candidates = _rank_facts(knowledge_base.review_facts(), query)

    grounded_matches = tuple(grounded_candidates[:limit])
    review_matches = tuple(review_candidates[:limit]) if review_candidates else ()

    selected_match = _best_grounded_match(grounded_matches)

    if grounded_matches and grounded_matches[0].score > 0:
        top_match = grounded_matches[0]
        if len(grounded_matches) > 1 and grounded_matches[1].score == top_match.score:
            return QueryResult(
                query=query,
                status="ambiguous",
                matches=grounded_matches,
                review_matches=review_matches,
                answer_text=None,
                explanation="; ".join(top_match.reasons),
            )

        if selected_match is not None:
            return QueryResult(
                query=query,
                status="answer_found",
                matches=grounded_matches,
                review_matches=review_matches,
                answer_text=_format_answer(selected_match.fact),
                explanation="; ".join(selected_match.reasons),
            )

    if include_needs_review and review_matches:
        top_review_match = review_matches[0]
        return QueryResult(
            query=query,
            status="review_only",
            matches=grounded_matches,
            review_matches=review_matches,
            answer_text=None,
            explanation="; ".join(top_review_match.reasons),
        )

    return QueryResult(
        query=query,
        status="no_grounded_answer",
        matches=grounded_matches,
        review_matches=review_matches,
        answer_text=None,
        explanation="",
    )


__all__ = [
    "KnowledgeBase",
    "QueryMatch",
    "QueryResult",
    "query_facts",
]
