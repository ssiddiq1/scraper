"""Relevance classifier behavior: lexicon hits, bands, context boost."""
from corpus.classify import RelevanceClassifier
from corpus.schema import RelevanceBand


def test_empty_text_is_low(tmp_cfg):
    c = RelevanceClassifier(tmp_cfg)
    r = c.score_text("")
    assert r.score == 0.0
    assert r.band == RelevanceBand.LOW


def test_combinatorial_text_scores_above_low(tmp_cfg):
    c = RelevanceClassifier(tmp_cfg)
    text = "the chromatic number of a bipartite graph is two; consider a tree T."
    r = c.score_text(text)
    assert r.score > 0.0
    assert r.band in {RelevanceBand.MEDIUM, RelevanceBand.HIGH}
    # Confirm the hits dict reflects real terms.
    assert "graph" in r.hits or "chromatic" in r.hits


def test_unrelated_text_scores_low(tmp_cfg):
    c = RelevanceClassifier(tmp_cfg)
    r = c.score_text("the cat sat on the mat watching television.")
    assert r.band == RelevanceBand.LOW


def test_context_terms_boost_score(tmp_cfg):
    c = RelevanceClassifier(tmp_cfg)
    text = "one graph result"
    no_ctx = c.score_text(text, context_terms=0).score
    with_ctx = c.score_text(text, context_terms=4).score
    assert with_ctx > no_ctx
