"""The command line.

    python -m inets check TABLE          check a table: a file, or a bundled name
    python -m inets rules TABLE          list a table's rules, and which are not local
    python -m inets ski TERM [--all | --demand] [--dot]
                                         reduce a term of S, K, I (prefix form)
    python -m inets ivm FILE.iv          run a program of Vine's IVM
    python -m inets demo                 one term, K I Ω, reduced three ways
"""
import os
import sys

from . import BUNDLED, bundled, check, ivm, load, ski


def table(name):
    return bundled(name) if name in BUNDLED else load(name)


def show_result(result):
    extra = f", {result.rounds} rounds, widest {result.widest}" if result.rounds else ""
    print(f"stopped: {result.reason}; {result.interactions} interactions{extra}; "
          f"{result.active_left} active pairs left; "
          + ", ".join(f"{k} {v}" for k, v in sorted(result.counts.items())), file=sys.stderr)


def demo():
    omega = "```SII``SII"
    term = "``KI" + omega
    print("One term, K I Ω, where Ω reduces to itself without end. K discards its second argument,")
    print("so the term has the normal form I. Whether a net reaches it depends on which pairs fire.\n")
    for how, title, cap in (("need", "ski table, by need: only the pairs the answer depends on", 10 ** 4),
                            ("all", "ski table, every pair fired: Ω runs although K will discard it", 300),
                            ("demand", "lazy table, every pair fired: the demand is carried in the net, and no work is shared", 10 ** 4)):
        run = ski.run(term, how=how, max_interactions=cap)
        r = run.result
        answer = ski.show(run.term) if r.stopped else f"none: stopped at the cap of {cap} interactions"
        print(title)
        print(f"  answer {answer}; {r.interactions} interactions, of which {r.counts.get('contract', 0)} contractions; "
              f"stopped because: {r.reason}; active pairs left: {r.active_left}")
    print("\nBy need stops with active pairs left: what it reaches is a normal form of what the root can")
    print("reach, not of the whole net. Ω is still there, unreduced, until it is swept away.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, args = args[0], args[1:]
    if command == "check" and len(args) == 1:
        system = table(args[0])
        problems = check(system)
        kinds = "with signs" if system.typed else "without signs"
        print(f"{len(system.agents)} agents, {len(system.rules)} rules, {kinds}; {len(problems)} problems")
        for p in problems:
            print("  " + p)
        return 1 if problems else 0
    if command == "rules" and len(args) == 1:
        for r in table(args[0]).rules:
            marks = [m for m, on in (("looks at a neighbour", r.peeks), ("expands a named net", r.kind == "expand"),
                                     ("calls the host", r.kind == "call"), ("keeps a node", any(r.keeps))) if on]
            print(f"{r.count or '?':<11} {r.title()}" + (f"   [not local: {', '.join(marks)}]" if marks else ""))
        return 0
    if command == "ski" and args:
        how = "all" if "--all" in args else "demand" if "--demand" in args else "need"
        terms = [a for a in args if not a.startswith("--")]
        if len(terms) != 1:
            print(__doc__)
            return 2
        run = ski.run(terms[0], how=how)
        if "--dot" in args:
            print(run.net.dot())
        else:
            print(ski.show(run.term) if run.result.stopped else "stopped at a cap")
        show_result(run.result)
        return 0 if run.result.stopped else 1
    if command == "ivm" and len(args) == 1:
        with open(args[0], encoding="utf-8") as f:
            run = ivm.run(f.read())
        sys.stdout.write(run.output)
        sys.stdout.flush()
        show_result(run.result)
        if run.flags:
            print("flags: " + ", ".join(sorted(run.flags)), file=sys.stderr)
        return 1 if run.flags or not run.result.stopped else 0
    if command == "demo":
        demo()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
