import pytest

import inets
from inets import ski

OMEGA = "```SII``SII"


def test_parse_and_show_round_trip():
    for text in ("S", "``SKK", "```S`K0`1I2"):
        assert ski.show(ski.parse(text)) == text
    for bad in ("``SK", "SK", "X"):
        with pytest.raises(ValueError):
            ski.parse(bad)


def test_one_term_three_ends():
    term = "``KI" + OMEGA
    need = ski.run(term, how="need")
    assert (ski.show(need.term), need.result.reason, need.result.counts["contract"]) == ("I", "wanted", 1)
    assert need.result.active_left > 0          # Ω is still there, unreduced
    every = ski.run(term, how="all", max_interactions=500)
    assert every.result.reason == "interactions" and every.term is None
    demand = ski.run(term, how="demand")
    assert (ski.show(demand.term), demand.result.reason, demand.result.active_left) == ("I", "normal", 0)


def test_a_sweep_removes_what_the_root_cannot_reach():
    run = ski.run("``KI" + OMEGA)
    run.net.sweep([run.root])
    assert run.net.active() == [] and ski.read(run.net, run.root) == "I"


def test_shared_work_is_done_once_by_need_and_twice_by_name():
    work = "```SKK```SKK```SKK0"            # six contractions
    twice = "```SII" + work
    tree_steps = ski.tree_normal_form(ski.parse(twice))[1]
    assert ski.run(work).result.counts["contract"] == 6
    assert ski.run(twice).result.counts["contract"] == 9
    assert ski.run(twice, how="demand").result.counts["contract"] == tree_steps == 15


@pytest.mark.parametrize("leaves,size", [(["S", "K", "I"], 5), (["S", "K", "I", 0, 1], 4)])
def test_census(leaves, size):
    """Every term up to a size, with a normal form by tree reduction."""
    for n in range(1, size + 1):
        for t in ski.terms(leaves, n):
            nf, steps = ski.tree_normal_form(t)
            if nf is None:
                continue
            need = ski.run(t, how="need", max_interactions=20000)
            assert need.term == nf and need.result.counts.get("contract", 0) <= steps
            every = ski.run(t, how="all", max_interactions=20000)
            assert every.term in (nf, None)
            for direct in (False, True):
                demand = ski.run(t, how="demand", direct=direct, max_interactions=50000)
                assert demand.term == nf and demand.result.counts.get("contract", 0) == steps
            main, definitions = ski.name(t)
            named = ski.run(main, how="need", definitions=definitions, direct=True)
            assert ski.unfold(main, definitions) == t
            assert named.term == nf
            assert named.result.counts.get("contract", 0) == need.result.counts.get("contract", 0)
            main, definitions = ski.name(t, any_term=True)
            named = ski.run(main, how="demand", definitions=definitions, direct=True, max_interactions=50000)
            assert named.term == nf and named.result.counts.get("contract", 0) == steps


def test_names_with_work_in_them_are_refused_for_the_ski_table():
    main, definitions = ski.name(ski.parse("```S`K``KI0``SKK1"), any_term=True)
    with pytest.raises(ValueError, match="not in normal form"):
        ski.run(main, how="need", definitions=definitions)


def test_by_need_wants_a_table_with_signs():
    net = inets.Net(inets.bundled("combinators"))
    with pytest.raises(ValueError):
        net.by_need(net.free())
