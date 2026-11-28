# Changes

## 0.1.4

Added:

- `inets.text`: nets written as equations between ports, as on the right-hand side of a
  rule. `text.read(system, text)` builds a net and returns it with its named free ports;
  `text.write(net, free)` writes one back; `text.same(...)` says whether two nets are the
  same up to the numbering of their nodes, in time quadratic in the largest closed piece.
  `y = x`, with each name used nowhere else, is two free ports joined to each other. Errors
  are `inets.NetTextError`.
- `inets.draw`: pictures of nets in the style of Lafont's figures (ellipses, an arrowhead on
  each principal port, italic free ports, `_`-names as bare ends). With signs, outputs sit
  on top and inputs below, and a wire that closes a cycle does not shape the layout.
  `draw.dot(net, names, top=, style=, arrows=)` gives Graphviz text, with `style="ports"`
  for `Net.dot`'s drawing; `draw.svg` runs Graphviz's `dot`; `draw.roughen` gives an SVG
  the look of a photocopied 1990 figure.
- The kernel (inets-kernel 0.1.4) reads net cells with `inets.text` and draws them with
  `inets.draw`, in Lafont's style by default. New commands are `%style lafont|ports`,
  `%arrows on|off` and `%retro on|off`. A net cell may now join two free ports (`a = b`).
  It needs inets 0.1.4.
- `notebooks/lafont1990/`: *Interaction nets, live*, a notebook companion to Lafont's
  *Interaction Nets* (1990), for JupyterLite, with its helper `livenet.py` (nets written as
  equations, drawn as in Lafont's figures, reduced step by step, compared up to numbering). `livenet.py` imports
  `inets.text` and `inets.draw`, so it needs inets 0.1.4. The notebook is published as a
  JupyterLite page at https://sigilante.github.io/inets/.

Fixed:

- A test of `unfold` on a deep term compared 5,000-deep tuples with `==`, which
  recurses past Python 3.10's limit; it compares their prefix forms. The 0.1.3 source
  archive's tests show that one failure on Python 3.10; the code is not affected.

## 0.1.3

Changes to the interface, made before 1.0:

- A table can declare that an agent is a duplicator: `agent dup - + + duplicator`.
  `Agent.duplicator` and `System.duplicators` say so, and `System.check` reports a
  duplicator whose signs are not `- + +`. The bundled `ski` and `lazy` tables declare
  `dup`.
- `Net.sweep` and `Net.reduce_by_need` collapse the table's duplicators unless told
  otherwise: `collapse=None`, the default, means the declared ones, and `()` none. Before,
  the default collapsed nothing; a caller that reduced the `ski` table by need without
  `collapse=("dup",)` now gets fewer copies, and the same contractions and answers. A table of your own
  is collapsed only if it declares its duplicators: one that does not now collapses
  nothing unless given `collapse=` by name.
- The options of `Net.reduce_by_need` after the port are keyword-only.
- `inets.ski.run` takes `table` (`"ski"`, `"lazy"` or a `System`) and `schedule`
  (`"need"` or `"rounds"`) separately, and `net_class`, the class of net to build. A
  table with an `nf` agent carries its own demand and is reduced in rounds.
  `schedule="lazy"` still works, with a `DeprecationWarning`.
- The ends of a link in a rule's body are the classes `Ext`, `New` and `Pair`, not tagged
  tuples. They, `Side`, `Rewrite`, `Expand`, `Call`, `Compare`, `Test`, `Peek` and
  `Otherwise` are exported from `inets`.
- `inets-kernel` 0.1.3 needs `inets` 0.1.3.

Fixes:

- Reduction by need kept a list entry for every interaction it made, so its memory grew
  with the length of a run even when the net stayed small. The list is now pruned. No
  count changes. On vine-aviary's SKIjack t1 check, the process's peak memory is lower
  (625 and 715 MB against 769 and 931 MB; that check runs the reference reducer and three
  runs by need) and the time of t1 by need as applications about the same (55 and 56 s
  against 57 and 50 s), in runs alternated with 0.1.2 on one loaded machine.
- `Net.sweep` and `Net.reduce_by_need` raise `Error` for a port that is wired to nothing;
  they raised `KeyError`.
- `inets.ivm`: printing a number that is no character (above `0x10FFFF`, or a surrogate,
  `0xD800` to `0xDFFF`) fails as an extrinsic function given a wrong argument does (the
  `ext_generic` flag); it raised an exception and lost the output. What the IVM itself
  does there has not been checked.
- `inets.ski.unfold` no longer reaches Python's recursion limit on deep terms, and a
  definition that refers to itself raises `TermError` (it raised `RecursionError`).
- The source archive holds the IVM test programs and their recorded results, so its
  tests run, and the change list.

## 0.1.2

- `Net.sweep` and `Net.reduce_by_need` take a new argument, `collapse`: the names of
  agents that are duplicators. In a sweep, a duplicator that has lost one of its copies
  is removed, and its input is joined to the other copy. `inets.ski.run` collapses `dup`
  in runs by need. Copy counts fall; contraction counts and answers do not change.
- `inets.ski.encode` now builds the arguments of an atom as applications unless `direct`
  is given, as its docstring says; it built them as a stuck application even without
  `direct`. Answers and contraction counts do not change. Other counts change for terms
  that apply an atom: one more `collect` for each such application and, with the `lazy`
  table, more `demand` and `arrive`. Counts recorded under 0.1.1 for such terms differ.

## 0.1.1

- `inets`: reduction by need no longer runs without end on a net built against its table's
  signs (an input joined to an input) or on a value that waits on itself. It raises
  `Stuck`. Before, the cap on interactions did not stop either case.
- `inets-kernel`: an equation with a side missing (`con (a b) =`) is reported in words; it
  raised a Python exception before.
- Counts are worded in the singular where there is one (`1 interaction`).
- The kernel's `%help` said a trace draws the net before each round; it draws it after.
- The README has an Install section for both packages, and its links work on PyPI. The
  kernel's README says what it left out: the table it starts with, separators and
  comments in a net, and that a Jupyter front end is installed separately.
- The notebooks are regenerated, with corrections to their wording.

## 0.1.0

First release: tables of rules, a checker, a net machine with three schedules, Ivy text,
four bundled systems, a command line, a Jupyter kernel and three notebooks.
