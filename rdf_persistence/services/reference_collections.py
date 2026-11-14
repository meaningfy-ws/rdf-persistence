"""Reference collections: what a collection is, and what a caller may ask of one (PD-7, PD-8, PD-28).

The helpers say what a collection is (a root typed with a class that has ``ReferenceCollection`` among
its ancestors, its member class, its rule); the write guard and the reads share them.
``ReferenceCollections`` holds one ``Session`` and the caller it acts for: the members of a
collection, the collections that hold a resource, and the cascading delete. ``Collaboration`` hands
these three over to it.
"""

from collections.abc import Iterator, Sequence
from collections.abc import Set as AbstractSet
from contextlib import contextmanager, suppress
from functools import cached_property
from typing import cast

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.exceptions import (
    BadQuery,
    CommitTooLarge,
    Forbidden,
    InvalidIri,
    NotFound,
    StoredDataInvalid,
)
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.domain.generated.service.rp_service import (
    AggregateHead,
    CallerAccess,
    Filter,
    ListPlan,
    ListRequest,
    MemberList,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import Iris, graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import DEFAULT_MAX_ROOTS, GeneratedModels, Mapper
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


def collection_class(classes: dict[URIRef, str], iri: str, graph: Graph) -> str | None:
    """The schema name of the collection class ``iri`` is typed with in ``graph``, if any."""
    return next(
        (
            classes[t]
            for t in graph.objects(URIRef(iri), RDF.type)
            if isinstance(t, URIRef) and t in classes
        ),
        None,
    )


def member_class_iris(view: SchemaView, member_class: str) -> set[str]:
    """The IRIs of the classes whose aggregates are members of a collection of ``member_class``: it and its descendants."""
    return {view.get_uri(c, expand=True) for c in view.class_descendants(member_class)}


def outside_member_class(
    view: SchemaView, member_class: str, members: Sequence[str], heads: Sequence[AggregateHead]
) -> list[str]:
    """The ``members`` that are not stored aggregates of ``member_class`` or of a class derived from it."""
    accepted = member_class_iris(view, member_class)
    stored = {str(h.head_iri): h for h in heads}
    return [
        m
        for m in members
        if m not in stored or not accepted.intersection(stored[m].head_types or [])
    ]


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


def rule_plan(listings: Listings, collection: ReferenceCollection) -> ListPlan:
    """The listing of the aggregates that meet the collection's rule.

    Raises:
        ValueError: The member class is not an aggregate root with a path.
        BadQuery: The rule names a slot or value a listing of the class refuses.
    """
    root = listings.served_root(collection.member_class)
    return listings.plan(root, ListRequest(filters=rule_filters(collection) or None))


# The members of a collection: those it names, and those that only meet its rule.
Held = tuple[set[str], set[str]]


class ReferenceCollections:
    """What a caller may ask of the reference collections of a tenant."""

    def __init__(
        self,
        session: Session,
        *,
        view: SchemaView,
        rules: AccessRules,
        iris: Iris,
        mapper: Mapper,
        models: GeneratedModels,
        listings: Listings,
        caller: VerifiedCaller,
        access: CallerAccess,
    ) -> None:
        self._session = session
        self._view = view
        self._mapper = mapper
        self._models = models
        self._listings = listings
        self._rules = rules
        self._iris = iris
        self._caller = caller
        self._access = access

    async def members(self, collection: str, *, deep: bool = False) -> MemberList:
        """The members of the collection that the caller may read, sorted; ``hidden_count`` is the
        number of other members, each counted once and never named.

        The members are those the collection names and those that meet its rule. ``deep`` also reads
        the members that are collections the caller may read, each collection once, so a cycle ends.

        Raises:
            LookupError: The schema does not import the collection module.
            NotFound: The caller can see nothing of ``collection``, or it has no graph.
            Forbidden: The caller may see ``collection`` but not read it.
            BadQuery: ``collection`` is not a reference collection.
            StoredDataInvalid: A collection read cannot be decoded, or its member class or rule is
                no longer one the schema accepts.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_collections()
        self._require_aggregate(collection)
        self._rules.require(self._caller, self._access, collection, Action.READ)
        named, ruled = await self._gather(collection, deep)
        return self._listed(named, ruled)

    async def collections_of(self, iri: str) -> MemberList:
        """The collections that hold ``iri``, by name or by rule, that the caller may read, sorted
        in ``member_iris``; ``hidden_count`` is the number of other collections that hold it.

        Raises:
            LookupError: The schema does not import the collection module.
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            StoredDataInvalid: A stored collection cannot be decoded, or its member class or rule is
                no longer one the schema accepts; the message names the collection only if the
                caller may read it.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_collections()
        self._require_aggregate(iri)
        self._rules.require(self._caller, self._access, iri, Action.READ)
        rows = await self._session.referrer_rows(iri)
        named = {
            referrer
            for referrer, referrer_class, _, predicate in rows
            if predicate == str(v.HAD_MEMBER) and URIRef(referrer_class) in self._collection_classes
        }
        return self._listed(named | await self._rule_holders(iri))

    async def delete_cascade(self, collection: str, if_version: str) -> None:
        """Delete the collection and each of its members, in one request, all or nothing.

        The members are those the collection names and those that meet its rule and that the caller
        may read, resolved now: not deep (a member that is a collection is deleted, its own members
        stay) and not the collection itself. An aggregate that only meets the rule and that the
        caller may not read stays, unmentioned. A member that is already gone is skipped. A plain
        delete of the collection keeps its members.

        Raises:
            LookupError: The schema does not import the collection module.
            InvalidIri: ``collection`` is the tenant root or not an aggregate IRI the policy mints
                for the tenant.
            NotFound: The caller can see nothing of ``collection``, or it has no graph.
            Forbidden: The caller may not delete ``collection``, or a member; the message names the
                members it may read and counts the others, which the collection names.
            BadQuery: ``collection`` is not a reference collection.
            StoredDataInvalid: The collection cannot be decoded, or its member class is not a
                served root, or its rule is no longer one the schema accepts, or it names a stored
                aggregate that is not of its member class (the message names the collection, not
                that aggregate).
            CommitTooLarge: The collection and its members are more than ``DEFAULT_MAX_ROOTS``;
                the message gives the limit, not the number of members.
            Conflict: ``collection`` is not at ``if_version``, or a member changed, or no longer
                meets the rule, since it was read; nothing is deleted.
            DatabaseGone: The tenant database does not exist.
        """
        if collection == str(self._access.tenant):
            raise InvalidIri("the tenant root is not a collection to cascade")
        self._require_collections()
        self._require_aggregate(collection)
        self._rules.require(self._caller, self._access, collection, Action.DELETE)
        stored = await self._collection(collection)
        self._require_served(collection, stored)
        found_named, found_ruled = await self._direct(collection, stored)
        # a rule member the caller may not read is no member for it: not deleted, and no refusal that
        # would tell the rule's author that something hidden matches (PD-28)
        visible = {m for m in found_ruled - {collection} if self._may(m, Action.READ)}
        held: Held = (found_named - {collection}, visible)
        self._require_room(held)
        self._require_deletable(held)
        heads = await self._session.heads(sorted(held[0] | held[1]))
        self._require_of_member_class(collection, stored, heads)
        by_rule = held[1]
        plan = self._plan(collection, stored) if by_rule else None
        async with self._session.transaction() as transaction:
            await transaction.remove(collection, if_version)
            for head in heads:
                iri, version = str(head.head_iri), str(head.head_version)
                with suppress(NotFound):  # went since the heads were read: nothing left to delete
                    await transaction.remove(iri, version)
                    if plan is not None and iri in by_rule:
                        transaction._require_match(iri, plan.target, plan.conditions or [])

    def _require_of_member_class(
        self, collection: str, stored: ReferenceCollection, heads: list[AggregateHead]
    ) -> None:
        """A stored collection is not trusted: a cascade deletes only aggregates of its member class."""
        found = [str(h.head_iri) for h in heads]
        if outside_member_class(self._view, stored.member_class, found, heads):
            raise StoredDataInvalid(
                f"the collection {collection} names an aggregate that is not of its member class "
                f"{stored.member_class}"
            )

    def _require_room(self, held: Held) -> None:
        """Only ``UnitOfWork.commit`` enforces the limit, so a cascade counts before it reads more.

        The message gives the limit and not how many members there are: some of them may match the
        rule of a caller who may not read them.
        """
        if len(held[0] | held[1]) + 1 > DEFAULT_MAX_ROOTS:
            raise CommitTooLarge(
                f"the collection and its members are more than the {DEFAULT_MAX_ROOTS} roots one "
                "commit holds"
            )

    def _require_deletable(self, held: Held) -> None:
        """The caller may delete every member; a refusal names the refused it may read and counts the
        others, which the collection names (the rule members it may not read were left out)."""
        refused = {m for m in held[0] | held[1] if not self._may(m, Action.DELETE)}
        parts = sorted(m for m in refused if self._may(m, Action.READ))
        if hidden := len(refused) - len(parts):
            parts.append(f"{hidden} not readable")
        if parts:
            raise Forbidden(f"delete is not permitted on {', '.join(parts)}")

    def _may(self, iri: str, action: Action) -> bool:
        return self._rules.may(self._caller, self._access, iri, action)

    def _require_aggregate(self, iri: str) -> None:
        if not self._iris.is_aggregate(self._access.tenant, iri):
            raise InvalidIri(f"{iri} is not an aggregate of the tenant")

    def _require_collections(self) -> None:
        if self._view.get_class(COLLECTION_MIXIN) is None:
            raise LookupError("the schema does not import the module rp_collections")

    def _require_served(self, iri: str, collection: ReferenceCollection) -> None:
        """A stored collection is not trusted: its member class must be a class the tenant serves."""
        with self._stored_valid(iri, ValueError):  # ``served_root`` refuses a class that is not one
            self._listings.served_root(collection.member_class)

    @cached_property
    def _collection_classes(self) -> dict[URIRef, str]:
        return collection_classes(self._view)

    def _listed(self, named: set[str], ruled: AbstractSet[str] = frozenset()) -> MemberList:
        """The IRIs of ``named`` and ``ruled`` the caller may read, sorted, and the number of the
        ``named`` it may not: an aggregate that only meets a rule is dropped without being counted."""
        readable = {i for i in named | ruled if self._may(i, Action.READ)}
        return MemberList(member_iris=sorted(readable) or None, hidden_count=len(named - readable))

    async def _gather(self, root: str, deep: bool) -> Held:
        """The members of ``root``, and with ``deep`` of the collections among them, breadth first."""
        named: set[str] = set()
        ruled: set[str] = set()
        visited = {root}
        queue = [(root, await self._collection(root))]
        while queue:
            iri, collection = queue.pop(0)
            if deep:
                self._require_served(iri, collection)
            found = await self._direct(iri, collection)
            named |= found[0]
            ruled |= found[1]
            if deep and COLLECTION_MIXIN in self._view.class_ancestors(collection.member_class):
                queue += await self._nested(found[0] | found[1], visited)
        return named, ruled - named

    async def _nested(
        self, members: set[str], visited: set[str]
    ) -> list[tuple[str, ReferenceCollection]]:
        """The collections among ``members`` that the caller may read and that are not visited yet."""
        unseen = {m for m in members - visited if self._may(m, Action.READ)}
        visited |= unseen
        nested = []
        for iri in sorted(unseen):
            with suppress(NotFound, BadQuery):  # a member that is gone, or no longer a collection
                nested.append((iri, await self._collection(iri)))
        return nested

    async def _direct(self, iri: str, collection: ReferenceCollection) -> Held:
        """The members ``collection`` names, and those that only meet its rule."""
        named = set(collection.had_member or [])
        matched: set[str] = set()
        if collection.membership_rule is not None:
            equals: dict[str, list[str]] = {}
            for f in rule_filters(collection):
                equals.setdefault(f.slot, []).append(f.value)
            # the generated class of the name: LookupError; ``find``: ValueError (not a root), BadQuery
            with self._stored_valid(iri, BadQuery, ValueError, LookupError):
                member_class = self._models.named(collection.member_class)
                matched = set(await self._session.find(member_class, **equals))
        return named, matched - named

    async def _collection(self, iri: str) -> ReferenceCollection:
        graph, _, _ = await self._session.get_graph(iri)
        return self._decoded(iri, graph)

    def _decoded(self, iri: str, graph: Graph) -> ReferenceCollection:
        name = collection_class(self._collection_classes, iri, graph)
        if name is None:
            raise BadQuery(f"{iri} is not a reference collection")
        with self._stored_valid(iri, ValueError):  # the generated class refuses the triples
            return decode_collection(self._mapper, self._models, name, iri, graph)

    @contextmanager
    def _stored_valid(self, iri: str, *caught: type[Exception]) -> Iterator[None]:
        """Turns what a stored collection that the schema does not accept raises into ``StoredDataInvalid``.

        Only the ``caught`` types: each step names what it documents. The message names the
        collection, and why, only if the caller may read it.
        """
        try:
            yield
        except caught as error:
            if not self._rules.may(self._caller, self._access, iri, Action.READ):
                raise StoredDataInvalid("one collection of the tenant cannot be read") from error
            raise StoredDataInvalid(f"the collection {iri} cannot be read: {error}") from error

    async def _rule_holders(self, iri: str) -> set[str]:
        """The collections whose rule ``iri`` meets, of the class ``iri`` is (exactly, as ``find``)."""
        heads = await self._session.heads([iri])
        types = set(heads[0].head_types or []) if heads else set()
        if not types:
            return set()
        held = set()
        for root, graph in sorted((await self._session.graphs_with(v.MEMBERSHIP_RULE)).items()):
            if collection_class(self._collection_classes, root, graph) is None:
                continue  # a stray rule triple on another aggregate is no collection
            collection = self._decoded(root, graph)
            self._require_served(root, collection)  # a class the schema no longer has: no IRI
            exact = self._view.get_uri(collection.member_class, expand=True)
            if exact in types and await self._meets(root, collection, iri):
                held.add(root)
        return held

    async def _meets(self, iri: str, collection: ReferenceCollection, member: str) -> bool:
        """Whether ``member`` meets the rule of the collection ``iri``, by the conditions ``find`` uses."""
        plan = self._plan(iri, collection)
        return await self._session.matches(member, plan.target, plan.conditions or [])

    def _plan(self, iri: str, collection: ReferenceCollection) -> ListPlan:
        with self._stored_valid(iri, ValueError, BadQuery):
            return rule_plan(self._listings, collection)
