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

A test of drawing `inets` nets in a notebook. With Graphviz's `dot` installed, the pictures are
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
## A constructor meets a duplicator

The example from the README, in the `combinators` table. The thick red wire is the active pair;
the numbers at the ends of a wire are port numbers, 0 being the principal port.
"""),
    code("""
net = inets.Net(inets.bundled("combinators"))
a, b = net.free(), net.free()
net.wire(net.make("con", a, b), net.make("dup", net.make("era"), net.make("era")))
draw(net, {a: "a", b: "b"})
"""),
    code("""
print(net.reduce())
draw(net, {a: "a", b: "b"})
"""),
    md("""
## S K K I, by need

The same term the `inets run ski` command reads. It reduces to `I`.
"""),
    code("""
from inets import ski

net = inets.Net(inets.bundled("ski"))
out = net.free()
net.wire(ski.encode(net, ski.parse("```SKKI")), out)
draw(net, {out: "result"})
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
