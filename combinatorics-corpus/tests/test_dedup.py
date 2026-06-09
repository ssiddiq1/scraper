"""Exact + near-duplicate clustering correctness."""
from datetime import datetime, timezone

from corpus.dedup import cluster_statements, normalize, shingles
from corpus.schema import RelevanceBand, Statement


def _stmt(sid: str, text: str, *, arxiv_id: str = "p1", version: int = 1) -> Statement:
    return Statement(
        id=sid, arxiv_id=arxiv_id, version=version, env_type="theorem",
        label=None, raw_latex=text, clean_text=text, citations=[],
        char_len=len(text), balanced=True, relevance_score=0.5,
        relevance_band=RelevanceBand.MEDIUM, parser_version="t",
        extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_normalize_lowercases_and_collapses_whitespace():
    assert normalize("  Hello   World  ") == "hello world"


def test_shingles_pad_short_input():
    s = shingles("a b", 3)
    # 2 words, k=3 → pad to 3 → 1 shingle.
    assert s == ["a b <pad>"]


def test_exact_duplicate_clusters_together(store, tmp_cfg, place_paper):
    place_paper("p1", 1, "clean.tex")
    place_paper("p2", 1, "clean.tex", submitted=datetime(2024, 2, 1, tzinfo=timezone.utc))
    # Manually insert two identical statements pointing at p1, p2.
    text = "every graph on n vertices has chromatic number at most maximum degree plus one"
    store.insert_statement(_stmt("s1", text, arxiv_id="p1"))
    store.insert_statement(_stmt("s2", text, arxiv_id="p2"))

    res = cluster_statements(tmp_cfg, store)
    assert res.n_statements == 2
    assert res.n_clusters == 1
    assert res.n_canonical == 1
    # Earliest submitted = p1 → s1 is canonical.
    row = store.conn.execute("SELECT id, is_canonical FROM statements ORDER BY id").fetchall()
    by_id = {r["id"]: r["is_canonical"] for r in row}
    assert by_id["s1"] == 1
    assert by_id["s2"] == 0


def test_near_duplicate_clusters_together(store, tmp_cfg, place_paper):
    place_paper("p1", 1, "clean.tex")
    place_paper("p2", 1, "clean.tex", submitted=datetime(2024, 2, 1, tzinfo=timezone.utc))
    # Lower jaccard threshold so the variants land in the same near-dup bucket.
    # Bump perm count: LSH banding at perm=64 has too-wide bands for low thresholds.
    tmp_cfg["dedup"]["jaccard_threshold"] = 0.3
    tmp_cfg["dedup"]["minhash_perm"] = 128
    base = "the chromatic number of any graph on n vertices is at most maximum degree plus one"
    variant = "the chromatic number of any graph on n vertices is bounded by maximum degree plus one"
    store.insert_statement(_stmt("s1", base, arxiv_id="p1"))
    store.insert_statement(_stmt("s2", variant, arxiv_id="p2"))

    res = cluster_statements(tmp_cfg, store)
    assert res.n_clusters == 1
    assert res.n_canonical == 1


def test_distinct_statements_not_clustered(store, tmp_cfg, place_paper):
    place_paper("p1", 1, "clean.tex")
    place_paper("p2", 1, "clean.tex", submitted=datetime(2024, 2, 1, tzinfo=timezone.utc))
    store.insert_statement(_stmt("s1", "every bipartite graph has no odd cycles", arxiv_id="p1"))
    store.insert_statement(_stmt("s2", "the number of subsets of size k is binomial n k", arxiv_id="p2"))
    res = cluster_statements(tmp_cfg, store)
    assert res.n_clusters == 2
    # Both their own canonical.
    canonicals = store.conn.execute("SELECT COUNT(*) FROM statements WHERE is_canonical=1").fetchone()[0]
    assert canonicals == 2
