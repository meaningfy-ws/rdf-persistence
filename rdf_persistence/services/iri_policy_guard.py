"""The policy guard: the IRI policy is fixed once a deployment has data (PD-9, PD-13).

The effective policy (defaults filled in, so "unset" and "set to the default" compare equal) is kept in
the system database, in the graph ``{base}toolkit/iri-policy``, as one statement: that IRI,
``rp:iriPolicy``, and the policy's JSON. ``put_graph`` replaces the whole graph, so two workers
recording the same policy at once leave one record.
"""

import logging
from typing import Any

from rdflib import Graph, Literal, URIRef

from rdf_persistence.domain.exceptions import IriPolicyChanged
from rdf_persistence.domain.generated.service.rp_service import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings,
)
from rdf_persistence.domain.iris import system_database_name
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

POLICY_SEGMENT = "toolkit/iri-policy"
SELECT_RECORD = "SELECT ?policy WHERE { GRAPH $graph { $graph $p_policy ?policy } }"


def effective(policy: IriPolicy | None) -> IriPolicy:
    """``policy`` with every default filled in, the id specs included."""
    policy = policy or IriPolicy()
    uuid = IdSpec(kind=IdKind.UUID4)
    return policy.model_copy(
        update={"tenant_id": policy.tenant_id or uuid, "object_id": policy.object_id or uuid}
    )


def differing_fields(stored: IriPolicy, configured: IriPolicy) -> list[str]:
    """The dotted names of the fields on which the two policies differ."""
    return _diff(stored.model_dump(), configured.model_dump(), "")


def _diff(stored: dict[str, Any], configured: dict[str, Any], path: str) -> list[str]:
    found: list[str] = []
    for name in stored:
        if isinstance(stored[name], dict) and isinstance(configured[name], dict):
            found += _diff(stored[name], configured[name], f"{path}{name}.")
        elif stored[name] != configured[name]:
            found.append(f"{path}{name}")
    return found


async def guard_iri_policy(store: Store, tenancy: Tenancy, settings: ServiceSettings) -> None:
    """Record the configured policy, or refuse to start when it differs from the one the data follows.

    Raises:
        IriPolicyChanged: The policy differs from the recorded one, or, with access records and no
            record, from the default; the message names each differing field.
    """
    database = system_database_name(settings.prefix)
    graph = URIRef(f"{settings.base}{POLICY_SEGMENT}")
    configured = effective(settings.iri_policy)
    stored = await _recorded(store, database, graph)
    if stored is None:
        if await tenancy.tenants():
            _refuse(effective(None), configured, "the stored data follows the default policy")
        await _record(store, database, graph, configured)
        return
    _refuse(stored, configured, "the recorded policy differs")


def _refuse(stored: IriPolicy, configured: IriPolicy, reason: str) -> None:
    fields = differing_fields(stored, configured)
    if not fields:
        return
    message = f"{reason}: the IRI policy cannot change once there is data; differing fields: {', '.join(fields)}"
    log.error(message, extra={"step": "iri-policy", "fields": fields})
    raise IriPolicyChanged(message)


async def _recorded(store: Store, database: str, graph: URIRef) -> IriPolicy | None:
    text = fill(SELECT_RECORD, graph=term(graph), p_policy=term(v.IRI_POLICY))
    rows = list(await store.query(database, text))
    return IriPolicy.model_validate_json(str(rows[0].policy)) if rows else None  # type: ignore[union-attr]


async def _record(store: Store, database: str, graph: URIRef, policy: IriPolicy) -> None:
    record = Graph()
    record.add((graph, v.IRI_POLICY, Literal(policy.model_dump_json())))
    await store.put_graph(database, graph, record)
