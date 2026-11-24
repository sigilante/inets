import pytest

import inets
from inets import ski
from test_net import sound

OMEGA = "```SII``SII"


def terms(leaves, size):
    """Every term with exactly `size` leaves."""
    if size == 1:
        return list(leaves)
    return [(a, b) for k in range(1, size) for a in terms(leaves, k) for b in terms(leaves, size - k)]


def test_parse_and_show_round_trip():
    for text in ("S", "``SKK", "```S`K0`1I2"):
        assert ski.show(ski.parse(text)) == text
    for bad in ("``SK", "SK", "X", ""):
        with pytest.raises(inets.TermError):
            ski.parse(bad)


def test_one_term_three_ends():
    term = "``KI" + OMEGA
    need = ski.run(term, schedule="need")
    assert (ski.show(need.term), need.result.reason, need.result.counts["contract"]) == ("I", "wanted", 1)
    assert need.result.active_left > 0          # Ω is still there, unreduced
    every = ski.run(term, schedule="rounds", max_interactions=500)
    assert every.result.reason == "interactions" and every.term is None
    lazy = ski.run(term, schedule="lazy")
    assert (ski.show(lazy.term), lazy.result.reason, lazy.result.active_left) == ("I", "normal", 0)


def test_a_sweep_removes_what_the_root_cannot_reach():
    run = ski.run("``KI" + OMEGA)
    run.net.sweep([run.root])
    assert run.net.active() == [] and ski.read_back(run.net, run.root) == "I"
    sound(run.net)


def test_shared_work_is_done_once_by_need_and_twice_by_name():
    work = "```SKK```SKK```SKK0"            # six contractions
    twice = "```SII" + work
    tree_steps = ski.tree_normal_form(ski.parse(twice))[1]
    assert ski.run(work).result.counts["contract"] == 6
    assert ski.run(twice).result.counts["contract"] == 9
    assert ski.run(twice, schedule="lazy").result.counts["contract"] == tree_steps == 15


@pytest.mark.parametrize("leaves,size", [(["S", "K", "I"], 5), (["S", "K", "I", 0, 1], 4)])
def test_census(leaves, size):
    """Every term up to a size that has a normal form by tree reduction within its caps.
    By need and by the lazy table reach it (the lazy table in exactly as many contractions
    as tree reduction takes steps, by need in no more); with every pair fired the ski
    table reaches it or runs into the cap. Sweeping after every interaction (`sweep_above=0`), building
    values directly and naming subterms change neither the answer nor the contractions."""
    for n in range(1, size + 1):
        for t in terms(leaves, n):
            nf, steps = ski.tree_normal_form(t)
            if nf is None:
                continue
            need = ski.run(t, schedule="need", max_interactions=20000)
            contractions = need.result.counts.get("contract", 0)
            assert need.term == nf and contractions <= steps
            swept = ski.run(t, schedule="need", sweep_above=0, max_interactions=20000)
            assert swept.term == nf and swept.result.counts.get("contract", 0) == contractions
            sound(swept.net)
            assert ski.run(t, schedule="rounds", max_interactions=20000).term in (nf, None)
            for direct in (False, True):
                lazy = ski.run(t, schedule="lazy", direct=direct, max_interactions=50000)
                assert lazy.term == nf and lazy.result.counts.get("contract", 0) == steps
            main, definitions = ski.name_subterms(t)
            assert ski.unfold(main, definitions) == t
            named = ski.run(main, schedule="need", definitions=definitions, direct=True)
            assert named.term == nf and named.result.counts.get("contract", 0) == contractions
            main, definitions = ski.name_subterms(t, any_term=True)
            named = ski.run(main, schedule="lazy", definitions=definitions, direct=True, max_interactions=50000)
            assert named.term == nf and named.result.counts.get("contract", 0) == steps


def test_by_need_can_stop_at_the_head():
    run = ski.run("``S`II`II", deep=False)        # S (I I) (I I): a value, its arguments not asked for
    assert run.result.counts.get("contract", 0) == 0
    assert ski.run("``S`II`II").result.counts["contract"] == 2


def test_names_with_work_in_them_are_refused_for_the_ski_table():
    main, definitions = ski.name_subterms(ski.parse("```S`K``KI0``SKK1"), any_term=True)
    with pytest.raises(inets.TermError, match="not in normal form"):
        ski.run(main, schedule="need", definitions=definitions)


def test_a_sweep_can_collapse_a_duplicator_that_lost_a_copy():
    for collapse, dups in (((), 1), (("dup",), 0)):
        net = inets.Net(inets.bundled("ski"))
        root = net.free()
        d = net.add_node("dup")
        net.wire((d, 0), net.make("S"))
        net.wire((d, 1), root)                       # one copy is wanted ...
        net.wire((d, 2), net.make("era"))            # ... and the other is not
        net.sweep([root], collapse)
        assert sum(k == "dup" for k in net.kind.values()) == dups
        assert ski.read_back(net, root) == "S"
        sound(net)
    with pytest.raises(inets.Error):
        net.sweep([root], ("app",))                  # not a duplicator: signs - - +


@pytest.mark.parametrize("text", ["```SII```SKK```SKK0", "``KI" + OMEGA, "```S``SKK``SKK```SII0", "````SSS`IS0",
                                  "```SII```SII```SII0"])
def test_collapsing_changes_copies_and_never_contractions(text):
    runs = []
    for collapse in ((), ("dup",)):
        net = inets.Net(inets.bundled("ski"))
        root = net.free()
        net.wire(root, ski.encode(net, ski.parse(text)))
        result = net.reduce_by_need(root, sweep_above=0, collapse=collapse)
        runs.append((ski.read_back(net, root), result.counts.get("contract", 0), result.counts.get("copy", 0)))
        sound(net)
    (term, contractions, copies), (term2, contractions2, copies2) = runs
    assert (term, contractions) == (term2, contractions2) and copies2 <= copies
    if text in ("```SII```SKK```SKK0", "```S``SKK``SKK```SII0"):
        assert copies2 < copies                      # where a copy was lost, it was not made


def test_an_atoms_arguments_are_built_directly_only_with_direct():
    assert ski.run("`01", deep=False).result.counts == {"collect": 1}
    assert ski.run("`01", deep=False, direct=True).result.counts == {}
