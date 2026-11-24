"""The command line.

    inets check TABLE                 check a table: a file, or a bundled name
    inets rules TABLE                 list a table's rules, marking those that are not local
    inets run ski TERM [--rounds | --lazy] [--dot]
                                      reduce a term of S, K, I (prefix form): by need, or
                                      with every pair fired, by the ski or the lazy table
    inets run ivm FILE.iv             run a program of Vine's IVM
    inets demo                        one term, K I Ω, reduced three ways

The bundled tables are combinators, ski, lazy and ivm. `python -m inets` is the same.
"""
import sys

from . import Error, System, bundled, ivm, ski
from .system import BUNDLED


def table(name):
    return bundled(name) if name in BUNDLED else System.load(name)


def show_result(result):
    extra = f", {result.rounds} rounds, widest {result.widest}" if result.rounds else ""
    counts = ", ".join(f"{k} {v}" for k, v in sorted(result.counts.items()))
    print(f"stopped: {result.reason}; {result.interactions} interactions{extra}; "
          f"{result.active_left} active pairs left" + (f"; {counts}" if counts else ""), file=sys.stderr)


def demo():
    term = "``KI```SII``SII"
    print("One term, K I Ω, where Ω reduces to itself without end. K discards its second argument,")
    print("so the term has the normal form I. Whether a net reaches it depends on which pairs fire.\n")
    for schedule, title, cap in (("need", "ski table, by need: only the pairs the answer depends on", 10 ** 4),
                                 ("rounds", "ski table, every pair fired: Ω runs although K will discard it", 300),
                                 ("lazy", "lazy table, every pair fired: the demand is carried in the net, and no work is shared", 10 ** 4)):
        run = ski.run(term, schedule=schedule, max_interactions=cap)
        r = run.result
        answer = ski.show(run.term) if r.finished else f"none: stopped at the cap of {cap} interactions"
        print(title)
        print(f"  answer {answer}; {r.interactions} interactions, of which {r.counts.get('contract', 0)} contractions; "
              f"stopped because: {r.reason}; active pairs left: {r.active_left}")
    print("\nBy need stops with active pairs left: what it reaches is a normal form of what the root can")
    print("reach, not of the whole net. Ω is still there, unreduced, until it is swept away.")


def command(args):
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    verb, args = args[0], args[1:]
    if verb == "check" and len(args) == 1:
        system = table(args[0])
        problems = system.check()
        print(f"{len(system.agents)} agents, {len(system.rules)} rules, {'with' if system.signed else 'without'} signs; "
              f"{len(problems)} problems")
        for p in problems:
            print("  " + p)
        return 1 if problems else 0
    if verb == "rules" and len(args) == 1:
        for r in table(args[0]).rules:
            print(f"{r.count or '?':<11} {r}" + (f"   [not local: {', '.join(r.not_local)}]" if r.not_local else ""))
        return 0
    if verb == "run" and len(args) >= 2 and args[0] == "ski":
        flags = [a for a in args[1:] if a.startswith("--")]
        terms = [a for a in args[1:] if not a.startswith("--")]
        if len(terms) != 1 or any(f not in ("--rounds", "--lazy", "--dot") for f in flags):
            print(__doc__)
            return 2
        schedule = "rounds" if "--rounds" in flags else "lazy" if "--lazy" in flags else "need"
        run = ski.run(terms[0], schedule=schedule)
        if "--dot" in flags:
            print(run.net.dot())
        else:
            print(ski.show(run.term) if run.result.finished else "stopped at the cap")
        show_result(run.result)
        return 0 if run.result.finished else 1
    if verb == "run" and len(args) == 2 and args[0] == "ivm":
        with open(args[1], encoding="utf-8") as f:
            run = ivm.run(f.read())
        sys.stdout.write(run.output)
        sys.stdout.flush()
        show_result(run.result)
        if run.flags:
            print("flags: " + ", ".join(sorted(run.flags)), file=sys.stderr)
        return 1 if run.flags or not run.result.finished else 0
    if verb == "demo" and not args:
        demo()
        return 0
    print(__doc__)
    return 2


def main(argv=None):
    try:
        return command(list(sys.argv[1:] if argv is None else argv))
    except (Error, OSError) as e:
        print(f"inets: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
