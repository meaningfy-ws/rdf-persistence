"""The fixed layout of the toolkit's IRIs and resource names (PD-4): what no policy changes.

Nothing here reads the IRI policy, ``Iris`` or a generated model, so the domain and the services both
use it. What a policy shapes (templates, ids, ``Iris``) is in ``services.iris``.
"""

import re
from uuid import UUID, uuid4

from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri

# The patterns of the schema's ``url_segment`` and ``ServiceSettings.prefix`` slots; a test pins them.
_SEGMENT = re.compile(r"[a-z][a-z0-9-]*")
_PREFIX = re.compile(r"[a-z][a-z0-9]{0,19}")
SYSTEM_SUFFIX = "-system"
TENANT_INFIX = "-t-"
# The application is the one place for data that belongs to no tenant: an id no tenant may take.
APPLICATION_ID = "app"
APPLICATION_SUFFIX = "-app"
TOOLKIT_SEGMENT = "toolkit"
# The graph, under the base, that records the effective IRI policy of the deployment (PD-9, PD-14b).
POLICY_SEGMENT = f"{TOOLKIT_SEGMENT}/iri-policy"
STAMPS_SEGMENT = f"{TOOLKIT_SEGMENT}/schema-stamps"
GENID = "/.well-known/genid/"
LOADED_GRAPH_TYPE = "content"
# The words the IRI layout owns; they are never an id (PD-5) and no class may take one as its type (PD-8).
LAYOUT_WORDS = (LOADED_GRAPH_TYPE, "graph", "parts", "access", "meta", "registry", "provenance")


def _segment(value: str) -> str:
    if not _SEGMENT.fullmatch(value):
        raise InvalidIri(f"not a path segment: {value!r}")
    return value


def _prefix(value: str) -> str:
    if not _PREFIX.fullmatch(value):
        raise InvalidIri(
            f"prefix must be a lower case letter then up to 19 lower case letters or digits: {value!r}"
        )
    return value


def graph_iri(root_iri: str) -> URIRef:
    """The named graph of an aggregate (PD-4); never the root's own IRI."""
    return URIRef(f"{root_iri}/graph")


def root_of_graph(graph: str) -> URIRef:
    """The root an aggregate's named graph belongs to; the inverse of ``graph_iri``."""
    root = str(graph).removesuffix("/graph")
    if root == str(graph) or not root:
        raise InvalidIri(f"not the graph of an aggregate: {graph!r}")
    return URIRef(root)


def skolem_iri(graph: str) -> URIRef:
    """A fresh skolem IRI under ``graph`` for a blank node (PD-8a)."""
    return URIRef(f"{graph}{GENID}{uuid4()}")


def is_skolem_of(graph: str, term: object) -> bool:
    """Whether ``term`` is a skolem IRI minted under ``graph`` (the inverse of ``skolem_iri``)."""
    return isinstance(term, URIRef) and term.startswith(f"{graph}{GENID}")


def toolkit_principal_iri(base: str) -> URIRef:
    """The principal the toolkit acts as when it works on its own behalf: ``{base}toolkit``."""
    return URIRef(f"{base}{TOOLKIT_SEGMENT}")


def policy_record_iri(base: str) -> URIRef:
    """The graph, and the subject in it, that record the effective IRI policy: ``{base}toolkit/iri-policy``."""
    return URIRef(f"{base}{POLICY_SEGMENT}")


def stamps_graph_iri(base: str) -> URIRef:
    """The graph of a database that records the schema versions its data follows: ``{base}toolkit/schema-stamps``."""
    return URIRef(f"{base}{STAMPS_SEGMENT}")


def is_inside_tenant(tenant_iri: str, iri: str) -> bool:
    """True when ``iri`` lies below the tenant's path (the tenant IRI itself does not)."""
    return iri.startswith(f"{tenant_iri}/")


def is_canonical_uuid(text: str) -> bool:
    """True for a UUID in its lower case hyphenated form: the only id the toolkit mints."""
    try:
        return str(UUID(text)) == text
    except ValueError:
        return False


def system_database_name(prefix: str) -> str:
    """The system database ``{prefix}-system``."""
    return f"{_prefix(prefix)}{SYSTEM_SUFFIX}"


def application_database_name(prefix: str) -> str:
    """The application database ``{prefix}-app``; it never starts with a tenant's ``{prefix}-t-``."""
    return f"{_prefix(prefix)}{APPLICATION_SUFFIX}"


def tenant_name_prefix(prefix: str) -> str:
    """What every tenant database and bucket name starts with; the sweep matches on it."""
    return f"{_prefix(prefix)}{TENANT_INFIX}"
