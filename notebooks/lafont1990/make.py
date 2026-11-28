"""Writes interaction-nets.ipynb: a live companion to Lafont's "Interaction Nets" (POPL 1990).

    python notebooks/lafont1990/make.py

The tables are taken from inets-benchmarks (tables/lafont1990), whose rules were checked
against the paper; their opening comments are dropped. The prose is ours: the notebook
follows the paper's sections and cites it, but does not reprint it.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
TABLES = Path.home() / "Code/inets-benchmarks/tables/lafont1990"
DOI = "https://doi.org/10.1145/96709.96718"


def table_text(name):
    lines = (TABLES / name).read_text().splitlines()
    while lines and (lines[0].startswith("#") or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines).strip("\n")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n")}


def table_cell(var, name):
    return code(f'{var} = L.table("""\n{table_text(name)}\n""")')


cells = [
md(f"""
# Interaction nets, live

*A companion to Yves Lafont, "Interaction Nets", POPL 1990 ([doi:10.1145/96709.96718]({DOI})).*

In 1990 Lafont proposed a model of computation that is a kind of graph rewriting. A program
is a set of **agents**, joined by wires, and a handful of **rules** that say what happens
when two agents meet. Nothing else happens: there is no program counter, no global
memory, no evaluation order to choose. Every step is local, so any number of steps can
happen at once.

This notebook follows the paper section by section. Read the paper next to it: each
section here says which pages it covers. Here you get every system and figure from the paper
as something you can run, draw and change. The prose is ours; the paper is not
reprinted.

Run the cells in order (in JupyterLite, *Run ▸ Run All Cells*). The pictures are drawn as
Lafont drew his: an agent is an ellipse, and its **principal port** carries an arrowhead
pointing out along its wire. Two arrowheads tip to tip, ▼▲, mark a pair of agents about to
interact.
"""),
code("""
try:
    import inets
except ImportError:          # in JupyterLite: fetch inets from PyPI
    %pip install -q inets
    import inets

import livenet as L
print("inets", inets.__version__)
"""),
md("""
To see every picture as a photocopy from 1990, run `L.retro(True)`; `L.retro(False)`
turns it off again.
"""),

# ---------------------------------------------------------------------------------------
md("""
## 1. Principles of interaction

*The paper, pp. 95–96 and figures 1–5.*

A **net** is an undirected graph whose vertices are **agents**. Each agent has a **symbol**
(its name, like `Cons` or `Add`), and each symbol has a fixed number of **ports**. One port
of each agent is its **principal port**; the others are **auxiliary**. A wire joins two
ports. A port joined to nothing inside the net is a **free port**: the net's interface to
the outside world.

A **rule** rewrites two agents that are joined by their principal ports into a new net with
the same free ports. Lafont calls such a pair **alive**. He asks three things of rules:

1. **Linearity.** Each free port of the pair appears exactly once in what the pair becomes.
   Nothing is copied or thrown away by accident; copying and erasing must be done by agents.
2. **Binary interaction.** Agents interact only through their principal ports, and only in
   pairs.
3. **No ambiguity.** At most one rule for each pair of distinct symbols, and none for a
   symbol meeting itself.

### Lists

His first example is appending two lists. A list is `Cons (x u)`, an element `x` and the
rest `u`, or `Nil`. `Append` has its principal port on its first argument, and auxiliary
ports for the second argument and the result. Here is the table, in the format inets
reads: a line `agent Cons + - -` declares `Cons` with its principal port first. The signs say
which ports are outputs (`+`) and inputs (`-`); section 2 explains them. Each rule is
followed by Lafont's own way of writing it, as a comment.
"""),
table_cell("lists", "lists.rules"),
md("""
A rule drawn as Lafont draws it: the alive pair on the left, what it becomes on the right.
The free ports `v`, `w`, `x`, `u` are the same on both sides. The result `w` is on top, an
output; the inputs hang below.
"""),
code("""
L.rule(lists, "Append (v w) = Cons (x u)", "u = Append (v t); w = Cons (x t)")
"""),
code("""
L.rule(lists, "Append (v w) = Nil", "w = v")
"""),
md("""
A net is written as equations between ports. `Append (v r) = Cons (P a1)` says that an
`Append` whose auxiliary ports are `v` and `r` has its principal port joined to that of a
`Cons`. A name used twice is a wire, and a name used once is a free port. Here is
`[P, O] ++ [L]`, reduced one interaction at a time:
"""),
code("""
n = L.Net(lists, "Append (v r) = Cons (P a1); a1 = Cons (O Nil); v = Cons (L Nil)")
n.steps()
"""),
code("""
print(n)
"""),
md("""
The `Append` walks down the first list, one `Cons` per step, and becomes the `Nil` rule at the
end. It takes time linear in the first list and never looks at the second.

### Order does not matter

Because a rule only touches its own pair, and two alive pairs never share an agent, two
rules can never get in each other's way. Lafont's **Proposition 1** (strong confluence)
says that if a net can take two different steps, each can be completed by one more step to
the same net. So the order in which alive pairs are reduced changes nothing in the result,
nor the number of steps. inets can reduce newest pair first (`stack`), oldest first
(`queue`) or at random:
"""),
code("""
text = "Append (v r) = Cons (P a1); a1 = Cons (O a2); a2 = Cons (P Nil); v = Cons (L Nil)"
results = []
for order in ["stack", "queue", "random"]:
    n = L.Net(lists, text)
    print(order, end=": ")
    n.reduce(order)
    results.append(n)
print("all the same:", all(results[0].same(m) for m in results))
"""),
md("""
### Arithmetic: copying and erasing

Linearity means a rule cannot use a variable twice or drop it. Multiplication has to do
both: `S x × y = x × y + y` uses `y` twice, and `0 × y = 0` drops it. So Lafont adds an
agent `Dupl` that copies a number and an agent `Erase` that destroys one (his figure 1).
Numbers are unary: `0`, `S (0)`, `S (S (0))`, ….
"""),
table_cell("arith", "arith.rules"),
md("""
The rule for `S x × y`: the multiplication meets a successor, and becomes a multiplication by
`x`, an addition, and a `Dupl` that copies `y` for each of them.
"""),
code("""
L.rule(arith, "Mult (y z) = S (x)", "x = Mult (y1 w); w = Add (y2 z); y = Dupl (y1 y2)")
"""),
code("""
L.rule(arith, "Dupl (a b) = S (x)", "x = Dupl (p q); a = S (p); b = S (q)")
"""),
md("""
Now 2 × 2. The `Dupl` agents walk down the number they copy, and the `Erase` at the end
eats the copy nobody needs. Below are the first steps, then the rest:
"""),
code("""
n = L.Net(arith, "Mult (two z) = S (S (0)); two = S (S (0))")
n.steps(limit=6)
"""),
code("""
n.reduce()
n
"""),
md("""
### Maximum needs a helper

Some functions cannot be written with one agent. The maximum of two numbers would need to
look at both arguments at once, and an agent sees only what is on its principal port. So
`Max` looks at its first argument, and if that is a successor it hands over to a second
agent, `Aux`, which looks at the other argument (figure 2). The program has to choose
which argument to look at first. Lafont notes that this rules out functions like
"parallel or", which must answer as soon as either argument does.
"""),
code("""
L.rule(arith, "Max (y z) = S (x)", "y = Aux (x z)")
"""),
code("""
L.rule(arith, "Aux (x z) = S (y)", "x = Max (y t); z = S (t)")
"""),
code("""
n = L.Net(arith, "Max (one z) = S (S (0)); one = S (0)")
n.steps()
"""),
md("""
Try changing the numbers. `Max (two z) = S (0); two = S (S (0))` is max(1, 2).

### A computation that never ends

Lafont adds a fourth condition: a rule's right-hand side contains no alive pair. Every
step then fully finishes its own work. That does not make every computation finite. His
**turnstile** (figure 3) is one rule, `Turn` meeting `Stile`, whose result has exactly the
shape it started with. The table has no signs: the paper gives these agents no types.
"""),
table_cell("turnstile", "turnstile.rules"),
code("""
n = L.Net(turnstile, "Turn (s) = Stile; s = Stile")
n.steps(limit=4)
"""),
code("""
n.reduce(limit=1000)
print(n.same("Turn (s) = Stile; s = Stile"))
"""),
md("""
### Concatenation in constant time

Appending lists takes time proportional to the first list. Logic programmers know a trick:
a **difference-list** keeps a pointer to the hole at the end of the list, so another list
can be plugged straight in. In a net that pointer is just a wire. `Diff (x y)` holds the
front of a list `x` and the hole at its end `y`, and `D_append` plugs one into the other in two
steps, however long the lists are (figure 4).
"""),
table_cell("difflists", "difflists.rules"),
code("""
L.rule(difflists, "D_append (v w) = Diff (x y)", "w = Diff (x t); v = Open (t y)")
"""),
md("""
His example is `POP ++ L`. In the first list the last tail `b` is the hole, joined back to
`Diff`; in the second, `e` is.
"""),
code("""
n = L.Net(difflists, "D_append (d r) = Diff (a b); a = Cons (P a1); a1 = Cons (O a2); "
                     "a2 = Cons (P b); d = Diff (c e); c = Cons (L e)")
n.steps()
"""),
code("""
print(n)
"""),
md("""
### Parsing

The second example reads arithmetic written in Polish (prefix) notation, `+ 1 1`, from a
stream of symbols, and builds a tree (figure 5). The stream is a chain of agents, one per
symbol. `Parse` eats one symbol at a time. At a `+` it splits into two parsers, one for
each operand, the second waiting for the rest of the stream the first leaves behind. The
paper's stream symbols are `+` and `1`. inets's table reader does not take those as names
in rules, so here they are `plus` and `one`, and the tree is built of `Plus` and `One`.
"""),
table_cell("parse", "parse.rules"),
code("""
n = L.Net(parse, "Parse (u y) = plus (s1); s1 = one (s2); s2 = one (x)")
n.steps()
"""),
md("""
`u` is the tree `Plus (One One)`, and `y = x`: the rest of the stream, which was never read,
is passed on. Try `+ + 1 1 1`:
`Parse (u y) = plus (s1); s1 = plus (s2); s2 = one (s3); s3 = one (s4); s4 = one (x)`.

### How much can nets compute?

Everything: Lafont remarks that Turing machines and SK combinators are easy to simulate. inets
comes with a table for S, K and I. Here `S K K I`, which is `I`, reduces in a few steps:
"""),
code("""
from inets import ski
r = ski.run("```SKKI")
print(r.result.reason, r.result.interactions, "interactions:", ski.show(r.term))
"""),

# ---------------------------------------------------------------------------------------
md("""
## 2. A type discipline

*The paper, pp. 100–104 and figures 6–7.*

Should every pair of symbols have a rule? It makes no sense for `Cons` to meet `Nil`, or
`Parse` to meet `Append`. And the no-ambiguity condition already forbids a rule for a
symbol meeting itself. So Lafont limits which nets are allowed, by **types**.

Each port gets a type and a direction: an **output** (`list+`) or an **input** (`list-`).
A net is well typed if every wire joins an output to an input of the same type. Two agents
**match** if their principal ports have opposite directions. A symbol whose principal port
is an output, like `Cons`, is a **constructor**; one whose principal port is an input, like
`Append`, is a **destructor**. Calling one direction "input" is only a convention, and
the theory treats constructors and destructors exactly alike.

A new condition asks for **completeness**: a rule for each pair of matching symbols. With
it, a well-typed alive pair can always be reduced.

The `+` and `-` in the tables above are these directions, principal port first. inets
checks a table against them, but it does not know the paper's type names (`list`, `atom`,
`nat`). So it reports `Append` meeting an atom as a missing rule, which the paper's types
rule out:
"""),
code("""
lists.check()
"""),
code("""
arith.check()
"""),
md("""
### When a typed net stops

**Proposition 2** says why a well-typed net can stop. From any agent, follow principal
ports: from an agent go along its principal port to the next agent, and so on. Either you
reach a free port, and the net is simply waiting for its surroundings, or you come back
where you started. That second case is a **vicious circle**: a ring of agents, each with
its principal port facing an auxiliary port of the next. None of them can ever interact,
and in Lafont's words (**Proposition 3**), "A vicious circle stays forever."

Vicious circles can appear during a computation. Feed `Append`'s result back into its own
second argument, and append the list `P, O, P`:
"""),
code("""
n = L.Net(lists, "Append (k k) = Cons (P a1); a1 = Cons (O a2); a2 = Cons (P a3); a3 = Nil")
n.steps()
"""),
md("""
The list has become a ring. It is well typed and has no alive pair, and it never will.
The degenerate case is `Append (k k) = Nil`: one step leaves a loop of bare wire.
Lafont draws it as an empty circle. inets keeps no wire that touches no agent, so here the net simply
becomes empty:
"""),
code("""
n = L.Net(lists, "Append (k k) = Nil")
n.reduce()
print(repr(str(n)))
"""),
md("""
### Simple nets

Forbidding cycles is not an option: the difference-lists and the parser need them. Lafont
instead tells good cycles from bad ones. Each symbol's auxiliary ports are grouped into a
**partition**. Most symbols put each port in a group of its own; `Dupl` puts its two copies
in one group (`{nat+, nat+}`), and `Erase` has a single empty group (figure 6).

A net is **simple** if it can be built from nothing using four operations. You can start
from an empty net. You can link two free ports with a wire. You can cut, joining two
simple nets by one wire. And you can graft a new agent, joining it to simple nets, one for
each group of its partition. Adding a fifth operation, putting two nets side by side, gives
**semi-simple** nets. When each port is in a group of its own, a simple net is just a
connected net with no cycle (Proposition 4).

Then:

- a semi-simple net contains no vicious circle (Proposition 5);
- if every rule is simple, reduction keeps a net simple (Proposition 6). This is the
  cut-elimination theorem of linear logic, adapted.

So with simple rules, a simple net can never deadlock (Proposition 7). The last condition
he asks of rules is simplicity, and all the rules in the paper are simple, given the right
partitions.

inets marks `Dupl`'s grouping with the word `duplicator` on its `agent` line. It does not
check simplicity.

The vicious circle above came from a net that was not simple: `Append`'s two auxiliary ports
are in different groups, yet one wire joined them.
"""),

# ---------------------------------------------------------------------------------------
md("""
## 3. A programming language

*The paper, pp. 104–106 and figures 8–11.*

Lafont sketches a concrete language with three parts: a `type` declaration, a `symbol`
declaration giving each symbol's port types (principal port first, partitions in braces),
and the rules. His notation for rules takes practice. The `Append` rule for `Cons` is written

    Cons [x, Append(v, t)]  )(  Append [v, Cons(x, t)]

Each side of `)(` is one agent of the pair, and the brackets list what each of its auxiliary
ports is joined to after the interaction. Names are shared across the two sides. So the
`Cons`'s tail now goes into a new `Append (v, t)`, and the old `Append`'s result becomes a
new `Cons (x, t)`. In the inets format the same rule is

    rule Append (v w) >< Cons (x u)
      => u = Append (v t); w = Cons (x t)

The comments in the tables above give every rule in Lafont's notation.

He also says how to run such programs on an ordinary computer. Agents are cells,
wires are pointers, and the alive pairs wait on a stack. Since nothing is ever shared,
no garbage collector is needed. inets's default order, `stack`, is the same: it takes the newest
alive pair first.

His idea for input and output: a keyboard is an endless stream of agents, one per
character, much like the parser's stream above.
"""),

# ---------------------------------------------------------------------------------------
md("""
## 4. Conclusion, and linear logic

*The paper, pp. 106–107.*

Lafont places interaction nets among other ways of programming:
- **Functional programming.** Nets share its strong types and its results that do not depend on order. They drop its built-in asymmetry between a function's input and its output, which he finds at odds with parallelism and with interactive programs.
- **Logic programming.** The rules resemble clauses, the difference-lists especially.
- **Dataflow and process calculi.** The pictures look alike. As far as he knew, though, those systems had neither principal ports, which make nets deterministic, nor partitions, which keep them from deadlocking.

The appendix makes the link to **linear logic** precise. Interaction nets generalise
Girard's *proof nets* for its multiplicative fragment. Each symbol declaration is a logical
rule, and an interaction is a step of **cut elimination**. In multiplicative linear logic
everything reduces in linear time. Nets are far more dynamic, and the turnstile shows that
their types do not ensure termination.

### Where to go next

- Lafont, *Interaction Combinators* (Information and Computation, 1997): three agents and six
  rules that can simulate any interaction net. inets bundles them as `inets.bundled("combinators")`.
- [inets](https://github.com/sigilante/inets), the library used here, can also reduce by need and step in rounds.
- [inets-benchmarks](https://github.com/sigilante/inets-benchmarks): every net in this
  notebook, with its expected result, checked against inets.
"""),
]

for i, cell in enumerate(cells):
    cell["id"] = f"cell-{i}"
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
(HERE / "interaction-nets.ipynb").write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n")
print("wrote", HERE / "interaction-nets.ipynb")
