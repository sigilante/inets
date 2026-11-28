"""Pictures of nets (inets.draw): the Graphviz text in Lafont's style, and SVG."""

import shutil

import pytest

import inets
from inets import draw, text

ARITH = inets.System.parse("""
agent 0   +
agent S   + -
agent Add - - +
""")

DIFF = inets.System.parse("""
agent P    +
agent Cons + - -
agent Diff + - +
""")

UNSIGNED = inets.System.parse("agent A 2\nagent B 0\n")


def picture(system, net, **options):
    n, free = text.read(system, net)
    return draw.dot(n, {p: name for name, p in free.items()}, **options)


def test_a_table_with_signs_is_laid_out_by_direction():
    graph = picture(ARITH, "Add (one z) = S (S (0)); one = S (0)")
    assert graph.startswith("digraph")
    assert "{ rank=min;" in graph            # the result, z, is put on top
    assert picture(UNSIGNED, "z = A (B B)").startswith("graph")


def test_cycles_mistyped_wires_and_joined_free_ports_are_drawn():
    assert "constraint=false" in picture(DIFF, "r = Diff (a b); a = Cons (P b)")   # the hole
    picture(ARITH, "S (a) = S (b)")            # two outputs joined
    picture(ARITH, "Add (a b) = Add (c d)")    # two inputs joined
    picture(ARITH, "y = x")


def test_arrows_bare_ends_and_the_ports_style():
    assert "arrowtail=inv" in picture(ARITH, "z = S (0)") or "arrowhead=inv" in picture(ARITH, "z = S (0)")
    assert "=inv" not in picture(ARITH, "z = S (0)", arrows=False)
    bare = picture(ARITH, "_a = S (_b)")
    assert "_a" not in bare and "_b" not in bare
    assert picture(ARITH, "z = S (0)", style="ports").startswith("graph net {")
    with pytest.raises(ValueError):
        picture(ARITH, "z = S (0)", style="sketch")


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz's dot is not installed")
def test_svg_and_its_retro_look():
    svg = draw.svg(picture(ARITH, "z = S (0)"))
    assert svg.startswith("<svg")
    rough = draw.roughen(svg)
    assert 'filter id="retro"' in rough and 'filter="url(#retro)"' in rough
