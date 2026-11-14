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
    """The write lost a race, or the thing to create already exists.

    ``iris`` are the root IRIs found conflicting, sorted; empty when the writer lost a race with no
    culprit left to name. A diagnosis read after the refusal, so it can itself race (PD-7).
    """

    def __init__(self, *args: object, iris: tuple[str, ...] = ()) -> None:
        super().__init__(*args)
        self.iris = tuple(iris)


class KeyConflict(Conflict):
    """A commit claims a value of a unique key that another aggregate of the tenant holds.

    ``iris`` are the roots of the commit whose claim clashed and ``keys`` the names of the keys,
    both sorted; never the holder's IRI, which the caller may not see. When it comes from the
    store it is a diagnosis, as ``Conflict.iris`` is: read after the refusal, it can race, so it
    says what another aggregate held at the read, not why the commit was refused. A clash between
    two changes of one commit is exact. A subclass, so code that catches ``Conflict`` catches it.
    """

    def __init__(
        self, *args: object, iris: tuple[str, ...] = (), keys: tuple[str, ...] = ()
    ) -> None:
        super().__init__(*args, iris=iris)
        self.keys = tuple(keys)


class CommitTooLarge(PersistenceError):
    """A unit of work holds more roots than its ``max_roots``; commit fewer, or in batches."""


class BadQuery(PersistenceError):
    """The store refused the SPARQL text as malformed."""


class InvalidGraph(PersistenceError):
    """A file of RDF does not parse; the message is the parser's."""


class InvalidIri(PersistenceError, ValueError):
    """A value breaks an IRI, path-segment or resource-name rule of the toolkit (``domain.iris``)."""


class IriPolicyChanged(PersistenceError):
    """The configured IRI policy differs from the one the deployment's data follows; the service does not start."""


class SparqlError(PersistenceError, ValueError):
    """A value cannot become a SPARQL term, or a template and its terms do not match."""


class InvalidToken(PersistenceError):
    """An access token is missing, expired, malformed, signed by an unknown key, or for another issuer or audience."""


class IdentityUnavailable(PersistenceError):
    """The identity provider's keys or management API cannot be reached, or answered with a server error."""


class InvalidRoleDefinition(PersistenceError, ValueError):
    """A file of role definitions cannot be read or holds an entry that is not a role definition."""


class InvalidWorkflow(PersistenceError, ValueError):
    """A workflow file cannot be read, is not a workflow, or contradicts itself, the role definitions or the schema."""


class UnknownRole(PersistenceError, ValueError):
    """A grant names a role that no tenant-level or aggregate-level role definition defines."""


class InvalidGrant(PersistenceError, ValueError):
    """A grant or prohibition targets something that is not the tenant or the graph of one of its aggregates, or names an assignee that is not an IRI."""


class InvalidBody(PersistenceError):
    """A request body is not a valid representation for its route: it fails the shape, names an IRI the
    client may not choose, or describes another aggregate than the one in the path."""


class NotAcceptable(PersistenceError):
    """The request's ``Accept`` names no representation the service produces."""


class UnsupportedMediaType(PersistenceError):
    """The request's ``Content-Type`` is not one the route accepts."""


class PreconditionRequired(PersistenceError):
    """An update or a delete came without the ``If-Match`` header that names the version it expects."""


class PayloadTooLarge(PersistenceError):
    """A request body is larger than the service takes: too many bytes, or too many nodes."""


class StoredDataInvalid(PersistenceError):
    """What the store holds cannot be decoded: a fault of the service or its data, never of the request."""
