"""The errors the toolkit raises; entrypoints map them to problems."""

# ruff: noqa: N818  (the names are the public vocabulary of the spec: DatabaseGone, Conflict, ...)


class PersistenceError(Exception):
    """Base of every error this toolkit raises on purpose."""


class StoreUnavailable(PersistenceError):
    """The triple store or the file store cannot be reached, or answered with a server error."""


class DatabaseGone(PersistenceError):
    """The dataset a request names does not exist (it was dropped, or never created)."""


class TenantGone(PersistenceError):
    """The bucket a file operation names does not exist: the tenant was deleted, or never created."""


class NotFound(PersistenceError):
    """The named thing does not exist."""


class Forbidden(PersistenceError):
    """The caller may see the thing but is not allowed the action (403)."""


class Conflict(PersistenceError):
    """The write lost a race, or the thing to create already exists."""


class BadQuery(PersistenceError):
    """The store refused the SPARQL text as malformed."""


class InvalidGraph(PersistenceError):
    """A file of RDF does not parse; the message is the parser's."""


class InvalidIri(ValueError):
    """A value breaks an IRI, path-segment or resource-name rule of the toolkit (``domain.iris``)."""


class SparqlError(ValueError):
    """A value cannot become a SPARQL term, or a template and its terms do not match."""


class InvalidToken(PersistenceError):
    """An access token is missing, expired, malformed, signed by an unknown key, or for another issuer or audience."""


class IdentityUnavailable(PersistenceError):
    """The identity provider's keys or management API cannot be reached, or answered with a server error."""


class InvalidRoleDefinition(ValueError):
    """A file of role definitions cannot be read or holds an entry that is not a role definition."""


class UnknownRole(ValueError):
    """A grant names a role that no tenant-level or aggregate-level role definition defines."""
