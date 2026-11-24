import inets


def net_and(*kinds):
    net = inets.Net(inets.bundled("combinators"))
    return net


def test_two_constructors_annihilate_straight_across():
    net = inets.Net(inets.bundled("combinators"))
    a, b, c, d = (net.free() for _ in range(4))
    net.wire(net.node("con", a, b), net.node("con", c, d))
    r = net.reduce()
    assert (r.reason, r.counts) == ("normal", {"annihilate": 1})
    assert net.link[a] == c and net.link[b] == d


def test_a_constructor_and_a_duplicator_commute():
    net = inets.Net(inets.bundled("combinators"))
    a, b, c, d = (net.free() for _ in range(4))
    net.wire(net.node("con", a, b), net.node("dup", c, d))
    r = net.reduce()
    assert r.counts == {"commute": 1}
    assert [net.kind[net.link[p][0]] for p in (a, b, c, d)] == ["dup", "dup", "con", "con"]


def copies_of_a_tree(order):
    """A duplicator copying a tree of three constructors whose leaves are erasers."""
    net = inets.Net(inets.bundled("combinators"))
    leaf = lambda: net.node("era")
    tree = net.node("con", net.node("con", leaf(), leaf()), net.node("con", leaf(), leaf()))
    net.wire(net.node("dup", net.node("era"), net.node("era")), tree)
    return net.reduce(order=order, seed=5) if order != "rounds" else net.rounds()


def test_every_order_takes_the_same_interactions():
    results = [copies_of_a_tree(o) for o in ("stack", "queue", "random", "rounds")]
    assert all(r.reason == "normal" for r in results)
    assert len({tuple(sorted(r.counts.items())) for r in results}) == 1
    assert results[-1].rounds >= 1 and results[-1].widest >= 2


def test_a_wire_from_a_pair_back_to_itself():
    """con(x x) meeting con(a b) joins a to b."""
    net = inets.Net(inets.bundled("combinators"))
    a, b = net.free(), net.free()
    n = net.new("con")
    net.wire((n, 1), (n, 2))
    net.wire((n, 0), net.node("con", a, b))
    net.reduce()
    assert net.link[a] == b


def test_dot_marks_the_active_pair():
    net = inets.Net(inets.bundled("combinators"))
    net.wire(net.node("era"), net.node("era"))
    assert 'penwidth=3' in net.dot()
