"""Interaction nets: declare a system as a table of rules, check it, and reduce nets by it.

    >>> import inets
    >>> system = inets.bundled("combinators")
    >>> system.check()
    []
    >>> net = inets.Net(system)
    >>> a, b = net.free(), net.free()
    >>> net.wire(net.make("con", a, b), net.make("dup", net.make("era"), net.make("era")))
    >>> result = net.reduce()
    >>> result.reason, result.counts
    ('normal', {'commute': 1, 'erase': 2})

See :mod:`inets.system` for the table format, :mod:`inets.net` for nets and schedules,
:mod:`inets.ski` for the combinators S, K and I as agents, :mod:`inets.ivm` for programs
of Vine's IVM, :mod:`inets.ivy` for Ivy text, :mod:`inets.text` for nets written as
equations, and :mod:`inets.draw` for pictures of nets in the style of Lafont's figures.
"""
from .errors import Error, IvyError, NetTextError, Stuck, TableError, TermError
from .net import Host, Library, Net, Port, Result
from .system import (Agent, Call, Compare, Expand, Ext, New, Otherwise, Pair, Peek, Rewrite, Rule,
                     Side, System, Test, bundled)

from . import draw, text  # noqa: E402  (after the classes they use)

__version__ = "0.1.4"

__all__ = ["System", "Agent", "Rule", "bundled", "Net", "Port", "Result", "Host", "Library",
           "Side", "Rewrite", "Ext", "New", "Pair", "Expand", "Call",
           "Compare", "Test", "Peek", "Otherwise",
           "Error", "TableError", "IvyError", "TermError", "Stuck", "NetTextError", "text", "draw"]
