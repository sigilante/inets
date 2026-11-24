# inets

Interaction nets in Python: declare an interaction system as a table of rules, check the
table, and reduce nets by it under a schedule you choose.

It is a reference and a teaching tool. It is small, it has no dependencies, and it is not
fast. What it says about a system rests on checks of the table and on tests, not on proof.

## Install

Both packages are on PyPI and need Python 3.10 or later.

```sh
pip install inets            # the library and the `inets` command; no dependencies
inets demo
```

For notebooks, add the Jupyter kernel and tell Jupyter about it:

```sh
pip install inets-kernel jupyterlab             # the kernel brings in inets and ipykernel
python -m inets_kernel.install --sys-prefix     # into this Python environment; or --user
jupyter lab                                     # then choose "Interaction nets"
```

The kernel's pictures need [Graphviz](https://graphviz.org/download/)'s `dot` program
(`brew install graphviz`, `apt install graphviz`); without it a cell shows the Graphviz
text instead. `jupyter kernelspec uninstall inets` removes the kernel again.

From source, with the tests:

```sh
git clone https://github.com/sigilante/inets && cd inets
pip install -e '.[test]'
pytest
pip install -e './kernel[test]'                 # the kernel, if you want it
```

## One term, three ends

An *interaction net* is a graph of nodes, called agents. Each agent has one *principal
port*, through which it interacts, and some auxiliary ports. Where a wire joins two
principal ports there is an *active pair*, and a rule replaces the pair by a small net.
That is all a net can do.

The rules do not say which active pair to fire first. For rules that look at nothing but
their pair, the order does not matter to the result: every order that stops, stops at the
same net after the same number of interactions. That is a theorem about interaction nets,
which this package relies on and does not prove. What the order does decide is *whether*
the net stops. `inets demo` shows it on one term of the combinators S, K and I: `K I Ω`,
where `Ω` reduces to itself without end and `K` discards it.

```
ski table, by need: only the pairs the answer depends on
  answer I; 2 interactions, of which 1 contraction; stopped because: wanted; active pairs left: 2
ski table, every pair fired: Ω runs although K will discard it
  answer none: stopped at the cap of 300 interactions; 301 interactions, of which 149 contractions; stopped because: interactions; active pairs left: 3
lazy table, every pair fired: the demand is carried in the net, and no work is shared
  answer I; 18 interactions, of which 1 contraction; stopped because: normal; active pairs left: 0
```

Every run says why it stopped. `normal` means no active pair is left. `wanted` means
reduction by need has what it was asked for and has left other pairs alone: what it reaches
is a normal form of the part of the net the answer can reach, not of the net.

## A system is a table

This is a whole table, for the symmetric interaction combinators. It comes with the
package as `combinators`.

```
agent con 2      # a constructor: two auxiliary ports
agent dup 2      # a duplicator
agent era 0      # an eraser

rule con (a b) >< con (c d)        # two of a kind annihilate
  => a = c; b = d
  count annihilate

rule dup (a b) >< dup (c d)
  => a = c; b = d
  count annihilate

rule con (a b) >< dup (c d)        # two of different kinds copy each other
  => a = dup (p q); b = dup (r s); c = con (p r); d = con (q s)
  count commute

rule era >< con (a b)              # an eraser erases, and sends erasers on
  => a = era; b = era
  count erase

rule era >< dup (a b)
  => a = era; b = era
  count erase

rule era >< era
  => nothing
  count erase
```

In the right-hand side of a rule a letter bound on the left is the port that was joined
there, any other letter is a new wire and occurs exactly twice, and `dup (p q)` is a new
node standing for its principal port. `count` names the statistic the rule adds to.

A table may also give each port a sign, `+` for an output and `-` for an input, as the
tables for S, K and I do:

```
agent S2    + - -          # S x y: an output, and two inputs for x and y
agent app   - - +          # application: (function) (argument result)

rule app (z r) >< S2 (x y)
  => z = dup (p q); x = app (p f); y = app (q g); f = app (g r)
  count contract
```

The full format, with conditions, references to named nets and calls to a host, is in the
docstring of [`inets.system`](https://github.com/sigilante/inets/blob/master/src/inets/system.py).

```python
import inets

system = inets.bundled("combinators")      # or inets.System.load("a-table-of-yours.rules")
print(system.check())                      # [] if no problem was found

net = inets.Net(system)
a, b = net.free(), net.free()              # two free ports: loose ends to attach to or read from
net.wire(net.make("con", a, b), net.make("dup", net.make("era"), net.make("era")))
result = net.reduce()                      # or net.reduce_in_rounds(), or net.reduce_by_need(port)
print(result.reason, result.counts)        # normal {'commute': 1, 'erase': 2}
print(net.dot())                           # the net as Graphviz text
```

`net.make(agent, *ports, param=value)` makes a node, joins its auxiliary ports to the ports
given, and returns its principal port; `net.wire` joins two ports. A port is a node's
number and an index, 0 for the principal port. To read a result, follow a free port:
`net.link[port]` is the port it is joined to, and `net.kind[node]` and `net.param[node]`
say what is there. A table whose rules expand named nets or call functions needs a host:
`inets.Net(system, inets.Library({name: build}))` supplies named nets, and a subclass of
`inets.Host` supplies functions.

## What checking a table means

`system.check()`, or `inets check TABLE`, reports each problem as a sentence. For any
table:

- a rule with no body or no count, or one that uses a parameter or a port it does not
  have, gives an agent a parameter it does not take, or names two ports with one letter;
- a rule whose right-hand side does not use every auxiliary port of its pair exactly once,
  or leaves a port of a new node unjoined: the net it makes must have the pair's free
  ports;
- a rule that can never apply, because an earlier one for the same pair always does;
- a pair whose rules have conditions that cannot be seen to cover every case (end with
  `otherwise`);
- a test of a neighbour on a port or of an agent that does not exist, and an `expand` of
  an agent that has auxiliary ports.

For a table without signs, also: a pair of agents with no rule.

For a table with signs, also: an agent without them; a rule not written consumer `><`
value (a consumer's principal port is an input, a value's an output); a consumer and value
with no rule, or a rule between two values or two consumers; and a rule that joins two
outputs or two inputs. If no rule does that, a net whose wires each join an output to an
input stays that way, so the only principal ports that can meet are a consumer's and a
value's, and each such pair has a rule.

It does not decide whether a system terminates, and it does not show that a rule is the
one intended: S with its arguments exchanged passes every check. `inets rules TABLE` marks
each rule that is *not* a local rule: one that looks at a neighbour, expands a named net,
calls the host, or keeps one of its pair. The theorem about order is for local rules.

## Three schedules

| Method | Fires | Needs | Stops with |
|---|---|---|---|
| `net.reduce(order=...)` | one active pair at a time: `"stack"` (newest first), `"queue"` (oldest first) or `"random"` | any table | `normal` |
| `net.reduce_in_rounds()` | every active pair, round by round | any table | `normal`, with the number of rounds and the widest round |
| `net.reduce_by_need(port)` | only the pairs that the value wanted at `port` depends on | a table with signs | `wanted`, with the active pairs it left |

Each takes `max_interactions` and stops with `interactions` if it gets there; a run in
rounds looks at the cap between rounds, so it may pass it by less than a round. The number
of rounds is the net's span: the longest chain of interactions that must follow one
another. A result's counts are for that run. Any schedule raises `inets.Stuck` at a pair
no rule applies to; reduction by need raises it too if the value wanted depends on a free
port.

Reduction by need never fires the pairs that would erase what is no longer wanted. So that
a long run does not fill up, it sweeps the net when it passes 20,000 nodes, and again each
time the net reaches twice the size the last sweep left (`sweep_above` sets the figure):
`net.sweep(ports)` keeps what those ports can reach and removes the rest. Sweeping needs a
table with exactly one eraser, an agent whose only port is an input; without one,
`net.sweep` raises an error and reduction by need goes on unswept. `deep=False` stops
reduction by need as soon as the value wanted is a value, its own inputs not asked for.

## The tables that come with it

| `inets.bundled(...)` | What | Agents, rules |
|---|---|---|
| `"combinators"` | The symmetric interaction combinators: a constructor, a duplicator, an eraser | 3, 6 |
| `"ski"` | The combinators S, K and I as agents, with signs. An application fires as soon as its function is a value | 12, 27 |
| `"lazy"` | The same with the demand for evaluation carried by agents in the net, so that every pair can be fired and only wanted work is done; no work is shared | 15, 50 |
| `"ivm"` | The interaction system of the IVM, the machine that runs [Vine](https://github.com/VineLang/vine), read from its source | 5, 20 |

[`inets.ski`](https://github.com/sigilante/inets/blob/master/src/inets/ski.py) reads and writes terms of S, K and I, builds them as nets,
names their subterms as references to nets, and reduces them in the three ways of the demo
(`inets run ski TERM`, with `--rounds` or `--lazy`, and `--dot` to print the net that is
left as Graphviz text):

```python
from inets import ski
run = ski.run("```SII0")                   # S I I 0, by need
ski.show(run.term), run.result.counts       # ('`00', {'collect': 3, 'contract': 3, 'copy': 1})
```

[`inets.ivm`](https://github.com/sigilante/inets/blob/master/src/inets/ivm.py) runs programs written in Ivy, Vine's text for nets, by the
`ivm` table (`inets run ivm FILE.iv`). For the thirteen programs in `tests/ivm`, the tests
hold it, in three orders of reduction, to the output, the six interaction counts and the
error flags that `ivm run` gave when they were recorded; with `IVM` set they compare
output and counts with the binary directly. Six programs compiled from Vine's own
examples, and the IVM's example `hi.iv`, agreed in the same way in a run that is not kept
here and cannot be repeated from this repository. It supplies twenty extrinsic functions (N32 arithmetic and comparison, the IVM's
branch, `print_char`, and the IO value's split and merge) and stops at any other.

[`inets.ivy`](https://github.com/sigilante/inets/blob/master/src/inets/ivy.py) reads Ivy text for any system.

`inets --help` lists the commands.

## In a notebook

[`kernel/`](https://github.com/sigilante/inets/tree/master/kernel) is a second small package, `inets-kernel`: a Jupyter kernel in which a
cell is a table, a net, or a command. A net is written as the right-hand side of a rule
is, and is drawn before and after it is reduced, with the active pairs marked.

It is installed as above; `jupyter lab notebooks/` in a copy of the repository opens the
notebooks.

[`notebooks/`](https://github.com/sigilante/inets/tree/master/notebooks) has three to start from: the three rules of the combinators;
building a system of your own, for adding numbers; and one term reaching three ends. They
are written and run by `notebooks/make.py`, so what they show is what the kernel gives.
The pictures need Graphviz's `dot`.

## Tests

```sh
pytest                              # about ten seconds; 13 tests are skipped unless IVM is set
IVM=/path/to/ivm pytest             # also compares with an ivm binary directly
```

The tests cover the checks on the bundled tables and on deliberately broken ones; small
nets of the combinators, with one net reduced in every order; the Ivy reader; the command
line; the IVM programs against counts recorded from `ivm run` (VineLang/vine at commit
`cf0c325`); and a census of S, K and I. The census takes every term up to size 5 (size 4
with two atoms) that has a normal form by ordinary term rewriting within its caps. By need
and by the `lazy` table each reaches that normal form, the `lazy` table in exactly as many
contractions as rewriting takes steps and by need in no more. With every pair fired, the
`ski` table reaches it or runs into the cap.

## What it is not

- **Fast.** A net is Python dictionaries: roughly a hundred thousand interactions a
  second, measured by hand on one laptop.
- **A language.** There is a table format and a Python interface, and nothing above them.
- **A proof.** Checks and tests.
- **Complete for the IVM.** Memory, depth, workers and most extrinsic functions are left
  out.

## Where it comes from

The tables, the checks and the machine were worked out in
[vine-aviary](https://github.com/sigilante/vine-aviary), which has the measurements behind
the `ski` and `lazy` tables and the argument for why a net of agents cannot both stop when
it should and share work. This package is that code made general. It does not yet replace
it: vine-aviary's own machine also removes a duplicator that has lost one of its copies,
where this one gives the lost copy to an eraser, so its counts of copies under reduction
by need should be lower than this package's (the two have not been compared).

## Licence

MIT. See [LICENSE](https://github.com/sigilante/inets/blob/master/LICENSE).
