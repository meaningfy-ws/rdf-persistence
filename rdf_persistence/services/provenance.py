"""What an activity record is: the triples of one completed activity (message-bus PD-3).

An activity is a ``prov:Activity`` typed with its own class and every ancestor class, with its start and
end time, the principals it was associated with and its parts: one blank node per generation or
invalidation of an entity at a version. The triples are built from the vocabulary alone: this module
(like the session) never imports the mapper, which imports the session (PD-6).
"""

from collections.abc import Iterable
from datetime import datetime

from rdflib import RDF, BNode, Literal, URIRef

from rdf_persistence.domain.generated.rp_provenance import Activity, Generation, Invalidation
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services import vocabulary as v


def _part_triples(
    activity: URIRef, *, link: URIRef, kind: URIRef, parts: Iterable[Generation | Invalidation]
) -> list[Triple]:
    """One blank node per part, linked from ``activity`` by ``link``, with its class and slots (PD-3)."""
    triples: list[Triple] = []
    for part in parts:
        node = BNode()
        triples += [
            (activity, link, node),
            (node, RDF.type, kind),
            (node, v.PART_ACTIVITY, URIRef(part.activity)),
            (node, v.AT_TIME, Literal(part.at_time)),
            (node, v.ENTITY, URIRef(part.entity)),
            (node, v.ENTITY_VERSION, Literal(part.entity_version)),
        ]
        if part.entity_class is not None:
            triples.append((node, v.ENTITY_CLASS, URIRef(part.entity_class)))
    return triples


def _times(activity: Activity) -> tuple[datetime, datetime]:
    """The start and end time of ``activity``; ``ValueError`` naming it when either is missing."""
    if activity.started_at_time is None or activity.ended_at_time is None:
        raise ValueError(f"activity {activity.id} has no start or no end time")
    return activity.started_at_time, activity.ended_at_time


def activity_triples(activity: Activity, types: Iterable[URIRef]) -> list[Triple]:
    """The statements of one completed activity: its types, times, principals and parts (PD-3).

    ``types`` are the activity's own class and every ancestor up to ``prov:Activity``; the session
    cannot know a consumer's subclasses, so the caller names them. The parts are blank nodes.
    Raises ``ValueError`` naming the activity when it has no start or end time.
    """
    started, ended = _times(activity)
    subject = URIRef(activity.id)
    triples: list[Triple] = [(subject, RDF.type, t) for t in types]
    triples += [
        (subject, v.ACTIVITY_STARTED, Literal(started)),
        (subject, v.ACTIVITY_ENDED, Literal(ended)),
    ]
    triples += [(subject, v.ASSOCIATED_WITH, URIRef(w)) for w in activity.was_associated_with or []]
    triples += _part_triples(
        subject, link=v.HAS_GENERATION, kind=v.GENERATION, parts=activity.generations or []
    )
    triples += _part_triples(
        subject, link=v.HAS_INVALIDATION, kind=v.INVALIDATION, parts=activity.invalidations or []
    )
    return triples
