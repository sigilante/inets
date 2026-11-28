"""Live interaction nets for a notebook: write a net as equations, see it drawn in the
style of Lafont's figures, and watch it reduce step by step.

    arith = table(\"\"\"...rules...\"\"\")
    n = Net(arith, "Add (one z) = S (S (0)); one = S (0)")
    n              # a picture of the net
    n.steps()      # its reduction, one interaction at a time
    n.reduce()     # all of it, and what it cost

A net is written as equations between ports, as on the right-hand side of a rule:
``Add (one z)`` is an agent and stands for its principal port, its auxiliary ports in
brackets; a name used twice is a wire, a name used once is a free port. A free port whose
name begins with ``_`` is drawn as a bare end, without its name.

Pictures: with Graphviz's ``dot`` installed, made here; without it (JupyterLite), drawn in
the page by viz.js, which needs a network connection. ``retro(True)`` draws everything as a
photocopied 1990 figure, and ``arrows(False)`` leaves out the arrowheads that mark
principal ports.

The drawing and the net reader are copied from inets's notebook drawing and from
inets-benchmarks (bench/nettext.py), until both move into inets itself.
"""

import html as _html
import json
import shutil
import subprocess
import uuid
from collections import deque

import inets
from inets.net import _FREE, Port
from inets.system import tokens

VIZ = "https://cdn.jsdelivr.net/npm/@viz-js/viz@3.31.0/+esm"
DRAW_UP_TO = 80   # nodes: larger nets are described, not drawn
_RETRO = [False]
_ARROWS = [True]


def arrows(on=True):
    """Mark principal ports with arrowheads from now on, or not (as in Lafont's first
    pictures, before principal ports are introduced)."""
    _ARROWS[0] = bool(on)


def retro(on=True):
    """Draw every picture from now on as a photocopied 1990 figure, or not."""
    _RETRO[0] = bool(on)


def table(text):
    """A table of agents and rules, in inets's format."""
    return inets.System.parse(text)


# Grain and ragged ink: noise displaces the strokes a little, then speckles of paper eat
# into the ink, then what is left is thickened slightly, as toner spreads.
RETRO = """<defs><filter id="retro" x="-5%" y="-5%" width="110%" height="110%">
<feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="2" seed="3" result="warp"/>
<feDisplacementMap in="SourceGraphic" in2="warp" scale="2.2" xChannelSelector="R" yChannelSelector="G" result="ragged"/>
<feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="1" seed="9" result="grain"/>
<feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -14 8.6" result="holes"/>
<feComposite in="ragged" in2="holes" operator="in" result="speckled"/>
<feMorphology in="speckled" operator="dilate" radius="0.25" result="spread"/>
<feComponentTransfer in="spread"><feFuncA type="discrete" tableValues="0 1 1 1"/></feComponentTransfer>
</filter></defs>"""


def _arity(net, n):
    kind = net.kind[n]
    return 0 if kind == _FREE else net.system.agents[kind].arity


def _outputs(net, named):
    """The named free ports joined to a port signed ``+``, in a table with signs."""
    out = []
    for n in named:
        q = net.link.get(Port(n, 0))
        if q is None or net.kind[q.node] == _FREE:
            continue
        signs = net.system.agents[net.kind[q.node]].signs
        if signs is not None and signs[q.index] == "+":
            out.append(n)
    return out


def lafont_dot(net, names=None, top=None):
    """The net as Graphviz text, drawn as in Lafont's figures."""
    names = {Port(*p).node: label for p, label in (names or {}).items()}
    tops = [Port(*p).node for p in top] if top is not None else (_outputs(net, names) or list(names)[:1])
    # Breadth first from the top ports together, then from whatever is left: a node's
    # depth is its rank, and each wire runs down from the node that reached it.
    order, depth = [], {}
    rest = sorted(net.kind, key=lambda n: (net.kind[n] == _FREE or _arity(net, n) == 0, n))
    for starts in [tops] + [[n] for n in list(names) + rest]:
        starts = [n for n in starts if n not in depth]
        if not starts:
            continue
        for n in starts:
            depth[n] = 0
        queue = deque(starts)
        while queue:
            n = queue.popleft()
            order.append(n)
            for i in range(_arity(net, n) + 1):
                q = net.link.get(Port(n, i))
                if q is not None and q.node not in depth:
                    depth[q.node] = depth[n] + 1
                    queue.append(q.node)
    out = [
        "graph net {",
        '  graph [nodesep=0.25, ranksep=0.3, ordering=out, splines=polyline, bgcolor="transparent"];',
        '  node [shape=ellipse, fontname="Helvetica", fontsize=14, margin="0.06,0.02",'
        ' width=0, height=0, penwidth=1.3];',
        '  edge [penwidth=1.3, arrowsize=0.8, dir=both, arrowhead=none, arrowtail=none];',
    ]
    if len(tops) > 1:
        out.append("  { rank=same; " + " ".join(f"n{n};" for n in tops) + " }")
    for n in order:
        kind = net.kind[n]
        if kind == _FREE:
            label = names.get(n)
            if label is None or label.startswith("_"):  # a bare end, as in Lafont's figures
                out.append(f'  n{n} [label="", shape=none, width=0.01, height=0.01, margin=0];')
            else:
                out.append(f'  n{n} [label=<<i>{label}</i>>, shape=plaintext, height=0.2, margin=0];')
        else:
            text = kind + (f" {net.param[n]}" if n in net.param else "")
            shape = ", shape=circle" if len(text) <= 2 else ""
            out.append(f'  n{n} [label="{text}"{shape}];')
    rank = {n: i for i, n in enumerate(order)}
    below = lambda p, q: (depth[q.node], rank[q.node]) > (depth[p.node], rank[p.node])
    # Spread the wires that leave a node downwards across its lower edge, in port order.
    # Likewise the wires that arrive from above across its upper edge.
    down, up = {}, {}
    for n in order:
        for i in range(_arity(net, n) + 1):
            q = net.link.get(Port(n, i))
            if q is not None:
                (down if below(Port(n, i), q) else up).setdefault(n, []).append(i)
    spread = {"s": {1: ["s"], 2: ["sw", "se"], 3: ["sw", "s", "se"]},
              "n": {1: ["n"], 2: ["nw", "ne"], 3: ["nw", "n", "ne"]}}

    def compass(port, side):
        ports = (down if side == "s" else up).get(port.node, [])
        if port.index not in ports:
            return side
        return spread[side].get(len(ports), [side] * len(ports))[ports.index(port.index)]
    seen = set()
    for n in order:
        for i in range(_arity(net, n) + 1):
            p = Port(n, i)
            q = net.link.get(p)
            if q is None or (q, p) in seen:
                continue
            seen.add((p, q))
            tail, head = (p, q) if below(p, q) else (q, p)
            attrs = []
            for end, port, side in (("tail", tail, "s"), ("head", head, "n")):
                if net.kind[port.node] == _FREE:
                    continue
                if port.index == 0 and _ARROWS[0]:
                    attrs.append(f"arrow{end}=inv")
                attrs.append(f"{end}port={compass(port, side)}")
            if depth[head.node] <= depth[tail.node]:
                attrs.append("constraint=false")
            out.append(f"  n{tail.node} -- n{head.node} [{', '.join(attrs)}];")
    out.append("}")
    return "\n".join(out)


def roughen(svg):
    """An SVG with the retro filter over the whole drawing."""
    start = svg.index(">", svg.index("<svg")) + 1
    svg = svg[:start] + RETRO + svg[start:]
    return svg.replace('<g id="graph0"', '<g filter="url(#retro)" id="graph0"', 1)


def _svg(dot):
    """Graphviz text as SVG from a local ``dot``, or None."""
    program = shutil.which("dot")
    if program is None:
        return None
    try:
        r = subprocess.run([program, "-Tsvg"], input=dot, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout[r.stdout.index("<svg"):] if r.returncode == 0 and "<svg" in r.stdout else None


class NetTextError(Exception):
    pass


def build(system, text):
    """A net from equations: ``(net, {free port's name: port})``."""
    net = inets.Net(system, inets.Library())
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
                    raise NetTextError(f"{head} has {agent.arity} auxiliary ports")
                kid = term(toks)
                if isinstance(kid, str):
                    meet(kid, inets.Port(n, i))
                else:
                    net.wire(inets.Port(n, i), kid)
            if not toks or i != agent.arity:
                raise NetTextError(f"{head} has {agent.arity} auxiliary ports")
            toks.pop(0)
        return inets.Port(n, 0)

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
            raise NetTextError(f"{a} = {b} joins two wires: write one name for both")
        free[a], free[b] = net.free(), net.free()
        net.wire(free[a], free[b])
    for name, port in seen.items():
        free[name] = net.free()
        net.wire(free[name], port)
    return net, free


def show(net, free):
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
        return head + " (" + " ".join(follow(inets.Port(n, i)) for i in range(1, arity + 1)) + ")"

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
        lines.append(f"{left} = {follow(inets.Port(n, 0))}")
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
            p, q = a.link.get(inets.Port(x, i)), b.link.get(inets.Port(y, i))
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
                    q = net.link.get(inets.Port(n, i))
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
                q = net.link.get(inets.Port(n, i))
                if q is not None and q.node not in place:
                    place[q.node] = len(order)
                    order.append(q.node)
        return tuple(
            (label(net, n),) + tuple(
                (-1, -1) if (q := net.link.get(inets.Port(n, i))) is None else (place[q.node], q.index)
                for i in range(ports(net, n)))
            for n in order)

    return pieces(a, set(m)) == pieces(b, used)


def _picture(dot):
    """HTML for one picture: SVG made here, or a box that viz.js fills in the page."""
    svg = _svg(dot)
    if svg is not None:
        return roughen(svg) if _RETRO[0] else svg
    box = "net-" + uuid.uuid4().hex
    text = json.dumps(dot).replace("</", "<\\/")
    filt = json.dumps(RETRO if _RETRO[0] else "")
    return f"""<div id="{box}">drawing&hellip;</div>
<script>
import("{VIZ}")
  .then(viz => viz.instance())
  .then(viz => {{
    let svg = viz.renderString({text}, {{format: "svg"}});
    svg = svg.slice(svg.indexOf("<svg"));
    const retro = {filt};
    if (retro) {{
      const start = svg.indexOf(">", svg.indexOf("<svg")) + 1;
      svg = (svg.slice(0, start) + retro + svg.slice(start)).replace('<g id="graph0"', '<g filter="url(#retro)" id="graph0"');
    }}
    document.getElementById("{box}").innerHTML = svg;
  }})
  .catch(e => {{ document.getElementById("{box}").textContent = "viz.js could not draw this: " + e; }});
</script>"""


def _row(pictures, captions=None, between="&rarr;"):
    """Pictures side by side, with arrows between them and a caption under each."""
    captions = captions or [""] * len(pictures)
    cells = []
    for i, (pic, cap) in enumerate(zip(pictures, captions)):
        if i:
            cells.append(f'<div style="font-size:28px;padding:0 6px">{between}</div>')
        cells.append(f'<div style="text-align:center">{pic}'
                     f'<div style="font-size:12px;color:#666">{_html.escape(cap)}</div></div>')
    return ('<div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px">'
            + "".join(cells) + "</div>")


class _HTML:
    def __init__(self, html):
        self.html = html

    def _repr_html_(self):
        return self.html


class Net:
    """A net built from equations, shown as a picture when it is the value of a cell.

    ``top`` names the free ports to draw at the top. By default these are, in a table
    with signs, those that carry an output, and otherwise the first one written."""

    def __init__(self, system, text, top=None):
        self.system, self.text = system, text
        self.net, self.free = build(system, text)
        self.top = top

    def _names(self):
        """Free ports and their names, in the order the names first occur in the text, so
        that in a table without signs the net hangs from the first one written."""
        first = {}
        for i, t in enumerate(tokens(self.text.replace(";", " ").replace("=", " "))):
            first.setdefault(t, i)
        order = sorted(self.free, key=lambda name: first.get(name, len(first)))
        return {self.free[name]: name for name in order}

    def _top(self):
        return None if self.top is None else [self.free[t] for t in self.top]

    def _dot(self):
        return lafont_dot(self.net, self._names(), self._top())

    def _repr_html_(self):
        if len(self.net.kind) > DRAW_UP_TO:
            return f"<p>{len(self.net.kind)} nodes: too many to draw. As text: {_html.escape(str(self))}</p>"
        return _picture(self._dot())

    def __str__(self):
        return show(self.net, self.free)

    def __repr__(self):
        return f"Net({str(self)!r})"

    def alive(self):
        """The number of alive pairs: agents joined by their principal ports."""
        seen = 0
        for p, q in self.net.link.items():
            if p.index == 0 and q.index == 0 and _FREE not in (self.net.kind[p.node], self.net.kind[q.node]):
                seen += 1
        return seen // 2

    def step(self, order="stack"):
        """One interaction, if there is an alive pair; the rule's count name, or None."""
        before = dict(self.net.counts)
        r = self.net.reduce(order, max_interactions=1)
        if not r.interactions:
            return None
        return next((k for k, v in self.net.counts.items() if v != before.get(k, 0)), "?")

    def steps(self, limit=12, order="stack"):
        """The net and each net it becomes, one interaction at a time, up to ``limit``."""
        pictures, captions = [self._repr_html_()], ["start"]
        for i in range(limit):
            rule = self.step(order)
            if rule is None:
                break
            pictures.append(self._repr_html_())
            captions.append(f"{i + 1}: {rule}")
        else:
            if self.alive():
                captions[-1] += " (and on)"
        return _HTML(_row(pictures, captions))

    def reduce(self, order="stack", limit=10 ** 6, seed=0):
        """Reduces the net (all of it, or ``limit`` interactions) and says what this call
        cost, and how many interactions the net has had in all. ``order`` is ``"stack"``
        (newest alive pair first), ``"queue"`` (oldest first) or ``"random"`` (by ``seed``)."""
        r = self.net.reduce(order, seed=seed, max_interactions=limit)
        counts = ", ".join(f"{k} {v}" for k, v in sorted(r.counts.items()))
        print(f"{r.reason}: {r.interactions} interactions ({counts}); {r.active_left} alive pairs left;"
              f" {self.net.interactions} in all")
        return self

    def reduce_by_need(self, port, limit=10 ** 6):
        """Reduces only what the free port ``port`` needs (a table with signs)."""
        r = self.net.reduce_by_need(self.free[port], max_interactions=limit)
        counts = ", ".join(f"{k} {v}" for k, v in sorted(r.counts.items()))
        print(f"{r.reason}: {r.interactions} interactions ({counts}); {r.active_left} alive pairs left;"
              f" {self.net.interactions} in all")
        return self

    def same(self, other):
        """Whether two nets are the same, up to the numbering of their agents."""
        if isinstance(other, str):
            other = Net(self.system, other)
        return same(self.net, self.free, other.net, other.free)


def side_by_side(*nets, captions=None, between="&rarr;"):
    """Several nets in a row, with arrows between them."""
    return _HTML(_row([n._repr_html_() for n in nets], captions, between))


def rule(system, left, right, top=None):
    """A rule drawn as Lafont draws it: the alive pair, an arrow, and what it becomes.
    ``left`` is the pair as equations (``Add (y z) = S (x)``), ``right`` the rule's
    right-hand side; ``top`` names the free ports drawn on top in both."""
    return side_by_side(Net(system, left, top), Net(system, right, top))
