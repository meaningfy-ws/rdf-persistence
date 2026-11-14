"""The access-aware reads and writes over a session: who refers to a resource (PD-1, PD-3).

A ``Collaboration`` holds one ``Session`` and the caller it acts for. The session knows no schema and
checks no access; the schema's names and the access filter live here, so the generic API and the
unit of work, which bypass this class, are unaffected. The reads and the cascade of reference
collections are ``ReferenceCollections``'s; this class hands them over, so the public face is one.
"""

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.exceptions import BadQuery, InvalidIri
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    MemberList,
    Referrer,
    ReferrerList,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.reference_collections import ReferenceCollections
from rdf_persistence.services.session import ReferrerRow, Session


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
        self._rules = rules
        self._iris = iris
        self._caller = caller
        self._access = access
        self._collections = ReferenceCollections(
            session,
            view=view,
            rules=rules,
            iris=iris,
            mapper=mapper,
            models=models,
            listings=listings,
            caller=caller,
            access=access,
        )

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
        The ``Raises`` are those of ``ReferenceCollections.members``.
        """
        return await self._collections.members(collection, deep=deep)

    async def collections_of(self, iri: str) -> MemberList:
        """The collections that hold ``iri``, by name or by rule, that the caller may read, sorted
        in ``member_iris``; ``hidden_count`` is the number of other collections that hold it.

        The ``Raises`` are those of ``ReferenceCollections.collections_of``.
        """
        return await self._collections.collections_of(iri)

    async def delete_cascade(self, collection: str, if_version: str) -> None:
        """Delete the collection and each of its members, in one request, all or nothing.

        The members are those the collection names and those that meet its rule, resolved now: not
        deep (a member that is a collection is deleted, its own members stay) and not the collection
        itself. A member that is already gone is skipped. A plain delete of the collection keeps its
        members. The ``Raises`` are those of ``ReferenceCollections.delete_cascade``.
        """
        await self._collections.delete_cascade(collection, if_version)

    def _require_readable(self, iri: str) -> None:
        if not self._iris.is_aggregate(self._access.tenant, iri):
            raise InvalidIri(f"{iri} is not an aggregate of the tenant")
        self._rules.require(self._caller, self._access, iri, Action.READ)

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
