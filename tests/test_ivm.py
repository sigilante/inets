import json
import os
import pathlib
import re
import subprocess

import pytest

from inets import ivm

HERE = pathlib.Path(__file__).parent / "ivm"
EXPECTED = json.loads((HERE / "expected.json").read_text())
KINDS = ("annihilate", "commute", "copy", "erase", "graft", "extrinsic")


@pytest.mark.parametrize("name", sorted(EXPECTED))
@pytest.mark.parametrize("order", ["stack", "queue", "random"])
def test_counts_output_and_flags_are_the_ivms(name, order):
    """`expected.json` was recorded from `ivm run` (VineLang/vine at cf0c325)."""
    want = EXPECTED[name]
    run = ivm.run((HERE / name).read_text(), order=order, seed=11)
    assert run.result.reason == "normal"
    assert {k: run.result.counts.get(k, 0) for k in KINDS} == want["counts"]
    assert run.output == want["output"]
    assert sorted(run.flags) == want["flags"]


@pytest.mark.skipif("IVM" not in os.environ, reason="set IVM to an ivm binary to compare with it directly")
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_against_the_ivm_itself(name):
    r = subprocess.run([os.environ["IVM"], "run", str(HERE / name)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    theirs = {k.lower(): int(v.replace("_", "")) for k, v in re.findall(r"(Annihilate|Commute|Copy|Erase|Graft|Extrinsic)\s+([0-9_]+)", r.stderr)}
    run = ivm.run((HERE / name).read_text())
    assert {k: run.result.counts.get(k, 0) for k in KINDS} == theirs
    assert run.output == r.stdout


def test_an_unknown_extrinsic_function_stops_the_run():
    program = "iv:main { ^ = ivm:x(io o)  io = ivm:ext:merge[some:other:function](ivm:n32#1 o) }"
    with pytest.raises(NotImplementedError):
        ivm.run(program)
