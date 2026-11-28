"""Nets as text: equations between ports, as on the right-hand side of a rule.

    >>> import inets
    >>> from inets import text
    >>> system = inets.bundled("combinators")
    >>> net, free = text.read(system, "con (a b) = dup (era era)")
    >>> net.reduce().reason
    'normal'
    >>> text.write(net, free)
    'a = dup (era era); b = dup (era era)'

``con (a b)`` is an agent and stands for its principal port; its auxiliary ports are given
in brackets, left to right. A name that is not an agent is a wire if it occurs twice and a
free port if it occurs once; ``y = x``, with each name occurring nowhere else, is two free
ports joined to each other. An agent with a parameter takes it after its name: ``atom 3``.
Equations are separated by ``;`` or new lines. A name used more than twice is refused, and
a name that is also an agent's is read as the agent. Names are as in tables: a letter or
``_`` followed by letters, digits, ``_`` or ``.``.

:func:`read` builds a net from text, :func:`write` writes one back, and :func:`same` says
whether two nets are the same up to the numbering of their nodes. The inets kernel's net
cells are read by :func:`read`.
"""

from .errors import NetTextError
from .net import _FREE, Library, Net, Port
from .system import tokens

__all__ = ["read", "write", "same", "NetTextError"]


def read(system, text):
    """A net from equations: ``(net, {free port's name: port})``. ``y = x``, with each name
    used nowhere else, is two free ports joined to each other. Text that is not a net raises
    :class:`NetTextError` (or :class:`inets.TableError`, for words the table reader cannot
    read)."""
    net = Net(system, Library())
    agents = system.agents
    seen, count, straight = {}, {}, []

    def meet(name, port):
        count[name] = count.get(name, 0) + 1
        if count[name] > 2:
            raise NetTextError(f"the wire {name} has more than two ends")
        if name in seen:
            net.wire(seen.pop(name), port)
        else:
            seen[name] = port

    def term(toks):
        if not toks:
            raise NetTextError("an equation is PORT = PORT, and one side is missing")
        head = toks.pop(0)
        if head in ("(", ")", "=", ";"):
            raise NetTextError(f"expected a node or a wire, not {head}")
        if head not in agents:
            return head
        agent = agents[head]
        param = None
        if agent.param:
            if not toks:
                raise NetTextError(f"{head} takes a parameter")
            word = toks.pop(0)
            param = int(word) if word.isdigit() else word
        n = net.add_node(head, param)
        if agent.arity:
            if not toks or toks.pop(0) != "(":
                raise NetTextError(f"{head} needs its {agent.arity} ports in brackets")
            i = 0
            while toks and toks[0] != ")":
                i += 1
                if i > agent.arity:
                    raise NetTextError(f"{head} has {agent.arity} auxiliary port" + ("" if agent.arity == 1 else "s"))
                kid = term(toks)
                if isinstance(kid, str):
                    meet(kid, Port(n, i))
                else:
                    net.wire(Port(n, i), kid)
            if not toks or i != agent.arity:
                raise NetTextError(f"{head} has {agent.arity} auxiliary port" + ("" if agent.arity == 1 else "s"))
            toks.pop(0)
        return Port(n, 0)

    for equation in text.replace("\n", ";").split(";"):
        if not equation.strip():
            continue
        toks = tokens(equation)
        a = term(toks)
        if not toks or toks.pop(0) != "=":
            raise NetTextError("an equation is PORT = PORT: " + equation.strip())
        b = term(toks)
        if toks:
            raise NetTextError("unexpected " + toks[0] + " in: " + equation.strip())
        if isinstance(a, str) and isinstance(b, str):
            straight.append((a, b))  # two free ports joined to each other: checked below
            continue
        if isinstance(a, str):
            meet(a, b)
        elif isinstance(b, str):
            meet(b, a)
        else:
            net.wire(a, b)
    free = {}
    for a, b in straight:
        if a == b or a in count or b in count or sum(a in x or b in x for x in straight) > 1:
            if a == b:
                raise NetTextError(f"{a} = {a} joins a wire to itself")
            raise NetTextError(f"{a} = {b} joins two wires: write one name for both")
        free[a], free[b] = net.free(), net.free()
        net.wire(free[a], free[b])
    for name, port in seen.items():
        free[name] = net.free()
        net.wire(free[name], port)
    return net, free


def write(net, free):
    """The net as equations, read from its free ports in order of name, then from what is
    left. Trees hanging from a free port print as one term; any other joining of two ports
    is a wire named ``w1``, ``w2``, ... in the order met, skipping the free ports' names.
    An empty net is ``""``. A port joined to nothing cannot be written, and raises
    :class:`NetTextError`."""
    name_of = {p.node: name for name, p in free.items()}
    visited, wires, done_free = set(), {}, set()

    def node(n):
        visited.add(n)
        kind = net.kind[n]
        head = kind + (f" {net.param[n]}" if n in net.param else "")
        arity = net.system.agents[kind].arity
        if not arity:
            return head
        return head + " (" + " ".join(follow(Port(n, i)) for i in range(1, arity + 1)) + ")"

    def follow(p):
        q = net.link.get(p)
        if q is None:
            raise NetTextError(f"port {p.index} of node {p.node} ({net.kind[p.node]}) is joined to nothing")
        if net.kind[q.node] == _FREE:
            done_free.add(q.node)
            return name_of[q.node]
        if q.index == 0 and q.node not in visited:
            return node(q.node)
        key = frozenset((p, q))
        if key not in wires:
            k = len(wires) + 1
            while f"w{k}" in free or f"w{k}" in wires.values():
                k += 1
            wires[key] = f"w{k}"
        return wires[key]

    lines = []
    for name in sorted(free):
        p = free[name]
        q = net.link.get(p)
        if q is None:
            raise NetTextError(f"the free port {name} is joined to nothing")
        if p.node in done_free or (net.kind[q.node] != _FREE and q.index != 0):
            continue  # joined to an auxiliary port: it is named where that node is written
        done_free.add(p.node)
        lines.append(f"{name} = {follow(p)}")
    # What no free port reaches (rings, closed nets): agents with auxiliary ports first,
    # so that a leaf is written inside the agent that holds it.
    rest = [n for n in sorted(net.kind) if net.kind[n] != _FREE]
    for n in sorted(rest, key=lambda n: net.system.agents[net.kind[n]].arity == 0):
        if n in visited:
            continue
        left = node(n)
        lines.append(f"{left} = {follow(Port(n, 0))}")
    return "; ".join(lines)


def same(a, free_a, b, free_b):
    """Whether two nets are the same up to the numbering of their nodes: a one-to-one map
    of nodes that keeps agents, parameters, free ports' names and every wire, port for
    port.

    A node's ports are numbered, so once one node of a connected piece is matched, every
    node joined to it is matched too, port by port. The part reached from the free ports is
    therefore matched by following wires from them; what is left is closed pieces, and two
    nets are the same if those are the same pieces, as many times each. A closed piece is
    compared by a canonical form: of the walks from each of its nodes, the least. This
    takes time quadratic in the size of the largest closed piece."""
    if set(free_a) != set(free_b):
        return False

    def label(net, n):
        return str((net.kind[n], net.param.get(n)))

    def ports(net, n):
        k = net.kind[n]
        return 1 if k == _FREE else net.system.agents[k].arity + 1

    # Match by following wires from the free ports.
    m, used = {}, set()
    todo = [(free_a[k].node, free_b[k].node) for k in free_a]
    for x, y in todo:
        m[x] = y
        used.add(y)
    while todo:
        x, y = todo.pop()
        if label(a, x) != label(b, y):
            return False
        for i in range(ports(a, x)):
            p, q = a.link.get(Port(x, i)), b.link.get(Port(y, i))
            if p is None or q is None:
                if p is not q:
                    return False
                continue
            if p.index != q.index:
                return False
            if p.node in m:
                if m[p.node] != q.node:
                    return False
            elif q.node in used:
                return False
            else:
                m[p.node] = q.node
                used.add(q.node)
                todo.append((p.node, q.node))

    # Compare what is left, closed piece by closed piece.
    def pieces(net, done):
        left = {n for n in net.kind if n not in done}
        out = []
        while left:
            piece, stack = set(), [min(left)]
            while stack:
                n = stack.pop()
                if n in piece:
                    continue
                piece.add(n)
                for i in range(ports(net, n)):
                    q = net.link.get(Port(n, i))
                    if q is not None and q.node not in piece:
                        stack.append(q.node)
            left -= piece
            out.append(min(walk(net, start) for start in piece))
        return sorted(out)

    def walk(net, start):
        """The piece as seen from ``start``: its nodes in the order a breadth-first walk
        meets them, each with its label and, port by port, the place in that order of the
        node it is joined to and the port there."""
        order, place = [start], {start: 0}
        for n in order:
            for i in range(ports(net, n)):
                q = net.link.get(Port(n, i))
                if q is not None and q.node not in place:
                    place[q.node] = len(order)
                    order.append(q.node)
        return tuple(
            (label(net, n),) + tuple(
                (-1, -1) if (q := net.link.get(Port(n, i))) is None else (place[q.node], q.index)
                for i in range(ports(net, n)))
            for n in order)

    return pieces(a, set(m)) == pieces(b, used)
