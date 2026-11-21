"""Write guards: what a transaction checks before it collects an add or a replace (PD-6).

``WriteGuards.prepare`` returns the triples to write or raises. The one rule so far is the
collection's: a root typed with a class that has ``ReferenceCollection`` among its ancestors names
a member class that is served, and members that exist, are minted for the tenant and are of that
class; its rule names slots and values a listing of that class accepts. Whoever may modify a
collection thus learns whether an IRI it names is a registered aggregate of the member class, and so,
by trying member classes, the class of a hidden aggregate whose IRI it holds, never its content
(RISK-8, accepted). What a collection is lives in ``reference_collections``.
"""

from collections.abc import Sequence

from rdflib import Graph, Literal

from rdf_persistence.collaboration.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.collaboration.services.reference_collections import (
    COLLECTION_MIXIN,
    accepted_members,
    collection_class,
    collection_classes,
    decode_collection,
    outside_member_class,
    rule_plan,
)
from rdf_persistence.collaboration.services.nesting import walk_from
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.core.domain.exceptions import BadQuery, InvalidBody, InvalidIri
from rdf_persistence.core.domain.generated.rp_annotations import Tracked
from rdf_persistence.core.domain.sparql import Triple
from rdf_persistence.persistence.services.generated.rp_persistence_services import AggregateHead
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.persistence.services.session import GuardContext, Session
from rdf_persistence.schema.services import vocabulary as v


class WriteGuards:
    """The checks of the writes of one schema, built once and shared by every session."""

    def __init__(
        self,
        mapper: Mapper,
        models: GeneratedModels,
        listings: Listings,
        workflows: Workflows | None = None,
    ) -> None:
        self._mapper = mapper
        self._models = models
        self._listings = listings
        self._collections = collection_classes(mapper.view)
        self._workflows = workflows

    async def prepare(  # noqa: PLR0913 - the WriteGuard port's signature (nested-collections PD-5)
        self,
        session: Session,
        iri: str,
        triples: list[Triple],
        stored: Tracked | None,
        allowed_state: str | None,
        *,
        context: GuardContext,
    ) -> list[Triple]:
        """The triples to write for the root ``iri`` (``stored`` is ``None`` for an add).

        ``allowed_state`` is the state the transaction allows the root to take; only the workflow
        rule uses it.

        Raises:
            InvalidBody: The triples of a collection do not decode, or it names a member class that
                is not served, a member that is not a stored aggregate of the class, or a rule a
                listing refuses.
            InvalidIri: A member is not an aggregate IRI of the tenant.
            Forbidden: The triples of an aggregate under a workflow change its state.
        """
        graph = Graph()
        for triple in triples:
            graph.add(triple)
        name = collection_class(self._collections, iri, graph)
        if name is not None:
            decoded = self._decoded(name, iri, graph)
            await self._check_collection(session, name, decoded, context, adding=stored is None)
        if self._workflows is None:
            return triples
        return await self._workflows.keep_state(session, iri, triples, stored, allowed_state)

    def _decoded(self, name: str, iri: str, graph: Graph) -> ReferenceCollection:
        try:
            return decode_collection(self._mapper, self._models, name, iri, graph)
        except ValueError as error:
            # the generated class refuses the triples; its text names internals
            raise InvalidBody(f"the triples of {iri} are not those of a {name}") from error

    async def _check_collection(
        self,
        session: Session,
        name: str,
        collection: ReferenceCollection,
        context: GuardContext,
        *,
        adding: bool,
    ) -> None:
        view = self._mapper.view
        try:
            self._listings.served_root(collection.member_class)
        except ValueError as error:
            raise InvalidBody(str(error)) from error
        if collection.nests and COLLECTION_MIXIN in view.class_ancestors(collection.member_class):
            raise InvalidBody("nests needs a member class that is not a collection")
        members = collection.has_part or []
        if outside := session.not_aggregates(members):
            raise InvalidIri(f"not aggregate IRIs of the tenant: {outside}")
        heads = await session.heads(members)
        wrong = outside_member_class(accepted_members(view, name, collection), members, heads)
        if not wrong and collection.nests:
            wrong = await self._unlike_nested(session, name, collection, heads)
        if wrong:
            raise InvalidBody(f"not stored aggregates of {collection.member_class}: {wrong}")
        try:
            rule_plan(self._listings, collection)
        except BadQuery as error:
            raise InvalidBody(str(error)) from error
        if collection.nests:
            await self._check_no_cycle(session, name, collection, heads, context, adding=adding)

    async def _check_no_cycle(  # noqa: PLR0913 - what the walk reads and what it relies on
        self,
        session: Session,
        name: str,
        collection: ReferenceCollection,
        heads: Sequence[AggregateHead],
        context: GuardContext,
        *,
        adding: bool,
    ) -> None:
        """Refuse a nested member that leads back to the collection, and rely on what was walked (PD-4)."""
        iri = str(collection.id)
        own = self._mapper.view.get_uri(name, expand=True)
        nested = {str(h.head_iri) for h in heads if own in (h.head_types or [])}
        stored = set() if adding else await self._stored_members(session, iri)
        if not (new := sorted(nested - stored)):
            return  # nothing nested is added: no walk, no guard
        skeleton = await self._skeleton(session, name, collection, context)
        walk = walk_from(iri, new, {each: members for each, (_, members) in skeleton.items()})
        if walk.cycle is not None:
            raise InvalidBody(
                f"saving {iri} would make a cycle: {iri} → {walk.cycle.closing}"
                f" → ({walk.cycle.between} more) → {iri}"
            )
        reached = sorted(walk.reached - set(context.collected))  # a collected one has its own guard
        for each in (i for i in reached if i in skeleton):
            context.rely_on(each, str(skeleton[each][0]))
        # a leaf (nests false) may be turned into a nesting collection meanwhile: guard it too
        for head in await session.heads([i for i in reached if i not in skeleton]):
            if own in (head.head_types or []):
                context.rely_on(str(head.head_iri), str(head.head_version))

    @staticmethod
    async def _stored_members(session: Session, iri: str) -> set[str]:
        return {str(m) for m in (await session.root_values(iri, [v.HAS_PART]))[v.HAS_PART]}

    async def _skeleton(
        self, session: Session, name: str, collection: ReferenceCollection, context: GuardContext
    ) -> dict[str, tuple[str | None, list[str]]]:
        """``{collection: (version, members)}`` of the tenant's nesting collections like ``collection``.

        The collections the transaction collected before overlay the stored ones; they have no version.
        """
        skeleton: dict[str, tuple[str | None, list[str]]] = {}
        for iri, graph in (await session.graphs_with(v.NESTS, Literal(True))).items():
            if (members := self._members_if_alike(name, collection, iri, graph)) is not None:
                skeleton[iri] = (str(graph.value(graph_iri(iri), v.VERSION)), members)
        for iri, triples in context.collected.items():
            graph = Graph()
            for triple in triples:
                graph.add(triple)
            members = self._members_if_alike(name, collection, iri, graph)
            if members is None:
                skeleton.pop(iri, None)
            else:
                skeleton[iri] = (None, members)
        return skeleton

    def _members_if_alike(
        self, name: str, collection: ReferenceCollection, iri: str, graph: Graph
    ) -> list[str] | None:
        """The members of ``iri`` when it nests and is of ``collection``'s class and member class."""
        if collection_class(self._collections, iri, graph) != name:
            return None
        other = self._decoded(name, iri, graph)
        if not other.nests or other.member_class != collection.member_class:
            return None
        return [str(m) for m in other.has_part or []]

    async def _unlike_nested(
        self,
        session: Session,
        name: str,
        collection: ReferenceCollection,
        heads: Sequence[AggregateHead],
    ) -> list[str]:
        """The nested members (stored with exactly the collection's class) whose member class differs."""
        own = self._mapper.view.get_uri(name, expand=True)
        wrong = []
        for head in heads:
            if own not in (head.head_types or []):
                continue
            iri = str(head.head_iri)
            graph, _, _ = await session.get_graph(iri)
            if self._decoded(name, iri, graph).member_class != collection.member_class:
                wrong.append(iri)
        return wrong
