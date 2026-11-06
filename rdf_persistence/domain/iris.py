"""IRIs and resource names of the toolkit (PD-4, PD-6, PD-6a): the only place they are derived."""

import re
from urllib.parse import quote
from uuid import UUID, uuid4

from rdflib import URIRef

from rdf_persistence.domain.exceptions import InvalidIri, NotFound

# The patterns of the schema's ``url_segment`` and ``ServiceSettings.prefix`` slots; a test pins them.
_SEGMENT = re.compile(r"[a-z][a-z0-9-]*")
_PREFIX = re.compile(r"[a-z][a-z0-9]{0,19}")
SYSTEM_SUFFIX = "-system"
TENANT_INFIX = "-t-"
ACCESS_SEGMENT = "access"
TOOLKIT_SEGMENT = "toolkit"
GENID = "/.well-known/genid/"


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


def mint_tenant_iri(base: str, tenant_segment: str) -> URIRef:
    """A fresh tenant IRI ``{base}{tenant_segment}/{uuid4}``."""
    return URIRef(f"{base}{_segment(tenant_segment)}/{uuid4()}")


def tenant_iri(base: str, tenant_segment: str, tenant_id: str) -> URIRef:
    """The IRI of the tenant whose id in a path is ``tenant_id``: ``{base}{tenant_segment}/{id}``.

    Raises:
        NotFound: ``tenant_id`` is not a canonical UUID, so no tenant has it.
        InvalidIri: ``tenant_segment`` is not a path segment.
    """
    if not is_canonical_uuid(tenant_id):
        raise NotFound(f"no tenant {tenant_id!r}")
    return URIRef(f"{base}{_segment(tenant_segment)}/{tenant_id}")


def aggregate_iri(tenant: str, rp_path: str, aggregate_id: str) -> URIRef:
    """The IRI of the aggregate whose id in a path is ``aggregate_id``: ``{tenant}/{rp_path}/{id}``.

    Raises:
        NotFound: ``aggregate_id`` is not a canonical UUID, so no aggregate has it.
        InvalidIri: ``rp_path`` is not a path segment.
    """
    if not is_canonical_uuid(aggregate_id):
        raise NotFound(f"no aggregate {aggregate_id!r}")
    return URIRef(f"{tenant}/{_segment(rp_path)}/{aggregate_id}")


def mint_aggregate_iri(tenant_iri: str, rp_path: str) -> URIRef:
    """A fresh aggregate IRI ``{tenant_iri}/{rp_path}/{uuid4}``."""
    return URIRef(f"{tenant_iri}/{_segment(rp_path)}/{uuid4()}")


def skolem_iri(graph: str) -> URIRef:
    """A fresh skolem IRI under ``graph`` for a blank node (PD-8a)."""
    return URIRef(f"{graph}{GENID}{uuid4()}")


def toolkit_principal_iri(base: str) -> URIRef:
    """The principal the toolkit acts as when it works on its own behalf: ``{base}toolkit``."""
    return URIRef(f"{base}{TOOLKIT_SEGMENT}")


def is_inside_tenant(tenant_iri: str, iri: str) -> bool:
    """True when ``iri`` lies below the tenant's path (the tenant IRI itself does not)."""
    return iri.startswith(f"{tenant_iri}/")


def is_canonical_uuid(text: str) -> bool:
    """True for a UUID in its lower case hyphenated form: the only id the toolkit mints."""
    try:
        return str(UUID(text)) == text
    except ValueError:
        return False


def is_aggregate_iri(tenant_iri: str, iri: str) -> bool:
    """True for what the toolkit mints as an aggregate: the tenant root, its access record, or
    ``{tenant_iri}/{rp_path}/{canonical uuid}``. Anything else could alias another graph."""
    if iri in (tenant_iri, str(access_iri(tenant_iri))):
        return True
    path, _, last = iri.rpartition("/")
    parent, _, segment = path.rpartition("/")
    return parent == tenant_iri and bool(_SEGMENT.fullmatch(segment)) and is_canonical_uuid(last)


def is_aggregate_graph_iri(tenant_iri: str, iri: str) -> bool:
    """True when ``iri`` is the ``graph_iri`` of an aggregate of the tenant (never of the tenant root)."""
    root = iri.removesuffix("/graph")
    return root != iri and root != tenant_iri and is_aggregate_iri(tenant_iri, root)


def is_loaded_graph_of(root_iri: str, graph: str) -> bool:
    """True when ``graph`` is exactly ``{root_iri}/content/{canonical uuid}`` (see ``loaded_graph_iri``)."""
    path, _, last = graph.rpartition("/")
    return path == f"{root_iri}/content" and is_canonical_uuid(last)


def mint_part_iri(root_iri: str) -> URIRef:
    """A fresh IRI ``{root_iri}/parts/{uuid4}`` for an owned part that has none."""
    return URIRef(f"{root_iri}/parts/{uuid4()}")


def loaded_graph_iri(aggregate_iri: str) -> URIRef:
    """A fresh IRI for a graph loaded into an aggregate."""
    return URIRef(f"{aggregate_iri}/content/{uuid4()}")


def meta_graph_iri(tenant_iri: str) -> URIRef:
    """The graph that holds the tenant's root object."""
    return URIRef(f"{tenant_iri}/meta")


def registry_graph_iri(tenant_iri: str) -> URIRef:
    """The graph that holds the tenant's registry entries."""
    return URIRef(f"{tenant_iri}/registry")


def access_iri(tenant_iri: str) -> URIRef:
    """The IRI of the tenant's access record; its graph is ``graph_iri`` of it."""
    return URIRef(f"{tenant_iri}/{ACCESS_SEGMENT}")


def tenant_iri_of_access(access_record_iri: str) -> URIRef:
    """The tenant an access record belongs to; the inverse of ``access_iri``."""
    tenant, _, last = access_record_iri.rpartition("/")
    if last != ACCESS_SEGMENT or not tenant:
        raise InvalidIri(f"not an access record IRI: {access_record_iri!r}")
    return URIRef(tenant)


def system_database_name(prefix: str) -> str:
    """The system database ``{prefix}-system``."""
    return f"{_prefix(prefix)}{SYSTEM_SUFFIX}"


def tenant_name_prefix(prefix: str) -> str:
    """What every tenant database and bucket name starts with; the sweep matches on it."""
    return f"{_prefix(prefix)}{TENANT_INFIX}"


def tenant_resource_name(prefix: str, tenant_iri: str) -> str:
    """The tenant's database and bucket name ``{prefix}-t-{uuid hex}``."""
    try:
        last = tenant_iri.rsplit("/", 1)[1]
        tenant_id = UUID(last)
    except (IndexError, ValueError) as error:
        raise InvalidIri(f"tenant IRI must end in a UUID: {tenant_iri!r}") from error
    if str(tenant_id) != last:
        raise InvalidIri(f"tenant IRI must end in a canonical UUID: {tenant_iri!r}")
    return f"{tenant_name_prefix(prefix)}{tenant_id.hex}"


def principal_iri(issuer: str, subject: str) -> URIRef:
    """The IRI of the person or service account a token's ``sub`` names: ``{issuer}/users/{sub}``.

    The issuer names the provider, so the IRI is unique across providers; percent-encoding keeps a
    ``sub`` from leaving its path segment.
    """
    return URIRef(f"{issuer.rstrip('/')}/users/{quote(subject, safe='')}")
