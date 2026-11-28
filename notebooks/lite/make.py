"""Writes draw-test.ipynb: the drawing helper (from draw.py, inlined so the notebook stands
alone and its cells can be pasted elsewhere) and two nets drawn before and after they reduce.

    python notebooks/lite/make.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n")}


helper = (HERE / "draw.py").read_text()
helper = helper[helper.index('"""', 3) + 3:].lstrip("\n")  # drop the module docstring

cells = [
    md("""
# Drawing interaction nets

A test of drawing `inets` nets in a notebook, in the style of Lafont's figures. With Graphviz's `dot` installed, the pictures are
made locally; in JupyterLite, viz.js (Graphviz compiled to WebAssembly) draws them in the page.
"""),
    code("""
try:
    import inets
except ImportError:
    %pip install -q inets
    import inets
print(inets.__version__)
"""),
    code(helper),
    md("""
## Lafont's unary arithmetic

The rules for `Add` from *Interaction Nets* (Lafont, POPL 1990, figure 8), with the paper's
polarities as signs: `+` for an output, `-` for an input. `Add`'s principal port takes the
first argument; its auxiliary ports are the second argument and the result. An arrowhead
marks each principal port, so two arrowheads tip to tip are an active pair, and the signs
put the result on top.
"""),
    code("""
arith = inets.System.parse(\"\"\"
agent 0   +
agent S   + -
agent Add - - +
# 0 )( Add [y, y]
rule Add (y z) >< 0
  => z = y
  count add
# S [Add(y, t)] )( Add [y, S(t)]
rule Add (y z) >< S (x)
  => x = Add (y t); z = S (t)
  count add
\"\"\")
net = inets.Net(arith)
z = net.free()
two = net.make("S", net.make("S", net.make("0")))
one = net.make("S", net.make("0"))
net.wire(net.make("Add", one, z), two)
draw(net, {z: "z"})
"""),
    code("""
print(net.reduce())
draw(net, {z: "z"})
"""),
    md("""
## The same, photocopied

`retro=True` gives the look of a 1990 figure.
"""),
    code("""
net = inets.Net(arith)
z = net.free()
net.wire(net.make("Add", net.make("S", net.make("0")), z), net.make("S", net.make("0")))
draw(net, {z: "z"}, retro=True)
"""),
    md("""
## S K K I, by need

The `ski` table marks which ports are outputs, so the result goes on top on its own.
`style="ports"` shows the same net with port numbers.
"""),
    code("""
from inets import ski

net = inets.Net(inets.bundled("ski"))
out = net.free()
net.wire(ski.encode(net, ski.parse("```SKKI")), out)
draw(net, {out: "result"})
"""),
    code("""
draw(net, {out: "result"}, style="ports")
"""),
    code("""
print(net.reduce_by_need(out))
print(ski.show(ski.read_back(net, out)))
draw(net, {out: "result"})
"""),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
for i, cell in enumerate(cells):
    cell["id"] = f"cell-{i}"
(HERE / "draw-test.ipynb").write_text(json.dumps(notebook, indent=1) + "\n")
print("wrote", HERE / "draw-test.ipynb")
