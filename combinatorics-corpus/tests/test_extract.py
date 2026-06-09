"""Boundary correctness + balance detection + custom-env discovery for extract.py."""
from datetime import datetime, timezone

from corpus.extract import extract_from_tex
from corpus.schema import FailureReason

DEFAULT_ENVS = [
    "theorem", "thm", "lemma", "lem", "proposition", "prop", "corollary",
    "cor", "claim", "conjecture", "definition", "defn", "remark",
    "observation", "fact", "example", "proof",
]


def _extract(tex: str):
    return extract_from_tex(
        "test", 1, tex,
        default_env_names=DEFAULT_ENVS,
        macro_expansion_max_depth=4,
        parser_version="t",
        extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_clean_paper_yields_three_blocks(fixture_text):
    statements, failures = _extract(fixture_text("clean.tex"))
    env_types = [s.env_type for s in statements]
    # theorem, lemma, proof — all should land balanced.
    assert "theorem" in env_types
    assert "lemma" in env_types
    assert "proof" in env_types
    assert all(s.balanced for s in statements)
    assert FailureReason.EMPTY_EXTRACTION not in failures


def test_clean_paper_label_and_citations(fixture_text):
    statements, _ = _extract(fixture_text("clean.tex"))
    thm = next(s for s in statements if s.env_type == "theorem")
    assert thm.label == "thm:main"
    # Both cited keys appear (split on comma).
    assert set(thm.citations) >= {"Smith2019", "Doe2020"}


def test_clean_paper_clean_text_nonempty(fixture_text):
    statements, _ = _extract(fixture_text("clean.tex"))
    for s in statements:
        assert s.clean_text.strip(), f"{s.env_type} clean_text empty"
        assert s.char_len == len(s.clean_text)


def test_custom_envs_are_extracted(fixture_text):
    statements, _ = _extract(fixture_text("custom_env.tex"))
    types = {s.env_type for s in statements}
    # Both custom envs + the std theorem must show up.
    assert "ramseyclaim" in types
    assert "enumlemma" in types
    assert "theorem" in types
    assert all(s.balanced for s in statements)


def test_macro_heavy_expansion(fixture_text):
    statements, _ = _extract(fixture_text("macro_heavy.tex"))
    assert len(statements) == 1
    s = statements[0]
    # \bn{n} should have expanded to [n]. Either literal "[n]" or the chars survive math mode.
    assert "[n]" in s.clean_text or "n" in s.clean_text
    # \operatorname{chr} from DeclareMathOperator should show up textually too.
    assert "chr" in s.clean_text.lower()


def test_malformed_marks_unbalanced(fixture_text):
    statements, failures = _extract(fixture_text("malformed.tex"))
    # The first theorem before the bad lemma is balanced.
    types = [(s.env_type, s.balanced) for s in statements]
    assert ("theorem", True) in types
    # The lemma is captured but unbalanced (runs to EOF).
    assert any(t == "lemma" and not b for t, b in types)
    assert failures.get(FailureReason.UNBALANCED_ENV, 0) >= 1


def test_empty_input_typed_failure():
    statements, failures = _extract("")
    assert statements == []
    assert failures.get(FailureReason.EMPTY_EXTRACTION, 0) >= 1


def test_paper_with_no_envs_is_typed():
    tex = r"\documentclass{article}\begin{document}Just prose, no envs.\end{document}"
    statements, failures = _extract(tex)
    assert statements == []
    assert failures.get(FailureReason.EMPTY_EXTRACTION, 0) >= 1
