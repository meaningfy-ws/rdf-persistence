"""The access-aware reads and writes over a session: who refers to a resource (PD-1, PD-3).

A ``Collaboration`` holds one ``Session`` and the caller it acts for. The session knows no schema and
checks no access; the schema's names and the access filter live here, so the generic API and the
unit of work, which bypass this class, are unaffected. The reads and the cascade of reference
collections are ``ReferenceCollections``'s; this class hands them over, so the public face is one.
"""

from collections.abc import Callable, Sequence
from functools import partial

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.access.domain.generated.rp_access import Action
from rdf_persistence.access.services.access import AccessRules
from rdf_persistence.access.services.generated.rp_access_services import (
    CallerAccess,
    VerifiedCaller,
)
from rdf_persistence.collaboration.domain.generated.rp_discussion import Comment, PostComment
from rdf_persistence.collaboration.domain.generated.rp_workflow import Assignment, Transition
from rdf_persistence.collaboration.services.assignments import AccessOf, Assignments
from rdf_persistence.collaboration.services.discussion import Discussion
from rdf_persistence.collaboration.services.generated.rp_collaboration_services import (
    MemberList,
    ReferrerList,
)
from rdf_persistence.collaboration.services.reference_collections import ReferenceCollections
from rdf_persistence.collaboration.services.referrer_naming import located, named, referrer_item
from rdf_persistence.collaboration.services.transitions import Transitions
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.core.domain.exceptions import BadQuery, InvalidIri
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.generated.rows.rp_persistence_rows import ReferrerRow
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.persistence.services.session import Session


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
        workflows: Workflows | None = None,
        access_of: AccessOf | None = None,
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
        self._discussion = Discussion(
            session,
            view=view,
            rules=rules,
            iris=iris,
            mapper=mapper,
            caller=caller,
            access=access,
        )
        self._transitions = Transitions(
            session,
            view=view,
            rules=rules,
            iris=iris,
            mapper=mapper,
            caller=caller,
            access=access,
            workflows=workflows,
        )
        self._assignments = Assignments(
            session,
            view=view,
            rules=rules,
            iris=iris,
            mapper=mapper,
            caller=caller,
            access=access,
            workflows=workflows,
            access_of=access_of,
        )

    @property
    def session(self) -> Session:
        """The session this collaboration writes through, for the message bus, which gives it to
        handlers and observers. The session checks no access: a caller of ``session`` holds the
        session's full reach."""
        return self._session

    async def referrers(
        self, iri: str, *, class_name: str | None = None, slot: str | None = None
    ) -> ReferrerList:
        """The aggregates of the tenant that refer to ``iri`` and that the caller may read, one item per
        referrer and slot, sorted by IRI and slot; ``hidden_count`` is the number of other referring
        aggregates, each counted once and never named.

        ``class_name`` and ``slot`` keep only the listed referrers of that schema class and the links
        by that slot. The hidden count ignores them: it counts every referrer the caller may not
        read, so narrowing cannot show the class or slot of one. The links of a comment to what it
        was made on do not count.

        Raises:
            InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            BadQuery: ``class_name`` or ``slot`` is not a name of the schema.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_readable(iri)
        self._require_names(class_name, slot)
        rows = await self._session.referrer_rows(iri)
        readable = await self.readable_referrers(iri, rows)
        return self._listed(
            named(self._view, rows),
            class_name,
            slot,
            readable,
            partial(located, self._view, self._iris),
        )

    async def readable_referrers(self, iri: str, rows: Sequence[ReferrerRow]) -> set[str]:
        """Of the referrers of ``iri`` in ``rows``, the IRIs the caller may read (PD-9, DEC-3).

        A comment is readable when its thread shows it to the caller and by no other right; any
        other referrer, when the caller may read it (PD-3, PD-30). It checks nothing of ``iri``.
        """
        judged = await self._discussion.judged(iri, rows)
        return {
            referrer
            for referrer in {row.referrer for row in rows}
            if (
                judged[referrer]
                if referrer in judged
                else self._rules.may(self._caller, self._access, referrer, Action.READ)
            )
        }

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

    async def comment(
        self,
        iri: str,
        text: str,
        *,
        audience: Sequence[str] = (),
        references: Sequence[str] = (),
        reply_to: str | None = None,
        command: PostComment | None = None,
    ) -> str:
        """Post a comment on the aggregate ``iri`` and return its IRI.

        The aggregate is not written, and deleting it deletes its comments. The request's activity
        is the post (``command``, if given, or a new ``PostComment``, a ``PostReply`` for a reply).
        The ``Raises`` are those of ``Discussion.comment``.
        """
        return await self._discussion.comment(
            iri,
            text,
            audience=audience,
            references=references,
            reply_to=reply_to,
            command=command,
        )

    async def thread(self, iri: str) -> list[Comment]:
        """The comments on ``iri`` that the caller sees, oldest first, a reply naming its parent.

        The ``Raises`` are those of ``Discussion.thread``.
        """
        return await self._discussion.thread(iri)

    async def transition(
        self,
        iri: str,
        to: str,
        *,
        if_version: str,
        comment: str | None = None,
        command: Transition | None = None,
    ) -> str:
        """Move the aggregate ``iri`` to the state named ``to`` and return its new version.

        The state and the comment, if any, are stored in one request, whose activity is the move
        (``command``, if given, or a new ``Transition``). The ``Raises`` are those of
        ``Transitions.transition``.
        """
        return await self._transitions.transition(
            iri, to, if_version=if_version, comment=comment, command=command
        )

    async def transitions(self, iri: str) -> list[Transition]:
        """The moves of ``iri``, oldest first.

        The ``Raises`` are those of ``Transitions.transitions``.
        """
        return await self._transitions.transitions(iri)

    async def assign(
        self,
        iri: str,
        principals: Sequence[str],
        *,
        if_version: str,
        command: Assignment | None = None,
    ) -> str:
        """Make ``principals`` the assignees of the aggregate ``iri`` and return its new version.

        The set is stored in one request, whose activity is the change (``command``, if given, or a
        new ``Assignment``). The ``Raises`` are those of ``Assignments.assign``.
        """
        return await self._assignments.assign(
            iri, list(principals), if_version=if_version, command=command
        )

    async def release_unreadable(self, record: CallerAccess) -> None:
        """Release the assignees who may no longer read what they are assigned, by the access ``record`` of the tenant.

        The ``Raises`` are those of ``Assignments.release_unreadable``.
        """
        await self._assignments.release_unreadable(record)

    async def assignments(self, iri: str) -> list[Assignment]:
        """The changes of the assignees of ``iri``, oldest first.

        The ``Raises`` are those of ``Assignments.assignments``.
        """
        return await self._assignments.assignments(iri)

    async def roles_held(self, iri: str) -> frozenset[str]:
        """The names of the roles the caller holds on ``iri``: the roles that decide who sees a
        comment (its audience) and who may make a move.

        The schema needs no discussion module.

        Raises:
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
        """
        self._rules.require(self._caller, self._access, iri, Action.READ)
        return frozenset(self._rules.roles(self._caller, self._access, iri))

    async def delete_cascade(self, collection: str, if_version: str) -> None:
        """Delete the collection and each of its members, in one request, all or nothing.

        The members are those the collection names and those that meet its rule, resolved now: not
        deep (a member that is a collection is deleted, its own members stay) and not the collection
        itself. A member that is already gone is skipped. A plain delete of the collection keeps its
        members. A member of a refusing class that an aggregate outside the cascade refers to
        refuses the whole cascade with ``InUse``, naming the referrers the caller may read. The
        ``Raises`` are those of ``ReferenceCollections.delete_cascade``, which include ``InUse``.
        """
        await self._collections.delete_cascade(
            collection, if_version, readable=self.readable_referrers
        )

    def _require_readable(self, iri: str) -> None:
        if not self._iris.is_aggregate(self._access.tenant, iri):
            raise InvalidIri(f"{iri} is not an aggregate of the tenant")
        self._rules.require(self._caller, self._access, iri, Action.READ)

    def _require_names(self, class_name: str | None, slot: str | None) -> None:
        if class_name is not None and self._view.get_class(class_name) is None:
            raise BadQuery(f"the schema has no class {class_name!r}")
        if slot is not None and self._view.get_slot(slot) is None:
            raise BadQuery(f"the schema has no slot {slot!r}")

    @staticmethod
    def _listed(
        named: set[tuple[str, str, str]],
        class_name: str | None,
        slot: str | None,
        readable: set[str],
        locate: Callable[[str, str], tuple[str, str] | None],
    ) -> ReferrerList:
        """The items of the ``readable`` referrers, narrowed and sorted, and the number of other referrers (PD-26).

        ``locate(class name, IRI)`` gives the ``(rp_path, id)`` a referrer is served at, or ``None``:
        both fields of an item are set from it, or neither.
        """
        referrers = {referrer for referrer, _, _ in named}
        items = [
            referrer_item(r, c, s, locate(c, r))
            for r, c, s in sorted(named)
            if r in readable and class_name in (None, c) and slot in (None, s)
        ]
        return ReferrerList(referrers=items or None, hidden_count=len(referrers - readable))
