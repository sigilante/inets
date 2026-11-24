# Changes

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
