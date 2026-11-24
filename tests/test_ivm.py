import json
import os
import pathlib
import re
import subprocess

import pytest

import inets
from inets import ivm

HERE = pathlib.Path(__file__).parent / "ivm"
EXPECTED = json.loads((HERE / "expected.json").read_text())
KINDS = ("annihilate", "commute", "copy", "erase", "graft", "extrinsic")


@pytest.mark.parametrize("name", sorted(EXPECTED))
@pytest.mark.parametrize("order", ["stack", "queue", "random"])
def test_counts_output_and_flags_are_as_recorded_from_the_ivm(name, order):
    """`expected.json` was recorded from `ivm run` (VineLang/vine at cf0c325)."""
    want = EXPECTED[name]
    run = ivm.run((HERE / name).read_text(), order=order, seed=11)
    assert run.result.reason == "normal"
    assert {k: run.result.counts.get(k, 0) for k in KINDS} == want["counts"]
    assert run.output == want["output"]
    assert sorted(run.flags) == want["flags"]


@pytest.mark.skipif("IVM" not in os.environ, reason="set IVM to an ivm binary to compare with it directly")
@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_counts_and_output_against_the_ivm_itself(name):
    r = subprocess.run([os.environ["IVM"], "run", str(HERE / name)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    theirs = {k.lower(): int(v.replace("_", "")) for k, v in re.findall(r"(Annihilate|Commute|Copy|Erase|Graft|Extrinsic)\s+([0-9_]+)", r.stderr)}
    run = ivm.run((HERE / name).read_text())
    assert {k: run.result.counts.get(k, 0) for k in KINDS} == theirs
    assert run.output == r.stdout


def test_an_extrinsic_function_that_is_not_supplied_stops_the_run():
    with pytest.raises(inets.Error, match="no extrinsic function"):
        ivm.run("iv:main { ^ = ivm:x(io o)  io = ivm:ext:merge[some:other:function](ivm:n32#1 o) }")


def test_a_program_needs_a_main_net():
    with pytest.raises(inets.IvyError):
        ivm.run("m:n { ^ = ivm:eraser }")
