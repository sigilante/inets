"""The kernel itself, through Jupyter: installed into a temporary directory and given a
small notebook to run."""
import os
import sys

import pytest

nbclient = pytest.importorskip("nbclient")
nbformat = pytest.importorskip("nbformat")


def test_a_notebook_runs_through_the_kernel(tmp_path, monkeypatch):
    import inets_kernel.install
    inets_kernel.install.install(prefix=str(tmp_path))
    monkeypatch.setenv("JUPYTER_PATH", str(tmp_path / "share" / "jupyter"))
    here = os.path.dirname(os.path.abspath(__file__))
    paths = [os.path.join(here, "..", "src"), os.path.join(here, "..", "..", "src")]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(paths + [os.environ.get("PYTHONPATH", "")]))
    cells = ["con (a b) = dup (era era)", "%schedule sideways", "%ski ``KI```SII``SII"]
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(c) for c in cells])
    nbclient.NotebookClient(nb, kernel_name="inets", timeout=60, allow_errors=True).execute()
    first, second, third = (c.outputs for c in nb.cells)
    text = "".join(o.get("text", "") for o in first if o.output_type == "stream")
    assert "3 interactions" in text and "commute 1, erase 2" in text
    assert [o.output_type for o in second] == ["error"] and "a schedule is one of" in second[0].evalue
    assert "".join(o.get("text", "") for o in third).startswith("I\n")
    assert sys.executable in (tmp_path / "share" / "jupyter" / "kernels" / "inets" / "kernel.json").read_text()
