"""The access-aware reads and writes over a session: who refers to a resource (PD-1, PD-3).

A ``Collaboration`` holds one ``Session`` and the caller it acts for. The session knows no schema and
checks no access; the schema's names and the access filter live here, so the generic API and the
unit of work, which bypass this class, are unaffected.
"""

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef

from rdf_persistence.domain.exceptions import BadQuery, InvalidIri
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    Referrer,
    ReferrerList,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.access import AccessRules
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
        caller: VerifiedCaller,
        access: CallerAccess,
    ) -> None:
        self._session = session
        self._view = view
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

        ``class_name`` and ``slot`` keep only the referrers of that schema class and the links by that
        slot. The links of a comment or a transition record to what they were made on do not count.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            BadQuery: ``class_name`` or ``slot`` is not a name of the schema.
            DatabaseGone: The tenant database does not exist.
        """
        if not self._iris.is_aggregate(self._access.tenant, iri):
            raise InvalidIri(f"{iri} is not an aggregate of the tenant")
        self._rules.require(self._caller, self._access, iri, Action.READ)
        rows = await self._session.referrer_rows(
            iri, class_iri=self._class_iri(class_name), slot_iri=self._slot_iri(slot)
        )
        return self._readable(self._named(rows))

    def _class_iri(self, name: str | None) -> URIRef | None:
        if name is None:
            return None
        found = self._view.get_class(name)
        if found is None:
            raise BadQuery(f"the schema has no class {name!r}")
        return URIRef(self._view.get_uri(found, expand=True))

    def _slot_iri(self, name: str | None) -> URIRef | None:
        if name is None:
            return None
        found = self._view.get_slot(name)
        if found is None:
            raise BadQuery(f"the schema has no slot {name!r}")
        return URIRef(self._view.get_uri(found, expand=True))

    def _named(self, rows: list[ReferrerRow]) -> set[tuple[str, str, str]]:
        """``(referrer, class name, slot name)`` of each row; an IRI the schema does not know stays as it is."""
        classes = {
            self._view.get_uri(c, expand=True): name for name, c in self._view.all_classes().items()
        }
        return {
            (
                referrer,
                classes.get(cls, cls),
                self._slot_name(classes.get(subject or cls), predicate),
            )
            for referrer, cls, subject, predicate in rows
        }

    def _slot_name(self, class_name: str | None, predicate: str) -> str:
        """The slot of ``class_name`` whose ``slot_uri`` is ``predicate``, or ``predicate`` itself."""
        slots = self._view.class_induced_slots(class_name) if class_name else []
        return next(
            (s.name for s in slots if self._view.get_uri(s, expand=True) == predicate), predicate
        )

    def _readable(self, named: set[tuple[str, str, str]]) -> ReferrerList:
        """The items the caller may read, sorted, and the number of other referrers (PD-3 step 4)."""
        referrers = {referrer for referrer, _, _ in named}
        readable = {
            r for r in referrers if self._rules.may(self._caller, self._access, r, Action.READ)
        }
        items = [
            Referrer(referrer=r, referrer_class=c, referrer_slot=s)
            for r, c, s in sorted(named)
            if r in readable
        ]
        return ReferrerList(referrers=items or None, hidden_count=len(referrers - readable))
