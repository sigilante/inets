# inets

Interaction nets in Python: declare an interaction system as a table of rules, check the
table, and reduce nets by it under a schedule you choose.

It is a reference and a teaching tool. It is small, it has no dependencies, and it is not
fast. What it says about a system rests on tests and on checks of the table, not on proof.

```sh
git clone https://github.com/sigilante/inets && cd inets
pip install -e .        # Python 3.10 or later; not on PyPI
inets demo
```

## One term, three ends

An *interaction net* is a graph of nodes, called agents. Each agent has one *principal
port*, through which it interacts, and some auxiliary ports. Where a wire joins two
principal ports there is an *active pair*, and a rule replaces the pair by a small net.
That is all a net can do.

The rules do not say which active pair to fire first, and for local rules it does not
matter to the result: every order that stops, stops at the same net after the same number
of interactions. What the order decides is *whether* it stops. `inets demo` shows it on one
term of the combinators S, K and I: `K I Ω`, where `Ω` reduces to itself without end and
`K` discards it.

```
ski table, by need: only the pairs the answer depends on
  answer I; 2 interactions, of which 1 contractions; stopped because: wanted; active pairs left: 2
ski table, every pair fired: Ω runs although K will discard it
  answer none: stopped at the cap of 300 interactions; 301 interactions, of which 149 contractions; stopped because: interactions; active pairs left: 3
lazy table, every pair fired: the demand is carried in the net, and no work is shared
  answer I; 18 interactions, of which 1 contractions; stopped because: normal; active pairs left: 0
```

Every run says why it stopped. `normal` means no active pair is left. `wanted` means
reduction by need has what it was asked for and has left other pairs alone: what it reaches
is a normal form of the part of the net the answer can reach, not of the net.

## A system is a table

```
agent con 2      # a constructor: two auxiliary ports
agent dup 2      # a duplicator
agent era 0      # an eraser

rule con (a b) >< con (c d)
  => a = c; b = d
  count annihilate

rule con (a b) >< dup (c d)
  => a = dup (p q); b = dup (r s); c = con (p r); d = con (q s)
  count commute
```

That is part of the table for the symmetric interaction combinators, which comes with the
package. In the right-hand side of a rule a letter bound on the left is the port that was
joined there, any other letter is a new wire and occurs exactly twice, and `dup (p q)` is a
new node standing for its principal port. `count` names the statistic the rule adds to.

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
docstring of [`inets.system`](src/inets/system.py).

```python
import inets

system = inets.load("my.rules")          # or inets.bundled("combinators")
print(inets.check(system))               # [] if no problem was found

net = inets.Net(system)
a, b = net.free(), net.free()            # two free ports
net.wire(net.node("con", a, b), net.node("dup", net.node("era"), net.node("era")))
result = net.reduce()                    # or net.rounds(), or net.by_need(port)
print(result.reason, result.counts)      # normal {'commute': 1, 'erase': 2}
print(net.dot())                         # the net as Graphviz text
```

## What checking a table means

`inets.check` (or `inets check TABLE`) looks for these, and reports each as a sentence:

- a rule that does not use every auxiliary port of its pair exactly once, or that leaves a
  port of a new node unjoined: the net it makes must have the pair's free ports;
- a pair of agents with no rule;
- several rules for one pair whose conditions may leave a case out;
- in a table with signs, a rule that joins two outputs or two inputs. If no rule does, a
  net whose wires each join an output to an input keeps that property, so the only
  principal ports that can meet are an output's and an input's, and each such pair has a
  rule.

It does not decide whether a system terminates, and it does not show that a rule is the
right one: S with its arguments exchanged passes every check. For local rules, that the
order of reduction does not matter is a theorem about interaction nets and is not checked
here. `inets rules TABLE` marks each rule that is *not* local in that sense: one that looks
at a neighbour, expands a named net, calls the host, or keeps one of its pair.

## Three schedules

| Method | Fires | Needs | Says when it stops |
|---|---|---|---|
| `net.reduce(order=...)` | one active pair at a time: newest first, oldest first, or at random | any table | `normal` |
| `net.rounds()` | every active pair, round by round | any table | `normal`, with the number of rounds and the widest round |
| `net.by_need(port)` | only the pairs that the value wanted at `port` depends on | a table with signs | `wanted`, with the active pairs it left |

The number of rounds is the net's span: the longest chain of interactions that must follow
one another. Each schedule takes caps on interactions and on nodes and reports which it
hit. Reduction by need never fires the pairs that would erase what is no longer wanted;
`net.sweep` removes what a port cannot reach.

## The tables that come with it

| `inets.bundled(...)` | What | Agents, rules |
|---|---|---|
| `"combinators"` | The symmetric interaction combinators: a constructor, a duplicator, an eraser | 3, 6 |
| `"ski"` | The combinators S, K and I as agents, with signs. An application fires as soon as its function is a value | 12, 27 |
| `"lazy"` | The same with the demand for evaluation carried by agents in the net, so that every pair can be fired and only wanted work is done; no work is shared | 15, 50 |
| `"ivm"` | The interaction system of the IVM, the machine that runs [Vine](https://github.com/VineLang/vine), read from its source | 5, 20 |

[`inets.ski`](src/inets/ski.py) reads and writes terms of S, K and I, builds them as nets,
names their subterms as references, and reduces them in the three ways of the demo:

```python
from inets import ski
run = ski.run("```SII0")                  # S I I 0, by need
ski.show(run.term), run.result.counts      # ('`00', {'collect': 3, 'contract': 3, 'copy': 1})
```

[`inets.ivm`](src/inets/ivm.py) runs programs written in Ivy, Vine's text for nets, by the
`ivm` table (`inets ivm FILE.iv`). On the twelve programs in `tests/ivm`, in three orders of
reduction, it prints what `ivm run` prints and agrees with it on each of the IVM's six
interaction counts and on its error flags; the same held, in a run that is not kept, for
six of Vine's own examples compiled to Ivy. It supplies twenty of the IVM's extrinsic
functions and stops at any other.

[`inets.ivy`](src/inets/ivy.py) reads and writes Ivy text for any system.

## Tests

```sh
pip install pytest
pytest                              # about fifteen seconds
IVM=/path/to/ivm pytest             # also compares with an ivm binary directly
```

The tests cover the checks on the bundled tables and on deliberately broken ones; small
nets of the combinators; every term of S, K and I up to size 5 against ordinary term
rewriting, in each of the three ways and with named subterms; and the IVM programs against
counts recorded from `ivm run` (VineLang/vine at commit `cf0c325`).

## What it is not

- **Fast.** A net is Python dictionaries. Tens of thousands of interactions a second.
- **A language.** There is a table format and a Python interface, and nothing above them.
- **A proof.** Checks and tests.
- **Complete for the IVM.** Memory, depth, workers and most extrinsic functions are left
  out.

## Where it comes from

The tables, the checks and the machine were worked out in
[vine-aviary](https://github.com/sigilante/vine-aviary), which has the measurements behind
the `ski` and `lazy` tables and the argument for why a net of agents cannot both stop when
it should and share work. This package is that code made general. It does not yet replace
it: vine-aviary's own machine also drops a duplicator that has lost one of its copies, so
its counts of copies under reduction by need are lower than this package's.

No licence has been chosen yet.
