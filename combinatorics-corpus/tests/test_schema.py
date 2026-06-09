"""Schema validation rejects bad records, accepts good ones."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from corpus.schema import (
    Paper,
    RelevanceBand,
    SourceStatus,
    Statement,
)


def test_paper_strips_arxiv_prefix_and_version():
    p = Paper(
        arxiv_id="arXiv:2401.00123v3",
        version=3,
        title="t", abstract="a",
        primary_category="math.CO", all_categories=["math.CO"],
        is_cross_listed_co=False, authors=["A"],
        submitted=datetime.now(timezone.utc), updated=datetime.now(timezone.utc),
        source_status=SourceStatus.PENDING,
        harvest_run_id="r1",
    )
    # The validator should normalize to bare 2401.00123.
    assert p.arxiv_id == "2401.00123"


def test_paper_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Paper(
            arxiv_id="2401.00001", version=1, title="t", abstract="a",
            primary_category="math.CO", all_categories=["math.CO"],
            is_cross_listed_co=False, authors=["A"],
            submitted=datetime.now(timezone.utc), updated=datetime.now(timezone.utc),
            source_status=SourceStatus.PENDING,
            harvest_run_id="r1",
            sneaky_field="nope",
        )


def test_paper_rejects_negative_version():
    with pytest.raises(ValidationError):
        Paper(
            arxiv_id="2401.00001", version=0, title="t", abstract="a",
            primary_category="math.CO", all_categories=["math.CO"],
            is_cross_listed_co=False, authors=["A"],
            submitted=datetime.now(timezone.utc), updated=datetime.now(timezone.utc),
            source_status=SourceStatus.PENDING,
            harvest_run_id="r1",
        )


def test_statement_relevance_score_must_be_in_unit_interval():
    base = dict(
        id="x", arxiv_id="p1", version=1, env_type="theorem",
        label=None, raw_latex="r", clean_text="c", citations=[],
        char_len=1, balanced=True,
        relevance_band=RelevanceBand.LOW, parser_version="t",
        extracted_at=datetime.now(timezone.utc),
    )
    Statement(relevance_score=0.0, **base)
    Statement(relevance_score=1.0, **base)
    with pytest.raises(ValidationError):
        Statement(relevance_score=1.5, **base)
    with pytest.raises(ValidationError):
        Statement(relevance_score=-0.1, **base)
