"""Ivy text: Vine's notation for nets.

A file is named nets. A net is equations between trees, in braces. A tree is a wire (a
name used exactly twice in the net), the net's free port ``^``, or a node: a name with a
``:`` in it, an optional payload ``#12``, optional names in square brackets, and its
auxiliary ports' trees in round brackets. A node stands for its principal port.

    iv:main {
      ^ = ivm:x(io0 io1)
      io0 = ivm:ext:merge[root:io:print_char](ivm:n32#72 io1)
    }

:func:`read` gives each net as a list of equations; :func:`instantiate` builds one in a
:class:`~inets.net.Net`, given a function that says which agent a node name means.
"""
from __future__ import annotations

import re

TOKEN = re.compile(r"\s*(?://[^\n]*\s*)*([{}()\[\],=;^]|#[0-9A-Fa-fx]+|[A-Za-z0-9_:]+)")


def read(text):
    """``{net name: [(tree, tree)]}``. A tree is a wire's name (``"^"`` for the free
    port) or ``(path, payload, [names], [trees])``. A net's name is its whole text,
    payload and bracketed names included."""
    toks, at = [], 0
    text = text.rstrip()
    while at < len(text):
        m = TOKEN.match(text, at)
        if not m:
            if text[at:].strip().startswith("//") or not text[at:].strip():
                break
            raise SyntaxError("cannot read: " + text[at:at + 40])
        toks.append(m.group(1))
        at = m.end()
    pos = 0

    def name():
        nonlocal pos
        path = toks[pos]
        pos += 1
        payload, names = None, []
        if pos < len(toks) and toks[pos].startswith("#"):
            payload = int(toks[pos][1:], 0)
            pos += 1
        if pos < len(toks) and toks[pos] == "[":
            pos += 1
            while toks[pos] != "]":
                names.append(name()[3])
                if toks[pos] == ",":
                    pos += 1
            pos += 1
        whole = path + (f"#{payload}" if payload is not None else "") + (f"[{','.join(names)}]" if names else "")
        return path, payload, names, whole

    def tree(eqs):
        nonlocal pos
        if toks[pos] == "^" or ":" not in toks[pos]:
            pos += 1
            out = toks[pos - 1]
        else:
            path, payload, names, _ = name()
            kids = []
            if pos < len(toks) and toks[pos] == "(":
                pos += 1
                while toks[pos] != ")":
                    kids.append(tree(eqs))
                pos += 1
            out = (path, payload, names, kids)
        while pos < len(toks) and toks[pos] == "{":   # equations attached to a tree
            pos += 1
            block(eqs)
        return out

    def block(eqs):
        nonlocal pos
        while toks[pos] != "}":
            a = tree(eqs)
            if toks[pos] != "=":
                raise SyntaxError("expected = in a net")
            pos += 1
            eqs.append((a, tree(eqs)))
            if toks[pos] == ";":
                pos += 1
        pos += 1

    nets = {}
    while pos < len(toks):
        net = name()[3]
        if pos >= len(toks) or toks[pos] != "{":
            raise SyntaxError("expected { after " + net)
        pos += 1
        eqs = []
        block(eqs)
        nets[net] = eqs
    return nets


def write(nets):
    """Ivy text for ``{name: [(tree, tree)]}``."""
    def text(t):
        if isinstance(t, str):
            return t
        path, payload, names, kids = t
        return (path + (f"#{payload}" if payload is not None else "") + (f"[{', '.join(names)}]" if names else "")
                + (f"({' '.join(text(k) for k in kids)})" if kids else ""))

    return "\n".join(name + " {\n" + "".join(f"  {text(a)} = {text(b)}\n" for a, b in eqs) + "}\n"
                     for name, eqs in nets.items())


def instantiate(net, equations, agent_of):
    """Builds a net's equations in ``net`` and returns the port its free port ``^`` is
    joined to. ``agent_of(path, payload, names)`` gives ``(agent kind, parameter)`` for a
    node name."""
    waiting, alias = {}, {}

    def meet(wire, port):
        wire = alias.get(wire, wire)
        if wire in waiting:
            net.wire(waiting.pop(wire), port)
        else:
            waiting[wire] = port

    def build(t):
        """A tree's port, or ("wire", name)."""
        stack = [(t, None, None)]
        # Recursion is replaced by an explicit stack: trees can be deep.
        result = []

        def make(tree, parent, index):
            path, payload, names, kids = tree
            kind, param = agent_of(path, payload, names)
            n = net.new(kind, param)
            if len(kids) != net.system.agents[kind].arity:
                raise SyntaxError(f"{path} has {len(kids)} ports written, and {kind} has {net.system.agents[kind].arity}")
            for i, kid in enumerate(kids, 1):
                if isinstance(kid, str):
                    meet(kid, (n, i))
                else:
                    stack.append((kid, n, i))
            if parent is None:
                result.append((n, 0))
            else:
                net.wire((parent, index), (n, 0))

        make(*stack.pop())
        while stack:
            make(*stack.pop())
        return result[0]

    for a, b in equations:
        if isinstance(a, str) and isinstance(b, str):
            # Two wires said to be one: whichever is met later stands for the other.
            a, b = alias.get(a, a), alias.get(b, b)
            if a in waiting and b in waiting:
                net.wire(waiting.pop(a), waiting.pop(b))
            elif a in waiting:
                alias[b] = a
            else:
                alias[a] = b
        elif isinstance(a, str):
            meet(a, build(b))
        elif isinstance(b, str):
            meet(b, build(a))
        else:
            net.wire(build(a), build(b))
    root = alias.get("^", "^")
    if root not in waiting:
        raise SyntaxError("the net has no free port ^, or uses it twice")
    out = waiting.pop(root)
    if waiting:
        raise SyntaxError("wires used once: " + ", ".join(sorted(waiting)))
    return out
