"""IRIs and resource names of the toolkit (PD-4, PD-6, PD-6a): the only place they are derived."""

import re
from uuid import UUID, uuid4

from rdflib import URIRef

_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]*")
_PREFIX = re.compile(r"[a-z0-9][a-z0-9-]{0,19}")
SYSTEM_SUFFIX = "-system"
TENANT_INFIX = "-t-"
ACCESS_SEGMENT = "access"


def _segment(value: str) -> str:
    if not _SEGMENT.fullmatch(value):
        raise ValueError(f"not a path segment: {value!r}")
    return value


def _prefix(value: str) -> str:
    if not _PREFIX.fullmatch(value):
        raise ValueError(
            f"prefix must be lower case letters, digits or hyphens, 1-20 long: {value!r}"
        )
    return value


def graph_iri(root_iri: str) -> URIRef:
    """The named graph of an aggregate (PD-4); never the root's own IRI."""
    return URIRef(f"{root_iri}/graph")


def mint_tenant_iri(base: str, tenant_segment: str) -> URIRef:
    """A fresh tenant IRI ``{base}{tenant_segment}/{uuid4}``."""
    return URIRef(f"{base}{_segment(tenant_segment)}/{uuid4()}")


def mint_aggregate_iri(tenant_iri: str, rp_path: str) -> URIRef:
    """A fresh aggregate IRI ``{tenant_iri}/{rp_path}/{uuid4}``."""
    return URIRef(f"{tenant_iri}/{_segment(rp_path)}/{uuid4()}")


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
        raise ValueError(f"not an access record IRI: {access_record_iri!r}")
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
        tenant_id = UUID(tenant_iri.rsplit("/", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"tenant IRI must end in a UUID: {tenant_iri!r}") from error
    return f"{tenant_name_prefix(prefix)}{tenant_id.hex}"
