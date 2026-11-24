# Changes

## 0.1.3 (not released)

- Reduction by need kept a list entry for every interaction it made, so its memory grew
  with the length of a run even when the net stayed small. The list is now pruned. No
  count changes; vine-aviary's SKIjack t1 by need took 37 s instead of 41 s on one machine.
- `Net.sweep` and `Net.reduce_by_need` raise `Error` for a port that is wired to nothing;
  they raised `KeyError`. `collapse=None` collapses nothing; it raised `TypeError`.
- `inets.ivm`: printing a number that is no character fails as an extrinsic function
  given a wrong argument does (the `ext_generic` flag); it raised `OverflowError` and lost
  the output. What the IVM itself does there has not been checked.
- `inets.ski.unfold` no longer reaches Python's recursion limit on deep terms.
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
  `Stuck`, and the cap on interactions was not reached in either case before.
- `inets-kernel`: an equation with a side missing (`con (a b) =`) is reported in words; it
  raised a Python exception before.
- Counts are worded in the singular where there is one (`1 interaction`).
- The kernel's `%help` said a trace draws the net before each round; it draws it after.
- The README has an Install section for both packages, and its links work on PyPI. The
  kernel's README says what it left out: the table it starts with, separators and
  comments in a net, and that a Jupyter front end is installed separately.
- The notebooks are regenerated, with four sentences made exact.

## 0.1.0

First release: tables of rules, a checker, a net machine with three schedules, Ivy text,
four bundled systems, a command line, a Jupyter kernel and three notebooks.
