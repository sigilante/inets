"""Ivy text: Vine's notation for nets.

A file is named nets. A net is equations between trees, in braces. A tree is a wire (a
name used exactly twice in the net), the net's free port ``^``, or a node: a name with a
``:`` in it, an optional payload ``#12``, optional names in square brackets, and its
auxiliary ports' trees in round brackets. A node stands for its principal port. ``//``
starts a comment.

    iv:main {
      ^ = ivm:x(io0 io1)
      io0 = ivm:ext:merge[root:io:print_char](ivm:n32#72 io1)
    }

:func:`read` gives each net as a list of equations; :func:`instantiate` builds one in a
:class:`~inets.net.Net`, given a function that says which agent a node name means.
"""
from __future__ import annotations

import re
import sys
from typing import NamedTuple

from .errors import IvyError
from .net import Port

TOKEN = re.compile(r"\s*([{}()\[\],=;^]|#[0-9A-Fa-fx]+|[A-Za-z0-9_:]+)")


class Tree(NamedTuple):
    """A node in Ivy text: its name's path, its payload (or None), the names in its
    square brackets, and the trees on its auxiliary ports. A wire is a plain string."""
    path: str
    payload: int | None
    names: tuple
    kids: tuple


def read(text):
    """``{net name: [(tree, tree)]}``: each net as its equations. A tree is a wire's name
    (``"^"`` for the free port) or a :class:`Tree`. A net's name is its whole text,
    payload and bracketed names included."""
    text = re.sub(r"//[^\n]*", "", text)
    toks, at = [], 0
    while at < len(text):
        m = TOKEN.match(text, at)
        if not m:
            if not text[at:].strip():
                break
            raise IvyError("cannot read: " + text[at:at + 40].strip())
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
            if not re.fullmatch(r"\^|[A-Za-z0-9_]+", out):
                raise IvyError(f"expected a wire or a node, not {out}")
        else:
            path, payload, names, _ = name()
            kids = []
            if pos < len(toks) and toks[pos] == "(":
                pos += 1
                while toks[pos] != ")":
                    kids.append(tree(eqs))
                pos += 1
            out = Tree(path, payload, tuple(names), tuple(kids))
        while pos < len(toks) and toks[pos] == "{":   # equations attached to a tree
            pos += 1
            block(eqs)
        return out

    def block(eqs):
        nonlocal pos
        while toks[pos] != "}":
            a = tree(eqs)
            if toks[pos] != "=":
                raise IvyError("expected = in a net")
            pos += 1
            eqs.append((a, tree(eqs)))
            if toks[pos] == ";":
                pos += 1
        pos += 1

    nets = {}
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 20000))
    try:
        while pos < len(toks):
            net = name()[3]
            if pos >= len(toks) or toks[pos] != "{":
                raise IvyError("expected { after " + net)
            pos += 1
            eqs = []
            block(eqs)
            nets[net] = eqs
    except IndexError:
        raise IvyError("the text ends in the middle of a net") from None
    except RecursionError:
        raise IvyError("a tree is nested too deeply to read") from None
    finally:
        sys.setrecursionlimit(limit)
    return nets


def instantiate(net, equations, agent_of):
    """Builds a net's equations in ``net`` and returns the port its free port ``^`` is
    joined to. ``agent_of(tree)`` gives ``(agent kind, parameter)`` for a node."""
    # Wires said to be one (`a = b`) are one wire: find each wire's representative.
    same = {}

    def find(w):
        while same.get(w, w) != w:
            same[w] = same.get(same[w], same[w])
            w = same[w]
        return w

    for a, b in equations:
        if isinstance(a, str) and isinstance(b, str):
            same[find(a)] = find(b)
    waiting = {}

    def meet(wire, port):
        wire = find(wire)
        if wire in waiting:
            net.wire(waiting.pop(wire), port)
        else:
            waiting[wire] = port

    def build(tree):
        """A tree's principal port. (An explicit stack: trees can be deep.)"""
        root, stack = None, [(tree, None)]
        while stack:
            t, parent = stack.pop()
            kind, param = agent_of(t)
            n = net.add_node(kind, param)
            if len(t.kids) != net.system.agents[kind].arity:
                raise IvyError(f"{t.path} is written with {len(t.kids)} ports, and {kind} has {net.system.agents[kind].arity}")
            for i, kid in enumerate(t.kids, 1):
                if isinstance(kid, str):
                    meet(kid, Port(n, i))
                else:
                    stack.append((kid, Port(n, i)))
            if parent is None:
                root = Port(n, 0)
            else:
                net.wire(parent, Port(n, 0))
        return root

    for a, b in equations:
        if isinstance(a, str) and isinstance(b, str):
            continue
        if isinstance(a, str):
            meet(a, build(b))
        elif isinstance(b, str):
            meet(b, build(a))
        else:
            net.wire(build(a), build(b))
    root = find("^")
    if root not in waiting:
        raise IvyError("the net has no free port ^, or uses it twice")
    out = waiting.pop(root)
    if waiting:
        raise IvyError("wires used once: " + ", ".join(sorted(waiting)))
    return out
