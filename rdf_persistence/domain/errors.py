"""The errors the persistence layers raise; entrypoints map them to problems."""

# ruff: noqa: N818  (the names are the public vocabulary of the spec: DatabaseGone, Conflict, ...)


class PersistenceError(Exception):
    """Base of every error this toolkit raises on purpose."""


class StoreUnavailable(PersistenceError):
    """The triple store cannot be reached or answered with a server error."""


class DatabaseGone(PersistenceError):
    """The dataset a request names does not exist (it was dropped, or never created)."""


class NotFound(PersistenceError):
    """The named thing does not exist."""


class Conflict(PersistenceError):
    """The write lost a race, or the thing to create already exists."""


class BadQuery(PersistenceError):
    """The store refused the SPARQL text as malformed."""
