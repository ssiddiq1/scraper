"""Shared pytest fixtures: tiny config + temp store + tex fixture loader."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

# Make src/ importable for the test session.
import sys
_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
sys.path.insert(0, str(_ROOT / "src"))

from corpus.store import Store  # noqa: E402


FIXTURE_DIR = _TESTS / "fixtures"


@pytest.fixture
def fixture_path():
    def _p(name: str) -> Path:
        return FIXTURE_DIR / name
    return _p


@pytest.fixture
def fixture_text(fixture_path):
    def _t(name: str) -> str:
        return fixture_path(name).read_text(encoding="utf-8")
    return _t


@pytest.fixture
def tmp_cfg(tmp_path):
    cfg = {
        "run": {"run_id": "test-run", "seed": 1234, "parser_version": "0.1.0"},
        "categories": {"primary": ["math.CO"], "include_cross_listed": True},
        "date_range": {"date_from": "2024-01-01", "date_to": "2024-01-31"},
        "arxiv_api": {
            "base_url": "https://export.arxiv.org/api/query",
            "rate_limit_s": 0.01,
            "page_size": 1000,
            "max_retries": 1,
            "backoff_base_s": 0.01,
        },
        "s3": {"enabled": False, "bucket": "arxiv", "prefix": "src/",
               "manifest_key": "src/arXiv_src_manifest.xml", "region": "us-east-1"},
        "eprint": {"base_url": "https://arxiv.org/e-print/", "rate_limit_s": 0.01},
        "paths": {
            "cache_dir": str(tmp_path / "cache"),
            "output_dir": str(tmp_path / "output"),
            "db_filename": "corpus.db",
        },
        "extract": {
            "default_env_names": [
                "theorem", "thm", "lemma", "lem", "proposition", "prop",
                "corollary", "cor", "claim", "conjecture", "definition", "defn",
                "remark", "observation", "fact", "example", "proof",
            ],
            "macro_expansion_max_depth": 6,
            "min_char_len": 20,
            "max_char_len": 5000,
        },
        "classify": {
            "lexicon": ["graph", "chromatic", "tree", "ramsey", "bipartite",
                        "permutation", "binomial", "generating", "vertex", "edge",
                        "subset", "colouring", "coloring"],
            "bands": {"high": 0.5, "medium": 0.2},
        },
        "dedup": {"jaccard_threshold": 0.8, "minhash_perm": 64, "shingle_size": 3},
        "qc": {
            "audit_sample_size": 5,
            "thresholds": {
                "min_source_coverage": 0.5,
                "min_balance_rate": 0.5,
                "max_zero_extraction_rate": 0.5,
                "min_audit_boundary_correctness": 0.5,
            },
        },
        "logging": {"level": "WARNING"},
        "_config_hash": "testhash",
        "_config_path": str(tmp_path / "config" / "default.yaml"),
    }
    # Write config to disk so resolve_under_root has a real path to walk from.
    cfg_path = tmp_path / "config" / "default.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg))
    # Drop a pyproject.toml so project_root() finds tmp_path.
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
    return cfg


@pytest.fixture
def store(tmp_cfg):
    s = Store(Path(tmp_cfg["paths"]["output_dir"]) / tmp_cfg["paths"]["db_filename"])
    yield s
    s.close()


@pytest.fixture
def place_paper(tmp_cfg, store):
    """Helper: register a fake paper + drop its tex into the expected cache path."""
    from datetime import datetime, timezone
    from corpus.schema import Paper, SourceStatus

    cache_dir = Path(tmp_cfg["paths"]["cache_dir"])

    def _place(arxiv_id: str, version: int, fixture_name: str, *,
               primary_category: str = "math.CO",
               submitted: datetime | None = None) -> Path:
        submitted = submitted or datetime(2024, 1, 1, tzinfo=timezone.utc)
        tex = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
        safe = arxiv_id.replace("/", "_")
        out = cache_dir / "tex" / safe[:4] / f"{safe}v{version}.tex"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tex, encoding="utf-8")
        paper = Paper(
            arxiv_id=arxiv_id,
            version=version,
            title=f"fixture {fixture_name}",
            abstract="graph chromatic ramsey bipartite",
            primary_category=primary_category,
            all_categories=[primary_category],
            is_cross_listed_co=(primary_category != "math.CO"),
            authors=["A. Author"],
            submitted=submitted,
            updated=submitted,
            source_status=SourceStatus.OK,
            harvest_run_id="test-run",
        )
        store.upsert_paper(paper)
        return out
    return _place
