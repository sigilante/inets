"""Draw an inets net in a notebook, with or without Graphviz installed.

``draw(net, names)`` returns something a notebook shows as a picture of the net.

- With Graphviz's ``dot`` program on the PATH (ordinary Jupyter), the SVG is made here.
  It is saved with the notebook, so GitHub and nbviewer show it too.
- Without it (JupyterLite, where the browser cannot run programs), the Graphviz text is
  sent to the page, and viz.js, Graphviz compiled to WebAssembly, draws it there. That
  picture is drawn each time the notebook is opened and needs a network connection to
  load viz.js.

``names`` maps free ports to labels, as for ``Net.dot``.
"""

import json
import shutil
import subprocess
import uuid

from IPython.display import HTML, SVG

VIZ = "https://cdn.jsdelivr.net/npm/@viz-js/viz@3.31.0/+esm"
DRAW_UP_TO = 80  # nodes: larger nets are described, not drawn (as in the inets kernel)


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


def draw(net, names=None):
    if len(net.kind) > DRAW_UP_TO:
        return HTML(f"<p>{len(net.kind)} nodes: too many to draw.</p>")
    dot = net.dot(names)
    svg = _svg(dot)
    if svg is not None:
        return SVG(svg)
    box = "net-" + uuid.uuid4().hex
    text = json.dumps(dot).replace("</", "<\\/")
    return HTML(f"""<div id="{box}">drawing the net&hellip;</div>
<script>
import("{VIZ}")
  .then(viz => viz.instance())
  .then(viz => document.getElementById("{box}").replaceChildren(viz.renderSVGElement({text})))
  .catch(e => {{ document.getElementById("{box}").textContent = "viz.js could not draw the net: " + e; }});
</script>""")
