"""The policy guard: the IRI policy is fixed once a deployment has data (PD-9, PD-13, PD-14).

The effective policy (defaults filled in and the settings written into the templates, so "unset" and
"set to the default" compare equal) is kept in the system database, in the graph
``{base}toolkit/iri-policy``, as one statement: that IRI, ``rp:iriPolicy``, and the policy's JSON. The
first write is conditional (insert only if no record exists) and is read back, so two workers that start
with different policies cannot both serve.
"""

import logging

from pydantic import ValidationError
from rdflib import Literal, URIRef

from rdf_persistence.domain.exceptions import IriPolicyChanged
from rdf_persistence.domain.generated.service.rp_service import IriPolicy, ServiceSettings
from rdf_persistence.domain.iris import effective_policy, policy_differences, policy_record_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

SELECT_RECORD = "SELECT ?policy WHERE { GRAPH $graph { $graph $p_policy ?policy } }"
INSERT_RECORD = (
    "INSERT { GRAPH $graph { $graph $p_policy $policy } } "
    "WHERE { FILTER NOT EXISTS { GRAPH $graph { $graph $p_policy ?any } } }"
)


async def guard_iri_policy(store: Store, tenancy: Tenancy, settings: ServiceSettings) -> None:
    """Record the configured policy, or refuse to start when it differs from the one the data follows.

    Raises:
        IriPolicyChanged: The policy differs from the recorded one, or, with access records and no
            record, from the default (the message names each differing field); or the record is
            unreadable, or there is more than one.
    """
    graph = policy_record_iri(settings.base)
    database = tenancy.system_database
    configured = effective_policy(settings.iri_policy, settings)
    stored = await _recorded(store, database, graph, settings)
    if stored is None:
        if await tenancy.has_access_records():
            _require_same(
                effective_policy(None, settings),
                configured,
                "the stored data follows the default policy",
            )
        await _record_if_none(store, database, graph, configured)
        stored = await _recorded(store, database, graph, settings)
    if stored is None:
        raise IriPolicyChanged("the IRI policy record cannot be read back after it was written")
    _require_same(stored, configured, "the recorded policy differs")


def _require_same(stored: IriPolicy, configured: IriPolicy, reason: str) -> None:
    fields = policy_differences(stored, configured)
    if not fields:
        return
    message = f"{reason}: the IRI policy cannot change once there is data; differing fields: {', '.join(fields)}"
    log.error(message, extra={"step": "iri-policy", "fields": fields})
    raise IriPolicyChanged(message)


async def _recorded(
    store: Store, database: str, graph: URIRef, settings: ServiceSettings
) -> IriPolicy | None:
    """The recorded policy, made effective under ``settings``; None when none is recorded."""
    text = fill(SELECT_RECORD, graph=term(graph), p_policy=term(v.IRI_POLICY))
    rows = list(await store.query(database, text))
    if not rows:
        return None
    if len(rows) > 1:
        raise _unreadable(f"it holds {len(rows)} records")
    try:
        policy = IriPolicy.model_validate_json(str(rows[0].policy))  # type: ignore[union-attr]
    except ValidationError as error:
        raise _unreadable("it cannot be parsed") from error
    return effective_policy(policy, settings)


def _unreadable(why: str) -> IriPolicyChanged:
    message = f"the recorded IRI policy is unreadable: {why}"
    log.error(message, extra={"step": "iri-policy"})
    return IriPolicyChanged(message)


async def _record_if_none(store: Store, database: str, graph: URIRef, policy: IriPolicy) -> None:
    text = fill(
        INSERT_RECORD,
        graph=term(graph),
        p_policy=term(v.IRI_POLICY),
        policy=term(Literal(policy.model_dump_json())),
    )
    await store.update(database, text)
