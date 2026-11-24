"""Interaction systems declared as tables: agents and rules, read from text and checked.

A table is lines of text::

    agent NAME PORTS [param P]
    rule LEFT >< RIGHT [when CONDITION]
      => BODY
      count NAME
      flag NAME [when CONDITION]
      note TEXT

``#`` starts a comment.

**Agents.** PORTS is either a number, the count of auxiliary ports, or a sign for each port
beginning with the principal one: ``+`` for an output, ``-`` for an input. A table gives
signs to all its agents or to none. ``param P`` says the agent carries a value, which the
rules call ``P``.

**Rules.** LEFT and RIGHT name an agent, its parameter if it has one, and its auxiliary
ports in brackets: ``comb l (a b)``. A rule for ``A >< B`` also serves ``B >< A``. Where a
pair has several rules the first whose condition holds is used.

CONDITION is tests joined by ``and``:

- ``x = y`` and ``x != y``, where each side is a parameter or a whole number;
- ``x.name`` and ``not x.name``, an attribute of a parameter's value;
- ``p is AGENT x``: the auxiliary port ``p`` is joined now to the principal port of an
  AGENT, whose parameter is then ``x`` (this looks at a neighbour, which a rule of an
  interaction net in the strict sense may not do);
- ``otherwise``, which always holds.

BODY is one of:

- ``nothing``: the pair vanishes;
- equations between ports, separated by ``;``. A letter bound on the left of the rule is
  the port that was joined there. Any other letter is a new wire and occurs exactly twice.
  ``AGENT p (x y)`` is a new node and stands for its principal port; its parameter may be
  written ``p.name`` for an attribute of a parameter's value. ``left`` and ``right`` stand
  for the pair's own two nodes, kept and joined to something new;
- ``expand P``: the agent whose parameter is ``P`` is replaced by a new copy of the net
  that ``P`` names, and the other agent stays;
- ``call F (v ...) -> p ...``: the host function named by the parameter ``F`` is given
  values and joins something to each port.

``count`` names the statistic the rule adds one to (``none`` for no count), and ``flag`` a
flag it sets.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TOKEN = re.compile(r"\s*(><|=>|->|!=|[()=;]|[A-Za-z_][A-Za-z_0-9.]*|[0-9]+)")


class TableError(Exception):
    """A table that cannot be read."""


def tokens(text):
    out, at = [], 0
    text = text.strip()
    while at < len(text):
        m = TOKEN.match(text, at)
        if not m:
            raise TableError("cannot read: " + text[at:])
        out.append(m.group(1))
        at = m.end()
    return out


@dataclass(frozen=True)
class Agent:
    name: str
    arity: int
    signs: tuple | None = None    # ("+", "-", ...) beginning with the principal port
    param: str | None = None

    @property
    def value(self):
        """Whether the principal port is an output (typed tables only)."""
        return self.signs is not None and self.signs[0] == "+"


@dataclass
class Rule:
    """One rule. ``nodes`` and ``links`` are the net an equation body makes: ``nodes`` is
    ``[(agent name, parameter expression or None)]`` and a link joins two ends, an end
    being ``("ext", letter)`` for what was joined to that auxiliary port of the pair,
    ``("new", node index, port index)``, or ``("pair", 0 or 1)`` for the principal port of
    the pair's left or right node, kept."""
    left: tuple = None            # (agent name, parameter letter or None, [letters])
    right: tuple = None
    when: list = field(default_factory=list)
    kind: str = "net"             # "net" | "expand" | "call"
    nodes: list = field(default_factory=list)
    links: list = field(default_factory=list)
    keeps: tuple = (False, False)  # whether the left and right nodes are kept
    expand: str | None = None
    call: tuple | None = None     # (function parameter, [value letters], [port letters])
    count: str | None = None
    flags: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    text: str = ""
    line: int = 0

    def title(self):
        def show(side):
            name, param, aux = side
            return name + (" " + param if param else "") + (" (" + " ".join(aux) + ")" if aux else "")
        when = " when " + " and ".join(" ".join(c) for c in self.when) if self.when else ""
        return show(self.left) + " >< " + show(self.right) + when.replace("and otherwise", "otherwise")

    @property
    def peeks(self):
        return any(len(c) == 4 for c in self.when)


@dataclass
class System:
    agents: dict
    rules: list
    name: str = ""

    def __post_init__(self):
        self.typed = any(a.signs is not None for a in self.agents.values())
        self.by_pair = {}
        for r in self.rules:
            self.by_pair.setdefault((r.left[0], r.right[0]), []).append((r, False))
            if r.left[0] != r.right[0]:
                self.by_pair.setdefault((r.right[0], r.left[0]), []).append((r, True))

    def rules_for(self, a, b):
        """The rules for the agent kinds ``a`` and ``b`` in order, each with whether it is
        written the other way round."""
        return self.by_pair.get((a, b), [])


# ---------------------------------------------------------------------------------------
# Reading.

def _side(toks, agents):
    name = toks.pop(0)
    if name not in agents:
        raise TableError(f"unknown agent {name}")
    agent = agents[name]
    param = toks.pop(0) if agent.param else None
    aux = []
    if agent.arity:
        if not toks or toks.pop(0) != "(":
            raise TableError(f"{name} needs its {agent.arity} ports in brackets")
        while toks[0] != ")":
            aux.append(toks.pop(0))
        toks.pop(0)
    if len(aux) != agent.arity:
        raise TableError(f"{name} has {agent.arity} auxiliary ports")
    return (name, param, aux)


def _when(toks):
    conds = []
    while toks:
        if toks[0] == "and":
            toks.pop(0)
        elif toks[0] == "not":
            conds.append(("not", toks[1]))
            del toks[:2]
        elif toks[0] == "otherwise":
            conds.append(("otherwise",))
            toks.pop(0)
        elif len(toks) >= 4 and toks[1] == "is":
            conds.append((toks[0], "is", toks[2], toks[3]))
            del toks[:4]
        elif len(toks) >= 3 and toks[1] in ("=", "!="):
            conds.append((toks[0], toks[1], toks[2]))
            del toks[:3]
        else:
            conds.append((toks.pop(0),))
    return conds


def _term(toks, agents, rule, raw):
    """An end, or ("var", letter). Makes nodes and raw links as it goes."""
    head = toks.pop(0)
    if head == "left":
        return ("pair", 0)
    if head == "right":
        return ("pair", 1)
    if head not in agents:
        return ("var", head)
    agent = agents[head]
    param = toks.pop(0) if agent.param else None
    index = len(rule.nodes)
    rule.nodes.append((head, param))
    if agent.arity:
        if not toks or toks.pop(0) != "(":
            raise TableError(f"{head} needs its {agent.arity} ports in brackets")
        port = 1
        while toks[0] != ")":
            raw.append((("new", index, port), _term(toks, agents, rule, raw)))
            port += 1
        toks.pop(0)
        if port != agent.arity + 1:
            raise TableError(f"{head} has {agent.arity} auxiliary ports")
    return ("new", index, 0)


def _body(text, agents, rule):
    toks = tokens(text)
    if toks == ["nothing"]:
        return
    if toks and toks[0] == "expand":
        if len(toks) != 2:
            raise TableError("expand takes one parameter")
        rule.kind, rule.expand = "expand", toks[1]
        return
    if toks and toks[0] == "call":
        if "(" not in toks or ")" not in toks or "->" not in toks:
            raise TableError("call F (values) -> ports")
        rule.kind = "call"
        rule.call = (toks[1], toks[toks.index("(") + 1:toks.index(")")], toks[toks.index("->") + 1:])
        return
    raw = []
    while toks:
        a = _term(toks, agents, rule, raw)
        if not toks or toks.pop(0) != "=":
            raise TableError("expected =")
        raw.append((a, _term(toks, agents, rule, raw)))
        if toks and toks.pop(0) != ";":
            raise TableError("expected ;")
    bound = set(rule.left[2] + rule.right[2])
    raw = [tuple(("ext", e[1]) if e[0] == "var" and e[1] in bound else e for e in pair) for pair in raw]
    # A new wire has two ends: join what they are joined to.
    while True:
        fresh = next((e for pair in raw for e in pair if e[0] == "var"), None)
        if fresh is None:
            break
        uses = [i for i, pair in enumerate(raw) if fresh in pair]
        if len(uses) == 1 and raw[uses[0]][0] == raw[uses[0]][1]:
            raise TableError(f"wire {fresh[1]} is joined to itself")
        if len(uses) != 2:
            raise TableError(f"new wire {fresh[1]} has {len(uses)} ends, not two")
        i, j = uses
        other = lambda pair: pair[1] if pair[0] == fresh else pair[0]
        joined = (other(raw[i]), other(raw[j]))
        raw = [pair for k, pair in enumerate(raw) if k not in (i, j)] + [joined]
    rule.links = raw
    ends = [e for pair in raw for e in pair]
    rule.keeps = (("pair", 0) in ends, ("pair", 1) in ends)


def parse(text, name=""):
    """A :class:`System` from the text of a table."""
    agents, rules, rule = {}, [], None
    for number, line in enumerate(text.split("\n"), 1):
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        word, rest = (line.split(None, 1) + [""])[:2]
        try:
            if word == "agent":
                parts = rest.split()
                param = None
                if "param" in parts:
                    param = parts[parts.index("param") + 1]
                    parts = parts[:parts.index("param")]
                if len(parts) == 2 and parts[1].isdigit():
                    agents[parts[0]] = Agent(parts[0], int(parts[1]), None, param)
                elif len(parts) >= 2 and all(p in "+-" for p in parts[1:]):
                    agents[parts[0]] = Agent(parts[0], len(parts) - 2, tuple(parts[1:]), param)
                else:
                    raise TableError("agent NAME, then a number of auxiliary ports or a sign for each port")
            elif word == "rule":
                rule = Rule(line=number)
                rules.append(rule)
                sides, _, when = rest.partition(" when ")
                if "><" not in sides:
                    raise TableError("rule LEFT >< RIGHT")
                left, right = sides.split("><")
                rule.left, rule.right = _side(tokens(left), agents), _side(tokens(right), agents)
                rule.when = _when(tokens(when))
            elif rule is None:
                raise TableError("expected agent or rule")
            elif word == "=>":
                rule.text = rest.strip()
                _body(rest, agents, rule)
            elif word == "count":
                rule.count = rest.strip()
            elif word == "flag":
                flag, _, when = rest.partition(" when ")
                rule.flags.append((flag.strip(), _when(tokens(when))))
            elif word == "note":
                rule.notes.append(rest.strip())
            else:
                raise TableError("unknown line")
        except (TableError, IndexError) as e:
            raise TableError(f"{name or 'table'}:{number}: {e}") from None
    return System(agents, rules, name)


def load(path):
    """A :class:`System` from a file."""
    with open(path, encoding="utf-8") as f:
        return parse(f.read(), str(path))


# ---------------------------------------------------------------------------------------
# Checking.

def _complete(group):
    """Whether the conditions of a pair's rules, in order, leave no case out, as far as
    this can tell: the last is unconditional or `otherwise`, or two rules are each
    other's opposite."""
    last = group[-1].when
    if not last or last[-1] == ("otherwise",):
        return True
    seen = {tuple(r.when) for r in group}
    for when in seen:
        if len(when) == 1:
            c = when[0]
            if len(c) == 3 and ((c[0], "!=" if c[1] == "=" else "=", c[2]),) in seen:
                return True
            if len(c) == 1 and (("not", c[0]),) in seen:
                return True
    return False


def check(system):
    """Problems with a table, as a list of sentences; empty if none were found.

    For every table: each rule has a count; a rule that is a net uses every auxiliary
    port of its pair exactly once and gives every port of every new node exactly one
    connection (so the net it makes has the same free ports as the pair); the parameters
    it uses are in hand; and where a pair has several rules their conditions leave no
    case out, as far as can be told.

    For a table without signs: every pair of agents has a rule.

    For a table with signs: rules are written consumer >< value, there is one for every
    such pair, and every connection a rule makes joins an output to an input. Then in a
    net whose wires each join an output to an input, the only principal ports that can
    meet are a consumer's and a value's, and each such pair has a rule.
    """
    problems = []
    agents = system.agents
    if system.typed and any(a.signs is None for a in agents.values()):
        problems.append("some agents have signs and some do not")
        return problems
    flip = {"+": "-", "-": "+"}
    groups = {}
    for r in system.rules:
        left, right = agents[r.left[0]], agents[r.right[0]]
        where = f"line {r.line}"
        groups.setdefault(frozenset([left.name, right.name]), []).append(r)
        if r.count is None:
            problems.append(f"{where}: no count")
        if system.typed and (left.value or not right.value):
            problems.append(f"{where}: with signs, a rule is written consumer >< value")
            continue
        letters = r.left[2] + r.right[2]
        if len(set(letters)) != len(letters):
            problems.append(f"{where}: a letter names two ports")
        bound = [c[3] for c in r.when if len(c) == 4]
        params = {p for p in (r.left[1], r.right[1]) if p} | set(bound)
        root = lambda expression: expression.split(".")[0]
        if r.kind == "expand":
            if r.expand not in (r.left[1], r.right[1]):
                problems.append(f"{where}: expand needs the parameter of one of the pair")
            else:
                side = r.left if r.expand == r.left[1] else r.right
                if side[2]:
                    problems.append(f"{where}: the agent that is expanded must have no auxiliary ports")
            continue
        if r.kind == "call":
            f, values, ports = r.call
            for v in [f] + values:
                if root(v) not in params:
                    problems.append(f"{where}: {v} is not a parameter in hand")
            peeked = [c[0] for c in r.when if len(c) == 4]
            used = ports + peeked
            for letter in letters:
                if used.count(letter) != 1:
                    problems.append(f"{where}: port {letter} is used {used.count(letter)} times, not once")
            continue
        for name, param in r.nodes:
            if (param is None) != (agents[name].param is None):
                problems.append(f"{where}: {name} is given a parameter it does not take, or lacks one")
            elif param is not None and not param.isdigit() and root(param) not in params:
                problems.append(f"{where}: {param} is not a parameter in hand")
        used = [e[1] for pair in r.links for e in pair if e[0] == "ext"]
        peeked = [c[0] for c in r.when if len(c) == 4]
        for letter in letters:
            n = used.count(letter) + peeked.count(letter)
            kept = (letter in r.left[2] and r.keeps[0]) or (letter in r.right[2] and r.keeps[1])
            if n != (0 if kept else 1):
                problems.append(f"{where}: port {letter} is used {n} times, not {'at all (its node is kept)' if kept else 'once'}")
        ends = [e for pair in r.links for e in pair if e[0] == "new"]
        for index, (name, _) in enumerate(r.nodes):
            for port in range(agents[name].arity + 1):
                if ends.count(("new", index, port)) != 1:
                    problems.append(f"{where}: port {port} of the new {name} is joined {ends.count(('new', index, port))} times")
        if system.typed:
            outside = {}
            for (name, _, aux), agent in ((r.left, left), (r.right, right)):
                for letter, sign in zip(aux, agent.signs[1:]):
                    outside[letter] = flip[sign]

            def sign(end):
                if end[0] == "ext":
                    return outside[end[1]]
                if end[0] == "pair":
                    return (left, right)[end[1]].signs[0]
                return agents[r.nodes[end[1]][0]].signs[end[2]]

            for a, b in r.links:
                if sign(a) == sign(b):
                    problems.append(f"{where}: joins two {'outputs' if sign(a) == '+' else 'inputs'}")
    names = sorted(agents)
    for i, a in enumerate(names):
        for b in names[i:]:
            group = groups.get(frozenset([a, b]))
            if system.typed:
                wanted = agents[a].value != agents[b].value
                if group and not wanted:
                    problems.append(f"{a} >< {b}: a rule between two {'values' if agents[a].value else 'consumers'}")
                elif wanted and not group:
                    consumer, value = (b, a) if agents[a].value else (a, b)
                    problems.append(f"no rule for {consumer} >< {value}")
            elif not group:
                problems.append(f"no rule for {a} >< {b}")
            if group and not _complete(group):
                problems.append(f"{a} >< {b}: the conditions may leave a case out (end with `otherwise`)")
    return problems
