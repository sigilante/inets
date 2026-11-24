import pytest

import inets


def combinators():
    return inets.Net(inets.bundled("combinators"))


def sound(net):
    """Every port of every node is joined, joins go both ways, and none is to a node
    that is gone."""
    for n in net.kind:
        for p in net.ports(n):
            q = net.link[p]
            assert q.node in net.kind and net.link[q] == p
    assert all(p.node in net.kind for p in net.link)


def test_two_constructors_annihilate_straight_across():
    net = combinators()
    a, b, c, d = (net.free() for _ in range(4))
    net.wire(net.make("con", a, b), net.make("con", c, d))
    r = net.reduce()
    assert (r.reason, r.counts, r.interactions) == ("normal", {"annihilate": 1}, 1)
    assert net.link[a] == c and net.link[b] == d
    sound(net)


def test_a_constructor_and_a_duplicator_commute():
    net = combinators()
    a, b, c, d = (net.free() for _ in range(4))
    net.wire(net.make("con", a, b), net.make("dup", c, d))
    assert net.reduce().counts == {"commute": 1}
    assert [net.kind[net.link[p].node] for p in (a, b, c, d)] == ["dup", "dup", "con", "con"]
    sound(net)


def a_tree_being_copied():
    """A duplicator copying a tree of three constructors whose leaves are erasers."""
    net = combinators()
    leaf = lambda: net.make("era")
    tree = net.make("con", net.make("con", leaf(), leaf()), net.make("con", leaf(), leaf()))
    net.wire(net.make("dup", net.make("era"), net.make("era")), tree)
    return net


def test_every_order_takes_the_same_interactions_on_one_net():
    results = [a_tree_being_copied().reduce(order=o, seed=5) for o in ("stack", "queue", "random")]
    results.append(a_tree_being_copied().reduce_in_rounds())
    assert all(r.reason == "normal" for r in results)
    assert len({tuple(sorted(r.counts.items())) for r in results}) == 1
    assert results[-1].rounds >= 1 and results[-1].widest >= 2


def test_a_wire_from_a_pair_back_to_itself():
    """con(x x) meeting con(a b) joins a to b. (The IVM's programs do this: a net whose
    free port is `ivm:x(io io)`.)"""
    net = combinators()
    a, b = net.free(), net.free()
    n = net.add_node("con")
    net.wire((n, 1), (n, 2))
    net.wire((n, 0), net.make("con", a, b))
    net.reduce()
    assert net.link[a] == b
    sound(net)


def test_a_cap_stops_a_run_and_counts_are_for_the_run():
    net = a_tree_being_copied()
    first = net.reduce(max_interactions=2)
    assert (first.reason, first.interactions, first.finished) == ("interactions", 2, False)
    second = net.reduce()
    assert second.reason == "normal"
    assert first.interactions + second.interactions == net.interactions
    assert sum(first.counts.values()) + sum(second.counts.values()) == sum(net.counts.values())


def test_wrong_use_raises_the_packages_error():
    net = combinators()
    with pytest.raises(inets.Error):
        net.make("con", net.free())          # con has two auxiliary ports
    with pytest.raises(inets.Error):
        net.add_node("no such agent")
    with pytest.raises(inets.Error):
        net.reduce(order="sideways")
    with pytest.raises(inets.Error):
        net.reduce_by_need(net.free())       # the table has no signs


def test_a_pair_with_no_rule_is_stuck():
    s = inets.System.parse("agent a 0\nagent b 0\nrule a >< a\n  => nothing\n  count x\n")
    net = inets.Net(s)
    net.wire(net.make("a"), net.make("b"))
    with pytest.raises(inets.Stuck):
        net.reduce()


def test_dot_marks_the_active_pair():
    net = combinators()
    net.wire(net.make("era"), net.make("era"))
    assert "penwidth=3" in net.dot()


def test_a_host_call_whose_outputs_are_wired_to_the_pair_itself():
    """A split function whose two outputs are joined to each other: the two results meet."""
    from inets import ivm
    net = inets.Net(inets.bundled("ivm"), ivm.IvmHost({}))
    f = net.add_node("fn", ivm.Fn("vi:io:split", split=True))
    net.wire((f, 1), (f, 2))
    net.wire((f, 0), net.make("val", param=ivm.IO))
    r = net.reduce()
    assert r.reason == "normal" and net.kind == {} and net.link == {}
    assert r.counts == {"extrinsic": 1, "erase": 1} and "ext_erase" in net.flags


def test_sweeping_after_every_interaction_really_does():
    from inets import ski

    class Counting(inets.Net):
        swept = 0

        def sweep(self, roots):
            self.swept += 1
            super().sweep(roots)

    net = Counting(inets.bundled("ski"))
    root = net.free()
    net.wire(root, ski.encode(net, ski.parse("```SII```SKK```SKK0")))
    r = net.reduce_by_need(root, sweep_above=0)
    assert net.swept == r.interactions > 5
    assert ski.read_back(net, root) == (0, 0)
    sound(net)


def test_by_need_does_not_report_a_cap_it_did_not_need():
    from inets import ski
    exact = ski.run("```SKKI").result.interactions
    assert ski.run("```SKKI", max_interactions=exact).result.reason == "wanted"
    assert ski.run("```SKKI", max_interactions=exact - 1).result.reason == "interactions"
