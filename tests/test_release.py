import pathlib
import re

import pytest

import inets

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _field(path, pattern):
    m = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.M)
    assert m, f"{path}: nothing matches {pattern}"
    return m.group(1)


def test_every_version_string_agrees():
    if not (ROOT / "kernel").is_dir():
        pytest.skip("a source archive of inets holds no kernel/")
    version = inets.__version__
    assert _field("pyproject.toml", r'^version = "([^"]+)"') == version
    assert _field("kernel/pyproject.toml", r'^version = "([^"]+)"') == version
    assert _field("kernel/src/inets_kernel/__init__.py", r'^__version__ = "([^"]+)"') == version
    assert _field("kernel/pyproject.toml", r'"inets>=([^",]+)[,"]') == version
    assert _field("CHANGELOG.md", r"^## (\S+)") == version
