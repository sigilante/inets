import pytest

import inets
from inets import ivm, ivy


def test_read_gives_trees_and_wires():
    nets = ivy.read("iv:main { ^ = ivm:x(a ivm:n32#7)  a = ivm:eraser } // done")
    (root, tree), (wire, eraser) = nets["iv:main"]
    assert root == "^" and wire == "a"
    assert (tree.path, tree.kids[0], tree.kids[1].payload) == ("ivm:x", "a", 7)
    assert eraser == ivy.Tree("ivm:eraser", None, (), ())


def test_names_keep_their_payload_and_brackets():
    nets = ivy.read(":f#3[:g, :h[:k]] { ^ = ivm:eraser }")
    assert list(nets) == [":f#3[:g,:h[:k]]"]


def test_a_comment_at_the_very_end_is_only_a_comment():
    assert list(ivy.read("m:n { ^ = ivm:eraser }//x")) == ["m:n"]


@pytest.mark.parametrize("text", ["m:n { ^ = ", "m:n { ^ = ivm:x(a }", "m:n ^", "m:n { ^ ivm:eraser }", "m:n { ^ = ivm:n32#ff }"])
def test_text_that_is_not_a_net_is_an_ivy_error(text):
    with pytest.raises(inets.IvyError):
        ivy.read(text)


def build(text):
    net = inets.Net(inets.bundled("ivm"))
    return net, ivy.instantiate(net, ivy.read(text)["m:n"], ivm.agent_of)


def test_wires_said_to_be_one_are_one_however_they_are_chained():
    for text in ("m:n { a = b  b = c  ^ = ivm:x(a c) }", "m:n { ^ = a  a = b  b = ivm:eraser }",
                 "m:n { ^ = ivm:x(a c)  b = c  a = b }"):
        net, port = build(text)
        assert net.kind[port.node] in ("comb", "era")


@pytest.mark.parametrize("text", ["m:n { ^ = ivm:x(a b)  a = ivm:eraser }", "m:n { ivm:eraser = ivm:eraser }",
                                  "m:n { ^ = ivm:x(ivm:eraser) }", "m:n { ^ = some:thing }", "m:n { ^ = ivm:graft }",
                                  "m:n { ^ = ivm:ext:merge(a a) }"])
def test_what_is_not_a_net_of_the_system_is_an_ivy_error(text):
    with pytest.raises(inets.IvyError):
        build(text)


def test_a_deep_tree_is_read_or_refused_cleanly():
    depth = 3000
    text = "m:n { ^ = " + "ivm:x(ivm:eraser " * depth + "ivm:eraser" + ")" * depth + " }"
    try:
        net, port = build(text)
        assert len(net.kind) == 2 * depth + 1
    except inets.IvyError as e:
        assert "nested too deeply" in str(e)
