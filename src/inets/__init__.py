"""Interaction nets: declare a system as a table of rules, check it, and reduce nets by it.

    >>> import inets
    >>> system = inets.bundled("combinators")
    >>> inets.check(system)
    []
    >>> net = inets.Net(system)
    >>> a, b = net.free(), net.free()
    >>> net.wire(net.node("con", a, b), net.node("con", net.node("era"), net.node("era")))
    >>> net.reduce().reason
    'normal'

See :mod:`inets.system` for the table format, :mod:`inets.net` for nets and schedules, and
:mod:`inets.ski` for the combinators S, K and I as agents.
"""
from functools import lru_cache
from importlib import resources

from .net import FREE, Host, Net, Result, Stuck
from .system import Agent, Rule, System, TableError, check, load, parse

__version__ = "0.1.0"

BUNDLED = ("combinators", "ski", "lazy", "ivm")


@lru_cache(maxsize=None)
def bundled(name):
    """One of the tables that come with the package: ``combinators`` (the symmetric
    interaction combinators), ``ski`` and ``lazy`` (S, K and I as agents; see
    :mod:`inets.ski`), ``ivm`` (the interaction system of Vine's IVM; see
    :mod:`inets.ivm`). The same object is returned each time: do not change it."""
    text = resources.files("inets.systems").joinpath(name + ".rules").read_text(encoding="utf-8")
    return parse(text, name)


__all__ = ["Agent", "Rule", "System", "TableError", "check", "load", "parse", "bundled",
           "Net", "Host", "Result", "Stuck", "FREE"]
