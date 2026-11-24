"""Write guards: what a transaction checks before it collects an add or a replace (PD-6).

``WriteGuards.prepare`` returns the triples to write or raises. The one rule so far is the
collection's: a root typed with a class that has ``ReferenceCollection`` among its ancestors names
a member class that is served, and members that exist, are minted for the tenant and are of that
class; its rule names slots and values a listing of that class accepts. Whoever may modify a
collection thus learns whether an IRI it names is a registered aggregate of the member class, and so,
by trying member classes, the class of a hidden aggregate whose IRI it holds, never its content
(RISK-8, accepted). What a collection is lives in ``reference_collections``.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence

from pydantic import BaseModel
from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.collaboration.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateValidators,
    DeleteValidators,
    root_types,
    run_aggregate_validators,
    run_delete_validators,
)
from rdf_persistence.collaboration.services.reference_collections import (
    COLLECTION_MIXIN,
    accepted_members,
    collection_class,
    collection_classes,
    decode_collection,
    outside_member_class,
    rule_plan,
)
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.core.domain.exceptions import BadQuery, Conflict, InvalidBody, InvalidIri
from rdf_persistence.core.domain.generated.rp_annotations import Tracked
from rdf_persistence.core.domain.sparql import Triple
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.persistence.services.generated.rp_persistence_services import AggregateHead
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.persistence.services.session import GuardContext, Session, changed_text
from rdf_persistence.schema.services import vocabulary as v


def _walk_from(
    root: str, new: Iterable[str], skeleton: Mapping[str, Collection[str]]
) -> tuple[frozenset[str], tuple[str, int] | None]:
    """Follow ``skeleton`` (``{collection: members}``) from each of the ``new`` members of ``root``.

    Depth first, iterative, so the depth of a tree costs nothing. A node not in ``skeleton`` is
    reached and not entered. Returns ``(reached, cycle)``: ``reached`` is every node the walk
    reached (never ``root``); ``cycle`` is ``None``, or ``(closing, between)`` when ``root`` was
    reached: the new member it was reached from and the number of other collections on the way.
    """
    reached: set[str] = set()
    for start in new:
        stack = [(start, start, 0)]  # (node, the new member it was reached from, depth)
        while stack:
            node, origin, depth = stack.pop()
            if node == root:
                return frozenset(reached), (origin, max(depth - 1, 0))
            if node in reached:
                continue
            reached.add(node)
            stack.extend((member, origin, depth + 1) for member in skeleton.get(node, ()))
    return frozenset(reached), None


class WriteGuards:
    """The checks of the writes of one schema, built once and shared by every session."""

    def __init__(  # noqa: PLR0913 - the schema's parts and the two registries of rules
        self,
        mapper: Mapper,
        models: GeneratedModels,
        listings: Listings,
        workflows: Workflows | None = None,
        *,
        validators: AggregateValidators | None = None,
        delete_validators: DeleteValidators | None = None,
    ) -> None:
        self._validators = validators
        self._delete_validators = delete_validators
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
        graph = self._graph_of(triples)
        name = collection_class(self._collections, iri, graph)
        if name is not None:
            decoded = self._decoded(name, iri, graph)
            await self._check_collection(
                session, iri, name, decoded, context, adding=stored is None
            )
        if self._workflows is not None:
            triples = await self._workflows.keep_state(session, iri, triples, stored, allowed_state)
        await self._run_aggregate_validators(session, iri, triples, stored, context)
        return triples

    async def prepare_remove(
        self, session: Session, iri: str, if_version: str, *, context: GuardContext
    ) -> None:
        """Run the consumer's delete rules on the root ``iri`` before its removal is collected (D-5).

        Nothing is read when no delete rule is registered (G-4, E15).

        Raises:
            Conflict: ``if_version`` is not the stored version: it wins over a refusal, as for a
                replace (E17).
            Refused: (a ``Conflict``) A rule refuses.
            RuntimeError: A rule is buggy, or the stored root does not decode or has types on two
                lines that a rule applies to.
            TypeError: A rule returns a value.
        """
        deletes = self._delete_validators
        if deletes is None or not deletes.has_rules:
            return
        graph, tracked_in, stored_version = await session.get_graph(iri)
        try:
            selected = deletes.select(iri, (str(t) for t in graph.objects(URIRef(iri), RDF.type)))
        except (
            InvalidBody
        ) as error:  # stored data the client cannot fix, and a delete has no body (D-13)
            raise RuntimeError(f"the stored {iri} is invalid: {error}") from error
        if selected is None:
            return
        name, rules = selected
        try:
            old = self._mapper.from_graph(self._models.named(name), iri, graph, tracked_in)
        except ValueError as error:
            raise RuntimeError(f"the stored {iri} does not decode: {error}") from error
        reader = deletes.reader(session, context, self._decode)
        try:
            await run_delete_validators(rules, old, session.principal, reader)
        except Conflict as refusal:
            if (
                stored_version != if_version
            ):  # the client read an older state: not the rule's refusal
                raise Conflict(changed_text(iri, stored_version), iris=(iri,)) from refusal
            raise

    async def _run_aggregate_validators(
        self,
        session: Session,
        iri: str,
        triples: list[Triple],
        stored: Tracked | None,
        context: GuardContext,
    ) -> None:
        """Run the consumer's rules on the root as it is about to be written (aggregate-validators PD-6).

        Nothing is decoded or read when no rule applies (G-4).
        """
        validators = self._validators
        if validators is None or not validators.has_rules:
            return
        selected = validators.select(iri, root_types(iri, triples))
        if selected is None:
            return
        name, rules = selected
        new = self._decoded_new(name, iri, triples)
        old = None if stored is None else await self._decoded_stored(session, iri, validators)
        reader = validators.reader(session, context, self._decode)
        await run_aggregate_validators(rules, old, new, session.principal, reader)

    def _decode(self, name: str, iri: str, graph: Graph, tracked_in: URIRef | None) -> BaseModel:
        """The root ``iri`` of class ``name`` as its model, for the reader a rule gets."""
        return self._mapper.from_graph(self._models.named(name), iri, graph, tracked_in)

    def _decoded_new(self, name: str, iri: str, triples: list[Triple]) -> BaseModel:
        """The root as written: no tracking slots, the session adds them after the guard."""
        try:
            return self._mapper.from_graph(
                self._models.named(name), iri, self._graph_of(triples), None
            )
        except ValueError as error:
            raise InvalidBody(f"the triples of {iri} are not those of a {name}") from error

    async def _decoded_stored(
        self, session: Session, iri: str, validators: AggregateValidators
    ) -> BaseModel:
        """The root as stored, tracking included; a 500 if it does not decode, the client cannot fix it."""
        graph, tracked_in, _ = await session.get_graph(iri)
        name = validators.model_class(str(t) for t in graph.objects(URIRef(iri), RDF.type))
        try:
            if name is None:
                raise ValueError("it has no single root class")
            return self._mapper.from_graph(self._models.named(name), iri, graph, tracked_in)
        except ValueError as error:
            raise RuntimeError(f"the stored {iri} does not decode: {error}") from error

    def _decoded(self, name: str, iri: str, graph: Graph) -> ReferenceCollection:
        try:
            return decode_collection(self._mapper, self._models, name, iri, graph)
        except ValueError as error:
            # the generated class refuses the triples; its text names internals
            raise InvalidBody(f"the triples of {iri} are not those of a {name}") from error

    async def _check_collection(  # noqa: PLR0913 - the root, its class, its decoding and what the transaction holds
        self,
        session: Session,
        iri: str,
        name: str,
        collection: ReferenceCollection,
        context: GuardContext,
        *,
        adding: bool,
    ) -> None:
        if not adding:
            await self._check_held_member_class(session, iri, name, collection, context)
        # the nested members already stored stay valid (the check above); only new ones are checked
        stored = (
            await self._stored_members(session, iri, collection.member_class)
            if collection.nests and not adding
            else set()
        )
        heads = await self._check_members(session, name, collection, stored, context)
        try:
            rule_plan(self._listings, collection)
        except BadQuery as error:
            raise InvalidBody(str(error)) from error
        if collection.nests:
            await self._check_no_cycle(session, iri, name, collection, heads, context, stored)

    async def _check_held_member_class(
        self,
        session: Session,
        iri: str,
        name: str,
        collection: ReferenceCollection,
        context: GuardContext,
    ) -> None:
        """Refuse another member class for a collection that a nesting one of its class holds (C-1).

        The holder's member class is the stored one of ``iri``: a nested member is checked against it
        when the holder is saved, so it must not drift after. The holders are the stored ones, the
        collected ones of the transaction overlaying them (as in ``_skeleton``). The text names no
        holder: it may be hidden.
        """
        for other in await self._holders(session, iri, name, context):
            if other.member_class != collection.member_class:
                raise InvalidBody(
                    f"the member class of {iri} cannot change while a nesting collection holds it"
                )

    async def _holders(
        self, session: Session, iri: str, name: str, context: GuardContext
    ) -> list[ReferenceCollection]:
        """The nesting collections of class ``name`` that name ``iri``, as the transaction leaves them."""
        graphs = dict(await session.graphs_with(v.HAS_PART, URIRef(iri)))
        for holder, triples in context.collected.items():
            graphs[holder] = self._graph_of(triples)  # the collected state replaces the stored one
        decoded = (self._decoded_if_nesting(name, h, g) for h, g in graphs.items())
        return [d for d in decoded if d is not None and iri in {str(m) for m in d.has_part or []}]

    @staticmethod
    def _graph_of(triples: Iterable[Triple]) -> Graph:
        graph = Graph()
        for triple in triples:
            graph.add(triple)
        return graph

    def _decoded_of_class(self, name: str, iri: str, graph: Graph) -> ReferenceCollection | None:
        """``iri`` decoded when it is a collection of class ``name``: else none.

        A graph that does not decode is none: it is another collection's corruption, which neither
        blocks this save nor is named by it.
        """
        if collection_class(self._collections, iri, graph) != name:
            return None
        try:
            return decode_collection(self._mapper, self._models, name, iri, graph)
        except ValueError:
            return None

    def _decoded_if_nesting(self, name: str, iri: str, graph: Graph) -> ReferenceCollection | None:
        """``iri`` decoded when it is a collection of class ``name`` that nests: else none."""
        other = self._decoded_of_class(name, iri, graph)
        return other if other is not None and other.nests else None

    async def _check_members(
        self,
        session: Session,
        name: str,
        collection: ReferenceCollection,
        stored: set[str],
        context: GuardContext,
    ) -> Sequence[AggregateHead]:
        """The heads of the members, once the member class and the members are checked.

        ``stored`` are the nested members the stored collection already holds: not checked again.
        """
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
            wrong = await self._unlike_nested(session, name, collection, heads, stored, context)
        if wrong:
            raise InvalidBody(f"not stored aggregates of {collection.member_class}: {wrong}")
        return heads

    async def _check_no_cycle(  # noqa: PLR0913 - what the walk reads and what it relies on
        self,
        session: Session,
        iri: str,
        name: str,
        collection: ReferenceCollection,
        heads: Sequence[AggregateHead],
        context: GuardContext,
        stored: set[str],
    ) -> None:
        """Refuse a nested member that leads back to the collection, and rely on what was walked (PD-4)."""
        own = self._mapper.view.get_uri(name, expand=True)
        nested = {str(h.head_iri) for h in self._exact_heads(own, heads)}
        if not (new := sorted(nested - stored)):
            return  # nothing nested is added: no walk, no guard
        skeleton = await self._skeleton(session, name, collection, context)
        walked, cycle = _walk_from(
            iri, new, {each: members for each, (_, members) in skeleton.items()}
        )
        if cycle is not None:
            closing, between = cycle
            raise InvalidBody(
                f"saving {iri} would make a cycle: {iri} → {closing} → ({between} more) → {iri}"
            )
        reached = sorted(walked - set(context.collected))  # a collected one has its own guard
        await self._rely_on_walked(session, own, reached, skeleton, context)

    @staticmethod
    async def _rely_on_walked(
        session: Session,
        own: str,
        reached: list[str],
        skeleton: dict[str, tuple[str | None, list[str]]],
        context: GuardContext,
    ) -> None:
        """Guard the versions of the collections a walk reached, and of the leaves that may become one."""
        for each in (i for i in reached if i in skeleton):
            context.rely_on(each, str(skeleton[each][0]))
        leaves = [i for i in reached if i not in skeleton]
        # a leaf (nests false) may be turned into a nesting collection meanwhile: guard it too
        for head in WriteGuards._exact_heads(own, await session.heads(leaves)):
            context.rely_on(str(head.head_iri), str(head.head_version))

    @staticmethod
    def _exact_heads(own: str, heads: Iterable[AggregateHead]) -> list[AggregateHead]:
        """The ``heads`` stored with exactly the class whose IRI is ``own``."""
        return [h for h in heads if own in (h.head_types or [])]

    @staticmethod
    async def _stored_members(session: Session, iri: str, member_class: str) -> set[str]:
        """The members the stored collection already holds as nested ones: none if it does not nest.

        A stored leaf (nests false) holds no nested member, whatever it names, so every nested member
        of a leaf turned nesting is new and walked. So is each one when the member class changes: the
        stored ones were checked against the old class.
        """
        values = await session.root_values(iri, [v.HAS_PART, v.NESTS, v.MEMBER_CLASS])
        nests = Literal(True) in {Literal(n) for n in values[v.NESTS]}
        if not nests or {str(c) for c in values[v.MEMBER_CLASS]} != {member_class}:
            return set()
        return {str(m) for m in values[v.HAS_PART]}

    async def _skeleton(
        self, session: Session, name: str, collection: ReferenceCollection, context: GuardContext
    ) -> dict[str, tuple[str | None, list[str]]]:
        """``{collection: (version, members)}`` of the tenant's nesting collections like ``collection``.

        The collections the transaction collected before overlay the stored ones; they have no version.
        """
        skeleton: dict[str, tuple[str | None, list[str]]] = {}
        for iri, graph in (await session.graphs_with(v.NESTS, Literal(True))).items():
            members = self._members_if_alike(name, collection, iri, graph)
            if members is not None:
                skeleton[iri] = (str(graph.value(graph_iri(iri), v.VERSION)), members)
        for iri, triples in context.collected.items():
            members = self._members_if_alike(name, collection, iri, self._graph_of(triples))
            if members is None:
                skeleton.pop(iri, None)
            else:
                skeleton[iri] = (None, members)
        return skeleton

    def _members_if_alike(
        self, name: str, collection: ReferenceCollection, iri: str, graph: Graph
    ) -> list[str] | None:
        """The members of ``iri`` when it nests and is of ``collection``'s class and member class.

        A graph that does not decode is none (see ``_decoded_of_class``).
        """
        other = self._decoded_if_nesting(name, iri, graph)
        if other is None or other.member_class != collection.member_class:
            return None
        return [str(m) for m in other.has_part or []]

    async def _unlike_nested(  # noqa: PLR0913 - the root's class, its decoding, its heads, what is stored and collected
        self,
        session: Session,
        name: str,
        collection: ReferenceCollection,
        heads: Sequence[AggregateHead],
        stored: set[str],
        context: GuardContext,
    ) -> list[str]:
        """The new nested members (stored with exactly the collection's class) whose member class differs.

        A member the stored collection already nests, with the same member class, is not read: its
        member class cannot have changed while it is held (``_check_held_member_class``). A member
        the transaction collected is read as collected, not as stored.
        """
        own = self._mapper.view.get_uri(name, expand=True)
        wrong = []
        for head in self._exact_heads(own, heads):
            iri = str(head.head_iri)
            if iri in stored:
                continue
            graph = await self._collected_or_stored(session, iri, context)
            if self._decoded(name, iri, graph).member_class != collection.member_class:
                wrong.append(iri)
        return wrong

    async def _collected_or_stored(
        self, session: Session, iri: str, context: GuardContext
    ) -> Graph:
        """The graph of ``iri`` as the transaction collected it, else as stored."""
        if iri in context.collected:
            return self._graph_of(context.collected[iri])
        graph, _, _ = await session.get_graph(iri)
        return graph
