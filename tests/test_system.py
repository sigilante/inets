import pytest

import inets
from inets import system


@pytest.mark.parametrize("name,agents,rules,typed", [
    ("combinators", 3, 6, False), ("ski", 12, 27, True), ("lazy", 15, 50, True), ("ivm", 5, 20, False)])
def test_bundled_tables_are_clean(name, agents, rules, typed):
    s = inets.bundled(name)
    assert (len(s.agents), len(s.rules), s.typed) == (agents, rules, typed)
    assert inets.check(s) == []


def broken(old, new, name="ski"):
    from importlib import resources
    text = resources.files("inets.systems").joinpath(name + ".rules").read_text()
    assert old in text
    return text.replace(old, new, 1)


def test_two_outputs_joined_is_refused():
    s = system.parse(broken("f = app (g r)", "f = app (r g)"))
    assert any("joins two" in p for p in inets.check(s))


def test_a_port_left_unused_is_refused():
    s = system.parse(broken("=> r = x; y = era", "=> r = x"))
    assert any("port y is used 0 times" in p for p in inets.check(s))


def test_a_missing_rule_is_refused():
    text = broken("rule era >< I\n  => nothing\n  count erase\n", "")
    assert "no rule for era >< I" in inets.check(system.parse(text))


def test_a_wire_with_three_ends_is_refused():
    with pytest.raises(inets.TableError, match="3 ends"):
        system.parse(broken("=> p = K1 (a); q = K1 (b); x = dup (a b)", "=> p = K1 (a); q = K1 (a); x = dup (a b)"))


def test_a_missing_pair_is_refused_without_signs():
    text = broken("rule era >< era\n  => nothing\n  count erase\n", "", "combinators")
    assert "no rule for era >< era" in inets.check(system.parse(text))


def test_conditions_that_may_leave_a_case_out_are_reported():
    text = broken("rule comb l (a b) >< comb m (c d) when l = m", "rule comb l (a b) >< comb m (c d) when l = 0", "ivm")
    assert any("may leave a case out" in p for p in inets.check(system.parse(text)))


def test_typing_does_not_make_a_rule_right():
    """S with its arguments exchanged is well typed; only running it shows the fault."""
    from inets import ski
    text = broken("=> r = S2 (x y)", "=> r = S2 (y x)")
    s = system.parse(text)
    assert inets.check(s) == []
    net = inets.Net(s)
    root = net.free()
    net.wire(root, ski.encode(net, ski.parse("```SKS0")))
    net.by_need(root)
    assert ski.read(net, root) != ski.tree_normal_form(ski.parse("```SKS0"))[0]


def test_rules_that_are_not_local_are_marked():
    s = inets.bundled("ivm")
    assert sum(r.peeks for r in s.rules) == 1
    assert sum(r.kind == "call" for r in s.rules) == 2
    assert sum(r.kind == "expand" for r in s.rules) == 3
    assert sum(any(r.keeps) for r in s.rules) == 1
