"""The combinators S, K and I as agents: terms, nets of them, and three ways to reduce.

A term is ``"S"``, ``"K"``, ``"I"``, an ``int`` (an inert atom), a :class:`Ref` (a
reference to a named term), or a pair ``(function, argument)``. In text a term is in
prefix form: a backtick applies the next term to the one after it; ``S``, ``K`` and ``I``
stand for themselves; a digit is an atom.

    >>> from inets import ski
    >>> ski.run("```SII0").term
    (0, 0)
    >>> ski.show(ski.run("``KI```SII``SII").term)        # K I Ω, by need
    'I'
    >>> ski.run("``KI```SII``SII", schedule="rounds", max_interactions=1000).result.reason
    'interactions'
    >>> ski.show(ski.run("``KI```SII``SII", table="lazy", schedule="rounds").term)
    'I'

Two tables are used (:func:`inets.bundled`):

- ``ski``: an application fires as soon as its function is a value. Reduced with every
  pair fired (``schedule="rounds"``) it runs work nobody wants and may not stop; reduced by
  need (``schedule="need"``) a cursor fires only what the answer depends on, and shares
  work.
- ``lazy``: the demand is carried in the net by agents of its own, so every pair can be
  fired (``table="lazy", schedule="rounds"``) and only wanted work is done; but no work
  is shared.
"""
from __future__ import annotations

from dataclasses import dataclass

import warnings

from .errors import TermError
from .net import Library, Net, Result
from .system import System, bundled

ARITY = {"S": 3, "K": 2, "I": 1}
PARTIAL = {("S", 1): "S1", ("S", 2): "S2", ("K", 1): "K1"}


@dataclass(frozen=True)
class Ref:
    """A reference to a named term."""
    name: object


_SYSTEMS = {}


def _system(name):
    if name not in _SYSTEMS:
        _SYSTEMS[name] = bundled(name)
    return _SYSTEMS[name]


def parse(text):
    """A term from prefix form."""
    stack, done = [], None
    for ch in text:
        if ch.isspace():
            continue
        if done is not None:
            raise TermError("text after the end of the term")
        if ch == "`":
            stack.append([])
            continue
        if ch not in "SKI" and not ch.isdigit():
            raise TermError("not a term: " + ch)
        t = int(ch) if ch.isdigit() else ch
        while stack:
            stack[-1].append(t)
            if len(stack[-1]) < 2:
                break
            t = tuple(stack.pop())
        else:
            done = (t,)
    if done is None:
        raise TermError("the term is not complete")
    return done[0]


def show(term):
    """A term in prefix form. Atoms above 9 are written as their numbers, which
    :func:`parse` will not read back."""
    out, stack = [], [term]
    while stack:
        t = stack.pop()
        if isinstance(t, tuple):
            out.append("`")
            stack.append(t[1])
            stack.append(t[0])
        else:
            out.append(str(t))
    return "".join(out)


def is_normal(term):
    """Whether a term has no redex of its own: no combinator has all its arguments, and
    no reference is applied (it might name anything)."""
    todo = [term]
    while todo:
        t, count = todo.pop(), 0
        while isinstance(t, tuple):
            todo.append(t[1])
            t = t[0]
            count += 1
        if count and (isinstance(t, Ref) or (isinstance(t, str) and count >= ARITY[t])):
            return False
    return True


def encode(net, term, direct=False):
    """Builds a term in a net of the ``ski`` or ``lazy`` table and returns its output
    port. With ``direct`` a combinator short of arguments is built as the value it is
    (``S a b`` as ``S2(a b)``), not as applications that will make it."""
    lazy = "ap" in net.system.agents
    result, pending = [None], []
    work = [(term, result, 0)]
    while work:
        t, box, at = work.pop()
        if isinstance(t, str):
            box[at] = (net.add_node(t), 0)
            continue
        if isinstance(t, int):
            box[at] = (net.add_node("atom", t), 0)
            continue
        if isinstance(t, Ref):
            box[at] = (net.add_node("ref", t.name), 0)
            continue
        head, args = t, []
        while isinstance(head, tuple):
            args.append(head[1])
            head = head[0]
        args.reverse()
        take = min(len(args), ARITY[head] - 1) if direct and isinstance(head, str) else 0
        if take:
            v = net.add_node(PARTIAL[(head, take)])
            ports = [None] * take
            pending.append((v, 1, ports))
            for i in range(take):
                work.append((args[i], ports, i))
            out = (v, 0)
        else:
            out = [None]
            work.append((head, out, 0))
        for x in args[take:]:
            # An atom's arguments: with `direct`, the stuck application they make; without
            # it, applications that will make it.
            held = direct and isinstance(head, int)
            inert = held or lazy
            n = net.add_node("stuck" if held else "ap" if lazy else "app")
            ports = [out, None]
            pending.append((n, 1 if inert else 0, ports))
            work.append((x, ports, 1))
            out = (n, 0) if inert else (n, 2)
        box[at] = out
    resolve = lambda p: resolve(p[0]) if isinstance(p, list) else p
    for n, first, ports in pending:
        for i, p in enumerate(ports):
            net.wire((n, first + i), resolve(p))
    return resolve(result[0])


def read_back(net, port, definitions=None):
    """The term whose output is joined to the input ``port``. Sharing is unfolded, and
    references are replaced by what ``definitions`` says they name."""
    result = [None]
    work = [("go", net.link[port], result, 0)]
    while work:
        op = work.pop()
        if op[0] == "pair":
            _, pair, box, at = op
            box[at] = (pair[0], pair[1])
            continue
        _, (n, i), box, at = op
        kind = net.kind[n]
        if kind == "atom":
            box[at] = net.param[n]
        elif kind == "ref":
            box[at] = unfold(Ref(net.param[n]), definitions or {})
        elif kind in ("S", "K", "I"):
            box[at] = kind
        elif kind in ("K1", "S1"):
            pair = [kind[0], None]
            work.append(("pair", pair, box, at))
            work.append(("go", net.link[(n, 1)], pair, 1))
        elif kind == "S2":
            inner, pair = ["S", None], [None, None]
            work.append(("pair", pair, box, at))
            work.append(("go", net.link[(n, 2)], pair, 1))
            work.append(("pair", inner, pair, 0))
            work.append(("go", net.link[(n, 1)], inner, 1))
        elif kind in ("stuck", "ap") or (kind == "app" and i == 2):
            pair = [None, None]
            first, second = ((n, 0), (n, 1)) if kind == "app" else ((n, 1), (n, 2))
            work.append(("pair", pair, box, at))
            work.append(("go", net.link[second], pair, 1))
            work.append(("go", net.link[first], pair, 0))
        elif (kind == "dup" and i in (1, 2)) or (kind in ("ev", "nf") and i == 1):
            work.append(("go", net.link[(n, 0)], box, at))
        else:
            raise TermError(f"cannot read a term at port {i} of {kind}")
    return result[0]


def unfold(term, definitions):
    """The term with every reference replaced by the term it names."""
    # Iterative, so that a deep term does not reach Python's recursion limit.
    memo, result, stack = {}, [], [("term", term)]
    while stack:
        kind, x = stack.pop()
        if kind == "term":
            if isinstance(x, Ref):
                if x.name in memo:
                    result.append(memo[x.name])
                else:
                    stack.append(("named", x.name))
                    stack.append(("term", definitions[x.name]))
            elif isinstance(x, tuple):
                args = []
                while isinstance(x, tuple):
                    args.append(x[1])
                    x = x[0]
                # Built in order: the head, then each argument from the first.
                stack.append(("apply", len(args)))
                stack.extend(("term", a) for a in args)
                stack.append(("term", x))
            else:
                result.append(x)
        elif kind == "named":
            memo[x] = result[-1]
        else:
            args = result[len(result) - x:]
            del result[len(result) - x:]
            out = result.pop()
            for a in args:
                out = (out, a)
            result.append(out)
    return result[0]


def name_subterms(term, any_term=False):
    """Names subterms: returns ``(main, definitions)``, where ``main`` is the term with a
    :class:`Ref` in place of each named subterm and ``definitions`` maps each name to its
    term, in which named arguments are again references.

    A subterm is named when it is an application in argument position (or the whole
    term) and is in normal form. Equal subterms get one
    name. Only normal forms are named because a reference is expanded afresh at each use:
    naming a term with work left in it would repeat the work. With ``any_term`` every such
    application is named, which is right only for the ``lazy`` table, where no work is
    shared in the first place.
    """
    number, info, by_id = {}, [], {}   # info[n] = (leaf, f, a, size, normal, head, nargs)
    stack = [term]
    while stack:
        t = stack[-1]
        if not isinstance(t, tuple):
            stack.pop()
            if t not in number:
                number[t] = len(info)
                info.append((t, None, None, 1, True, t, 0))
            continue
        if id(t) in by_id:
            stack.pop()
            continue
        f, a = t
        fn = by_id.get(id(f)) if isinstance(f, tuple) else number.get(f)
        an = by_id.get(id(a)) if isinstance(a, tuple) else number.get(a)
        if fn is None or an is None:
            if an is None:
                stack.append(a)
            if fn is None:
                stack.append(f)
            continue
        stack.pop()
        key = (fn, an)
        if key not in number:
            fs, fnorm, head, nargs = info[fn][3:]
            asz, anorm = info[an][3:5]
            under = nargs + 1 < ARITY[head] if isinstance(head, str) else True
            number[key] = len(info)
            info.append((None, fn, an, min(fs + asz, 10 ** 9), fnorm and anorm and under, head, nargs + 1))
        by_id[id(t)] = number[key]
    root = by_id[id(term)] if isinstance(term, tuple) else number[term]
    named = lambda n: info[n][0] is None and (any_term or info[n][4])
    inline, definitions = [None] * len(info), {}
    for n, (leaf, f, a, *_rest) in enumerate(info):
        inline[n] = leaf if leaf is not None else (inline[f], Ref(a) if named(a) else inline[a])
    for n in range(len(info)):
        if named(n):
            definitions[n] = inline[n]
    main = Ref(root) if named(root) else inline[root]
    keep, todo, seen = {}, [main], set()
    while todo:
        t = todo.pop()
        if isinstance(t, Ref):
            if t.name not in keep:
                keep[t.name] = definitions[t.name]
                todo.append(definitions[t.name])
        elif isinstance(t, tuple) and id(t) not in seen:
            seen.add(id(t))
            todo.extend(t)
    return main, keep


def tree_step(term):
    """One leftmost-outermost step of ordinary rewriting of a term as a tree, or None if
    the term is in normal form. This is the yardstick the nets are measured against."""
    head, args = term, []
    while isinstance(head, tuple):
        args.append(head[1])
        head = head[0]
    args.reverse()
    n = ARITY.get(head) if isinstance(head, str) else None
    if n is not None and len(args) >= n:
        new = args[0] if head in ("I", "K") else ((args[0], args[2]), (args[1], args[2]))
        for a in args[n:]:
            new = (new, a)
        return new
    for i, a in enumerate(args):
        b = tree_step(a)
        if b is not None:
            for x in args[:i] + [b] + args[i + 1:]:
                head = (head, x)
            return head
    return None


def tree_normal_form(term, max_steps=2000, max_leaves=20000):
    """``(normal form, steps)`` by leftmost-outermost tree reduction, or ``(None, steps)``
    if a cap is reached first."""
    def leaves(t):
        n, stack = 0, [t]
        while stack:
            u = stack.pop()
            if isinstance(u, tuple):
                stack.extend(u)
            else:
                n += 1
        return n

    for steps in range(max_steps):
        nxt = tree_step(term)
        if nxt is None:
            return term, steps
        term = nxt
        if leaves(term) > max_leaves:
            return None, steps
    return None, max_steps


@dataclass
class Run:
    """A finished run: the net, why it stopped, the term read back (None if the run did
    not finish), and the free port the term's value is joined to."""
    net: Net
    result: Result
    term: object
    root: tuple


def run(term, schedule="need", definitions=None, direct=False, deep=True, sweep_above=20000,
        max_interactions=10 ** 6, *, table=None, net_class=Net):
    """Reduces a term (a term, or its prefix form) and reads the result back.

    ``table`` is ``"ski"`` (the default), ``"lazy"``, or a :class:`~inets.System` of the
    same agents (a copy of either table, say). A table with an ``nf`` agent carries its
    own demand, as ``lazy`` does: a demand for the normal form is placed at the root, and
    it must be given ``schedule="rounds"`` (the default, ``"need"``, raises
    :class:`~inets.errors.TermError`). ``schedule`` is ``"need"`` (by need,
    :meth:`inets.Net.reduce_by_need`) or ``"rounds"`` (every pair fired,
    :meth:`inets.Net.reduce_in_rounds`). ``schedule="lazy"`` is an older way to say
    ``table="lazy", schedule="rounds"`` and gives a ``DeprecationWarning``.

    ``definitions`` are the named terms that references in ``term`` name
    (:func:`name_subterms`). With ``direct`` a combinator short of arguments is built as
    the value it is. ``deep`` and ``sweep_above`` are for reduction by need: with ``deep``
    false it stops when the head is a value. By need, each sweep removes a duplicator
    that has lost one of its copies (:meth:`inets.Net.sweep`). ``net_class`` is the class
    of the net built, a subclass of :class:`inets.Net` that keeps tallies, say.
    """
    if schedule == "lazy":
        warnings.warn('schedule="lazy" is now table="lazy", schedule="rounds"', DeprecationWarning, stacklevel=2)
        if table not in (None, "lazy"):
            raise TermError('schedule="lazy" names the lazy table; give table= and schedule="rounds" instead')
        table, schedule = "lazy", "rounds"
    if schedule not in ("need", "rounds"):
        raise TermError('schedule is "need" or "rounds"')
    if table is None:
        table = "ski"
    if isinstance(table, str):
        if table not in ("ski", "lazy"):
            raise TermError('table is "ski", "lazy" or a System')
        table = _system(table)
    elif not isinstance(table, System):
        raise TermError('table is "ski", "lazy" or a System')
    demand = "nf" in table.agents
    if demand and schedule != "rounds":
        raise TermError('a table that carries its own demand (with an nf agent) is reduced with schedule="rounds"')
    if isinstance(term, str):
        term = parse(term)
    definitions = definitions or {}
    if not demand:
        for k, t in definitions.items():
            if not is_normal(t):
                raise TermError(f"the term named {k} is not in normal form: with the ski table only normal forms may be named")
    host = Library({k: (lambda net, t=t: encode(net, t, direct)) for k, t in definitions.items()})
    net = net_class(table, host)
    root = net.free()
    out = encode(net, term, direct)
    if demand:
        ask = net.add_node("nf")
        net.wire((ask, 0), out)
        net.wire(root, (ask, 1))
    else:
        net.wire(root, out)
    if schedule == "need":
        result = net.reduce_by_need(root, deep=deep, sweep_above=sweep_above, max_interactions=max_interactions)
    else:
        result = net.reduce_in_rounds(max_interactions)
    return Run(net, result, read_back(net, root, definitions) if result.finished else None, root)
