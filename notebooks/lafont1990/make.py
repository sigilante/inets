"""Writes interaction-nets.ipynb: a live companion to Lafont's "Interaction Nets" (POPL 1990).

    python notebooks/lafont1990/make.py

The tables are taken from inets-benchmarks (tables/lafont1990), whose rules were checked
against the paper. Their opening comments, and the comments that give each rule in the
paper's own notation, are dropped. The prose is ours: the notebook follows the paper's
sections and cites them, but does not reprint the paper.
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
    lines = [l for l in lines if not (l.startswith("#") and ")(" in l)]
    return "\n".join(lines).strip("\n")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n")}


def table_cell(var, name):
    return code(f'{var} = L.table("""\n{table_text(name)}\n""")')


TURNSTILE = """\
agent Turn  - -
agent Stile +

rule Turn (x) >< Stile
  => x = Turn (s); s = Stile
  count turn"""

cells = [
md(f"""
# Interaction nets, live

*A companion to Yves Lafont, "Interaction Nets", POPL 1990 ([doi:10.1145/96709.96718]({DOI})).*

In 1990 Lafont proposed a model of computation that is a kind of graph rewriting. A program
is a set of **agents** joined by wires, together with a handful of **rules** that say what
happens when two agents meet. Nothing else happens: there is no program counter, no global
memory, and no evaluation order to choose. Every step is local, so independent steps can
happen at the same time.

This notebook follows the paper section by section, and each section names the pages it
covers. Read the two side by side. The paper's systems and examples appear here as nets you
can run, draw and change. The prose is ours, and the paper is not reprinted.

Run the cells in order (in JupyterLite, *Run ▸ Run All Cells*). The pictures are drawn as
Lafont drew his. An agent is an ellipse, and its **principal port** carries an arrowhead
pointing out along its wire. Two arrowheads tip to tip, ▼▲, mark two agents about to
interact.
"""),
code("""
try:
    import inets
except ImportError:          # in JupyterLite: fetch inets from PyPI
    %pip install -q "inets>=0.1.3,<0.2"
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

*The paper, pp. 95–100, and figures 1–5.*

A **net** is a graph whose vertices are **agents**. Each agent has a **symbol**, its name
(`Cons` or `Add`, say), and each symbol has a fixed number of **ports**. One port of each
agent is its **principal port**; the others are **auxiliary**. A wire joins two ports. A
port joined to nothing inside the net is a **free port**, and the free ports are the net's
connections to the outside.

Two agents joined by their principal ports form an **alive pair**. A **rule** rewrites an
alive pair into a new net with the same free ports. Lafont asks three things of rules, and
adds a fourth below:

1. **Linearity.** Each free port of the pair appears exactly once in what the pair becomes.
   A rule never copies or drops anything by itself; agents must do any copying or erasing.
2. **Binary interaction.** Agents interact only through their principal ports, and only in
   pairs.
3. **No ambiguity.** Each pair of different symbols has at most one rule, and no symbol has
   a rule for meeting itself.

### Lists

His first example appends two lists. A list is either `Cons (x u)`, an element `x` followed
by the rest `u`, or `Nil`. `Append` takes its first argument on its principal port; its
auxiliary ports are the second argument and the result.

Below is the table in the format inets reads. The line `agent Cons + - -` declares `Cons`
with three ports, principal port first. Ignore the signs for now; section 2 explains them.
"""),
table_cell("lists", "lists.rules"),
md("""
A rule drawn as Lafont draws it: the alive pair on the left, what it becomes on the right.
The free ports `v`, `w`, `x`, `u` are the same on both sides. The result `w` is on top; the
inputs hang below.
"""),
code("""
L.rule(lists, "Append (v w) = Cons (x u)", "u = Append (v t); w = Cons (x t)")
"""),
code("""
L.rule(lists, "Append (v w) = Nil", "w = v")
"""),
md("""
A net is written as equations between ports. `Append (v r) = Cons (P a1)` says that an
`Append` with auxiliary ports `v` and `r` has its principal port joined to that of a `Cons`.
A name used twice is a wire, and a name used once is a free port. Here is `[P, O] ++ [L]`,
reduced one interaction at a time:
"""),
code("""
n = L.Net(lists, "Append (v r) = Cons (P a1); a1 = Cons (O Nil); v = Cons (L Nil)")
n.steps()
"""),
code("""
print(n)
"""),
md("""
The `Append` walks down the first list, one `Cons` per step, and meets the `Nil` at the end.
The time it takes grows with the first list, and it never looks at the second.

### Arithmetic: copying and erasing

Linearity means a rule cannot use anything twice or drop it. Multiplication has to do both:
`S x × y = x × y + y` uses `y` twice, and `0 × y = 0` drops it. So Lafont adds an agent
`Dupl` that copies a number and an agent `Erase` that destroys one (his figure 1). Numbers
are unary: `0`, `S (0)`, `S (S (0))`, and so on.
"""),
table_cell("arith", "arith.rules"),
md("""
The rule for `S x × y`. The multiplication meets a successor and becomes three agents: a
multiplication by `x`, an addition, and a `Dupl` that copies `y` for the two of them.
"""),
code("""
L.rule(arith, "Mult (y z) = S (x)", "x = Mult (y1 w); w = Add (y2 z); y = Dupl (y1 y2)")
"""),
code("""
L.rule(arith, "Dupl (a b) = S (x)", "x = Dupl (p q); a = S (p); b = S (q)")
"""),
md("""
Now 2 × 2. The `Dupl` agents walk down the number they copy, and an `Erase` at the end eats
the copy nobody needs. First the opening steps, then the rest:
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
### Order does not matter

A rule touches only its own pair, and two alive pairs never share an agent, so rules never
interfere. Lafont's **Proposition 1** (strong confluence) says that if a net can take two
different steps, each result can take one more step to reach the same net. It follows that
for a net that finishes, the order of reduction changes neither the result nor the number
of steps.

The 2 × 2 net above has up to three alive pairs at once. inets can reduce the newest pair
first (`stack`), the oldest first (`queue`), or pairs at random:
"""),
code("""
text = "Mult (two z) = S (S (0)); two = S (S (0))"
results = []
for order, seed in [("stack", 0), ("queue", 0), ("random", 1), ("random", 2), ("random", 3)]:
    n = L.Net(arith, text)
    print(order, seed, end=": ")
    n.reduce(order, seed=seed)
    results.append(n)
print("all the same:", all(results[0].same(m) for m in results))
"""),
md("""
### Maximum needs a helper

Some functions cannot be written with one agent. The maximum of two numbers would have to
look at both arguments at once, but an agent sees only what is on its principal port. So
`Max` looks at its first argument, and if that is a successor it hands over to a second
agent, `Aux`, which looks at the other argument (figure 2). The program has to choose which
argument to look at first. Lafont notes that this rules out functions like "parallel or",
which must answer as soon as either argument does.
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
Try changing the numbers: `Max (two z) = S (0); two = S (S (0))` is max(1, 2).

### A computation that never ends

Lafont adds a fourth condition on rules: a rule's right-hand side contains no alive pair, so
no step leaves an interaction of its own undone. That still does not make every computation
finite. His **turnstile** (figure 3) has one rule, `Turn` meeting `Stile`, and a net of one
`Turn` and two `Stile`s comes out of that rule unchanged.

The paper gives these two agents no types. They can be given some, though: `Stile` an
output, and `Turn` an input on both its ports. We use those signs here, and the table
passes inets's check.
"""),
code(f'turnstile = L.table("""\n{TURNSTILE}\n""")\nturnstile.check()'),
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

Appending lists takes time that grows with the first list. Logic programmers know a trick: a
**difference-list** keeps a pointer to the hole at the end of the list, so you can plug
another list straight in. In a net that pointer is just a wire. `Diff (x y)` holds the front
of a list, `x`, and the hole at its end, `y`. `D_append` plugs one difference-list into
another in two steps, however long the lists are (figure 4).
"""),
table_cell("difflists", "difflists.rules"),
code("""
L.rule(difflists, "D_append (v w) = Diff (x y)", "w = Diff (x t); v = Open (t y)")
"""),
md("""
His example is `POP ++ L`. In the first list the last tail, `b`, is the hole, joined back to
its `Diff`; in the second list the hole is `e`.
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

The second example reads arithmetic written in Polish (prefix) notation, such as `+ 1 1`,
from a stream of symbols, and builds a tree (figure 5). The stream is a chain of agents, one
per symbol. `Parse` eats one symbol at a time. At a `+` it splits into two parsers, one for
each operand; the second waits for whatever stream the first leaves behind. inets's table
reader does not accept `+` and `1` as agent names, so here the stream's symbols are `plus`
and `one`, and the tree is built of `Plus` and `One`.
"""),
table_cell("parse", "parse.rules"),
code("""
n = L.Net(parse, "Parse (u y) = plus (s1); s1 = one (s2); s2 = one (x)")
n.steps()
"""),
md("""
`u` is now the tree `Plus (One One)`, and `y = x`: the rest of the stream, never read, is
passed on. Try `+ + 1 1 1`:
`Parse (u y) = plus (s1); s1 = plus (s2); s2 = one (s3); s3 = one (s4); s4 = one (x)`.

### How much can nets compute?

Lafont remarks that Turing machines and SK combinators are easily simulated. inets comes with
a table of its own for the combinators S, K and I; it is not from the paper. `ski.run`
takes a term in prefix form, where a backtick applies the term after it to the one after
that, so ``` ```SKKI ``` is `((S K) K) I`. It reduces by need, doing only the work the answer
requires, and reports `wanted` when the answer is complete. `S K K I` is `I`:
"""),
code("""
from inets import ski
r = ski.run("```SKKI")
print(r.result.reason, r.result.interactions, "interactions:", ski.show(r.term))
"""),

# ---------------------------------------------------------------------------------------
md("""
## 2. A type discipline

*The paper, pp. 100–104, and figures 6–7.*

Not every pair of symbols should have a rule: `Cons` and `Nil` have nothing to do with each
other. Lafont limits which agents may meet by giving their ports **types**.

Each port has a type and a direction: an **output** (`list+`) or an **input** (`list-`). A
net is well typed if every wire joins an output to an input of the same type. Two symbols
**match** if their principal ports have opposite directions. A symbol whose principal port
is an output, like `Cons`, is a **constructor**; one whose principal port is an input, like
`Append`, is a **destructor**. Which direction to call "input" is a convention, and nothing
in the theory favours constructors over destructors.

Lafont then asks for **completeness**: a rule for each pair of matching symbols. With it, a
well-typed alive pair can always be reduced.

The `+` and `-` in the tables above are these directions, principal port first. inets
checks a table against them, but it does not know the paper's type names (`list`, `atom`,
`nat`). So it reports `Append` meeting an atom as a missing rule, a meeting that the paper's
types rule out:
"""),
code("""
lists.check()
"""),
code("""
arith.check()
"""),
md("""
### When a typed net stops

**Proposition 2** describes how a net can come to a stop. Take a well-typed, finite,
nonempty net in which no rule applies. Start at any agent and follow principal ports, from
agent to agent. Either you reach a free port, and the net is waiting for its surroundings,
or you come back to where you started.

The second case is a **vicious circle**: a ring of agents, each with its principal port
facing an auxiliary port of the next. No agent in it can ever interact. In Lafont's words
(**Proposition 3**), "A vicious circle stays forever."

Vicious circles can appear during a computation. Feed `Append`'s result back into its own
second argument, and append the list `P, O, P`:
"""),
code("""
n = L.Net(lists, "Append (k k) = Cons (P a1); a1 = Cons (O a2); a2 = Cons (P a3); a3 = Nil")
n.steps()
"""),
md("""
The list has become a ring. It is well typed and has no alive pair, and it never will. The
degenerate case is `Append (k k) = Nil`: one step leaves a loop of bare wire, which Lafont
draws as an empty circle. inets does not represent a wire with no agents, so here the net
becomes empty:
"""),
code("""
n = L.Net(lists, "Append (k k) = Nil")
n.reduce()
print(repr(str(n)))
"""),
md("""
### Simple nets

Forbidding cycles is no answer, because the difference-lists and the parser need them.
Lafont instead tells good cycles from bad ones. Each symbol's auxiliary ports are divided
into groups, a **partition**. Most symbols put each port in a group of its own. `Dupl` puts
its two copies in one group, and `Erase` has a single empty group (p. 102); `Diff` and
`Parse` also put their two auxiliary ports together (figure 6).

A net is **simple** if it can be built using only three operations: *link*, a single wire;
*cut*, joining two simple nets by one wire; and *graft*, joining a new agent to simple nets,
one for each group of its partition. Allowing two more operations, the empty net and
putting two nets side by side, gives the larger class of **semi-simple** nets. When every
port is in a group of its own, a simple net is a connected net with no cycle, and a
semi-simple net is one with no cycle (Proposition 4).

Then:

- a semi-simple net contains no vicious circle (Proposition 5);
- if every rule is simple, reduction keeps a net simple (Proposition 6). Lafont describes
  this as essentially the cut-elimination theorem of multiplicative linear logic, adapted.

So a last condition asks that rules be simple, and then a simple net never deadlocks
(Proposition 7). With suitable partitions, every rule in the paper is simple.

The vicious circle above came from a net that was not simple: `Append`'s two auxiliary ports
are in different groups, yet one wire joined them. inets records no partitions and does not
check simplicity.
"""),

# ---------------------------------------------------------------------------------------
md("""
## 3. A programming language

*The paper, pp. 104–106, and figures 8–11.*

Lafont sketches a concrete language in three parts. A `type` declaration lists the types,
a `symbol` declaration gives each symbol's port types (principal port first, partitions in
braces), and then come the rules. In his notation the `Append` rule for `Cons` is

    Cons [x, Append(v, t)]  )(  Append [v, Cons(x, t)]

Each side of `)(` is one agent of the pair. Its brackets list what each of its auxiliary
ports is joined to after the interaction, and names are shared across the two sides. So the
`Cons`'s tail now feeds a new `Append (v, t)`, and the old `Append`'s result becomes a new
`Cons (x, t)`. In the inets format the same rule is

    rule Append (v w) >< Cons (x u)
      => u = Append (v t); w = Cons (x t)
      count append

where `count` names the rule in the tallies inets keeps.

He also says how to run such programs on an ordinary computer: agents are cells, wires are
pointers, and the alive pairs wait on a stack. Since no agent is ever shared, no garbage
collector is needed. inets's default order, `stack`, does the same: it takes the newest
alive pair first.

For input and output, he suggests treating a keyboard as an endless stream of agents, one
per character, much like the parser's stream above.
"""),

# ---------------------------------------------------------------------------------------
md("""
## 4. Conclusion, and linear logic

*The paper, pp. 107–108.*

Lafont compares interaction nets with other ways of programming:

- **Functional programming.** Nets keep its strong types and its determinism. They give up
  the fixed roles of a function's argument and result, which he sees as a poor fit for
  parallel and interactive programs.
- **Logic programming.** The rules recall clauses, the difference-lists especially.
- **Dataflow and process calculi.** He notes some similarities with dataflow languages and
  with CCS and CSP. As far as he knew, though, none of them had principal ports, which make
  nets deterministic, or semi-simplicity, which prevents deadlock.

The appendix relates nets to **linear logic**. From its first page the paper presents nets
as a generalisation of Girard's *proof nets*. The appendix shows that each symbol declaration
acts as a logical rule and that interaction is cut elimination. Nets generalise the
multiplicative fragment of linear logic, in which everything reduces in linear time. Their
types, unlike that fragment, do not ensure termination: the typed turnstile above never
stops.

### Where to go next

- Lafont, *Interaction Combinators* (Information and Computation, 1997): three agents and six
  rules that can simulate any interaction net. inets bundles them as `inets.bundled("combinators")`.
- [inets](https://github.com/sigilante/inets), the library used here. It can also reduce by
  need and step in rounds.
- [inets-benchmarks](https://github.com/sigilante/inets-benchmarks): the nets of this
  notebook with their expected results, checked against inets.
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
