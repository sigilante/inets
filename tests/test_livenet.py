"""The notebook helper notebooks/lafont1990/livenet.py: reading and writing nets as text,
comparing nets, and the Graphviz text it draws from. The source archive leaves out the
notebooks, so there these tests are skipped."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent / "notebooks" / "lafont1990"
if not (HERE / "livenet.py").exists():
    pytest.skip("notebooks/lafont1990 is not in this copy", allow_module_level=True)
sys.path.insert(0, str(HERE))
import livenet as L  # noqa: E402

ARITH = """
agent 0   +
agent S   + -
agent Add - - +
rule Add (y z) >< 0
  => z = y
  count add
rule Add (y z) >< S (x)
  => x = Add (y t); z = S (t)
  count add
"""

DIFF = """
agent P    +
agent Cons + - -
agent Diff + - +
"""


def test_text_round_trips():
    arith = L.table(ARITH)
    for text in ["Add (one z) = S (S (0)); one = S (0)", "Add (z y) = 0", "x = y"]:
        n = L.Net(arith, text)
        assert n.same(str(n)), text


def test_same_tells_nets_apart():
    arith = L.table(ARITH)
    assert not L.Net(arith, "z = S (0)").same("z = S (S (0))")
    assert not L.Net(arith, "z = S (0)").same("w = S (0)")
    assert L.Net(arith, "Add (a b) = S (0); a = 0").same("Add (0 b) = S (0)")


def test_reduce_and_steps_reduce_the_net():
    arith = L.table(ARITH)
    n = L.Net(arith, "Add (one z) = S (S (0)); one = S (0)")
    n.steps(limit=1)
    assert n.net.interactions == 1
    n.reduce()
    assert n.same("z = S (S (S (0)))")


def test_layout_follows_signs():
    arith = L.table(ARITH)
    assert L.Net(arith, "z = S (0)")._dot().startswith("digraph")
    unsigned = L.table("agent A 1\nagent B 0")
    assert L.Net(unsigned, "z = A (B)")._dot().startswith("graph")


def test_cycles_mistyped_wires_and_joined_free_ports_draw():
    arith, diff = L.table(ARITH), L.table(DIFF)
    # A difference-list: the hole is a cycle back to Diff.
    assert "digraph" in L.Net(diff, "r = Diff (a b); a = Cons (P b)")._dot()
    # Two outputs joined, and two inputs joined: not well typed, but drawn.
    L.Net(arith, "S (a) = S (b)")._dot()
    L.Net(arith, "Add (a b) = Add (c d)")._dot()
    # Two free ports joined to each other.
    L.Net(arith, "y = x")._dot()


def test_bare_ends_and_arrows():
    arith = L.table(ARITH)
    dot = L.Net(arith, "_a = S (_b)")._dot()
    assert "_a" not in dot and "_b" not in dot
    L.arrows(False)
    try:
        assert "inv" not in L.Net(arith, "z = S (0)")._dot()
    finally:
        L.arrows(True)
    assert "inv" in L.Net(arith, "z = S (0)")._dot()
