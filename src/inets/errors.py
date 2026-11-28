"""The package's errors. All derive from :class:`Error`."""


class Error(Exception):
    """Anything this package raises on purpose."""


class TableError(Error):
    """A table that cannot be read."""


class IvyError(Error):
    """Ivy text that cannot be read, or that is not a net."""


class TermError(Error):
    """Text that is not a term of S, K and I, or a term that cannot be used as asked."""


class Stuck(Error):
    """A net that cannot go on: an active pair no rule applies to, or a value wanted
    that depends on a free port."""


class NetTextError(Error):
    """Text that is not a net: see :mod:`inets.text`."""
