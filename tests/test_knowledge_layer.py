"""Tests for the in-memory knowledge layer and deterministic query ranking."""

from __future__ import annotations

from superjoin_fact_knowledge import Fact, KnowledgeBase, query_facts


def _fact(
    *,
    fact_id: str,
    subject: str,
    fact_type: str,
    raw_value: str,
    normalized_value: float | int | str | None,
    unit: str | None,
    page_number: int,
    status: str = "grounded",
    document_name: str = "sample.pdf",
    evidence_text: str = "",
) -> Fact:
    return Fact(
        fact_id=fact_id,
        subject=subject,
        fact_type=fact_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=unit,
        metric=fact_type,
        evidence_text=evidence_text or f"{subject} {raw_value}".strip(),
        page_number=page_number,
        document_id="doc-1",
        document_name=document_name,
        confidence=1.0,
        status=status,
        metadata={},
    )


def test_adding_a_fact_returns_an_immutable_copy() -> None:
    """The knowledge base should defensively copy added facts."""
    fact = _fact(
        fact_id="fact-1",
        subject="Revenue",
        fact_type="currency",
        raw_value="$12.4 million",
        normalized_value=12400000.0,
        unit="currency",
        page_number=7,
        evidence_text="Revenue increased to $12.4 million in FY2025.",
    )

    knowledge_base = KnowledgeBase.empty().add_fact(fact)

    fact.metadata["touched"] = True

    assert knowledge_base.facts[0].fact_id == "fact-1"
    assert knowledge_base.facts[0].metadata == {}


def test_adding_multiple_facts_preserves_order() -> None:
    """Adding multiple facts should keep all facts in deterministic insertion order."""
    facts = [
        _fact(
            fact_id="fact-1",
            subject="Revenue",
            fact_type="currency",
            raw_value="$12.4 million",
            normalized_value=12400000.0,
            unit="currency",
            page_number=7,
        ),
        _fact(
            fact_id="fact-2",
            subject="Operating margin",
            fact_type="percentage",
            raw_value="18.2%",
            normalized_value=18.2,
            unit="percent",
            page_number=8,
        ),
    ]

    knowledge_base = KnowledgeBase.empty().add_facts(facts)

    assert [fact.fact_id for fact in knowledge_base.facts] == ["fact-1", "fact-2"]


def test_query_matches_by_subject() -> None:
    """Subject terms should retrieve the matching fact."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Revenue",
                fact_type="currency",
                raw_value="$12.4 million",
                normalized_value=12400000.0,
                unit="currency",
                page_number=7,
                evidence_text="Revenue increased to $12.4 million in FY2025.",
            )
        ]
    )

    result = knowledge_base.query("revenue")

    assert result.status == "answer_found"
    assert result.matches[0].fact.subject == "Revenue"
    assert result.answer_text == "Revenue was $12.4 million."


def test_query_matches_by_year_and_prefers_the_exact_year() -> None:
    """Year-specific queries should rank the matching year ahead of other candidates."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Revenue",
                fact_type="currency",
                raw_value="$10 million",
                normalized_value=10000000.0,
                unit="currency",
                page_number=7,
                evidence_text="Revenue was $10 million in FY2024.",
            ),
            _fact(
                fact_id="fact-2",
                subject="Revenue",
                fact_type="currency",
                raw_value="$12 million",
                normalized_value=12000000.0,
                unit="currency",
                page_number=8,
                evidence_text="Revenue was $12 million in FY2025.",
            ),
        ]
    )

    result = knowledge_base.query("revenue in 2025")

    assert [match.fact.fact_id for match in result.matches[:2]] == ["fact-2", "fact-1"]
    assert result.answer_text == "Revenue was $12 million."


def test_query_matches_by_value_context() -> None:
    """Shared value context should retrieve the most relevant fact."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Revenue",
                fact_type="currency",
                raw_value="$12.4 million",
                normalized_value=12400000.0,
                unit="currency",
                page_number=7,
                evidence_text="Revenue increased to $12.4 million in FY2025.",
            ),
            _fact(
                fact_id="fact-2",
                subject="Employees",
                fact_type="quantity",
                raw_value="1,250",
                normalized_value=1250.0,
                unit="employees",
                page_number=2,
                evidence_text="Employees totalled 1,250.",
            ),
        ]
    )

    result = knowledge_base.query("million")

    assert result.matches[0].fact.fact_id == "fact-1"
    assert result.matches[0].score > result.matches[1].score


def test_query_matches_by_fact_type() -> None:
    """Fact-type keywords should retrieve the matching percentage fact."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Operating margin",
                fact_type="percentage",
                raw_value="18.2%",
                normalized_value=18.2,
                unit="percent",
                page_number=8,
                evidence_text="Operating margin was 18.2% in FY2025.",
            )
        ]
    )

    result = knowledge_base.query("percentage")

    assert result.matches[0].fact.fact_type == "percentage"
    assert result.answer_text == "Operating margin was 18.2%."


def test_deterministic_ranking_keeps_ties_stable() -> None:
    """Facts with the same score should retain insertion order."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Revenue",
                fact_type="currency",
                raw_value="$10 million",
                normalized_value=10000000.0,
                unit="currency",
                page_number=7,
                evidence_text="Revenue was $10 million in FY2024.",
            ),
            _fact(
                fact_id="fact-2",
                subject="Revenue",
                fact_type="currency",
                raw_value="$12 million",
                normalized_value=12000000.0,
                unit="currency",
                page_number=8,
                evidence_text="Revenue was $12 million in FY2025.",
            ),
        ]
    )

    result = knowledge_base.query("revenue")

    assert result.status == "ambiguous"
    assert [match.fact.fact_id for match in result.matches[:2]] == ["fact-1", "fact-2"]
    assert result.answer_text is None


def test_needs_review_facts_are_not_grounded_by_default() -> None:
    """Review-only facts should not be promoted to authoritative answers."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Revenue",
                fact_type="currency",
                raw_value="$12.4 million",
                normalized_value=12400000.0,
                unit="currency",
                page_number=7,
                status="needs_review",
                evidence_text="Revenue increased to $12.4 million in FY2025.",
            )
        ]
    )

    result = knowledge_base.query("revenue")

    assert result.status == "no_grounded_answer"
    assert result.matches == ()
    assert result.review_matches[0].fact.status == "needs_review"
    assert result.answer_text is None


def test_grounded_results_preserve_provenance_and_evidence() -> None:
    """Grounded results should expose page and evidence text without losing traceability."""
    knowledge_base = KnowledgeBase.from_facts(
        [
            _fact(
                fact_id="fact-1",
                subject="Operating margin",
                fact_type="percentage",
                raw_value="18.2%",
                normalized_value=18.2,
                unit="percent",
                page_number=8,
                evidence_text="Operating margin was 18.2% in FY2025.",
            )
        ]
    )

    result = query_facts(knowledge_base, "operating margin")

    assert result.matches[0].fact.page_number == 8
    assert result.matches[0].fact.evidence_text == "Operating margin was 18.2% in FY2025."
    assert result.matches[0].fact.status == "grounded"


def test_no_match_queries_return_an_explicit_unanswered_result() -> None:
    """Queries without a relevant fact should return an explicit unanswered result."""
    knowledge_base = KnowledgeBase.empty()

    result = knowledge_base.query("operating margin")

    assert result.status == "no_grounded_answer"
    assert result.matches == ()
    assert result.review_matches == ()
    assert result.answer_text is None


def test_unexpected_query_text_does_not_crash() -> None:
    """Non-semantic query text should be handled safely."""
    knowledge_base = KnowledgeBase.empty()

    result = knowledge_base.query("@@@ ??? /\\")

    assert result.status == "no_grounded_answer"
    assert result.matches == ()
