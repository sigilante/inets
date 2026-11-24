"""What a cell means. No Jupyter here: a :class:`Session` takes a cell's text and returns
a list of outputs, so it can be tested and used on its own.

A cell is one of three things.

**A table.** Lines beginning ``agent`` or ``rule`` (with a rule's ``=>``, ``count`` and
``flag`` lines) are added to the current table, in the format of :mod:`inets.system`. The
table is then checked.

**A net.** Equations between ports, written as the right-hand side of a rule is::

    con (a b) = dup (era era)

``con (a b)`` is a node and stands for its principal port. A name that is not an agent is a
wire if it occurs twice and a free port if it occurs once. An agent with a parameter takes
it after its name: ``atom 3``. Equations are separated by ``;`` or new lines. The net is
drawn, reduced by the current schedule, and drawn again, with why it stopped and what it
cost.

**Commands**, one to a line, beginning ``%``:

    %system NAME      start from a bundled table (combinators, the default; ski; lazy), or
                      `new` for none
    %table            show the current table
    %check            check it
    %rules            list its rules, marking those that are not local
    %schedule HOW     stack (default), queue, random, rounds, or `need PORT`: by need for
                      the free port named PORT (default out), in a table with signs
    %cap N            stop a run after N interactions (default 10000)
    %trace on|off     with `rounds`, draw the net after each round, up to twelve rounds
                      (off by default)
    %ski TERM [--rounds | --lazy]
                      reduce a term of S, K and I in prefix form, by need unless said
    %demo             one term, K I Ω, reduced three ways
    %help             this list
"""
from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
from dataclasses import dataclass

import inets
from inets import ski
from inets.system import BUNDLED, tokens

HELP = __doc__.split("**Commands**")[1].split("\n\n", 1)[1].rstrip('"\n ')
SCHEDULES = ("stack", "queue", "random", "rounds", "need")
DRAW_UP_TO = 80     # nodes: larger nets are described, not drawn
FRAMES = 12         # the most rounds drawn by %trace


@dataclass
class Output:
    """One thing a cell shows: ``kind`` is ``"text"``, ``"svg"`` or ``"error"``."""
    kind: str
    data: str


class CellError(Exception):
    """A cell that cannot be carried out."""


def _svg(dot):
    """Graphviz text as SVG, or None if there is no `dot` program."""
    program = shutil.which("dot")
    if not program:
        return None
    try:
        r = subprocess.run([program, "-Tsvg"], input=dot, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout[r.stdout.index("<svg"):] if r.returncode == 0 and "<svg" in r.stdout else None


class Session:
    def __init__(self):
        self.text = ""
        self.system = inets.System.parse("")
        self.schedule, self.wanted = "stack", "out"
        self.cap, self.trace = 10000, False
        self.use("combinators")

    def use(self, name):
        if name == "new":
            self.text = ""
        elif name in BUNDLED and name != "ivm":
            from importlib import resources
            self.text = resources.files("inets.systems").joinpath(name + ".rules").read_text(encoding="utf-8")
        else:
            raise CellError(f"no table {name}: there are combinators, ski, lazy, and `new`")
        self.system = inets.System.parse(self.text, name)

    # --- a cell -----------------------------------------------------------------------

    def execute(self, code):
        """The outputs of a cell. An error ends the cell, and is the last output."""
        out = []
        try:
            lines = code.split("\n")
            rest = []
            for line in lines:
                if line.strip().startswith("%"):
                    out.extend(self.command(line.strip()))
                else:
                    rest.append(line)
            body = "\n".join(rest)
            plain = "\n".join(l.split("#", 1)[0] for l in rest).strip()
            if plain:
                first = plain.split()[0]
                out.extend(self.table(body) if first in ("agent", "rule") else self.net(plain))
        except (CellError, inets.Error) as e:
            out.append(Output("error", str(e)))
        return out

    # --- commands ---------------------------------------------------------------------

    def command(self, line):
        word, _, rest = line[1:].partition(" ")
        rest = rest.strip()
        if word == "help":
            return [Output("text", HELP)]
        if word == "system":
            self.use(rest or "combinators")
            return [Output("text", self.describe())]
        if word == "table":
            return [Output("text", self.text.strip() or "(no agents or rules yet)")]
        if word == "check":
            return [Output("text", self.describe())]
        if word == "rules":
            return [Output("text", "\n".join(
                f"{r.count or '?':<11} {r}" + (f"   [not local: {', '.join(r.not_local)}]" if r.not_local else "")
                for r in self.system.rules) or "(no rules yet)")]
        if word == "schedule":
            how, _, port = rest.partition(" ")
            if how not in SCHEDULES:
                raise CellError("a schedule is one of: " + ", ".join(SCHEDULES))
            self.schedule, self.wanted = how, port.strip() or "out"
            return [Output("text", f"schedule: {how}" + (f", for the free port {self.wanted}" if how == "need" else ""))]
        if word == "cap":
            if not rest.isdigit() or int(rest) < 1:
                raise CellError("%cap takes a whole number of interactions")
            self.cap = int(rest)
            return [Output("text", f"a run stops after {self.cap} interactions")]
        if word == "trace":
            if rest not in ("on", "off"):
                raise CellError("%trace on, or %trace off")
            self.trace = rest == "on"
            return [Output("text", f"trace: {rest}")]
        if word == "ski":
            return self.ski(rest)
        if word == "demo":
            from inets.__main__ import demo
            text = io.StringIO()
            with contextlib.redirect_stdout(text):
                demo()
            return [Output("text", text.getvalue().rstrip())]
        raise CellError(f"no command %{word}: see %help")

    def describe(self):
        problems = self.system.check()
        head = (f"{len(self.system.agents)} agents, {len(self.system.rules)} rules, "
                f"{'with' if self.system.signed else 'without'} signs; {len(problems)} problems")
        return "\n".join([head] + ["  " + p for p in problems])

    # --- a table ----------------------------------------------------------------------

    def table(self, body):
        text = (self.text.rstrip() + "\n\n" if self.text.strip() else "") + body.strip() + "\n"
        system = inets.System.parse(text, "cell")      # a table that cannot be read changes nothing
        self.text, self.system = text, system
        return [Output("text", self.describe())]

    # --- a net ------------------------------------------------------------------------

    def build(self, text):
        """A net from equations: ``(net, {free port's name: port})``."""
        net = inets.Net(self.system, inets.Library())
        agents = self.system.agents
        seen, count = {}, {}

        def meet(name, port):
            count[name] = count.get(name, 0) + 1
            if count[name] > 2:
                raise CellError(f"the wire {name} has more than two ends")
            if name in seen:
                net.wire(seen.pop(name), port)
            else:
                seen[name] = port

        def term(toks):
            if not toks:
                raise CellError("an equation is PORT = PORT, and one side is missing")
            head = toks.pop(0)
            if head in ("(", ")", "=", ";"):
                raise CellError(f"expected a node or a wire, not {head}")
            if head not in agents:
                return head
            agent = agents[head]
            param = None
            if agent.param:
                if not toks:
                    raise CellError(f"{head} takes a parameter")
                word = toks.pop(0)
                param = int(word) if word.isdigit() else word
            n = net.add_node(head, param)
            if agent.arity:
                if not toks or toks.pop(0) != "(":
                    raise CellError(f"{head} needs its {agent.arity} ports in brackets")
                i = 0
                while toks and toks[0] != ")":
                    i += 1
                    if i > agent.arity:
                        raise CellError(f"{head} has {agent.arity} auxiliary ports")
                    kid = term(toks)
                    if isinstance(kid, str):
                        meet(kid, inets.Port(n, i))
                    else:
                        net.wire(inets.Port(n, i), kid)
                if not toks or i != agent.arity:
                    raise CellError(f"{head} has {agent.arity} auxiliary ports")
                toks.pop(0)
            return inets.Port(n, 0)

        for equation in text.replace("\n", ";").split(";"):
            if not equation.strip():
                continue
            toks = tokens(equation)
            a = term(toks)
            if not toks or toks.pop(0) != "=":
                raise CellError("an equation is PORT = PORT: " + equation.strip())
            b = term(toks)
            if toks:
                raise CellError("unexpected " + toks[0] + " in: " + equation.strip())
            if isinstance(a, str) and isinstance(b, str):
                raise CellError(f"{a} = {b} joins two wires: write one name for both")
            if isinstance(a, str):
                meet(a, b)
            elif isinstance(b, str):
                meet(b, a)
            else:
                net.wire(a, b)
        free = {}
        for name, port in seen.items():
            free[name] = net.free()
            net.wire(free[name], port)
        return net, free

    def picture(self, net, free, title):
        names = {port: name for name, port in free.items()}
        if len(net.kind) > DRAW_UP_TO:
            return [Output("text", f"{title}: {len(net.kind)} nodes (too many to draw)")]
        svg = _svg(net.dot(names))
        if svg is None:
            return [Output("text", f"{title} (Graphviz's `dot` program is missing or did not draw it, so here is the Graphviz text):\n{net.dot(names)}")]
        return [Output("text", title + ":"), Output("svg", svg)]

    @staticmethod
    def says(result):
        some = lambda n, word: f"{n} {word}" + ("" if n == 1 else "s")
        extra = f", in {some(result.rounds, 'round')}, the widest of {result.widest}" if result.rounds else ""
        counts = ", ".join(f"{k} {v}" for k, v in sorted(result.counts.items()))
        why = {"normal": "no active pair is left", "wanted": "the value wanted is there",
               "interactions": "the cap was reached"}[result.reason]
        return (f"stopped: {why} ({result.reason}); {some(result.interactions, 'interaction')}{extra}; "
                f"{some(result.active_left, 'active pair')} left" + (f"; {counts}" if counts else ""))

    def net(self, text):
        if not self.system.agents:
            raise CellError("there is no table yet: define agents and rules, or use %system")
        net, free = self.build(text)
        out = self.picture(net, free, "the net")
        if self.schedule == "rounds" and self.trace:
            result, frames = None, 0
            total = inets.Result("normal")
            while True:
                result = net.reduce_in_rounds(max_interactions=1) if net.active() else None
                if result is None:
                    break
                # One round at a time: a cap of 1 lets exactly one round run.
                frames += 1
                total.interactions += result.interactions
                total.rounds += 1
                total.widest = max(total.widest, result.widest)
                for k, v in result.counts.items():
                    total.counts[k] = total.counts.get(k, 0) + v
                if frames <= FRAMES:
                    out += self.picture(net, free, f"after round {frames}")
                if total.interactions >= self.cap:
                    total.reason = "interactions"
                    break
            total.active_left = len(net.active())
            out.append(Output("text", self.says(total)))
            return out
        if self.schedule == "rounds":
            result = net.reduce_in_rounds(max_interactions=self.cap)
        elif self.schedule == "need":
            if self.wanted not in free:
                raise CellError(f"by need wants a free port named {self.wanted}: the net's free ports are "
                                + (", ".join(sorted(free)) or "none"))
            result = net.reduce_by_need(free[self.wanted], max_interactions=self.cap)
        else:
            result = net.reduce(order=self.schedule, max_interactions=self.cap)
        out.append(Output("text", self.says(result)))
        out += self.picture(net, free, "what is left")
        return out

    # --- S, K and I -------------------------------------------------------------------

    def ski(self, rest):
        words = rest.split()
        flags = [w for w in words if w.startswith("--")]
        terms = [w for w in words if not w.startswith("--")]
        if len(terms) != 1 or any(f not in ("--rounds", "--lazy") for f in flags) or len(flags) > 1:
            raise CellError("%ski TERM [--rounds | --lazy]")
        schedule = "rounds" if "--rounds" in flags else "lazy" if "--lazy" in flags else "need"
        run = ski.run(terms[0], schedule=schedule, max_interactions=self.cap)
        answer = ski.show(run.term) if run.result.finished else "no answer: the cap was reached"
        return [Output("text", f"{answer}\n{self.says(run.result)}")]
