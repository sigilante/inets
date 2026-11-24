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
    >>> ski.run("``KI```SII``SII", how="all", max_interactions=1000).result.reason
    'interactions'
    >>> ski.show(ski.run("``KI```SII``SII", how="demand").term)
    'I'

Two tables are used (:func:`inets.bundled`):

- ``ski``: an application fires as soon as its function is a value. Reduced with every
  pair fired (``how="all"``) it runs work nobody wants and may not stop; reduced by need
  (``how="need"``) a cursor fires only what the answer depends on, and shares work.
- ``lazy``: the demand is carried in the net by agents of its own, so every pair can be
  fired (``how="demand"``) and only wanted work is done; but no work is shared.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import bundled
from .net import Net, Result

ARITY = {"S": 3, "K": 2, "I": 1}
PARTIAL = {("S", 1): "S1", ("S", 2): "S2", ("K", 1): "K1"}


@dataclass(frozen=True)
class Ref:
    """A reference to the term named ``k``."""
    k: object


def parse(text):
    """A term from prefix form."""
    stack, done = [], None
    for ch in text:
        if ch.isspace():
            continue
        if done is not None:
            raise ValueError("text after the end of the term")
        if ch == "`":
            stack.append([])
            continue
        if ch not in "SKI" and not ch.isdigit():
            raise ValueError("not a term: " + ch)
        t = int(ch) if ch.isdigit() else ch
        while stack:
            stack[-1].append(t)
            if len(stack[-1]) < 2:
                break
            t = tuple(stack.pop())
        else:
            done = (t,)
    if done is None:
        raise ValueError("the term is not complete")
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


def normal(term):
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
            box[at] = (net.new(t), 0)
            continue
        if isinstance(t, int):
            box[at] = (net.new("atom", t), 0)
            continue
        if isinstance(t, Ref):
            box[at] = (net.new("ref", t.k), 0)
            continue
        head, args = t, []
        while isinstance(head, tuple):
            args.append(head[1])
            head = head[0]
        args.reverse()
        take = min(len(args), ARITY[head] - 1) if direct and isinstance(head, str) else 0
        if take:
            v = net.new(PARTIAL[(head, take)])
            ports = [None] * take
            pending.append((v, 1, ports))
            for i in range(take):
                work.append((args[i], ports, i))
            out = (v, 0)
        else:
            out = [None]
            work.append((head, out, 0))
        for x in args[take:]:
            inert = isinstance(head, int) or lazy
            n = net.new("stuck" if isinstance(head, int) else "ap" if lazy else "app")
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


def read(net, port, definitions=None, limit=10 ** 7):
    """The term whose output is joined to the input ``port``. Sharing is unfolded, and
    references are replaced by what ``definitions`` says they name."""
    result = [None]
    work = [("go", net.link[port], result, 0)]
    seen = 0
    while work:
        op = work.pop()
        if op[0] == "pair":
            _, pair, box, at = op
            box[at] = (pair[0], pair[1])
            continue
        _, (n, i), box, at = op
        seen += 1
        if seen > limit:
            raise ValueError("the term is larger than the limit")
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
            raise ValueError(f"cannot read a term at port {i} of {kind}")
    return result[0]


def unfold(term, definitions):
    """The term with every reference replaced by the term it names."""
    memo = {}

    def plain(t):
        if isinstance(t, Ref):
            if t.k not in memo:
                memo[t.k] = plain(definitions[t.k])
            return memo[t.k]
        if isinstance(t, tuple):
            spine = []
            while isinstance(t, tuple):
                spine.append(t[1])
                t = t[0]
            out = plain(t)
            for x in reversed(spine):
                out = (out, plain(x))
            return out
        return t

    return plain(term)


def name(term, least=2, any_term=False):
    """Names subterms: returns ``(main, definitions)``, where ``main`` is the term with a
    :class:`Ref` in place of each named subterm and ``definitions`` maps each name to its
    term, in which named arguments are again references.

    A subterm is named when it is an application in argument position (or the whole
    term), is in normal form, and has at least ``least`` leaves. Equal subterms get one
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
    named = lambda n: info[n][0] is None and (any_term or info[n][4]) and info[n][3] >= least
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
            if t.k not in keep:
                keep[t.k] = definitions[t.k]
                todo.append(definitions[t.k])
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


def terms(leaves, size):
    """Every term with exactly ``size`` leaves drawn from ``leaves``."""
    if size == 1:
        return list(leaves)
    return [(a, b) for k in range(1, size) for a in terms(leaves, k) for b in terms(leaves, size - k)]


@dataclass
class Run:
    """A finished run: the net, why it stopped, and the term read back (None at a cap)."""
    net: Net
    result: Result
    term: object
    root: tuple


def build(term, how="need", definitions=None, direct=False):
    """A net for a term, ready to reduce: returns ``(net, root)``, the root being the free
    port the term's value will be joined to. ``how`` chooses the table: ``"need"`` and
    ``"all"`` use ``ski``; ``"demand"`` uses ``lazy``, with a demand for the normal form
    placed at the root."""
    if isinstance(term, str) and how in ("need", "all", "demand") and (len(term) > 1 or term not in "SKI"):
        term = parse(term)
    system = bundled("lazy" if how == "demand" else "ski")
    net = Net(system)
    definitions = definitions or {}
    if how != "demand":
        for k, t in definitions.items():
            if not normal(t):
                raise ValueError(f"the term named {k} is not in normal form: with the ski table only normal forms may be named")
    for k, t in definitions.items():
        net.define(k, lambda net, t=t: encode(net, t, direct))
    root = net.free()
    out = encode(net, term, direct)
    if how == "demand":
        ask = net.new("nf")
        net.wire((ask, 0), out)
        net.wire(root, (ask, 1))
    else:
        net.wire(root, out)
    return net, root


def run(term, how="need", definitions=None, direct=False, deep=True,
        max_interactions=10 ** 6, max_nodes=10 ** 6):
    """Reduces a term (a term, or its prefix form) and reads the result back.

    ``how`` is ``"need"`` (the ``ski`` table, by need), ``"all"`` (the ``ski`` table, every
    pair fired in rounds) or ``"demand"`` (the ``lazy`` table, every pair fired in rounds).
    With ``deep`` false, reduction by need stops when the head is a value.
    """
    net, root = build(term, how, definitions, direct)
    if how == "need":
        result = net.by_need(root, deep, max_interactions, max_nodes)
    else:
        result = net.rounds(max_interactions, max_nodes)
    return Run(net, result, read(net, root, definitions) if result.stopped else None, root)
