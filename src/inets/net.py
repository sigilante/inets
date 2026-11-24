"""A net of agents, and ways of reducing it by the rules of a :class:`~inets.system.System`.

A net is nodes and wires. A node is an agent with a parameter; port 0 is its principal port
and ports 1, 2, ... its auxiliary ports. A :class:`Port` is a node's number and a port
index, and a wire joins two ports. A *free port* is a wire's loose end: somewhere to attach
more net, or to read a result from. Where a wire joins two principal ports there is an
*active pair*, and a rule can fire.

Three schedules are given, and each says why it stopped (:class:`Result`):

- :meth:`Net.reduce` fires one active pair at a time, in a chosen order;
- :meth:`Net.reduce_in_rounds` fires every active pair, round by round, as a parallel
  machine would;
- :meth:`Net.reduce_by_need` fires only the pairs a cursor is waiting on, starting from a
  port whose value is wanted. It needs a table with signs, since "wanted" follows inputs.

For a table of local rules the first two reach the same net when they stop, in the same
number of interactions, whatever the order: that is a theorem about interaction nets, not
something this module checks. Reduction by need can stop where they do not, because it
leaves alone the pairs nobody is waiting on. What it reaches is a normal form of the part
of the net the wanted port can reach, not of the net.

Any schedule raises :class:`~inets.errors.Stuck` at an active pair that no rule applies to;
reduction by need raises it too when the value wanted depends on a free port.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import NamedTuple

from .errors import Error, Stuck
from .system import Call, Compare, Expand, Otherwise, Test

_FREE = "@"   # the kind of the stand-in node behind a free port


class Port(NamedTuple):
    """A port of a node: the node's number, and 0 for its principal port or 1, 2, ...
    for an auxiliary one."""
    node: int
    index: int


@dataclass
class Result:
    """Why a run stopped, and what it cost.

    ``reason`` is ``"normal"`` (no active pair is left), ``"wanted"`` (reduction by need
    has what it was asked for, and ``active_left`` pairs remain that nobody waited on), or
    ``"interactions"`` (the cap was reached).

    ``interactions`` is the number of rules applied in this run, whatever they are counted
    as. ``counts`` holds the statistics that those rules name, for this run; a rule counted
    ``none`` adds to ``interactions`` and not to ``counts``. For a run in rounds,
    ``rounds`` is their number, the net's span, and ``widest`` the most pairs fired in one.
    """
    reason: str
    interactions: int = 0
    counts: dict = field(default_factory=dict)
    active_left: int = 0
    rounds: int = 0
    widest: int = 0

    @property
    def finished(self):
        """Whether the run ended of its own accord, not at a cap."""
        return self.reason in ("normal", "wanted")


class Host:
    """What a table leaves to its surroundings: the nets that `expand` copies and the
    functions that `call` runs. Subclass it."""

    def expand(self, net, name):
        """Builds a new copy of the net called ``name`` and returns the port its free
        port is joined to: the port to join to whatever met the reference."""
        raise Error(f"this host has no net named {name!r}")

    def call(self, net, function, values, ports):
        """Runs the host function ``function`` on ``values`` and joins something to each
        of ``ports``."""
        raise Error(f"this host has no function {function!r}")


class Library(Host):
    """A host whose named nets are functions: ``Library({name: build})``, where
    ``build(net)`` makes a new copy and returns the port to join."""

    def __init__(self, nets=None):
        self.nets = dict(nets or {})

    def expand(self, net, name):
        if name not in self.nets:
            raise Error(f"no net is defined under the name {name!r}")
        return self.nets[name](net)


class Net:
    """A net of a system. ``kind`` maps each node's number to its agent's name, ``param``
    to its parameter (for those that have one), and ``link`` each port to the port it is
    joined to. ``counts``, ``interactions`` and ``flags`` accumulate over the net's life."""

    def __init__(self, system, host=None):
        self.system = system
        self.host = host or Host()
        self.kind, self.param, self.link = {}, {}, {}
        self.counts = {}
        self.flags = set()
        self.interactions = 0
        self._next = 0
        self._active = []
        self._references = {(r.left if r.body.param == r.left.param else r.right).agent
                            for r in system.rules if isinstance(r.body, Expand)}
        erasers = [a.name for a in system.agents.values() if a.signs == ("-",)]
        self._eraser = erasers[0] if len(erasers) == 1 else None

    # --- building ---------------------------------------------------------------------

    def add_node(self, kind, param=None):
        """A new node of an agent, its ports not yet joined; returns its number."""
        if kind != _FREE and kind not in self.system.agents:
            raise Error(f"no agent {kind!r} in this system")
        self._next += 1
        self.kind[self._next] = kind
        if param is not None:
            self.param[self._next] = param
        return self._next

    def make(self, kind, *aux, param=None):
        """A new node with its auxiliary ports joined to the ports ``aux``; returns its
        principal port."""
        n = self.add_node(kind, param)
        if len(aux) != self.system.agents[kind].arity:
            raise Error(f"{kind} has {self.system.agents[kind].arity} auxiliary ports, and {len(aux)} were given")
        for i, p in enumerate(aux, 1):
            self.wire(Port(n, i), p)
        return Port(n, 0)

    def free(self):
        """A new free port."""
        return Port(self.add_node(_FREE), 0)

    def wire(self, p, q):
        """Joins two ports."""
        p, q = Port(*p), Port(*q)
        self.link[p] = q
        self.link[q] = p
        if p.index == 0 and q.index == 0 and _FREE not in (self.kind[p.node], self.kind[q.node]):
            self._active.append((p.node, q.node))
            # Reduction by need fires pairs without taking them from this list, so it
            # would grow with every interaction; prune it once it far outgrows the net.
            if len(self._active) > 1024 + 2 * len(self.kind):
                self.active()

    def ports(self, n):
        """The ports of a node."""
        count = 1 if self.kind[n] == _FREE else self.system.agents[self.kind[n]].arity + 1
        return [Port(n, i) for i in range(count)]

    def is_free(self, port):
        """Whether a port is a free port."""
        return self.kind[port[0]] == _FREE

    def _delete(self, n):
        for p in self.ports(n):
            self.link.pop(p, None)
        del self.kind[n]
        self.param.pop(n, None)

    # --- one interaction --------------------------------------------------------------

    def _live(self, a, b):
        return a in self.kind and b in self.kind and self.link.get((a, 0)) == (b, 0)

    def active(self):
        """The active pairs, as pairs of node numbers."""
        self._active = [(a, b) for a, b in dict.fromkeys(self._active) if self._live(a, b)]
        return list(self._active)

    def _value(self, text, env):
        if text.isdigit():
            return int(text)
        name, _, attribute = text.partition(".")
        value = env[name]
        if attribute:
            value = value[attribute] if isinstance(value, dict) else getattr(value, attribute)
        return value

    def _holds(self, cond, env, rule, pair, peeked):
        if isinstance(cond, Otherwise):
            return True
        if isinstance(cond, Test):
            return bool(self._value(cond.expression, env)) != cond.negated
        if isinstance(cond, Compare):
            return (self._value(cond.left, env) == self._value(cond.right, env)) == cond.equal
        for side, n in zip((rule.left, rule.right), pair):
            if cond.port in side.aux:
                target = self.link[(n, side.aux.index(cond.port) + 1)]
                if target.index == 0 and self.kind[target.node] == cond.agent:
                    env[cond.name] = self.param.get(target.node)
                    peeked.append(target.node)
                    return True
        return False

    def fire(self, a, b):
        """One interaction between the nodes ``a`` and ``b``, whose principal ports are
        joined. Returns the rule applied."""
        for rule, turned in self.system.rules_for(self.kind[a], self.kind[b]):
            pair = (b, a) if turned else (a, b)
            env, peeked = {}, []
            for side, n in zip((rule.left, rule.right), pair):
                if side.param:
                    env[side.param] = self.param.get(n)
            if all(self._holds(c, env, rule, pair, peeked) for c in rule.when):
                break
        else:
            raise Stuck(f"no rule applies to {self.kind[a]} >< {self.kind[b]}")
        for flag, when in rule.flags:
            if all(self._holds(c, env, rule, pair, []) for c in when):
                self.flags.add(flag)
        if rule.count and rule.count != "none":
            self.counts[rule.count] = self.counts.get(rule.count, 0) + 1
        self.interactions += 1
        body = rule.body
        if isinstance(body, Expand):
            ref, other = pair if body.param == rule.left.param else pair[::-1]
            name = self.param.get(ref)
            self._delete(ref)
            del self.link[Port(other, 0)]
            self.wire(Port(other, 0), self.host.expand(self, name))
            return rule
        outside = {}
        for side, n in zip((rule.left, rule.right), pair):
            for i, letter in enumerate(side.aux, 1):
                outside[letter] = self.link[(n, i)]
        if isinstance(body, Call):
            # A port of the pair may be wired to another port of the pair. The host is
            # then given a stand-in for each, and what it joins to them is joined up.
            gone = set(pair) | set(peeked)
            stand_ins = {letter: self.free() for letter, p in outside.items() if p.node in gone}
            for n in gone:
                self._delete(n)
            self.host.call(self, self._value(body.function, env), [self._value(v, env) for v in body.values],
                           [stand_ins.get(p, outside[p]) for p in body.ports])
            self._join_stand_ins(rule, pair, outside, stand_ins)
            return rule
        # Two auxiliary ports of the pair may be joined to each other: a wire from the
        # pair back to itself. Such a wire carries on whatever the rule joins to one end
        # to whatever it joins to the other.
        own = {}
        for side, n, keep in zip((rule.left, rule.right), pair, body.keeps):
            if not keep:
                for i, letter in enumerate(side.aux, 1):
                    own[Port(n, i)] = letter
        inner = {letter: own[p] for letter, p in outside.items() if p in own}
        for n, keep in zip(pair, body.keeps):
            if keep:
                del self.link[Port(n, 0)]
            else:
                self._delete(n)
        for n in peeked:
            self._delete(n)
        made = [self.add_node(name, None if p is None else self._value(p, env)) for name, p in body.nodes]

        def port(end):
            if end[0] == "ext":
                return outside[end[1]]
            if end[0] == "pair":
                return Port(pair[end[1]], 0)
            return Port(made[end[1]], end[2])

        links = list(body.links)
        while links:
            x, y = links.pop()
            for _ in range(2):
                while x[0] == "ext" and x[1] in inner:
                    other = ("ext", inner[x[1]])
                    k = next((k for k, l in enumerate(links) if other in l), None)
                    if k is None:      # the wire closes on itself: a loop with nothing on it
                        x = None
                        break
                    l = links.pop(k)
                    x = l[1] if l[0] == other else l[0]
                if x is None:
                    break
                x, y = y, x
            if x is not None:
                self.wire(port(x), port(y))
        return rule

    def _join_stand_ins(self, rule, pair, outside, stand_ins):
        """After a host call: each stand-in took the place of a port of the pair that was
        wired to another port of the pair. Joins what the host joined to the two ends of
        each such wire, and removes the stand-ins."""
        letter_at = {}
        for side, n in zip((rule.left, rule.right), pair):
            for i, letter in enumerate(side.aux, 1):
                letter_at[Port(n, i)] = letter
        for letter, stand_in in list(stand_ins.items()):
            if stand_in.node not in self.kind:
                continue
            other = stand_ins.get(letter_at.get(outside[letter]))
            mine = self.link.get(stand_in)
            theirs = self.link.get(other) if other is not None and other.node in self.kind else None
            self._delete(stand_in.node)
            if other is not None and other.node in self.kind:
                self._delete(other.node)
            if mine is not None and theirs is not None:
                self.wire(mine, theirs)

    # --- schedules --------------------------------------------------------------------

    def _result(self, reason, start, before, **more):
        counts = {k: v - before.get(k, 0) for k, v in self.counts.items() if v != before.get(k, 0)}
        return Result(reason, self.interactions - start, counts, len(self.active()), **more)

    def reduce(self, order="stack", seed=0, max_interactions=10 ** 6):
        """Fires one active pair at a time until none is left, or until
        ``max_interactions`` have been made. ``order`` is ``"stack"`` (the newest pair
        first), ``"queue"`` (the oldest first) or ``"random"`` (with ``seed``)."""
        if order not in ("stack", "queue", "random"):
            raise Error('order is "stack", "queue" or "random"')
        start, before, rng = self.interactions, dict(self.counts), random.Random(seed)
        while self.interactions - start < max_interactions:
            pairs = self._active
            while pairs:
                i = -1 if order == "stack" else 0 if order == "queue" else rng.randrange(len(pairs))
                a, b = pairs.pop(i)
                if self._live(a, b):
                    break
            else:
                return self._result("normal", start, before)
            self.fire(a, b)
        return self._result("interactions" if self.active() else "normal", start, before)

    def reduce_in_rounds(self, max_interactions=10 ** 6):
        """Fires every active pair, round by round, until none is left. The cap is looked
        at between rounds, so a run may pass ``max_interactions`` by less than one round.
        The number of rounds is the net's span: the longest chain of interactions that
        must follow one another."""
        start, before, count, widest = self.interactions, dict(self.counts), 0, 0
        while True:
            pairs = self.active()
            if not pairs:
                return self._result("normal", start, before, rounds=count, widest=widest)
            if self.interactions - start >= max_interactions:
                return self._result("interactions", start, before, rounds=count, widest=widest)
            self._active = []
            for a, b in pairs:
                self.fire(a, b)
            count += 1
            widest = max(widest, len(pairs))

    def _is_value(self, n):
        return self.kind[n] != _FREE and self.system.agents[self.kind[n]].is_value

    def reduce_by_need(self, port, deep=True, sweep_above=20000, max_interactions=10 ** 6, collapse=()):
        """Reduces only what is needed for the term whose output is joined to the input
        ``port`` (usually a free port) to be a value; with ``deep``, for that value's
        inputs to be values too, and theirs, from the first. The table must have signs.

        A reference that nothing consumes is expanded by the cursor itself, and counted
        as ``expand``.

        Reduction by need never fires the pairs that would erase what is no longer
        wanted, so when the net passes ``sweep_above`` nodes it is swept (:meth:`sweep`),
        and again each time it reaches twice the size it was left at. 0 sweeps after every
        interaction, None never. Sweeping needs exactly one eraser in the table and is
        skipped, silently, without one. ``collapse`` is passed to each sweep, and its
        names are checked only when a sweep happens.

        Raises :class:`~inets.errors.Stuck` if the value wanted depends on a free port,
        waits on itself, or lies beyond a wire that joins two inputs (a net built against
        the table's signs); and :class:`~inets.errors.Error` for a table without signs.
        """
        if not self.system.signed:
            raise Error("reduction by need needs a table with signs")
        port = Port(*port)
        if port not in self.link:
            raise Error(f"the port {tuple(port)} is not wired to anything")
        start, before = self.interactions, dict(self.counts)
        sweep_at = sweep_above if self._eraser else None
        todo = [port]
        while todo:
            wanted = todo.pop()
            stack = [wanted]
            while stack:
                capped = self.interactions - start >= max_interactions
                at = self.link[stack[-1]]
                n = at.node
                # What an input is joined to must be an output. A net built against the
                # table's signs could otherwise keep the cursor going round for ever.
                if self.kind[n] != _FREE and self.system.agents[self.kind[n]].signs[at.index] != "+":
                    raise Stuck(f"an input is joined to an input (port {at.index} of a {self.kind[n]}): "
                                "the net does not keep to the table's signs")
                if self.kind[n] in self._references and len(stack) == 1:
                    if capped:
                        return self._result("interactions", start, before)
                    name = self.param.get(n)
                    self._delete(n)
                    self.wire(stack[-1], self.host.expand(self, name))
                    self.counts["expand"] = self.counts.get("expand", 0) + 1
                    self.interactions += 1
                    continue
                if self._is_value(n):
                    stack.pop()
                    continue
                if self.kind[n] == _FREE:
                    raise Stuck("the value wanted depends on a free port")
                # n is a consumer one of whose outputs is wanted: its own principal port
                # must first meet a value.
                m = self.link[Port(n, 0)]
                if m.index == 0 and self._is_value(m.node):
                    if capped:
                        return self._result("interactions", start, before)
                    self.fire(n, m.node)
                    if sweep_at is not None and len(self.kind) > sweep_at:
                        self.sweep([port, wanted] + todo, collapse)
                        sweep_at = max(2 * len(self.kind), sweep_above) if sweep_above else 0
                        stack = [wanted]
                elif Port(n, 0) in stack:
                    raise Stuck("a vicious circle: the value wanted waits on itself")
                else:
                    stack.append(Port(n, 0))
            if deep:
                v = self.link[wanted].node
                signs = self.system.agents[self.kind[v]].signs
                todo.extend(Port(v, i) for i in range(len(signs) - 1, 0, -1) if signs[i] == "-")
        return self._result("wanted", start, before)

    def sweep(self, roots, collapse=()):
        """Keeps the nodes that own the ports ``roots`` (usually free ports) and every
        node that can be reached from those by following inputs, and removes the rest.
        An output of a kept node that a removed node held is given to an eraser.
        The table must have signs and exactly one eraser (an agent whose only port is an
        input).

        ``collapse`` names duplicators: agents with an input for a principal port and two
        outputs, each a copy of what the input is joined to. A kept node of one of these
        that has lost one copy is removed instead, and its input joined to the copy that
        is left: copying and discarding a copy leaves the term as it was. This is a
        property of the agent, which the table cannot state, so the caller says which
        agents have it. ``()`` or None collapses nothing.

        Raises :class:`~inets.errors.Error` if a root is not wired to anything."""
        if not self._eraser:
            raise Error("sweeping needs a table with signs and exactly one eraser")
        if collapse is None:
            collapse = ()
        elif isinstance(collapse, str):
            collapse = (collapse,)
        roots = [Port(*r) for r in roots]
        for r in roots:
            if r not in self.link:
                raise Error(f"the root {tuple(r)} is not wired to anything")
        for name in collapse:
            agent = self.system.agents.get(name)
            if agent is None or agent.signs != ("-", "+", "+"):
                raise Error(f"only an agent with signs - + + can be collapsed, and {name!r} is not one")
        # The nodes that own the roots are kept, and everything their inputs lead to.
        live, stack = set(), [r.node for r in roots]
        while stack:
            n = stack.pop()
            if n in live:
                continue
            live.add(n)
            if self.kind[n] == _FREE:
                stack.append(self.link[Port(n, 0)].node)
                continue
            for j, sign in enumerate(self.system.agents[self.kind[n]].signs):
                if sign == "-":
                    stack.append(self.link[Port(n, j)].node)
        loose = []
        for n in [n for n in self.kind if n not in live]:
            loose.extend(q for q in (self.link.get(p) for p in self.ports(n)) if q is not None and q.node in live)
            self._delete(n)
        for q in loose:
            self.link.pop(q, None)
        for q in loose:
            n = q.node
            if self.kind.get(n) in collapse and q.index in (1, 2):
                if self.link.get(Port(n, 3 - q.index)) is None:
                    # Both copies lost: the duplicator itself is still held by its input's
                    # side, so it is given an eraser in its place.
                    source = self.link[Port(n, 0)]
                    self._delete(n)
                    self.link.pop(source, None)
                    self.wire(source, Port(self.add_node(self._eraser), 0))
                else:
                    source, other = self.link[Port(n, 0)], self.link[Port(n, 3 - q.index)]
                    self._delete(n)
                    self.wire(source, other)
            elif n in self.kind:
                self.wire(q, Port(self.add_node(self._eraser), 0))

    # --- looking ----------------------------------------------------------------------

    def dot(self, names=None):
        """The net as Graphviz text: a box for each node, a point for each free port, a
        thick red edge for each active pair, and port numbers at the ends of each wire
        (0 is the principal port). ``names`` may map free ports to labels to show."""
        names = {Port(*p).node: label for p, label in (names or {}).items()}
        out = ["graph net {", '  node [shape=box, fontname="Helvetica"];']
        for n, kind in sorted(self.kind.items()):
            if kind == _FREE and n in names:
                out.append(f'  n{n} [label="{names[n]}", shape=plaintext];')
            elif kind == _FREE:
                out.append(f'  n{n} [label="", shape=point];')
            else:
                out.append(f'  n{n} [label="{kind}{" " + str(self.param[n]) if n in self.param else ""}"];')
        seen = set()
        for p, q in self.link.items():
            if (q, p) in seen:
                continue
            seen.add((p, q))
            active = p.index == 0 and q.index == 0 and _FREE not in (self.kind[p.node], self.kind[q.node])
            style = ', penwidth=3, color="red"' if active else ""
            out.append(f'  n{p.node} -- n{q.node} [taillabel="{p.index}", headlabel="{q.index}"{style}];')
        out.append("}")
        return "\n".join(out)
