import shutil

import pytest

from inets_kernel.session import Session


def texts(outputs):
    return "\n".join(o.data for o in outputs if o.kind == "text")


def kinds(outputs):
    return [o.kind for o in outputs]


def test_a_net_is_drawn_reduced_and_drawn_again():
    s = Session()
    out = s.execute("con (a b) = dup (era era)")
    assert "error" not in kinds(out)
    assert "stopped: no active pair is left (normal); 3 interactions" in texts(out)
    assert "commute 1, erase 2" in texts(out)
    if shutil.which("dot"):
        assert kinds(out).count("svg") == 2 and all(o.data.startswith("<svg") for o in out if o.kind == "svg")
    else:
        assert "Graphviz text" in texts(out)


def test_free_ports_are_the_names_used_once():
    s = Session()
    net, free = s.build("con (a b) = con (c d)")
    assert sorted(free) == ["a", "b", "c", "d"]
    net.reduce()
    assert net.link[free["a"]] == free["c"] and net.link[free["b"]] == free["d"]


def test_a_table_can_be_written_cell_by_cell():
    s = Session()
    assert "0 agents" in texts(s.execute("%system new"))
    out = s.execute("agent zero +\nagent succ + -\nagent add - - +")
    assert "3 agents, 0 rules, with signs; 2 problems" in texts(out)
    out = s.execute("rule add (y r) >< zero\n  => r = y\n  count add\n\n"
                    "rule add (y r) >< succ (x)\n  => r = succ (s); x = add (y s)\n  count add")
    assert "3 agents, 2 rules, with signs; 0 problems" in texts(out)
    out = s.execute("%schedule rounds\nsucc (succ (zero)) = add (succ (zero) out)")     # 2 + 1
    assert "3 interactions, in 3 rounds" in texts(out) and "error" not in kinds(out)
    net, free = s.build("succ (succ (zero)) = add (succ (zero) out)")
    net.reduce()
    n, depth = net.link[free["out"]].node, 0
    while net.kind[n] == "succ":
        n, depth = net.link[(n, 1)].node, depth + 1
    assert (net.kind[n], depth) == ("zero", 3)


def test_a_table_that_cannot_be_read_changes_nothing():
    s = Session()
    before = s.text
    out = s.execute("agent broken")
    assert kinds(out) == ["error"] and s.text == before


@pytest.mark.parametrize("cell,phrase", [
    ("con (a b) = con (a a)", "more than two ends"),
    ("con (a) = era", "2 auxiliary ports"),
    ("a = b", "joins two wires"),
    ("con (a b) era", "an equation is"),
    ("%nonsense", "no command"),
    ("%schedule sideways", "a schedule is one of"),
    ("%system ivm", "no table ivm"),
    ("%cap many", "whole number"),
    ("%schedule need\ncon (out b) = era", "needs a table with signs"),
])
def test_mistakes_are_reported_in_words(cell, phrase):
    out = Session().execute(cell)
    assert out[-1].kind == "error" and phrase in out[-1].data


def test_by_need_wants_its_port():
    s = Session()
    s.execute("%system ski")
    out = s.execute("%schedule need\nS = app (K r)")
    assert out[-1].kind == "error" and "free port named out" in out[-1].data
    out = s.execute("%schedule need\nI = app (K out)")
    assert "the value wanted is there (wanted)" in texts(out)


def test_trace_draws_each_round_and_adds_up():
    s = Session()
    s.execute("%schedule rounds\n%trace on")
    out = s.execute("con (con (era era) con (era era)) = dup (era era)")
    assert "after round 1" in texts(out)
    plain = Session()
    plain.execute("%schedule rounds")
    untraced = texts(plain.execute("con (con (era era) con (era era)) = dup (era era)"))
    assert untraced.split("stopped")[1].split("\n")[0] == texts(out).split("stopped")[1].split("\n")[0]


def test_the_cap_stops_a_run():
    s = Session()
    out = s.execute("%cap 50\n%ski ```SII``SII --rounds")
    assert "no answer: the cap was reached" in texts(out)
    assert "I\n" in texts(s.execute("%ski ``KI```SII``SII")) + "\n"
    assert texts(s.execute("%ski ``KI```SII``SII --lazy")).startswith("I")


def test_commands_that_show_things():
    s = Session()
    assert "%schedule HOW" in texts(s.execute("%help"))
    assert "agent con 2" in texts(s.execute("%table"))
    assert "commute" in texts(s.execute("%rules"))
    assert "0 problems" in texts(s.execute("%check"))
    assert "One term, K I" in texts(s.execute("%demo"))
