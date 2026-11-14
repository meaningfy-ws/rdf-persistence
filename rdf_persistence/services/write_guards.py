"""Write guards: what a transaction checks before it collects an add or a replace (PD-6).

``WriteGuards.prepare`` returns the triples to write or raises. The one rule so far is the
collection's: a root typed with a class that has ``ReferenceCollection`` among its ancestors names
a member class that is served, and members that exist, are minted for the tenant and are of that
class; its rule names slots and values a listing of that class accepts. Whoever may modify a
collection thus learns whether an IRI it names is a registered aggregate of the member class, and so,
by trying member classes, the class of a hidden aggregate whose IRI it holds, never its content
(RISK-8, accepted). What a collection is lives in ``reference_collections``.
"""

from rdflib import Graph

from rdf_persistence.domain.exceptions import BadQuery, InvalidBody, InvalidIri
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.reference_collections import (
    collection_class,
    collection_classes,
    decode_collection,
    outside_member_class,
    rule_plan,
)
from rdf_persistence.services.session import Session


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
            InvalidBody: The triples of a collection do not decode, or it names a member class that
                is not served, a member that is not a stored aggregate of the class, or a rule a
                listing refuses.
            InvalidIri: A member is not an aggregate IRI of the tenant.
        """
        graph = Graph()
        for triple in triples:
            graph.add(triple)
        name = collection_class(self._collections, iri, graph)
        if name is not None:
            await self._check_collection(session, self._decoded(name, iri, graph))
        return triples

    def _decoded(self, name: str, iri: str, graph: Graph) -> ReferenceCollection:
        try:
            return decode_collection(self._mapper, self._models, name, iri, graph)
        except ValueError as error:
            # the generated class refuses the triples; its text names internals
            raise InvalidBody(f"the triples of {iri} are not those of a {name}") from error

    async def _check_collection(self, session: Session, collection: ReferenceCollection) -> None:
        try:
            self._listings.served_root(collection.member_class)
        except ValueError as error:
            raise InvalidBody(str(error)) from error
        members = collection.had_member or []
        if outside := session.not_aggregates(members):
            raise InvalidIri(f"not aggregate IRIs of the tenant: {outside}")
        heads = await session.heads(members)
        wrong = outside_member_class(self._mapper.view, collection.member_class, members, heads)
        if wrong:
            raise InvalidBody(f"not stored aggregates of {collection.member_class}: {wrong}")
        try:
            rule_plan(self._listings, collection)
        except BadQuery as error:
            raise InvalidBody(str(error)) from error
