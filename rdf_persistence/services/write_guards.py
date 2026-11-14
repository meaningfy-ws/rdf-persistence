"""Write guards: what a transaction checks before it collects an add or a replace (PD-6).

``WriteGuards.prepare`` returns the triples to write or raises. The one rule so far is the
collection's: a root typed with a class that has ``ReferenceCollection`` among its ancestors names
a member class that is served, and members that exist, are minted for the tenant and are of that
class; its rule names slots and values a listing of that class accepts. Whoever may modify a
collection thus learns whether an IRI it names is a registered aggregate of the member class, even
one hidden from it (RISK-8, accepted).
"""

from typing import cast

from linkml_runtime.linkml_model.meta import ClassDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.exceptions import BadQuery, InvalidBody, InvalidIri
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.domain.generated.service.rp_service import Filter, ListRequest
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.session import Session

COLLECTION_MIXIN = "ReferenceCollection"


def collection_classes(view: SchemaView) -> dict[URIRef, str]:
    """The schema name of each class with ``ReferenceCollection`` among its ancestors, by class IRI.

    Empty for a schema that does not import the collection module.
    """
    return {
        URIRef(view.get_uri(name, expand=True)): name
        for name in view.all_classes()
        if COLLECTION_MIXIN in view.class_ancestors(name)
    }


def decode_collection(
    mapper: Mapper, models: GeneratedModels, name: str, iri: str, graph: Graph
) -> ReferenceCollection:
    """The collection of class ``name`` stored at ``iri`` in ``graph``, whose tracking is about ``graph_iri(iri)``."""
    model = models.named(name)
    return cast(ReferenceCollection, mapper.from_graph(model, iri, graph, graph_iri(iri)))


def rule_filters(collection: ReferenceCollection) -> list[Filter]:
    """The listing filters of the collection's rule: one per equality, none for no rule."""
    rule = collection.membership_rule
    return [
        Filter(slot=e.equals_slot, value=e.equals_value)
        for e in (rule.rule_equalities or [] if rule else [])
    ]


class WriteGuards:
    """The checks of the writes of one schema, built once and shared by every session."""

    def __init__(self, mapper: Mapper, models: GeneratedModels, listings: Listings) -> None:
        self._mapper = mapper
        self._models = models
        self._listings = listings
        self._collections = collection_classes(mapper.view)

    async def prepare(
        self, session: Session, iri: str, triples: list[Triple], stored: Tracked | None
    ) -> list[Triple]:
        """The triples to write for the root ``iri`` (``stored`` is ``None`` for an add).

        Raises:
            InvalidBody: A collection names a member class that is not served, a member that is not
                a stored aggregate of the class, or a rule a listing refuses.
            InvalidIri: A member is not an aggregate IRI of the tenant.
        """
        name = self._collection_class(iri, triples)
        if name is not None:
            await self._check_collection(session, self._decoded(name, iri, triples))
        return triples

    def _collection_class(self, iri: str, triples: list[Triple]) -> str | None:
        root = URIRef(iri)
        return next(
            (
                self._collections[o]
                for s, p, o in triples
                if s == root and p == RDF.type and isinstance(o, URIRef) and o in self._collections
            ),
            None,
        )

    def _decoded(self, name: str, iri: str, triples: list[Triple]) -> ReferenceCollection:
        graph = Graph()
        for triple in triples:
            graph.add(triple)
        return decode_collection(self._mapper, self._models, name, iri, graph)

    async def _check_collection(self, session: Session, collection: ReferenceCollection) -> None:
        member_class = self._served(collection.member_class)
        members = collection.had_member or []
        if outside := session.not_aggregates(members):
            raise InvalidIri(f"not aggregate IRIs of the tenant: {outside}")
        await self._check_members(session, collection.member_class, members)
        self._check_rule(collection, member_class)

    def _served(self, member_class: str) -> ClassDefinition:
        try:
            return self._listings.served_root(member_class)
        except ValueError as error:
            raise InvalidBody(str(error)) from error

    async def _check_members(self, session: Session, member_class: str, members: list[str]) -> None:
        view = self._mapper.view
        accepted = {view.get_uri(c, expand=True) for c in view.class_descendants(member_class)}
        heads = {h.head_iri: h for h in await session.heads(members)}
        wrong = [
            m
            for m in members
            if m not in heads or not accepted.intersection(heads[m].head_types or [])
        ]
        if wrong:
            raise InvalidBody(f"not stored aggregates of {member_class}: {wrong}")

    def _check_rule(self, collection: ReferenceCollection, member_class: ClassDefinition) -> None:
        filters = rule_filters(collection)
        try:
            self._listings.plan(member_class, ListRequest(filters=filters or None))
        except BadQuery as error:
            raise InvalidBody(str(error)) from error
