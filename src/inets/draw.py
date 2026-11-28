"""Pictures of nets, drawn as in Lafont's figures (Interaction Nets, POPL 1990).

    >>> import inets
    >>> from inets import draw, text
    >>> net, free = text.read(inets.bundled("combinators"), "con (a b) = dup (era era)")
    >>> graph = draw.dot(net, {p: name for name, p in free.items()})
    >>> graph.splitlines()[0]
    'graph net {'

:func:`dot` gives a net as Graphviz text. In Lafont's style (the default) an agent is an
ellipse, or a circle for a short name, with no port numbers; its principal port carries an
arrowhead pointing out along its wire, so an active pair shows as two arrowheads tip to
tip; a named free port is its name in italics, and one whose name begins with ``_`` is a
bare end. If every agent in the net has signs, each port is placed by its direction:
outputs on an agent's top edge, inputs on its bottom edge, in port order, so values flow
up; a wire that closes a cycle does not shape the layout. Otherwise the net hangs from its
top free ports. ``style="ports"`` is :meth:`inets.Net.dot`'s drawing instead: boxes, port
numbers, active pairs in red.

:func:`svg` turns Graphviz text into SVG with Graphviz's ``dot`` program, if it is
installed, and :func:`roughen` gives an SVG the look of a photocopied 1990 figure.
"""

import html
import shutil
import subprocess
from collections import deque

from .net import _FREE, Port

__all__ = ["dot", "lafont_dot", "svg", "roughen"]


def dot(net, names=None, top=None, style="lafont", arrows=True):
    """The net as Graphviz text.

    ``names`` maps free ports to labels (other ports in it are ignored). In Lafont's style
    (``style="lafont"``, the default):

    - if every agent in the net has signs, the text is a ``digraph`` laid out by direction,
      outputs on top; the free ports in ``top`` go in the top row, by default the named free
      ports joined to an output (the net's results);
    - otherwise it is a ``graph`` hung from the free ports in ``top``, by default the named
      free ports joined to an output, or else the first one named;
    - ``arrows=False`` leaves out the arrowheads on principal ports.

    ``style="ports"`` is :meth:`inets.Net.dot`'s drawing (a ``graph`` of boxes with port
    numbers, active pairs in red); it uses ``names`` and ignores ``top`` and ``arrows``. A
    port in ``top`` that is not a free port of the net raises ``ValueError``.
    """
    if style == "lafont":
        return lafont_dot(net, names, top, arrows)
    if style == "ports":
        return net.dot(names)
    raise ValueError('style is "lafont" or "ports"')


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


def _top_nodes(net, top):
    nodes = []
    for p in top:
        p = Port(*p)
        if net.kind.get(p.node) != _FREE:
            raise ValueError(f"{p} is not a free port of this net")
        nodes.append(p.node)
    return nodes


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


def lafont_dot(net, names=None, top=None, arrows=True):
    """The net as Graphviz text, drawn as in Lafont's figures. If every agent in the net has
    signs, each port is placed by its direction (:func:`_flow_dot`); otherwise, and for a net
    with no agents, the net hangs from its top free ports (:func:`_hung_dot`)."""
    agents = [k for k in net.kind.values() if k != _FREE]
    if agents and all(net.system.agents[k].signs is not None for k in agents):
        return _flow_dot(net, names, top, arrows)
    return _hung_dot(net, names, top, arrows)


def _flow_dot(net, names, top, arrows):
    """Lafont's orientation: outputs (+) on an agent's top edge, inputs (-) on its bottom
    edge, each in port order from left to right, so values flow up from the agent that makes
    them to the one that uses them. A free port takes the direction opposite to the port it
    is joined to: a free port joined to an output is one of the net's results, drawn above.
    A wire that would run against the flow closes a cycle; it is still drawn, but it does not
    shape the layout. A wire joining two outputs or two inputs is not well typed; it is drawn
    the same way. Two free ports joined to each other are ordered by node number, the first
    drawn above. ``top`` puts the free ports it names in the top rank."""
    names = {Port(*p).node: label for p, label in (names or {}).items()}

    def sign(port):
        kind = net.kind[port.node]
        if kind == _FREE:
            q = net.link.get(port)
            if q is not None and net.kind[q.node] == _FREE:  # two free ports joined: y = x
                return "-" if port.node < q.node else "+"
            return "-" if q is None or sign(q) == "+" else "+"
        return net.system.agents[kind].signs[port.index]

    out = [
        "digraph net {",
        '  graph [nodesep=0.3, ranksep=0.35, splines=polyline, bgcolor="transparent", rankdir=TB];',
        '  node [shape=ellipse, fontname="Helvetica", fontsize=14, margin="0.06,0.02",'
        ' width=0, height=0, penwidth=1.3];',
        '  edge [penwidth=1.3, arrowsize=0.8, dir=both, arrowhead=none, arrowtail=none];',
    ]
    for n in sorted(net.kind):
        kind = net.kind[n]
        if kind == _FREE:
            label = names.get(n)
            if label is None or label.startswith("_"):
                out.append(f'  n{n} [label="", shape=none, width=0.01, height=0.01, margin=0];')
            else:
                out.append(f'  n{n} [label=<<i>{html.escape(label)}</i>>, shape=plaintext, height=0.2, margin=0];')
        else:
            text = kind + (f" {net.param[n]}" if n in net.param else "")
            shape = ", shape=circle" if len(text) <= 2 else ""  # S, 0, Z: circles, as Lafont drew them
            out.append(f'  n{n} [label="{text}"{shape}];')
    tops = _top_nodes(net, top) if top is not None else \
        [n for n in names if sign(Port(n, 0)) == "-" and net.kind.get(n) == _FREE]
    if tops:
        out.append("  { rank=min; " + " ".join(f"n{n};" for n in tops) + " }")

    # Ports on each edge of each agent, in port order: outputs on top, inputs below.
    side = {}
    for n, kind in net.kind.items():
        if kind == _FREE:
            continue
        ports = range(net.system.agents[kind].arity + 1)
        side[n] = {"n": [i for i in ports if sign(Port(n, i)) == "+"],
                   "s": [i for i in ports if sign(Port(n, i)) == "-"]}
    spread = {"s": {1: ["s"], 2: ["sw", "se"], 3: ["sw", "s", "se"]},
              "n": {1: ["n"], 2: ["nw", "ne"], 3: ["nw", "n", "ne"]}}

    def compass(port, edge):
        ports = side[port.node][edge]
        if port.index not in ports:  # a wire between two outputs or two inputs
            return edge
        return spread[edge].get(len(ports), [edge] * len(ports))[ports.index(port.index)]

    # Walk down from the results, input to output, ports in order. A wire that comes back to
    # an agent still on the walk closes a cycle (a difference-list's hole, say): it is drawn
    # as a loop and left out of the layout, so the cycle is cut where Lafont cuts it.
    def below(n):
        for i in range(_arity(net, n) + 1):
            p, q = Port(n, i), net.link.get(Port(n, i))
            if q is not None and sign(p) == "-" and sign(q) == "+":
                yield p, q
    back, state = set(), {}
    starts = tops + [n for n in names if n not in tops] + sorted(net.kind)
    for start in starts:
        if start in state:
            continue
        state[start] = "open"
        stack = [(start, below(start))]
        while stack:
            n, wires = stack[-1]
            for p, q in wires:
                if state.get(q.node) == "open":
                    back.add(frozenset((p, q)))
                elif q.node not in state:
                    state[q.node] = "open"
                    stack.append((q.node, below(q.node)))
                    break
            else:
                state[n] = "done"
                stack.pop()

    seen = set()
    for p, q in sorted(net.link.items()):
        if (q, p) in seen:
            continue
        seen.add((p, q))
        # The wire runs from the input end (above) down to the output end (below).
        upper, lower = (p, q) if sign(p) == "-" else (q, p)
        attrs = []
        for end, port, edge in (("tail", upper, "s"), ("head", lower, "n")):
            if net.kind[port.node] == _FREE:
                continue
            if port.index == 0 and arrows:
                attrs.append(f"arrow{end}=inv")
            attrs.append(f"{end}port={compass(port, edge)}")
        if sign(p) == sign(q) or frozenset((p, q)) in back:
            attrs.append("constraint=false")  # closes a cycle, or not well typed
        out.append(f"  n{upper.node} -> n{lower.node} [{', '.join(attrs)}];")
    out.append("}")
    return "\n".join(out)


def _hung_dot(net, names, top, arrows):
    """The net hung from its top free ports: those in ``top``; else the named free ports that
    carry an output, in a table with signs; else the first named. The rest of the net is laid
    out breadth first below them."""
    names = {Port(*p).node: label for p, label in (names or {}).items()}
    tops = _top_nodes(net, top) if top is not None else (_outputs(net, names) or list(names)[:1])
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
                out.append(f'  n{n} [label=<<i>{html.escape(label)}</i>>, shape=plaintext, height=0.2, margin=0];')
        else:
            text = kind + (f" {net.param[n]}" if n in net.param else "")
            shape = ", shape=circle" if len(text) <= 2 else ""  # S, 0, Z: circles, as Lafont drew them
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
                if port.index == 0 and arrows:
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


def svg(dot):
    """Graphviz text as SVG, made by Graphviz's ``dot`` program; None if the program is not
    installed, fails, or takes more than 30 seconds."""
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
