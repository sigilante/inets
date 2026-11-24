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
of Vine's IVM, and :mod:`inets.ivy` for Ivy text.
"""
from .errors import Error, IvyError, Stuck, TableError, TermError
from .net import Host, Library, Net, Port, Result
from .system import Agent, Rule, System, bundled

__version__ = "0.1.1"

__all__ = ["System", "Agent", "Rule", "bundled", "Net", "Port", "Result", "Host", "Library",
           "Error", "TableError", "IvyError", "TermError", "Stuck"]
