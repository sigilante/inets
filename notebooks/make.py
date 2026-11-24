#!/usr/bin/env python3
"""Writes the notebooks in this directory and runs them, so that their outputs are what
the kernel gives.

    python notebooks/make.py

Needs inets and inets-kernel importable, with nbformat and nbclient; Graphviz's `dot` for
the pictures. The kernel is installed into a temporary directory for the run, not into
your Jupyter.
"""
import os
import pathlib
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = pathlib.Path(__file__).parent

NOTEBOOKS = {
    "01-three-rules.ipynb": [
        ("md", """# Interaction nets in three rules

An *interaction net* is a graph of **agents**. Each agent has one **principal port**, through which it interacts, and some auxiliary ports. Where a wire joins two principal ports there is an **active pair**, and a rule replaces the pair by a small net. That is all a net can do.

This notebook uses the smallest interesting system, the *symmetric interaction combinators*: a constructor `con`, a duplicator `dup` and an eraser `era`. The kernel starts with their table loaded."""),
        ("code", "%table"),
        ("md", """A cell that is not a table or a command is a **net**, written as the right-hand side of a rule is. `con (a b)` is a node and stands for its principal port. A name used twice is a wire; a name used once is a free port, a loose end.

In the pictures, port 0 is the principal port, and an active pair is drawn thick and red.

## Two of a kind annihilate"""),
        ("code", "con (a b) = con (c d)"),
        ("md", "The two nodes are gone, and `a` is joined to `c` and `b` to `d`.\n\n## Two of different kinds copy each other"),
        ("code", "con (a b) = dup (c d)"),
        ("md", "One interaction, and each node has been copied by the other. This is how a net duplicates: one node at a time.\n\n## An eraser erases, and sends erasers on"),
        ("code", "era = con (a b)"),
        ("md", """## Putting them together

A duplicator copying a small tree of constructors whose leaves are erasers. Watch it round by round: every active pair in a round fires at once, as a parallel machine would do it."""),
        ("code", "%schedule rounds\n%trace on\ncon (con (era era) con (era era)) = dup (p q)"),
        ("md", """The duplicator went through the tree one node at a time, leaving `p` and `q` each with a copy.

The number of rounds is the net's **span**: the longest chain of interactions that must follow one another. The order in which pairs fire does not change the result or the number of interactions. That is a theorem about interaction nets; here it is on this net, with one pair fired at a time in two different orders."""),
        ("code", "%trace off\n%schedule stack\ncon (con (era era) con (era era)) = dup (p q)"),
        ("code", "%schedule queue\ncon (con (era era) con (era era)) = dup (p q)"),
    ],
    "02-a-system-of-your-own.ipynb": [
        ("md", """# A system of your own: adding numbers

A system is a **table**: agents, and a rule for each pair that can meet. This notebook builds one from nothing, for unary numbers: `zero`, `succ`, and addition.

Start with an empty table."""),
        ("code", "%system new"),
        ("md", """## Agents

Each port gets a sign: `+` for an output and `-` for an input, the principal port first.

- `zero` is a value: its one port is an output.
- `succ` is a value holding a number: an output, and an input for the number it is one more than.
- `add` is a consumer. Its principal port is an input, waiting for its first number. Then come an input for the second number and an output for the sum."""),
        ("code", "agent zero +\nagent succ + -\nagent add  - - +"),
        ("md", "The check complains, rightly: `add` can meet `zero` and `succ`, and there is no rule for either.\n\n## Rules\n\nZero plus `y` is `y`. One more than `x`, plus `y`, is one more than `x` plus `y`."),
        ("code", """rule add (y r) >< zero
  => r = y
  count add

rule add (y r) >< succ (x)
  => r = succ (s); x = add (y s)
  count add"""),
        ("md", """No problems. The check has confirmed that each rule keeps its pair's free ports, and that every wire a rule makes joins an output to an input. With that, the only principal ports that can ever meet are a consumer's and a value's, and each such pair has a rule.

It has *not* confirmed that the rules are the right ones. Only running them shows that.

## Two plus one"""),
        ("code", "%schedule rounds\n%trace on\nsucc (succ (zero)) = add (succ (zero) out)"),
        ("md", """`out` is joined to three `succ`s and a `zero`: three.

Each round had one active pair. Addition this way is sequential: `add` walks down its first number one `succ` at a time.

## A rule that is typed and wrong

Change the first rule so that zero plus `y` is zero: the other number is thrown away, which takes an eraser and its two rules. The check cannot know that this is not what addition means."""),
        ("code", "%system new\nagent zero +\nagent succ + -\nagent add  - - +\nagent era  -"),
        ("code", """rule add (y r) >< zero
  => r = zero; y = era
  count add

rule add (y r) >< succ (x)
  => r = succ (s); x = add (y s)
  count add

rule era >< zero
  => nothing
  count erase

rule era >< succ (x)
  => x = era
  count erase"""),
        ("code", "%trace off\nsucc (succ (zero)) = add (succ (zero) out)"),
        ("md", "No problems reported, and two plus one is two. Signs keep a system from getting stuck; they do not make it mean what you intended."),
    ],
    "03-one-term-three-ends.ipynb": [
        ("md", """# One term, three ends

The order of reduction does not change where a net ends up. It does decide **whether** it gets there.

This notebook uses the combinators S, K and I as agents (the `ski` table). A term is written in prefix form: a backtick applies the next term to the one after it. `K x y` reduces to `x`; `I x` to `x`; `S x y z` to `x z (y z)`.

Take `Ω`, which is ```` ```SII``SII ```` and reduces to itself without end, and the term `K I Ω`. `K` discards its second argument, so the term has the normal form `I`."""),
        ("code", "%demo"),
        ("md", "## By need\n\nFire only the pairs the answer depends on. `K` takes `I`, then discards `Ω`, and `Ω` is never touched."),
        ("code", "%ski ``KI```SII``SII"),
        ("md", "It stopped with active pairs left: `Ω` is still there, unreduced. What reduction by need reaches is a normal form of what the answer can reach, not of the whole net.\n\n## Every pair fired\n\nThis is what a machine without a strategy does. `Ω` runs although `K` is about to discard it, and the eraser cannot catch it, because an eraser acts on a finished value and `Ω` never finishes."),
        ("code", "%cap 300\n%ski ``KI```SII``SII --rounds"),
        ("md", "## Every pair fired, with the demand carried in the net\n\nThe `lazy` table makes an application inert until a demand, itself an agent, reaches it. Now every pair can be fired and only wanted work is done."),
        ("code", "%cap 10000\n%ski ``KI```SII``SII --lazy"),
        ("md", """## What that costs

The `lazy` table does not share work. Take a term that uses its argument twice, `S I I x`, where `x` takes six steps to evaluate.

By need, `x` is evaluated once and the result copied: nine contractions in all."""),
        ("code", "%ski ```SII```SKK```SKK```SKK0"),
        ("md", "By the `lazy` table, each use evaluates its own copy: fifteen, the same as ordinary term rewriting."),
        ("code", "%ski ```SII```SKK```SKK```SKK0 --lazy"),
        ("md", """Why not both? Because an agent can be reached only through its one principal port, a piece of net that waits to be asked cannot be woken from two sides. So in a net of agents with every pair fired, stopping when you should and sharing work pull against each other. The argument, and measurements on larger programs, are in [vine-aviary](https://github.com/sigilante/vine-aviary).

## Looking inside

The `ski` table can be used directly too. `S K K 0` as a net, by need for the free port `out`:"""),
        ("code", "%system ski\n%schedule need out\nS = app (K a); a = app (K b); b = app (atom 0 out)"),
    ],
}


def build():
    import inets_kernel.install
    with tempfile.TemporaryDirectory() as directory:
        inets_kernel.install.install(prefix=directory)
        os.environ["JUPYTER_PATH"] = os.path.join(directory, "share", "jupyter")
        for name, cells in NOTEBOOKS.items():
            nb = new_notebook(cells=[new_markdown_cell(text) if kind == "md" else new_code_cell(text) for kind, text in cells])
            nb.metadata["kernelspec"] = {"name": "inets", "display_name": "Interaction nets", "language": "inets"}
            nb.metadata["language_info"] = {"name": "inets"}
            NotebookClient(nb, kernel_name="inets", timeout=120).execute()
            for i, cell in enumerate(nb.cells):
                cell["id"] = f"cell-{i}"
                if cell.cell_type == "code":
                    for o in cell.outputs:
                        if o.output_type == "error":
                            sys.exit(f"{name}: a cell failed: {cell.source!r}: {o.evalue}")
            nbformat.write(nb, HERE / name)
            print("wrote", name, "with", sum(len(c.get("outputs", [])) for c in nb.cells), "outputs")


if __name__ == "__main__":
    build()
