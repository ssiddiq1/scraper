# combinatorics-corpus

A reproducible, provenance-tracked pipeline that harvests **math.CO** arXiv papers and
extracts a deduplicated corpus of formal theorem-like statements (theorems, lemmas,
propositions, definitions, conjectures, and custom user-declared environments).

The output is embedding-ready and traceable: every statement carries its
arxiv_id + version, the raw LaTeX, macro-expanded clean text, citation keys,
balance validity, a combinatorics-relevance band, and a dedup cluster identity.

## Setup

```bash
cd combinatorics-corpus
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

The S3 bulk channel is **disabled by default** (`config/default.yaml` → `s3.enabled: false`).
The default channel is per-paper e-print HTTPS fetch, which is dev-friendly and needs no
AWS credentials.

To enable the requester-pays S3 channel later, set `s3.enabled: true` and configure
the standard AWS credential chain (`aws configure` or `AWS_PROFILE`). Note that this
will incur charges against your AWS account.

## Running

The orchestrator is `scripts/run_pipeline.py`. Every stage is idempotent and resumable.

```bash
python scripts/run_pipeline.py harvest    # arXiv Atom metadata
python scripts/run_pipeline.py fetch      # download/cache LaTeX source
python scripts/run_pipeline.py extract    # macros -> theorem extraction -> relevance
python scripts/run_pipeline.py dedup      # MinHash/LSH clustering, mark canonical
python scripts/run_pipeline.py qc         # gates + audit sample + datasheet + parquet
python scripts/run_pipeline.py run-all    # end-to-end
```

A non-default config:

```bash
python scripts/run_pipeline.py --config config/my.yaml run-all
```

Outputs land under `data/output/`:

```
data/output/corpus.db                  # SQLite (FTS5-indexed) — papers, statements, rejects, metrics
data/output/canonical_statements.parquet  # canonical-only export, ML-friendly
data/output/audit_sample.jsonl         # seeded random sample for human eval
data/output/datasheet.md               # auto-generated data card
```

The source cache lives under `data/cache/` and is content-addressed by
arxiv_id + version, so re-runs never re-download.

## Widening beyond math.CO

The default config is `math.CO`-only by design. Edit `config/default.yaml`:

```yaml
categories:
  primary: ["math.CO", "cs.DM", "math.PR"]
  include_cross_listed: true
```

Changing the category list invalidates the `categories_key` used by the harvest
cursor, so the next `harvest` run will re-walk months under the new set
(no stale partial pages).

## Tests

```bash
pytest -q
```

Fixtures under `tests/fixtures/` cover:
- `clean.tex` — standard envs, balanced
- `custom_env.tex` — user-declared envs via `\newtheorem`
- `macro_heavy.tex` — `[n]`, falling factorials, `\DeclareMathOperator`
- `malformed.tex` — unbalanced env that must be flagged, not crashed
- `non_latex.bin` — PDF-like magic bytes for the SOURCE_NOT_LATEX path

The end-to-end test (`tests/test_e2e.py`) places fixtures into the cache and
exercises extract → dedup → qc, asserting QC counts and determinism.

## QC philosophy

QC is **observability, not enforcement.** Low-relevance statements are *flagged*,
not deleted. Unbalanced blocks are recorded with `balanced=False` rather than
silently dropped. Source failures are typed against `FailureReason` so the
datasheet shows exactly what was missed and why.

## Determinism

A fixed config + seed reproduces the same corpus (`config_hash` + statement
`id`s are deterministic) and the same `audit_sample.jsonl` ordering.
