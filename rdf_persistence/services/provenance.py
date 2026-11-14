"""What an activity record is: the triples of one completed activity (message-bus PD-3).

An activity is a ``prov:Activity`` typed with its own class and every ancestor class, with its start and
end time, the principals it was associated with and its parts: one blank node per generation or
invalidation of an entity at a version. The triples are built from the vocabulary alone: this module
(like the session) never imports the mapper, which imports the session (PD-6).
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime

from rdflib import RDF, BNode, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_provenance import (
    Activity,
    Add,
    Generation,
    Invalidation,
    Remove,
    Replace,
)
from rdf_persistence.domain.sparql import SparqlTerm, Triple, fill, fragment, term, triples_block
from rdf_persistence.services import vocabulary as v

ID_PREFIX = "urn:uuid:"
# One more marked operation of the commit's request (PD-6), and the guard and the question about
# an activity IRI that is taken (PD-8).
_RECORD = "INSERT { GRAPH $provenance { $triples } } WHERE { $marked }"
_ID_FREE = "FILTER NOT EXISTS { GRAPH $provenance { $id ?taken_p ?taken_o } }"
ID_TAKEN = "ASK { GRAPH $provenance { $id ?p ?o } }"
_STANDARD_TYPES: dict[type[Activity], list[URIRef]] = {
    Add: [v.ADD, v.ACTIVITY],
    Replace: [v.REPLACE, v.ACTIVITY],
    Remove: [v.REMOVE, v.ACTIVITY],
    Activity: [v.ACTIVITY],
}


class Served:
    """A command the session records as its commit's activity (PD-8): the model with its id and no
    payload, its own statements, and its class IRIs (own and every ancestor). It serves one commit.

    Raises ``ValueError`` naming the id when it is not a ``urn:uuid:`` IRI: an aggregate IRI as an
    activity id would be rewritten on restore, and no unchecked text may reach an IRI (D-3).
    A plain class: it holds the state of one use, which a generated model does not.
    """

    def __init__(self, activity: Activity, triples: list[Triple], types: list[URIRef]) -> None:
        if not activity.id.startswith(ID_PREFIX):
            raise ValueError(f"the activity id {activity.id!r} is not a {ID_PREFIX} IRI")
        self.activity = activity
        self.triples = triples
        self.types = types
        self._spent = False

    def claim(self) -> None:
        """Take the one commit this serves; ``RuntimeError`` if it served one already."""
        if self._spent:
            raise RuntimeError(f"the command {self.activity.id} has served a commit already")
        self._spent = True


# One version of one entity a change generated or invalidated: (entity IRI, the root's class IRI if
# it has one, version token). What one change did: (generated, invalidated); an add generates, a
# remove invalidates, a replace does both.
Event = tuple[str, str | None, str]
Change = tuple[Event | None, Event | None]


def first_class(types: Iterable[Node]) -> str | None:
    """The class IRI an event names for a root with these ``types``: the first in sorted order."""
    return min(map(str, types), default=None)


def class_in(root: str, triples: Iterable[Triple]) -> str | None:
    """The class IRI of ``root`` among the ``triples`` a commit writes."""
    return first_class(o for s, p, o in triples if s == URIRef(root) and p == RDF.type)


def _standard(changes: Sequence[Change]) -> type[Activity]:
    """``Add``, ``Replace`` or ``Remove`` when every change is of that kind, else ``Activity`` (PD-7)."""
    kinds = {(made is not None, ended is not None) for made, ended in changes}
    found = {(True, False): Add, (True, True): Replace, (False, True): Remove}
    return found.get(next(iter(kinds)), Activity) if len(kinds) == 1 else Activity


def completed(
    changes: Sequence[Change],
    *,
    served: Served | None,
    principal: Principal,
    started: datetime,
    ended: datetime,
) -> tuple[Activity, list[URIRef]]:
    """The activity of a commit, with what the session fills, and its types (PD-7, PD-8).

    A served command keeps its own slots; the principal, times and parts are the session's, so a
    ``was_associated_with`` the command carried is overwritten.
    """
    if served is None:
        base = _standard(changes)(id=f"{ID_PREFIX}{uuid.uuid4()}")
        types = _STANDARD_TYPES[type(base)]
    else:
        base, types = served.activity, served.types

    def parts[P: (Generation, Invalidation)](kind: type[P], events: list[Event]) -> list[P] | None:
        return [
            kind(
                activity=base.id,
                at_time=ended,
                entity=entity,
                entity_class=class_iri,
                entity_version=version,
            )
            for entity, class_iri, version in events
        ] or None

    activity = base.model_copy(
        update={
            "started_at_time": started,
            "ended_at_time": ended,
            "was_associated_with": [principal.id],
            "generations": parts(Generation, [g for g, _ in changes if g]),
            "invalidations": parts(Invalidation, [i for _, i in changes if i]),
        }
    )
    return activity, list(types)


def record_operation(provenance: URIRef, marked: SparqlTerm, triples: Iterable[Triple]) -> str:
    """The operation that stores ``triples`` in the provenance graph while the commit's marker is there."""
    return fill(_RECORD, provenance=term(provenance), triples=triples_block(triples), marked=marked)


def id_guard(provenance: URIRef, activity_id: str) -> SparqlTerm:
    """The pattern that holds while no statement is made of ``activity_id`` in the provenance graph."""
    return fragment(_ID_FREE, provenance=term(provenance), id=term(URIRef(activity_id)))


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
