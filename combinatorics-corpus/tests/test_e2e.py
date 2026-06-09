"""End-to-end: extract -> dedup -> qc on a synthetic corpus of fixture papers.

We bypass the harvest/fetch HTTP stages (no network in tests) by placing
.tex fixtures directly into the cache and registering matching Paper rows.
"""
from datetime import datetime, timezone

from corpus.classify import RelevanceClassifier
from corpus.dedup import cluster_statements
from corpus.extract import extract_from_tex
from corpus.fetch_source import load_tex_for_paper
from corpus.metrics import MetricsRecorder, compute_yield_distribution
from corpus.qc import export_audit_sample, run_gates, write_datasheet
from corpus.schema import RelevanceBand


def _run_extract_pass(cfg, store, run_id):
    classifier = RelevanceClassifier(cfg)
    rows = list(store.iter_papers(source_status="OK"))
    n_stmts = 0
    n_rejects = 0
    for row in rows:
        tex = load_tex_for_paper(cfg, row["arxiv_id"], row["version"])
        assert tex is not None
        stmts, failures = extract_from_tex(
            row["arxiv_id"], row["version"], tex,
            default_env_names=cfg["extract"]["default_env_names"],
            macro_expansion_max_depth=cfg["extract"]["macro_expansion_max_depth"],
            parser_version=cfg["run"]["parser_version"],
            extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        for reason, count in failures.items():
            for _ in range(count):
                store.reject(run_id=run_id, stage="extract", reason=reason,
                             arxiv_id=row["arxiv_id"], version=row["version"])
                n_rejects += 1
        ctx = classifier.context_score(row["abstract"])
        for s in stmts:
            rel = classifier.score_text(s.clean_text, context_terms=ctx)
            s.relevance_score = rel.score
            s.relevance_band = rel.band
            store.insert_statement(s)
            n_stmts += 1
    return n_stmts, n_rejects


def test_pipeline_runs_endtoend_on_fixtures(tmp_cfg, store, place_paper, tmp_path):
    # Two identical clean papers (so dedup finds an exact pair),
    # one custom-env paper, one macro-heavy paper, one malformed paper.
    place_paper("2401.00001", 1, "clean.tex",
                submitted=datetime(2024, 1, 1, tzinfo=timezone.utc))
    place_paper("2401.00002", 1, "clean.tex",
                submitted=datetime(2024, 2, 1, tzinfo=timezone.utc))
    place_paper("2401.00003", 1, "custom_env.tex")
    place_paper("2401.00004", 1, "macro_heavy.tex")
    place_paper("2401.00005", 1, "malformed.tex")

    run_id = "test-e2e"
    rec = MetricsRecorder(run_id=run_id, config_hash="testhash", seed=tmp_cfg["run"]["seed"])
    n_stmts, n_rejects = _run_extract_pass(tmp_cfg, store, run_id)
    assert n_stmts > 0, "extract pass produced no statements at all"
    assert n_rejects >= 1, "malformed fixture should have produced at least one reject"

    # Dedup must cluster the two clean copies into one cluster.
    dres = cluster_statements(tmp_cfg, store)
    assert dres.n_statements == n_stmts
    # Among canonical statements: each cluster contributes exactly one.
    n_canonical = store.conn.execute(
        "SELECT COUNT(*) FROM statements WHERE is_canonical=1"
    ).fetchone()[0]
    assert n_canonical == dres.n_clusters

    rec.add_statements(n_stmts)
    rec.add_rejections(n_rejects)
    rec.add_papers_harvested(5)
    rec.add_papers_with_source(5)
    rec.set_yield_distribution(compute_yield_distribution(store))
    rec.set_failure_counts(store.failure_counts(run_id))
    rec.finish(store)

    gates = run_gates(tmp_cfg, store, run_id)
    by_name = {g.name: g for g in gates}
    # Source coverage is 5/5 = 1.0 (we placed source for every paper).
    assert by_name["source_coverage"].value == 1.0
    # Balance rate >= our 0.5 lenient threshold — most blocks balanced even with the malformed file.
    assert by_name["balance_rate"].status == "PASS"

    # Audit sample must exist and be deterministic.
    sample = export_audit_sample(tmp_cfg, store, run_id)
    assert sample.exists()
    n_lines = sum(1 for _ in sample.open())
    assert 0 < n_lines <= tmp_cfg["qc"]["audit_sample_size"]

    # Datasheet must materialize and reference the run identity.
    sheet = write_datasheet(tmp_cfg, store, run_id, gates)
    body = sheet.read_text()
    assert run_id in body
    assert "testhash" in body
    assert "Counts" in body and "Yield distribution" in body and "QC gates" in body


def test_pipeline_is_deterministic(tmp_cfg, place_paper, tmp_path, store):
    """Same fixtures + same seed must produce the same audit sample row order."""
    place_paper("2401.00001", 1, "clean.tex")
    place_paper("2401.00002", 1, "custom_env.tex")
    run_id = "det-run"
    _run_extract_pass(tmp_cfg, store, run_id)
    s1 = export_audit_sample(tmp_cfg, store, run_id)
    contents_a = s1.read_text()
    # Re-export.
    s2 = export_audit_sample(tmp_cfg, store, run_id)
    contents_b = s2.read_text()
    assert contents_a == contents_b
