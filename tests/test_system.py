from importlib import resources

import pytest

import inets
from inets import System, ski


@pytest.mark.parametrize("name,agents,rules,signed", [
    ("combinators", 3, 6, False), ("ski", 12, 27, True), ("lazy", 15, 50, True), ("ivm", 5, 20, False)])
def test_bundled_tables_are_clean(name, agents, rules, signed):
    s = inets.bundled(name)
    assert (len(s.agents), len(s.rules), s.signed) == (agents, rules, signed)
    assert s.check() == []


def broken(old, new, name="ski"):
    text = resources.files("inets.systems").joinpath(name + ".rules").read_text()
    assert old in text
    return System.parse(text.replace(old, new, 1))


def has(problems, phrase):
    return any(phrase in p for p in problems)


def test_two_outputs_joined_is_reported():
    assert has(broken("f = app (g r)", "f = app (r g)").check(), "joins two")


def test_a_port_left_unused_is_reported():
    assert has(broken("=> r = x; y = era", "=> r = x").check(), "port y is used 0 times")


def test_a_missing_rule_is_reported():
    assert "no rule for era >< I" in broken("rule era >< I\n  => nothing\n  count erase\n", "").check()
    assert "no rule for era >< era" in broken("rule era >< era\n  => nothing\n  count erase\n", "", "combinators").check()


def test_a_wire_with_three_ends_cannot_be_read():
    with pytest.raises(inets.TableError, match="3 ends"):
        broken("=> p = K1 (a); q = K1 (b); x = dup (a b)", "=> p = K1 (a); q = K1 (a); x = dup (a b)")


def test_conditions_that_may_leave_a_case_out_are_reported():
    s = broken("rule comb l (a b) >< comb m (c d) when l = m", "rule comb l (a b) >< comb m (c d) when l = 0", "ivm")
    assert has(s.check(), "may leave a case out")


def test_a_rule_that_can_never_apply_is_reported():
    s = broken("rule era >< era\n  => nothing\n  count erase\n",
               "rule era >< era\n  => nothing\n  count erase\n\nrule era >< era\n  => nothing\n  count erase\n", "combinators")
    assert has(s.check(), "can never apply")


def test_a_parameter_not_in_hand_is_reported():
    assert has(broken("when l = m", "when q = m", "ivm").check(), "q is not a parameter in hand")
    assert has(broken("=> call f (v) -> a b", "=> call f (v) -> a z", "ivm").check(), "z is not an auxiliary port")


def test_mixed_signs_are_reported():
    assert System.parse("agent a +\nagent b 0\n").check() == ["some agents have signs and some do not"]


def test_a_cut_short_line_is_a_table_error():
    with pytest.raises(inets.TableError):
        System.parse("agent a 1\nrule a (x >< a (y)\n")


def test_signs_do_not_make_a_rule_right():
    """S with its arguments exchanged passes every check; only running it shows the fault."""
    s = broken("=> r = S2 (x y)", "=> r = S2 (y x)")
    assert s.check() == []
    net = inets.Net(s)
    root = net.free()
    net.wire(root, ski.encode(net, ski.parse("```SKS0")))
    net.reduce_by_need(root)
    assert ski.read_back(net, root) != ski.tree_normal_form(ski.parse("```SKS0"))[0]


def test_rules_that_are_not_local_are_marked():
    marks = [m for r in inets.bundled("ivm").rules for m in r.not_local]
    assert sorted(marks) == sorted(["looks at a neighbour"] + ["calls the host"] * 2 + ["expands a named net"] * 3 + ["keeps a node"])
    assert all(not r.not_local for r in inets.bundled("combinators").rules)


def test_otherwise_stands_alone():
    s = broken("when f.split", "when f.split and otherwise", "ivm")
    assert has(s.check(), "`otherwise` stands alone")


def test_words_after_a_rules_side_cannot_be_read():
    with pytest.raises(inets.TableError, match="unexpected"):
        System.parse("agent e 0\nrule e junk >< e\n")


def test_a_table_declares_its_duplicators():
    system = inets.System.parse("agent v +\nagent d - + + duplicator\nagent e -\n")
    assert system.duplicators == ("d",)
    assert system.agents["d"].duplicator and not system.agents["e"].duplicator
    bad = inets.System.parse("agent v +\nagent d - - + duplicator\n")
    assert any("duplicator" in p for p in bad.check())
    assert inets.bundled("ski").duplicators == ("dup",)
    assert inets.bundled("lazy").duplicators == ("dup",)
    assert inets.bundled("combinators").duplicators == ()


def test_duplicator_is_a_keyword_only_as_the_last_word():
    s = inets.System.parse("agent duplicator - + +\nagent num + param duplicator\n")
    assert s.agents["duplicator"].signs == ("-", "+", "+") and not s.agents["duplicator"].duplicator
    assert s.agents["num"].param == "duplicator" and not s.agents["num"].duplicator
    assert s.duplicators == ()
    s = inets.System.parse("agent duplicator - + + duplicator\nagent v +\n")
    assert s.duplicators == ("duplicator",)


def test_keeps_follows_the_body():
    rewrite = inets.Rewrite()
    assert rewrite.keeps == (False, False)
    rewrite.links.append((inets.Pair(1), inets.Ext("a")))
    assert rewrite.keeps == (False, True)
    for rule in inets.bundled("lazy").rules:
        if isinstance(rule.body, inets.Rewrite):
            ends = [e for link in rule.body.links for e in link]
            assert rule.body.keeps == (inets.Pair(0) in ends, inets.Pair(1) in ends)


def test_the_ends_of_a_rules_body_are_classes():
    rule = inets.bundled("combinators").rules[2]       # con >< dup: commute
    ends = {type(e) for link in rule.body.links for e in link}
    assert ends == {inets.Ext, inets.New}
    assert inets.Ext("a") in [e for link in rule.body.links for e in link]
