"""Nets as text (inets.text): reading, writing back, and comparing up to numbering."""

import time

import pytest

import inets
from inets import text
from inets.errors import NetTextError

ARITH = inets.System.parse("""
agent 0   +
agent S   + -
agent Add - - +
rule Add (y z) >< 0
  => z = y
  count add
rule Add (y z) >< S (x)
  => x = Add (y t); z = S (t)
  count add
""")

UNSIGNED = inets.System.parse("agent A 2\nagent B 0\nagent D 1\n")


@pytest.mark.parametrize("net", [
    "Add (one z) = S (S (0)); one = S (0)",
    "Add (z y) = 0",
    "x = y",
    "z = S (w); w = 0",
])
def test_write_reads_back_as_the_same_net(net):
    n, free = text.read(ARITH, net)
    m, free2 = text.read(ARITH, text.write(n, free))
    assert text.same(n, free, m, free2)


def test_rings_and_closed_pieces_read_back():
    for net in ["A (a b) = A (b a)", "A (a a) = A (b b)", "D (u) = v; D (v) = u", "A (x x) = B"]:
        n, free = text.read(UNSIGNED, net)
        m, free2 = text.read(UNSIGNED, text.write(n, free))
        assert text.same(n, free, m, free2), net


def test_same_tells_nets_apart():
    def s(a, b, system=ARITH):
        return text.same(*text.read(system, a), *text.read(system, b))
    assert s("z = S (0)", "z = S (0)")
    assert not s("z = S (0)", "z = S (S (0))")
    assert not s("z = S (0)", "w = S (0)")                  # free ports' names count
    assert not s("A (a b) = A (b a)", "A (a a) = A (b b)", UNSIGNED)   # a twist in a ring
    assert s("D (a) = a; D (b) = c; D (c) = b", "D (c) = b; D (b) = c; D (a) = a", UNSIGNED)


def test_same_is_quick_on_many_alike_pieces():
    rings = lambda k: "; ".join(f"D (w{i}) = w{i}" for i in range(k))
    a = text.read(UNSIGNED, rings(200))
    b = text.read(UNSIGNED, rings(198) + "; D (u) = v; D (v) = u")
    start = time.monotonic()
    assert not text.same(*a, *b)
    assert time.monotonic() - start < 5


def test_wire_names_keep_clear_of_free_names():
    n, free = text.read(UNSIGNED, "w1 = A (a a)")
    written = text.write(n, free)
    assert "w1 = A (w2 w2)" == written
    m, free2 = text.read(UNSIGNED, written)
    assert text.same(n, free, m, free2)


@pytest.mark.parametrize("net, phrase", [
    ("a = b; a = B", "joins two wires"),
    ("A (a a) = a", "more than two ends"),
    ("A (a) = B", "auxiliary ports"),
    ("= B", "expected a node or a wire"),
    ("A (a b)", "PORT = PORT"),
])
def test_mistakes_are_refused_in_words(net, phrase):
    with pytest.raises(NetTextError, match=phrase):
        text.read(UNSIGNED, net)


def test_a_port_joined_to_nothing_cannot_be_written():
    net = inets.Net(UNSIGNED)
    out = net.free()
    net.wire(out, inets.Port(net.add_node("A"), 0))
    with pytest.raises(NetTextError, match="joined to nothing"):
        text.write(net, {"out": out})
