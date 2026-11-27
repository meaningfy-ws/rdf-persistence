"""The activities of one kind that used an aggregate, read from the provenance graph (PD-15, D-3).

One read for every kind of activity that is about an aggregate (a ``Transition``, an ``Assignment``):
the caller checks who may read the aggregate and that it is stored; this module finds, decodes,
narrows and orders the activities.
"""

from rdflib import RDF, Graph, URIRef

from rdf_persistence.collaboration.services.discussion import moment_of
from rdf_persistence.persistence.services.mapper import Mapper
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity
from rdf_persistence.schema.services import vocabulary as v


async def activities_about[A: Activity](
    session: Session, mapper: Mapper, activity_class: type[A], type_iri: URIRef, iri: str
) -> list[A]:
    """The activities of class ``activity_class`` (typed ``type_iri``) that used ``iri``, oldest
    first, ties by IRI, each narrowed to the generations and invalidations of ``iri``.

    No access is checked: the caller has done it.

    Raises:
        DatabaseGone: The tenant database does not exist.
    """
    found = await session.activities(type_iri, v.USED, URIRef(iri), entity=URIRef(iri))
    decoded = [
        _decode(mapper, activity_class, type_iri, root, graph) for root, graph in found.items()
    ]
    return sorted(
        (_about(r, iri) for r in decoded if r is not None),
        key=lambda r: (moment_of(r.started_at_time), r.id),
    )


def _decode[A: Activity](
    mapper: Mapper, activity_class: type[A], type_iri: URIRef, iri: str, graph: Graph
) -> A | None:
    """The activity at ``iri``, or None for a root that is not one (not typed so, or one the class refuses)."""
    if (URIRef(iri), RDF.type, type_iri) not in graph:
        return None
    try:
        return mapper.from_graph(activity_class, iri, graph, None)
    except ValueError:  # pydantic's refusal of the triples
        return None


def _about[A: Activity](move: A, iri: str) -> A:
    """``move`` with only the generations and invalidations of the entity ``iri``: what else the
    commit changed is no business of a reader of ``iri`` (D-6 b)."""
    return move.replaced(
        generations=_of(move.generations, iri), invalidations=_of(move.invalidations, iri)
    )


def _of[P](parts: list[P] | None, iri: str) -> list[P] | None:
    """The ``parts`` about the entity ``iri``, or None when there is none."""
    return [p for p in parts or [] if p.entity == iri] or None  # type: ignore[attr-defined]
