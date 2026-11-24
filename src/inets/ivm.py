"""Programs of Vine's IVM, run by the ``ivm`` table.

    >>> from inets import ivm
    >>> run = ivm.run('''
    ... iv:main {
    ...   ^ = ivm:x(io0 io1)
    ...   io0 = ivm:ext:merge[root:io:print_char](ivm:n32#72 io1)
    ... }''')
    >>> run.output, run.result.counts
    ('H', {'graft': 1, 'annihilate': 1, 'extrinsic': 1})

The table (``inets.bundled("ivm")``) holds the IVM's twenty rules. This module is its
host: it reads Ivy text of the ``ivm:`` system, copies a named net when a reference is
expanded, and supplies some of the IVM's extrinsic functions (N32 arithmetic and
comparison, ``ivm:branch``, ``root:io:print_char``, and the IO value's split and merge).
A program that calls another stops with ``NotImplementedError``.

The interaction counts are the IVM's own: on the programs tried they equal what ``ivm
run`` reports, kind by kind. Not modelled: memory, depth, workers, and the IVM's "vicious
circle" flag, which comes from its memory accounting.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, replace

from . import bundled, ivy
from .net import Host, Net, Result


@dataclass(frozen=True)
class Value:
    """An extrinsic value. ``copy`` says whether its type may be copied."""
    type: str
    data: object = None
    copy: bool = True


@dataclass(frozen=True)
class Fn:
    """What an extrinsic function node carries: the function's name, whether it is a
    split (one value in, two ports out) or a merge (two values in, one port out), and
    whether a merge's arguments are exchanged."""
    name: str
    split: bool = False
    exchanged: bool = False

    @property
    def merge(self):
        return not self.split

    @property
    def swapped(self):
        return replace(self, exchanged=not self.exchanged)


IO = Value("io", copy=False)


def agent_of(path, payload, names):
    """The agent and parameter that a node name of the ``ivm:`` system means."""
    if path in ("ivm:eraser", "ivm:error"):
        return "era", None
    if path == "ivm:graft":
        return "graft", names[0]
    if path in ("ivm:x", "ivm:y"):
        return "comb", int(path == "ivm:y")
    if path == "ivm:n32":
        return "val", Value("n32", payload or 0)
    if path == "ivm:f32":
        return "val", Value("f32", payload or 0)
    if path == "ivm:nil":
        return "val", Value("nil")
    if path == "ivm:branch":
        return "val", Value("branch", tuple(names))
    if path in ("ivm:ext:split", "ivm:ext:merge", "ivm:ext:merge:swap"):
        return "fn", Fn(names[0], path == "ivm:ext:split", path == "ivm:ext:merge:swap")
    raise SyntaxError("not a node of the ivm: system: " + path)


def _n32(f):
    def run(host, a, b):
        if a.type != "n32" or b.type != "n32":
            return None
        r = f(a.data, b.data)
        return None if r is None else Value("n32", int(r) & 0xFFFFFFFF)
    return run


def _branch(host, index, branches):
    if index.type != "n32" or branches.type != "branch" or index.data >= len(branches.data):
        return None
    return ("graft", branches.data[index.data])


def _print_char(host, io_value, n):
    if io_value.type != "io" or n.type != "n32":
        return None
    host.out.write(chr(n.data))
    return io_value


EXTRINSICS = {
    "vi:n32:add": _n32(lambda a, b: a + b),
    "vi:n32:sub": _n32(lambda a, b: a - b),
    "vi:n32:mul": _n32(lambda a, b: a * b),
    "vi:n32:div": _n32(lambda a, b: a // b if b else None),
    "vi:n32:rem": _n32(lambda a, b: a % b if b else None),
    "vi:n32:eq": _n32(lambda a, b: a == b),
    "vi:n32:ne": _n32(lambda a, b: a != b),
    "vi:n32:lt": _n32(lambda a, b: a < b),
    "vi:n32:le": _n32(lambda a, b: a <= b),
    "vi:n32:shl": _n32(lambda a, b: a << (b & 31)),
    "vi:n32:shr": _n32(lambda a, b: a >> (b & 31)),
    "vi:n32:and": _n32(lambda a, b: a & b),
    "vi:n32:or": _n32(lambda a, b: a | b),
    "vi:n32:xor": _n32(lambda a, b: a ^ b),
    "vi:n32:add_high": _n32(lambda a, b: (a + b) >> 32),
    "vi:n32:mul_high": _n32(lambda a, b: (a * b) >> 32),
    "ivm:branch": _branch,
    "root:io:print_char": _print_char,
    "vi:io:split": lambda host, v: [v, IO] if v.type == "io" else None,
    "vi:io:merge": lambda host, a, b: a if a.type == "io" and b.type == "io" else None,
}


class IvmHost(Host):
    """Named nets from Ivy text, and the extrinsic functions above."""

    def __init__(self, nets, out=None):
        self.nets = nets
        self.out = out if out is not None else io.StringIO()

    def expand(self, net, name):
        if name not in self.nets:
            raise KeyError(f"no net named {name}")
        if any(path == "ivm:error" for path in _paths(self.nets[name])):
            net.flags.add("error")
        return ivy.instantiate(net, self.nets[name], agent_of)

    def call(self, net, function, values, ports):
        if function.name not in EXTRINSICS:
            raise NotImplementedError(f"inets.ivm has no extrinsic function {function.name}")
        if function.exchanged:
            values = values[::-1]
        result = EXTRINSICS[function.name](self, *values)
        if result is None:
            net.flags.add("ext_generic")
            result = [None] * len(ports)
        elif not isinstance(result, list):
            result = [result]
        for port, value in zip(ports, result):
            if value is None:
                net.wire(port, net.node("era"))
            elif isinstance(value, tuple):
                net.wire(port, net.node(value[0], param=value[1]))
            else:
                net.wire(port, net.node("val", param=value))


def _paths(equations):
    stack = [t for pair in equations for t in pair]
    while stack:
        t = stack.pop()
        if not isinstance(t, str):
            yield t[0]
            stack.extend(t[3])


@dataclass
class Run:
    """A finished run of a program: the net, why it stopped, what it printed, and the
    flags it raised (the IVM's names, with ``no_io`` if the IO value was not returned)."""
    net: Net
    result: Result
    output: str
    flags: set


def run(text, order="stack", seed=0, max_interactions=10 ** 7):
    """Runs a program given as Ivy text of the ``ivm:`` system, as ``ivm run`` starts it:
    ``iv:main`` meets a label-0 combinator holding the IO value and the result."""
    nets = ivy.read(text)
    host = IvmHost(nets)
    net = Net(bundled("ivm"), host)
    root = net.free()
    start = net.node("comb", net.node("val", param=IO), root, param=0)
    net.wire(net.node("graft", param="iv:main"), start)
    result = net.reduce(order, seed, max_interactions)
    flags = set(net.flags)
    end = net.link[root][0]
    if not (net.kind[end] == "val" and net.param[end].type == "io"):
        flags.add("no_io")
    return Run(net, result, host.out.getvalue(), flags)
