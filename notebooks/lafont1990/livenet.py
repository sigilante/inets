"""Live interaction nets for a notebook: write a net as equations, see it drawn in the
style of Lafont's figures, and watch it reduce step by step.

    arith = table(\"\"\"...rules...\"\"\")
    n = Net(arith, "Add (one z) = S (S (0)); one = S (0)")
    n              # a picture of the net
    n.steps()      # its reduction, one interaction at a time
    n.reduce()     # all of it, and what it cost

A net is written as equations between ports (:mod:`inets.text`): ``Add (one z)`` is an
agent and stands for its principal port, its auxiliary ports in brackets; a name used twice
is a wire, a name used once is a free port. A free port whose name begins with ``_`` is
drawn as a bare end, without its name.

Pictures come from :mod:`inets.draw`: with Graphviz's ``dot`` installed they are made here;
without it (JupyterLite) they are drawn in the page by viz.js, which needs a network
connection. ``retro(True)`` draws everything as a photocopied 1990 figure, and
``arrows(False)`` leaves out the arrowheads that mark principal ports. These two are
switches for the whole module, not for one net. Nets of more than ``DRAW_UP_TO`` nodes,
free ports included, are shown as text.

Needs inets 0.1.4 or later, where the reading, writing, comparing and drawing of nets live.
"""

import html as _html
import json
import re
import uuid

import inets

_v = tuple(int(re.match(r"\d*", x).group() or 0) for x in inets.__version__.split(".")[:3])
if _v < (0, 1, 4):
    raise ImportError(f"livenet needs inets 0.1.4 or later; this is {inets.__version__}: "
                      "pip install -U inets")

from inets.draw import lafont_dot as _lafont_dot, roughen, svg as _svg  # noqa: E402
from inets.draw import RETRO  # noqa: E402
from inets.text import NetTextError, read as build, same, write as show  # noqa: E402
from inets.net import _FREE  # noqa: E402
from inets.system import tokens  # noqa: E402

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


def lafont_dot(net, names=None, top=None):
    """The net as Graphviz text in Lafont's style (:func:`inets.draw.lafont_dot`), with or
    without arrowheads as :func:`arrows` last said."""
    return _lafont_dot(net, names, top, _ARROWS[0])


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
        """Makes one interaction, if there is an alive pair, and returns the rule's count
        name ("?" if the rule has none), or None if there was nothing to do. ``order`` as for
        :meth:`reduce`; ``"random"`` always uses seed 0."""
        before = dict(self.net.counts)
        r = self.net.reduce(order, max_interactions=1)
        if not r.interactions:
            return None
        return next((k for k, v in self.net.counts.items() if v != before.get(k, 0)), "?")

    def steps(self, limit=12, order="stack"):
        """Reduces the net, one interaction at a time, up to ``limit``, and returns a row of
        pictures of it before and after each one. The net itself is reduced: call it again
        and it carries on from where it stopped."""
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
        cost, and how many interactions the net has had in all. The net itself is reduced,
        and returned, so a cell can end with ``n.reduce()`` to show it. ``order`` is ``"stack"``
        (newest alive pair first), ``"queue"`` (oldest first) or ``"random"`` (by ``seed``)."""
        r = self.net.reduce(order, seed=seed, max_interactions=limit)
        counts = ", ".join(f"{k} {v}" for k, v in sorted(r.counts.items()))
        print(f"{r.reason}: {r.interactions} interactions ({counts}); {r.active_left} alive pairs left;"
              f" {self.net.interactions} in all")
        return self

    def reduce_by_need(self, port, limit=10 ** 6):
        """Reduces only what the free port named ``port`` needs (a table with signs), says
        what it cost, and returns the net."""
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
