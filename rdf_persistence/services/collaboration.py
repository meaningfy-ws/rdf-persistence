"""The access-aware reads and writes over a session: who refers to a resource (PD-1, PD-3).

A ``Collaboration`` holds one ``Session`` and the caller it acts for. The session knows no schema and
checks no access; the schema's names and the access filter live here, so the generic API and the
unit of work, which bypass this class, are unaffected.
"""

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from functools import cached_property

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.exceptions import BadQuery, InvalidIri, NotFound, StoredDataInvalid
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_collections import ReferenceCollection
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    ListPlan,
    ListRequest,
    MemberList,
    Referrer,
    ReferrerList,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.session import ReferrerRow, Session
from rdf_persistence.services.write_guards import (
    COLLECTION_MIXIN,
    collection_classes,
    decode_collection,
    rule_filters,
)


class Collaboration:
    """What a caller may ask of a tenant beyond one aggregate at a time."""

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

    async def referrers(
        self, iri: str, *, class_name: str | None = None, slot: str | None = None
    ) -> ReferrerList:
        """The aggregates of the tenant that refer to ``iri`` and that the caller may read, one item per
        referrer and slot, sorted by IRI and slot; ``hidden_count`` is the number of other referring
        aggregates, each counted once and never named.

        ``class_name`` and ``slot`` keep only the listed referrers of that schema class and the links
        by that slot. The hidden count ignores them: it counts every referrer the caller may not
        read, so narrowing cannot show the class or slot of one. The links of a comment or a
        transition record to what they were made on do not count.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            BadQuery: ``class_name`` or ``slot`` is not a name of the schema.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_readable(iri)
        self._require_names(class_name, slot)
        named = self._named(await self._session.referrer_rows(iri))
        return self._readable(named, class_name, slot)

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
        self._rules.require(self._caller, self._access, collection, Action.READ)
        return self._listed(await self._gather(collection, deep))

    async def collections_of(self, iri: str) -> MemberList:
        """The collections that hold ``iri``, by name or by rule, that the caller may read, sorted
        in ``member_iris``; ``hidden_count`` is the number of other collections that hold it.

        Raises:
            LookupError: The schema does not import the collection module.
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            StoredDataInvalid: A stored collection cannot be decoded, or its member class or rule is
                no longer one the schema accepts.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_collections()
        self._require_readable(iri)
        rows = await self._session.referrer_rows(iri)
        named = {referrer for referrer, _, _, predicate in rows if predicate == str(v.HAD_MEMBER)}
        return self._listed(named | await self._rule_holders(iri))

    def _require_readable(self, iri: str) -> None:
        if not self._iris.is_aggregate(self._access.tenant, iri):
            raise InvalidIri(f"{iri} is not an aggregate of the tenant")
        self._rules.require(self._caller, self._access, iri, Action.READ)

    def _require_collections(self) -> None:
        if self._view.get_class(COLLECTION_MIXIN) is None:
            raise LookupError("the schema does not import the module rp_collections")

    @cached_property
    def _collection_classes(self) -> dict[URIRef, str]:
        return collection_classes(self._view)

    def _listed(self, found: set[str]) -> MemberList:
        """The IRIs of ``found`` the caller may read, sorted, and the number of the others."""
        readable = {i for i in found if self._rules.may(self._caller, self._access, i, Action.READ)}
        return MemberList(member_iris=sorted(readable) or None, hidden_count=len(found - readable))

    async def _gather(self, root: str, deep: bool) -> set[str]:
        """The members of ``root``, and with ``deep`` of the collections among them, breadth first."""
        found: set[str] = set()
        visited = {root}
        queue = [await self._collection(root)]
        while queue:
            collection = queue.pop(0)
            direct = await self._direct(root, collection)
            found |= direct
            if deep and COLLECTION_MIXIN in self._view.class_ancestors(collection.member_class):
                queue += await self._nested(direct, visited)
        return found

    async def _nested(self, members: set[str], visited: set[str]) -> list[ReferenceCollection]:
        """The collections among ``members`` that the caller may read and that are not visited yet."""
        unseen = {
            m
            for m in members - visited
            if self._rules.may(self._caller, self._access, m, Action.READ)
        }
        visited |= unseen
        nested = []
        for iri in sorted(unseen):
            with suppress(NotFound):  # a member that is gone has no members
                nested.append(await self._collection(iri))
        return nested

    async def _direct(self, iri: str, collection: ReferenceCollection) -> set[str]:
        """The members ``collection`` names and those that meet its rule."""
        found = set(collection.had_member or [])
        if collection.membership_rule is not None:
            equals: dict[str, list[str]] = {}
            for f in rule_filters(collection):
                equals.setdefault(f.slot, []).append(f.value)
            with self._stored_valid(iri):
                member_class = self._models.named(collection.member_class)
                found.update(await self._session.find(member_class, **equals))
        return found

    async def _collection(self, iri: str) -> ReferenceCollection:
        graph, _, _ = await self._session.get_graph(iri)
        return self._decoded(iri, graph)

    def _decoded(self, iri: str, graph: Graph) -> ReferenceCollection:
        name = next(
            (
                self._collection_classes[t]
                for t in graph.objects(URIRef(iri), RDF.type)
                if isinstance(t, URIRef) and t in self._collection_classes
            ),
            None,
        )
        if name is None:
            raise BadQuery(f"{iri} is not a reference collection")
        with self._stored_valid(iri):
            return decode_collection(self._mapper, self._models, name, iri, graph)

    @contextmanager
    def _stored_valid(self, iri: str) -> Iterator[None]:
        """Turns what a stored collection that the schema does not accept raises into ``StoredDataInvalid``."""
        try:
            yield
        except (BadQuery, ValueError, LookupError) as error:  # a decode error is a ValueError
            raise StoredDataInvalid(f"the collection {iri} cannot be read: {error}") from error

    async def _rule_holders(self, iri: str) -> set[str]:
        """The collections whose rule ``iri`` meets, of the class ``iri`` is (exactly, as ``find``)."""
        classes = self._classes_by_iri()
        heads = await self._session.heads([iri])
        types = (
            {classes[t] for t in (heads[0].head_types or []) if t in classes} if heads else set()
        )
        if not types:
            return set()
        graph = await self._session.rule_collections()
        held = set()
        for root in sorted({str(r) for r in graph.subjects(v.MEMBERSHIP_RULE, None)}):
            collection = self._decoded(root, graph)
            if collection.member_class in types and await self._meets(root, collection, iri):
                held.add(root)
        return held

    async def _meets(self, iri: str, collection: ReferenceCollection, member: str) -> bool:
        """Whether ``member`` meets the rule of the collection ``iri``, by the conditions ``find`` uses."""
        with self._stored_valid(iri):
            plan = self._plan(collection)
        return await self._session.matches(member, plan.target, plan.conditions or [])

    def _plan(self, collection: ReferenceCollection) -> ListPlan:
        root = self._listings.served_root(collection.member_class)
        return self._listings.plan(root, ListRequest(filters=rule_filters(collection) or None))

    def _require_names(self, class_name: str | None, slot: str | None) -> None:
        if class_name is not None and self._view.get_class(class_name) is None:
            raise BadQuery(f"the schema has no class {class_name!r}")
        if slot is not None and self._view.get_slot(slot) is None:
            raise BadQuery(f"the schema has no slot {slot!r}")

    def _classes_by_iri(self) -> dict[str, str]:
        return {
            self._view.get_uri(c, expand=True): name for name, c in self._view.all_classes().items()
        }

    def _named(self, rows: list[ReferrerRow]) -> set[tuple[str, str, str]]:
        """``(referrer, class name, slot name)`` of each row; an IRI the schema does not know stays as it is.

        A referrer with a type the schema knows is not also listed under the types it does not.
        """
        classes = self._classes_by_iri()
        typed = {referrer for referrer, cls, _, _ in rows if cls in classes}
        return {
            (
                referrer,
                classes.get(cls, cls),
                self._slot_name(classes.get(subject or cls), predicate),
            )
            for referrer, cls, subject, predicate in rows
            if cls in classes or referrer not in typed
        }

    def _slot_name(self, class_name: str | None, predicate: str) -> str:
        """The slot of ``class_name`` whose ``slot_uri`` is ``predicate``, or ``predicate`` itself."""
        slots = self._view.class_induced_slots(class_name) if class_name else []
        return next(
            (s.name for s in slots if self._view.get_uri(s, expand=True) == predicate), predicate
        )

    def _readable(
        self, named: set[tuple[str, str, str]], class_name: str | None, slot: str | None
    ) -> ReferrerList:
        """The items the caller may read, narrowed and sorted, and the number of other referrers (PD-26)."""
        referrers = {referrer for referrer, _, _ in named}
        readable = {
            r for r in referrers if self._rules.may(self._caller, self._access, r, Action.READ)
        }
        items = [
            Referrer(referrer=r, referrer_class=c, referrer_slot=s)
            for r, c, s in sorted(named)
            if r in readable and class_name in (None, c) and slot in (None, s)
        ]
        return ReferrerList(referrers=items or None, hidden_count=len(referrers - readable))
