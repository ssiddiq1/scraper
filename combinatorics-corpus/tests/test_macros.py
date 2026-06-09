"""Unit tests for macro scanning and bounded expansion."""
from corpus.macros import expand, scan


def test_scan_newcommand_simple(fixture_text):
    tex = fixture_text("macro_heavy.tex")
    env = scan(tex)
    assert "bn" in env.substitutions
    assert env.substitutions["bn"].nargs == 1
    assert env.substitutions["bn"].body == "[#1]"


def test_scan_def_with_args(fixture_text):
    tex = fixture_text("macro_heavy.tex")
    env = scan(tex)
    # \def\NN{...} — no args.
    assert "NN" in env.substitutions
    assert env.substitutions["NN"].nargs == 0
    # \def\fall is actually a \newcommand with 2 args — confirm it landed.
    assert env.substitutions["fall"].nargs == 2


def test_scan_declaremathop(fixture_text):
    tex = fixture_text("macro_heavy.tex")
    env = scan(tex)
    assert "Chrom" in env.substitutions
    # \DeclareMathOperator gets rewritten to \operatorname{chr}
    assert "operatorname" in env.substitutions["Chrom"].body


def test_scan_newtheorem(fixture_text):
    tex = fixture_text("custom_env.tex")
    env = scan(tex)
    assert "ramseyclaim" in env.custom_envs
    assert "enumlemma" in env.custom_envs


def test_expand_subs_macros():
    tex = r"\bn{5} and \bn{n}"
    from corpus.macros import MacroDef, MacroEnv
    env = MacroEnv(
        substitutions={"bn": MacroDef(name="bn", nargs=1, body="[#1]")},
    )
    out = expand(tex, env)
    assert out == "[5] and [n]"


def test_expand_handles_nested_macros():
    from corpus.macros import MacroDef, MacroEnv
    env = MacroEnv(substitutions={
        "outer": MacroDef("outer", 1, r"\inner{#1}"),
        "inner": MacroDef("inner", 1, "I(#1)"),
    })
    out = expand(r"\outer{x}", env, max_depth=4)
    assert "I(x)" in out


def test_expand_bounded_depth_does_not_loop():
    from corpus.macros import MacroDef, MacroEnv
    # Pathological: macro that expands to itself. Must terminate.
    env = MacroEnv(substitutions={
        "loop": MacroDef("loop", 0, r"\loop"),
    })
    out = expand(r"\loop", env, max_depth=3)
    # We just require it to return some string without exploding the process.
    assert isinstance(out, str)
