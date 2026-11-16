"""What an activity record is: the triples of one completed activity (message-bus PD-3).

An activity is a ``prov:Activity`` typed with its own class and every ancestor class, with its start and
end time, the principals it was associated with and its parts: one blank node per generation or
invalidation of an entity at a version. The triples are built from the vocabulary alone: this module
(like the session) never imports the mapper, which imports the session (PD-6).
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel
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
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services import vocabulary as v

ID_PREFIX = "urn:uuid:"


def new_activity_id() -> str:
    """A new activity IRI: ``urn:uuid:`` and a random UUID (PD-3)."""
    return f"{ID_PREFIX}{uuid.uuid4()}"


def is_activity_id(text: str) -> bool:
    """Whether ``text`` is ``urn:uuid:`` and a UUID in its canonical form."""
    tail = text.removeprefix(ID_PREFIX)
    try:
        return text.startswith(ID_PREFIX) and str(uuid.UUID(tail)) == tail
    except ValueError:
        return False


class Served:
    """A command the session records as its commit's activity (PD-8): the model with its id and no
    payload, its own statements, and its class IRIs (own and every ancestor). It serves one commit.

    Raises ``ValueError`` naming the id when it is not ``urn:uuid:`` and a UUID: an aggregate IRI as an
    activity id would be rewritten on restore, and no unchecked text may reach an IRI (D-3). It also
    refuses a triple about another subject than the activity or a blank node, and a triple of the
    activity that gives ``rdf:type`` or a slot the session fills (D-5 b).
    A plain class: it holds the state of one use, which a generated model does not.
    """

    def __init__(self, activity: Activity, triples: list[Triple], types: list[URIRef]) -> None:
        if not is_activity_id(activity.id):
            raise ValueError(f"the activity id {activity.id!r} is not a {ID_PREFIX}<uuid> IRI")
        own = URIRef(activity.id)
        for s, p, _ in triples:
            if s != own and not isinstance(s, BNode):
                raise ValueError(f"a served triple names the subject {s}, not the activity {own}")
            if s == own and (p == RDF.type or p in v.SESSION_FILLED_PREDICATES):
                raise ValueError(f"a served triple of the activity names {p}, which is not its own")
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


class ClassFinder(Protocol):
    """What finds a generated class by its schema name: ``GeneratedModels``, which this module cannot
    import (the mapper imports the session)."""

    def named(self, schema_name: str) -> type[BaseModel]: ...


def activity_class_of(
    view: SchemaView, models: ClassFinder, types: Iterable[Node]
) -> type[Activity]:
    """The most specific generated class among the schema classes whose class IRI is one of ``types``
    (the one with the most ancestors), so a consumer's subclass wins over its parent (PD-16).

    Raises:
        LookupError: No class of the schema has any of the ``types`` as its IRI, its generated
            class is missing, or it is not an ``Activity`` or a descendant (D-19).
    """
    wanted = {str(t) for t in types}
    found = [name for name in view.all_classes() if view.get_uri(name, expand=True) in wanted]
    if not found:
        raise LookupError(f"no class of the schema has any of the IRIs {sorted(wanted)}")
    best = max(found, key=lambda name: len(view.class_ancestors(name)))
    generated = models.named(best)
    if not issubclass(generated, Activity):
        raise LookupError(f"the class {best} is not an activity")
    return generated


def activity_class_named(view: SchemaView, models: ClassFinder, class_iri: str) -> type[Activity]:
    """The generated class of the schema class whose IRI is ``class_iri``; ``LookupError`` if none."""
    return activity_class_of(view, models, [URIRef(class_iri)])


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
        base = _standard(changes)(id=new_activity_id())
        types = v.activity_types(type(base).__name__)
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
            "ended_at_time": max(started, ended),  # a clock that went back (D-5 c)
            "was_associated_with": [principal.id],
            "generations": parts(Generation, [g for g, _ in changes if g]),
            "invalidations": parts(Invalidation, [i for _, i in changes if i]),
        }
    )
    return activity, list(types)


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
