"""Interaction systems declared as tables: agents and rules, read from text and checked.

A table is lines of text::

    agent NAME PORTS [param P] [duplicator]
    rule LEFT >< RIGHT [when CONDITION]
      => BODY
      count NAME
      flag NAME [when CONDITION]

``#`` starts a comment.

**Agents.** PORTS is either a number, the count of auxiliary ports (``agent con 2``), or a
sign for every port beginning with the principal one, ``+`` for an output and ``-`` for an
input (``agent app - - +`` has two auxiliary ports). A table gives signs to all its agents
or to none; :meth:`System.check` reports a mixture. ``param P`` says the agent carries a
value, which the rules call ``P``. ``duplicator`` says the agent's two outputs are each a
copy of what its input is joined to, which a table can state but its rules cannot show;
such an agent has signs ``- + +``. A sweep (:meth:`inets.Net.sweep`) removes a duplicator
that has lost one of its copies.

**Rules.** LEFT and RIGHT name an agent, its parameter if it has one, and its auxiliary
ports in brackets: ``comb l (a b)``. A rule for ``A >< B`` also serves ``B >< A``. Where a
pair has several rules the first whose condition holds is used.

CONDITION is tests joined by ``and``:

- ``x = y`` and ``x != y``, where each side is a parameter, an attribute of one
  (``x.name``), or a whole number;
- ``x.name`` and ``not x.name``, an attribute of a parameter's value;
- ``p is AGENT x``: the auxiliary port ``p`` is joined now to the principal port of an
  AGENT, whose parameter is then ``x``. That neighbour is consumed with the pair. (This
  looks beyond the pair, which a rule of an interaction net in the strict sense may not.)
- ``otherwise``, which always holds.

BODY is one of:

- ``nothing``: the pair vanishes;
- equations between ports, separated by ``;``. A letter bound on the left of the rule is
  the port that was joined there. Any other letter is a new wire and occurs exactly twice.
  ``AGENT p (x y)`` is a new node and stands for its principal port; its parameter may be
  a number, a parameter in hand, or an attribute of one (``p.name``). ``left`` and
  ``right`` stand for the pair's own two nodes, kept and joined to something new;
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
from importlib import resources
from typing import NamedTuple

from .errors import TableError

TOKEN = re.compile(r"\s*(><|=>|->|!=|[()=;]|[A-Za-z_][A-Za-z_0-9.]*|[0-9]+)")
BUNDLED = ("combinators", "ski", "lazy", "ivm")


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
    arity: int                       # the number of auxiliary ports
    signs: tuple | None = None       # ("+", "-", ...) beginning with the principal port
    param: str | None = None
    duplicator: bool = False         # its two outputs are copies of what its input holds

    @property
    def is_value(self):
        """Whether the principal port is an output. False in a table without signs."""
        return self.signs is not None and self.signs[0] == "+"


class Side(NamedTuple):
    """One side of a rule: an agent's name, the letter for its parameter (or None), and
    the letters for its auxiliary ports."""
    agent: str
    param: str | None
    aux: tuple


# --- conditions ---

@dataclass(frozen=True)
class Compare:
    """``left = right`` or ``left != right``."""
    left: str
    right: str
    equal: bool

    def __str__(self):
        return f"{self.left} {'=' if self.equal else '!='} {self.right}"


@dataclass(frozen=True)
class Test:
    """``x.name`` or ``not x.name``."""
    expression: str
    negated: bool = False

    def __str__(self):
        return ("not " if self.negated else "") + self.expression


@dataclass(frozen=True)
class Peek:
    """``port is AGENT name``: looks at the neighbour on an auxiliary port."""
    port: str
    agent: str
    name: str

    def __str__(self):
        return f"{self.port} is {self.agent} {self.name}"


@dataclass(frozen=True)
class Otherwise:
    def __str__(self):
        return "otherwise"


# --- bodies ---

@dataclass(frozen=True)
class Ext:
    """An end of a link in a rule's body: what was joined to the pair's auxiliary port
    named ``letter``."""
    letter: str


@dataclass(frozen=True)
class New:
    """An end of a link in a rule's body: port ``port`` (0 is the principal port) of the
    new node ``node``, an index into :attr:`Rewrite.nodes`."""
    node: int
    port: int


@dataclass(frozen=True)
class Pair:
    """An end of a link in a rule's body: the principal port of the pair's left (``side``
    0) or right (1) node, which is then kept."""
    side: int


@dataclass(frozen=True)
class _Var:
    letter: str


@dataclass
class Rewrite:
    """A body that is a net (``nothing`` is the empty one). ``nodes`` is ``[(agent name,
    parameter expression or None)]``. ``links`` is a list of pairs of ends, each an
    :class:`Ext`, a :class:`New` or a :class:`Pair`."""
    nodes: list = field(default_factory=list)
    links: list = field(default_factory=list)

    @property
    def keeps(self):
        ends = [e for link in self.links for e in link]
        return (Pair(0) in ends, Pair(1) in ends)


@dataclass
class Expand:
    """``expand P``."""
    param: str


@dataclass
class Call:
    """``call F (values) -> ports``."""
    function: str
    values: list
    ports: list


@dataclass
class Rule:
    left: Side
    right: Side
    when: list = field(default_factory=list)
    body: Rewrite | Expand | Call | None = None
    count: str | None = None
    flags: list = field(default_factory=list)      # [(flag name, [conditions])]
    line: int = 0

    def __str__(self):
        def show(side):
            return side.agent + (" " + side.param if side.param else "") + (" (" + " ".join(side.aux) + ")" if side.aux else "")
        when = " when " + " and ".join(str(c) for c in self.when) if self.when else ""
        return show(self.left) + " >< " + show(self.right) + when

    @property
    def not_local(self):
        """The ways in which this is not a rule of an interaction net in the strict
        sense, as a list of phrases; empty for a local rule."""
        marks = []
        if any(isinstance(c, Peek) for c in self.when):
            marks.append("looks at a neighbour")
        if isinstance(self.body, Expand):
            marks.append("expands a named net")
        if isinstance(self.body, Call):
            marks.append("calls the host")
        if isinstance(self.body, Rewrite) and any(self.body.keeps):
            marks.append("keeps a node")
        return marks


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
    if toks:
        raise TableError(f"unexpected {toks[0]} after {name}")
    return Side(name, param, tuple(aux))


def _when(toks):
    conds = []
    while toks:
        if toks[0] == "and":
            toks.pop(0)
        elif toks[0] == "not":
            conds.append(Test(toks[1], True))
            del toks[:2]
        elif toks[0] == "otherwise":
            conds.append(Otherwise())
            toks.pop(0)
        elif len(toks) >= 4 and toks[1] == "is":
            conds.append(Peek(toks[0], toks[2], toks[3]))
            del toks[:4]
        elif len(toks) >= 3 and toks[1] in ("=", "!="):
            conds.append(Compare(toks[0], toks[2], toks[1] == "="))
            del toks[:3]
        else:
            conds.append(Test(toks.pop(0)))
    return conds


def _term(toks, agents, body, raw):
    """An end, or ("var", letter). Makes nodes and raw links as it goes."""
    head = toks.pop(0)
    if head in ("left", "right"):
        return Pair(int(head == "right"))
    if head not in agents:
        return _Var(head)
    agent = agents[head]
    param = toks.pop(0) if agent.param else None
    index = len(body.nodes)
    body.nodes.append((head, param))
    if agent.arity:
        if not toks or toks.pop(0) != "(":
            raise TableError(f"{head} needs its {agent.arity} ports in brackets")
        port = 1
        while toks[0] != ")":
            raw.append((New(index, port), _term(toks, agents, body, raw)))
            port += 1
        toks.pop(0)
        if port != agent.arity + 1:
            raise TableError(f"{head} has {agent.arity} auxiliary ports")
    return New(index, 0)


def _body(text, agents, rule):
    toks = tokens(text)
    if toks == ["nothing"]:
        return Rewrite()
    if toks and toks[0] == "expand":
        if len(toks) != 2:
            raise TableError("expand takes one parameter")
        return Expand(toks[1])
    if toks and toks[0] == "call":
        if "(" not in toks or ")" not in toks or "->" not in toks:
            raise TableError("call F (values) -> ports")
        return Call(toks[1], toks[toks.index("(") + 1:toks.index(")")], toks[toks.index("->") + 1:])
    body, raw = Rewrite(), []
    while toks:
        a = _term(toks, agents, body, raw)
        if not toks or toks.pop(0) != "=":
            raise TableError("expected =")
        raw.append((a, _term(toks, agents, body, raw)))
        if toks and toks.pop(0) != ";":
            raise TableError("expected ;")
    bound = set(rule.left.aux + rule.right.aux)
    raw = [tuple(Ext(e.letter) if isinstance(e, _Var) and e.letter in bound else e for e in pair) for pair in raw]
    # A new wire has two ends: join what they are joined to.
    while True:
        fresh = next((e for pair in raw for e in pair if isinstance(e, _Var)), None)
        if fresh is None:
            break
        uses = [i for i, pair in enumerate(raw) if fresh in pair]
        if len(uses) == 1 and raw[uses[0]][0] == raw[uses[0]][1]:
            raise TableError(f"wire {fresh.letter} is joined to itself")
        if len(uses) != 2:
            raise TableError(f"new wire {fresh.letter} has {len(uses)} ends, not two")
        i, j = uses
        other = lambda pair: pair[1] if pair[0] == fresh else pair[0]
        joined = (other(raw[i]), other(raw[j]))
        raw = [pair for k, pair in enumerate(raw) if k not in (i, j)] + [joined]
    body.links = raw
    return body


@dataclass
class System:
    """An interaction system: its agents by name, and its rules in order."""
    agents: dict
    rules: list
    name: str = ""

    def __post_init__(self):
        self.signed = any(a.signs is not None for a in self.agents.values())
        self.duplicators = tuple(a.name for a in self.agents.values() if a.duplicator)
        self._by_pair = {}
        for r in self.rules:
            self._by_pair.setdefault((r.left.agent, r.right.agent), []).append((r, False))
            if r.left.agent != r.right.agent:
                self._by_pair.setdefault((r.right.agent, r.left.agent), []).append((r, True))

    def rules_for(self, a, b):
        """The rules for the agent kinds ``a`` and ``b`` in order, each with whether it is
        written the other way round."""
        return self._by_pair.get((a, b), [])

    @classmethod
    def parse(cls, text, name=""):
        """A system from the text of a table."""
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
                    duplicator = "duplicator" in parts
                    if duplicator:
                        parts.remove("duplicator")
                    if "param" in parts:
                        param = parts[parts.index("param") + 1]
                        parts = parts[:parts.index("param")]
                    if len(parts) == 2 and parts[1].isdigit():
                        agents[parts[0]] = Agent(parts[0], int(parts[1]), None, param, duplicator)
                    elif len(parts) >= 2 and all(p in "+-" for p in parts[1:]):
                        agents[parts[0]] = Agent(parts[0], len(parts) - 2, tuple(parts[1:]), param, duplicator)
                    else:
                        raise TableError("agent NAME, then a number of auxiliary ports or a sign for each port")
                elif word == "rule":
                    sides, _, when = rest.partition(" when ")
                    if "><" not in sides:
                        raise TableError("rule LEFT >< RIGHT")
                    left, right = sides.split("><")
                    rule = Rule(_side(tokens(left), agents), _side(tokens(right), agents), _when(tokens(when)), line=number)
                    rules.append(rule)
                elif rule is None:
                    raise TableError("expected agent or rule")
                elif word == "=>":
                    rule.body = _body(rest, agents, rule)
                elif word == "count":
                    rule.count = rest.strip()
                elif word == "flag":
                    flag, _, when = rest.partition(" when ")
                    rule.flags.append((flag.strip(), _when(tokens(when))))
                else:
                    raise TableError("unknown line")
            except (TableError, IndexError) as e:
                what = "the line is cut short" if isinstance(e, IndexError) else str(e)
                raise TableError(f"{name or 'table'}:{number}: {what}") from None
        return cls(agents, rules, name)

    @classmethod
    def load(cls, path):
        """A system from a file."""
        with open(path, encoding="utf-8") as f:
            return cls.parse(f.read(), str(path))

    def check(self):
        """Problems with the table, as a list of sentences; empty if none were found.

        In any table, for each rule: it has a body and a count; no letter names two
        ports; every parameter it uses, in a condition, a new node or a call, is in hand;
        a condition that looks at a neighbour names an auxiliary port of the pair; a body
        that is a net uses every auxiliary port of the pair exactly once (not at all, for
        a node that is kept) and gives every port of every new node exactly one
        connection, so that it has the pair's free ports; `expand` names the parameter of
        an agent without auxiliary ports; `call` uses each auxiliary port once. For each
        pair of agents: no rule comes after one that always applies; and where the last
        rule has a condition, the conditions must be seen to leave no case out, which
        means two rules that are each other's opposite (`x = y` and `x != y`, or `x.name`
        and `not x.name`); `otherwise` stands alone.

        In a table without signs: every pair of agents has a rule.

        In a table with signs: every agent has them; a rule is written consumer >< value;
        there is a rule for every consumer and value and none between two values or two
        consumers; and every connection a rule makes joins an output to an input. Then in
        a net whose wires each join an output to an input, the only principal ports that
        can meet are a consumer's and a value's, and each such pair has a rule.

        A duplicator has signs ``- + +``.

        Not checked: that the system terminates, that a rule is the one intended, or that
        a duplicator's rules really copy.
        """
        problems = []
        agents = self.agents
        if self.signed and any(a.signs is None for a in agents.values()):
            return ["some agents have signs and some do not"]
        for a in agents.values():
            if a.duplicator and a.signs != ("-", "+", "+"):
                problems.append(f"agent {a.name}: a duplicator has signs - + +")
        flip = {"+": "-", "-": "+"}
        groups = {}
        for r in self.rules:
            left, right = agents[r.left.agent], agents[r.right.agent]
            where = f"line {r.line}"
            groups.setdefault(frozenset([left.name, right.name]), []).append(r)
            if r.count is None:
                problems.append(f"{where}: no count")
            if r.body is None:
                problems.append(f"{where}: no body")
                continue
            if self.signed and (left.is_value or not right.is_value):
                problems.append(f"{where}: with signs, a rule is written consumer >< value")
                continue
            letters = r.left.aux + r.right.aux
            if len(set(letters)) != len(letters):
                problems.append(f"{where}: a letter names two ports")
            peeks = [c for c in r.when if isinstance(c, Peek)]
            params = {p for p in (r.left.param, r.right.param) if p} | {c.name for c in peeks}
            known = lambda e: e.isdigit() or e.split(".")[0] in params
            for c in r.when + [c for _, when in r.flags for c in when]:
                used_here = ([c.left, c.right] if isinstance(c, Compare) else [c.expression] if isinstance(c, Test) else [])
                for e in used_here:
                    if not known(e):
                        problems.append(f"{where}: {e} is not a parameter in hand")
                if isinstance(c, Peek):
                    if c.port not in letters:
                        problems.append(f"{where}: {c.port} is not an auxiliary port of the pair")
                    if c.agent not in agents:
                        problems.append(f"{where}: unknown agent {c.agent}")
            peeked = [c.port for c in peeks]
            if isinstance(r.body, Expand):
                if r.body.param not in (r.left.param, r.right.param):
                    problems.append(f"{where}: expand needs the parameter of one of the pair")
                elif (r.left if r.body.param == r.left.param else r.right).aux:
                    problems.append(f"{where}: the agent that is expanded must have no auxiliary ports")
                continue
            if isinstance(r.body, Call):
                for v in [r.body.function] + r.body.values:
                    if not known(v):
                        problems.append(f"{where}: {v} is not a parameter in hand")
                for p in r.body.ports:
                    if p not in letters:
                        problems.append(f"{where}: {p} is not an auxiliary port of the pair")
                used = r.body.ports + peeked
                for letter in letters:
                    if used.count(letter) != 1:
                        problems.append(f"{where}: port {letter} is used {used.count(letter)} times, not once")
                continue
            body = r.body
            for name, param in body.nodes:
                if (param is None) != (agents[name].param is None):
                    problems.append(f"{where}: {name} is given a parameter it does not take, or lacks one")
                elif param is not None and not known(param):
                    problems.append(f"{where}: {param} is not a parameter in hand")
            used = [e.letter for link in body.links for e in link if isinstance(e, Ext)]
            for letter in letters:
                n = used.count(letter) + peeked.count(letter)
                kept = (letter in r.left.aux and body.keeps[0]) or (letter in r.right.aux and body.keeps[1])
                if n != (0 if kept else 1):
                    problems.append(f"{where}: port {letter} is used {n} times, not {'at all (its node is kept)' if kept else 'once'}")
            ends = [e for link in body.links for e in link if isinstance(e, New)]
            for index, (name, _) in enumerate(body.nodes):
                for port in range(agents[name].arity + 1):
                    if ends.count(New(index, port)) != 1:
                        problems.append(f"{where}: port {port} of the new {name} is joined {ends.count(New(index, port))} times")
            if self.signed:
                outside = {}
                for side, agent in ((r.left, left), (r.right, right)):
                    for letter, sign in zip(side.aux, agent.signs[1:]):
                        outside[letter] = flip[sign]

                def sign(end):
                    if isinstance(end, Ext):
                        return outside[end.letter]
                    if isinstance(end, Pair):
                        return (left, right)[end.side].signs[0]
                    return agents[body.nodes[end.node][0]].signs[end.port]

                for a, b in body.links:
                    if sign(a) == sign(b):
                        problems.append(f"{where}: joins two {'outputs' if sign(a) == '+' else 'inputs'}")
        names = sorted(agents)
        for i, a in enumerate(names):
            for b in names[i:]:
                group = groups.get(frozenset([a, b]))
                if self.signed:
                    wanted = agents[a].is_value != agents[b].is_value
                    if group and not wanted:
                        problems.append(f"{a} >< {b}: a rule between two {'values' if agents[a].is_value else 'consumers'}")
                    elif wanted and not group:
                        consumer, value = (b, a) if agents[a].is_value else (a, b)
                        problems.append(f"no rule for {consumer} >< {value}")
                elif not group:
                    problems.append(f"no rule for {a} >< {b}")
                if group:
                    always = lambda r: not r.when or (len(r.when) == 1 and isinstance(r.when[0], Otherwise))
                    for r in group:
                        if len(r.when) > 1 and any(isinstance(c, Otherwise) for c in r.when):
                            problems.append(f"line {r.line}: `otherwise` stands alone, not with other conditions")
                    for k, r in enumerate(group[:-1]):
                        if always(r):
                            problems.append(f"line {group[k + 1].line}: this rule can never apply: the one at line {r.line} always does")
                            break
                    else:
                        if not _complete(group):
                            problems.append(f"{a} >< {b}: the conditions may leave a case out (end with `otherwise`)")
        return problems


def _complete(group):
    """Whether the conditions of a pair's rules, in order, can be seen to leave no case
    out: the last rule is unconditional or ends in `otherwise`, or two rules have single
    conditions that are each other's opposite."""
    last = group[-1].when
    if not last or (len(last) == 1 and isinstance(last[0], Otherwise)):
        return True
    single = {r.when[0] for r in group if len(r.when) == 1}
    for c in single:
        if isinstance(c, Compare) and Compare(c.left, c.right, not c.equal) in single:
            return True
        if isinstance(c, Test) and Test(c.expression, not c.negated) in single:
            return True
    return False


def bundled(name):
    """One of the tables that come with the package: ``"combinators"`` (the symmetric
    interaction combinators), ``"ski"`` and ``"lazy"`` (S, K and I as agents; see
    :mod:`inets.ski`), ``"ivm"`` (the interaction system of Vine's IVM; see
    :mod:`inets.ivm`)."""
    if name not in BUNDLED:
        raise TableError(f"no bundled table {name!r}: there are {', '.join(BUNDLED)}")
    text = resources.files("inets.systems").joinpath(name + ".rules").read_text(encoding="utf-8")
    return System.parse(text, name)
