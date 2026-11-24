# inets-kernel

A Jupyter kernel for interaction nets, built on [inets](https://github.com/sigilante/inets).
Write a table of rules, draw a net, and watch it reduce.

```sh
pip install inets-kernel
python -m inets_kernel.install --sys-prefix     # into this Python environment; or --user
jupyter lab
```

Choose "Interaction nets" for a notebook. `jupyter kernelspec uninstall inets` removes the
kernel again. The pictures need Graphviz's `dot` program; without it a cell shows the
Graphviz text instead.

## A cell is one of three things

**A net.** Equations between ports, written as the right-hand side of a rule is:

```
con (a b) = dup (era era)
```

`con (a b)` is a node and stands for its principal port. A name that is not an agent is a
wire if it occurs twice and a free port if it occurs once. An agent with a parameter takes
it after its name, as in `atom 3`. The net is drawn, reduced by the current schedule, and
drawn again, with why it stopped and what it cost. The kernel starts with the table of the
symmetric interaction combinators (`con`, `dup`, `era`).

**A table.** Lines beginning `agent` or `rule` are added to the current table, in
[the format of `inets`](https://github.com/sigilante/inets/blob/master/src/inets/system.py),
and the table is checked:

```
agent zero +
agent succ + -
agent add  - - +

rule add (y r) >< zero
  => r = y
  count add
```

**Commands**, one to a line:

| Command | Does |
|---|---|
| `%system NAME` | start from a bundled table (`combinators`, `ski`, `lazy`), or `new` for none |
| `%table`, `%check`, `%rules` | show the current table; check it; list its rules, marking those that are not local |
| `%schedule HOW` | `stack` (the default), `queue`, `random`, `rounds`, or `need PORT`: by need for the free port named PORT (default `out`), in a table with signs |
| `%cap N` | stop a run after N interactions (default 10000) |
| `%trace on` / `off` | with `rounds`, draw the net after each round, up to twelve |
| `%ski TERM [--rounds \| --lazy]` | reduce a term of S, K and I in prefix form, by need unless said |
| `%demo` | one term, K I Ω, reduced three ways |
| `%help` | this list |

A net of more than 80 nodes is described, not drawn.

## Notebooks

Three are in [`notebooks/`](https://github.com/sigilante/inets/tree/master/notebooks) of the
repository: the three rules of the combinators; a system of your own, for adding numbers;
and one term reaching three ends.

## Tests

```sh
pip install -e '.[test]'      # in kernel/, with inets installed
pytest
```

The tests run what a cell means without Jupyter, and one notebook through the kernel
itself.

## Licence

MIT.
