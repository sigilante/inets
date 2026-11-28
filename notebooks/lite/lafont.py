"""A net as Graphviz text in the style of Lafont's figures (Interaction Nets, POPL 1990).

An agent is an ellipse (a circle for a short name) with no port numbers. Its principal
port carries an arrowhead pointing out along the wire, so an active pair shows as two
arrowheads tip to tip. A named free port is the name in italics. The net hangs from its
named free ports: they are laid out first, at the top, and each node's other wires leave
from below it, auxiliary ports in order, left to right.
"""

from collections import deque

from inets.net import _FREE, Port


def lafont_dot(net, names=None):
    names = {Port(*p).node: label for p, label in (names or {}).items()}
    # Breadth first from the named free ports, then from whatever is left: a node's depth
    # is its rank, and each wire runs from the node that reached it.
    order, depth = [], {}
    starts = list(names) + sorted(net.kind)
    for start in starts:
        if start in depth:
            continue
        depth[start] = 0
        queue = deque([start])
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
        '  graph [nodesep=0.25, ranksep=0.3, ordering=out, splines=line, bgcolor="transparent"];',
        '  node [shape=ellipse, fontname="Helvetica", fontsize=14, margin="0.06,0.02",'
        ' width=0, height=0, penwidth=1.3];',
        '  edge [penwidth=1.3, arrowsize=0.8, dir=both, arrowhead=none, arrowtail=none];',
    ]
    for n in order:
        kind = net.kind[n]
        if kind == _FREE:
            label = names.get(n)
            if label is None:
                out.append(f'  n{n} [label="", shape=point, width=0.05];')
            else:
                out.append(f'  n{n} [label=<<i>{label}</i>>, shape=plaintext, height=0.2, margin=0];')
        else:
            text = kind + (f" {net.param[n]}" if n in net.param else "")
            shape = ", shape=circle" if len(text) <= 2 else ""
            out.append(f'  n{n} [label="{text}"{shape}];')
    rank = {n: i for i, n in enumerate(order)}
    # Spread the wires that leave a node downwards across its lower edge, in port order.
    down = {}
    for n in order:
        for i in range(_arity(net, n) + 1):
            q = net.link.get(Port(n, i))
            if q is not None and (depth[q.node], rank[q.node]) > (depth[n], rank[n]):
                down.setdefault(n, []).append(i)
    spread = {1: ["s"], 2: ["sw", "se"], 3: ["sw", "s", "se"]}
    seen = set()
    for n in order:
        for i in range(_arity(net, n) + 1):
            p = Port(n, i)
            q = net.link.get(p)
            if q is None or (q, p) in seen:
                continue
            seen.add((p, q))
            # Draw from the node met first, so the wire hangs down from it.
            tail, head = (p, q) if (depth[p.node], rank[p.node]) <= (depth[q.node], rank[q.node]) else (q, p)
            attrs = []
            ports = down.get(tail.node, [])
            below = spread.get(len(ports), ["s"] * len(ports))
            low = below[ports.index(tail.index)] if tail.index in ports else "s"
            for end, port, compass in (("tail", tail, low), ("head", head, "n")):
                if net.kind[port.node] == _FREE:
                    continue
                if port.index == 0:
                    attrs.append(f"arrow{end}=inv")
                attrs.append(f"{end}port={compass}")
            if depth[head.node] <= depth[tail.node]:
                attrs.append("constraint=false")
            out.append(f"  n{tail.node} -- n{head.node} [{', '.join(attrs)}];")
    out.append("}")
    return "\n".join(out)


def _arity(net, n):
    kind = net.kind[n]
    return 0 if kind == _FREE else net.system.agents[kind].arity
