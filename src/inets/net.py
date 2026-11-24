"""A net of agents, and ways of reducing it by the rules of a :class:`~inets.system.System`.

A net is nodes and wires. A node is an agent with a parameter; port 0 is its principal port
and ports 1, 2, ... its auxiliary ports. A port is the pair ``(node, index)``, and a wire
joins two ports. Where a wire joins two principal ports there is an *active pair*, and a
rule can fire.

Three schedules are given, and each says why it stopped (:class:`Result`):

- :meth:`Net.reduce` fires one active pair at a time, in a chosen order;
- :meth:`Net.rounds` fires every active pair, round by round, as a parallel machine would;
- :meth:`Net.by_need` fires only the pairs a cursor is waiting on, starting from a port
  whose value is wanted. It needs a table with signs, since "wanted" follows the inputs.

For a table of local rules the first two reach the same net when they stop, in the same
number of interactions, whatever the order. Reduction by need can stop where they do not,
because it leaves alone the pairs nobody is waiting on: what it reaches is a normal form of
the part of the net the wanted port can reach, not of the net.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

FREE = "@"   # the kind of a free port's stand-in node


class Stuck(Exception):
    """An active pair that no rule applies to."""


@dataclass
class Result:
    """Why a run stopped, and what it cost.

    ``reason`` is ``"normal"`` (no active pair is left), ``"wanted"`` (reduction by need
    has what it was asked for; ``active_left`` pairs remain that nobody waited on),
    ``"interactions"`` or ``"nodes"`` (a cap was reached).

    ``interactions`` is the number of rules applied, whatever they are counted as;
    ``counts`` holds the statistics the table's rules name, in which a rule counted
    ``none`` does not appear.
    """
    reason: str
    interactions: int = 0
    rounds: int = 0          # for `rounds`: the number of rounds, the net's span
    widest: int = 0          # for `rounds`: the most pairs fired in one round
    active_left: int = 0
    counts: dict = field(default_factory=dict)

    @property
    def stopped(self):
        """Whether the run ended of its own accord, not at a cap."""
        return self.reason in ("normal", "wanted")


class Host:
    """What a table leaves to its surroundings: the nets that `expand` copies and the
    functions that `call` runs. Subclass it, or use the default with :meth:`Net.define`."""

    def expand(self, net, name):
        """Builds a new copy of the net called ``name`` and returns its free port's
        partner: the port to join to whatever met the reference."""
        try:
            build = net.definitions[name]
        except KeyError:
            raise KeyError(f"no net is defined under the name {name!r}") from None
        return build(net)

    def call(self, net, function, values, ports):
        """Runs the host function ``function`` on ``values`` and joins something to each
        of ``ports``."""
        raise NotImplementedError(f"this host has no function {function!r}")


class Net:
    def __init__(self, system, host=None):
        self.system = system
        self.host = host or Host()
        self.kind, self.param, self.link = {}, {}, {}
        self.definitions = {}
        self._next = 0
        self._active = []
        self.counts = {}
        self.used = {}            # a rule's line in its table -> times applied
        self.flags = set()
        self.interactions = 0
        self.most = 0             # the most nodes at once
        self.sweeps = 0
        # Reduction by need sweeps away what its root cannot reach when the net passes
        # `sweep_at` nodes, then sets `sweep_at` to twice what is left or `sweep_floor`.
        self.sweep_floor = 20000
        self.sweep_at = self.sweep_floor
        self.sweep_always = False
        self._references = {r.left[0] if r.expand == r.left[1] else r.right[0]
                            for r in system.rules if r.kind == "expand"}
        erasers = [a.name for a in system.agents.values() if a.signs == ("-",)]
        self._eraser = erasers[0] if len(erasers) == 1 else None

    # --- building ---------------------------------------------------------------------

    def new(self, kind, param=None):
        """A new node of an agent; returns its number. Its ports are ``(n, 0)``,
        ``(n, 1)``, ..."""
        if kind != FREE and kind not in self.system.agents:
            raise KeyError(f"no agent {kind!r} in this system")
        self._next += 1
        self.kind[self._next] = kind
        if param is not None:
            self.param[self._next] = param
        if len(self.kind) > self.most:
            self.most = len(self.kind)
        return self._next

    def free(self):
        """A free port of the net: somewhere to leave a wire's other end."""
        return (self.new(FREE), 0)

    def wire(self, p, q):
        """Joins two ports."""
        self.link[p] = q
        self.link[q] = p
        if p[1] == 0 and q[1] == 0 and self.kind[p[0]] != FREE and self.kind[q[0]] != FREE:
            self._active.append((p[0], q[0]))

    def node(self, kind, *ports, param=None):
        """A new node with its auxiliary ports joined to ``ports``; returns its
        principal port."""
        n = self.new(kind, param)
        for i, p in enumerate(ports, 1):
            self.wire((n, i), p)
        return (n, 0)

    def define(self, name, build):
        """Names a net: ``build(net)`` must make a new copy and return its free port's
        partner. Used by `expand` rules with the default :class:`Host`."""
        self.definitions[name] = build

    def ports(self, n):
        return range(self.system.agents[self.kind[n]].arity + 1) if self.kind[n] != FREE else range(1)

    def _delete(self, n):
        for i in self.ports(n):
            self.link.pop((n, i), None)
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

    def _holds(self, cond, env, nodes, peeked):
        if cond == ("otherwise",):
            return True
        if cond[0] == "not":
            return not self._value(cond[1], env)
        if len(cond) == 4:
            letter, _, agent, name = cond
            for (kind, _, aux), n in zip(nodes[0], nodes[1]):
                if letter in aux:
                    target = self.link[(n, aux.index(letter) + 1)]
                    if target[1] == 0 and self.kind[target[0]] == agent:
                        env[name] = self.param.get(target[0])
                        peeked.append(target[0])
                        return True
            return False
        if len(cond) == 3:
            return (self._value(cond[0], env) == self._value(cond[2], env)) == (cond[1] == "=")
        return bool(self._value(cond[0], env))

    def fire(self, a, b):
        """One interaction between the nodes ``a`` and ``b``, whose principal ports are
        joined. Returns the rule applied."""
        for rule, turned in self.system.rules_for(self.kind[a], self.kind[b]):
            pair = (b, a) if turned else (a, b)
            env, peeked = {}, []
            for side, n in zip((rule.left, rule.right), pair):
                if side[1]:
                    env[side[1]] = self.param.get(n)
            if all(self._holds(c, env, ((rule.left, rule.right), pair), peeked) for c in rule.when):
                break
        else:
            raise Stuck(f"no rule applies to {self.kind[a]} >< {self.kind[b]}")
        left, right = pair
        for flag, when in rule.flags:
            if all(self._holds(c, env, ((rule.left, rule.right), pair), []) for c in when):
                self.flags.add(flag)
        if rule.count and rule.count != "none":
            self.counts[rule.count] = self.counts.get(rule.count, 0) + 1
        self.used[rule.line] = self.used.get(rule.line, 0) + 1
        self.interactions += 1
        if rule.kind == "expand":
            ref, other = (left, right) if rule.expand == rule.left[1] else (right, left)
            name = self.param.get(ref)
            self._delete(ref)
            del self.link[(other, 0)]
            self.wire((other, 0), self.host.expand(self, name))
            return rule
        outside = {}
        for side, n in zip((rule.left, rule.right), pair):
            for i, letter in enumerate(side[2], 1):
                outside[letter] = self.link[(n, i)]
        if rule.kind == "call":
            function, values, ports = rule.call
            for n in (left, right, *peeked):
                self._delete(n)
            self.host.call(self, self._value(function, env), [self._value(v, env) for v in values],
                           [outside[p] for p in ports])
            return rule
        for n, keep in zip(pair, rule.keeps):
            if keep:
                del self.link[(n, 0)]
            else:
                self._delete(n)
        for n in peeked:
            self._delete(n)
        made = [self.new(name, None if p is None else self._value(p, env)) for name, p in rule.nodes]
        # Two auxiliary ports of the pair may be joined to each other (a wire from the
        # pair back to itself). Such a wire carries on whatever the rule joins to one end
        # to whatever it joins to the other.
        own = {}
        for side, n, keep in zip((rule.left, rule.right), pair, rule.keeps):
            if not keep:
                for i, letter in enumerate(side[2], 1):
                    own[(n, i)] = letter
        inner = {letter: own[p] for letter, p in outside.items() if p in own}
        links = list(rule.links)

        def port(end):
            if end[0] == "ext":
                return outside[end[1]]
            if end[0] == "pair":
                return (pair[end[1]], 0)
            return (made[end[1]], end[2])

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

    # --- schedules --------------------------------------------------------------------

    def _result(self, reason, start, **more):
        return Result(reason, self.interactions - start, active_left=len(self.active()),
                      counts=dict(self.counts), **more)

    def reduce(self, order="stack", seed=0, max_interactions=10 ** 6, max_nodes=10 ** 6):
        """Fires one active pair at a time until none is left. ``order`` is ``"stack"``
        (the newest pair first), ``"queue"`` (the oldest first) or ``"random"``."""
        start, rng = self.interactions, random.Random(seed)
        while True:
            pairs = self._active
            while pairs:
                i = {"stack": -1, "queue": 0}.get(order)
                if i is None:
                    i = rng.randrange(len(pairs))
                a, b = pairs.pop(i)
                if self._live(a, b):
                    break
            else:
                return self._result("normal", start)
            self.fire(a, b)
            if self.interactions - start >= max_interactions:
                return self._result("interactions", start)
            if len(self.kind) > max_nodes:
                return self._result("nodes", start)

    def rounds(self, max_interactions=10 ** 6, max_nodes=10 ** 6, each=None):
        """Fires every active pair, round by round. ``each(net, round, pairs)``, if given,
        is called before each round. The number of rounds is the net's span: the longest
        chain of interactions that must follow one another."""
        start, count, widest = self.interactions, 0, 0
        while True:
            pairs = self.active()
            if not pairs:
                return self._result("normal", start, rounds=count, widest=widest)
            if each:
                each(self, count, pairs)
            self._active = []
            for a, b in pairs:
                self.fire(a, b)
            count += 1
            widest = max(widest, len(pairs))
            if self.interactions - start >= max_interactions:
                return self._result("interactions", start, rounds=count, widest=widest)
            if len(self.kind) > max_nodes:
                return self._result("nodes", start, rounds=count, widest=widest)

    def _is_value(self, n):
        kind = self.kind[n]
        return kind != FREE and self.system.agents[kind].value

    def _want(self, port, start, max_interactions, max_nodes, roots):
        """Fires what is needed for the output joined to the input ``port`` to be a
        value's principal port. Returns a cap's name, or None."""
        stack = [port]
        while stack:
            n, i = self.link[stack[-1]]
            if self.kind[n] in self._references and len(stack) == 1:
                # A reference that nothing consumes is expanded by the cursor.
                name = self.param.get(n)
                self._delete(n)
                self.link.pop(stack[-1], None)
                self.wire(stack[-1], self.host.expand(self, name))
                self.counts["expand"] = self.counts.get("expand", 0) + 1
                self.interactions += 1
                continue
            if self._is_value(n):
                stack.pop()
                continue
            # n is a consumer one of whose outputs is wanted: its own principal port
            # must first meet a value.
            m, j = self.link[(n, 0)]
            if j == 0 and self.kind[m] != FREE and (self._is_value(m)):
                self.fire(n, m)
                if self.interactions - start >= max_interactions:
                    return "interactions"
                if self.sweep_always or len(self.kind) > min(self.sweep_at, max_nodes):
                    if self._eraser:
                        self.sweep(roots)
                        self.sweep_at = max(2 * len(self.kind), self.sweep_floor)
                    if len(self.kind) > max_nodes:
                        return "nodes"
                    stack = [port]
            elif self.kind[m] == FREE:
                raise Stuck("the value wanted depends on a free port")
            else:
                stack.append((n, 0))
        return None

    def by_need(self, port, deep=True, max_interactions=10 ** 6, max_nodes=10 ** 6):
        """Reduces only what is needed for the term whose output is joined to the input
        ``port`` (usually a free port) to be a value; with ``deep``, for its arguments to
        be values too, and theirs, from the left. The table must have signs."""
        if not self.system.typed:
            raise ValueError("reduction by need needs a table with signs")
        start, todo = self.interactions, [port]
        while todo:
            p = todo.pop()
            cap = self._want(p, start, max_interactions, max_nodes, [port])
            if cap:
                return self._result(cap, start)
            if deep:
                v = self.link[p][0]
                signs = self.system.agents[self.kind[v]].signs
                todo.extend((v, i) for i in range(len(signs) - 1, 0, -1) if signs[i] == "-")
        return self._result("wanted", start)

    def sweep(self, roots):
        """Removes every node that the input ports ``roots`` cannot reach by following
        inputs. An output of a kept node that a removed node held is given to an eraser.
        This is housekeeping for reduction by need, which never fires the pairs that
        would have erased those nodes; it needs a table with signs and one eraser (an
        agent whose only port is an input)."""
        if not self._eraser:
            raise ValueError("sweeping needs a table with signs and exactly one eraser")
        live, stack = set(), [self.link[r] for r in roots]
        while stack:
            n = stack.pop()[0]
            if n in live:
                continue
            live.add(n)
            if self.kind[n] == FREE:
                continue
            for j, sign in enumerate(self.system.agents[self.kind[n]].signs):
                if sign == "-":
                    stack.append(self.link[(n, j)])
        live.update(r[0] for r in roots)
        loose = []
        for n in [n for n in self.kind if n not in live]:
            for j in self.ports(n):
                q = self.link.get((n, j))
                if q is not None and q[0] in live:
                    loose.append(q)
            self._delete(n)
        for q in loose:
            self.link.pop(q, None)
            self.wire(q, (self.new(self._eraser), 0))
        self.sweeps += 1

    # --- looking ----------------------------------------------------------------------

    def dot(self, title=""):
        """The net as Graphviz text: a box for each node, a thick edge for each active
        pair, and port numbers at the ends of each wire (0 is the principal port)."""
        out = ["graph net {", '  node [shape=box, fontname="Helvetica"];']
        if title:
            out.append(f'  label="{title}";')
        for n, kind in sorted(self.kind.items()):
            label = "" if kind == FREE else kind + (f" {self.param[n]}" if n in self.param else "")
            shape = ', shape=point' if kind == FREE else ""
            out.append(f'  n{n} [label="{label}"{shape}];')
        seen = set()
        for p, q in self.link.items():
            if (q, p) in seen:
                continue
            seen.add((p, q))
            active = p[1] == 0 and q[1] == 0 and FREE not in (self.kind[p[0]], self.kind[q[0]])
            style = ', penwidth=3, color="red"' if active else ""
            out.append(f'  n{p[0]} -- n{q[0]} [taillabel="{p[1]}", headlabel="{q[1]}"{style}];')
        out.append("}")
        return "\n".join(out)
