"""Assignments: the one write that changes who an aggregate is assigned to, and the activities it leaves (workflow-assignees D-3, D-4).

An assignment replaces the set of assignees of an aggregate under an assignable workflow. Who may
make it is decided here, not by the guard of the session: ``modify``, or the right of an assignee to
drop itself, or of a holder of a role on an edge that leaves the current state to take the work. The
aggregate and the record of the change (an ``Assignment``) are written in one transaction.
``Collaboration`` hands ``assign`` and ``assignments`` over to it.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import cast

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.access.domain.generated.rp_access import Action
from rdf_persistence.access.services.access import AccessRules
from rdf_persistence.access.services.generated.rp_access_services import (
    CallerAccess,
    VerifiedCaller,
)
from rdf_persistence.collaboration.domain.generated.rp_workflow import Assignment, Workflow
from rdf_persistence.collaboration.services.aggregate_activities import activities_about
from rdf_persistence.collaboration.services.workflows import (
    Workflows,
    current_state,
    state_iri,
)
from rdf_persistence.core.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidBody,
    NotFound,
    StoredDataInvalid,
)
from rdf_persistence.core.domain.sparql import Triple, is_absolute_iri
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import error_type, log_extra
from rdf_persistence.core.services.yaml_files import SHOWN
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.mapper import Mapper
from rdf_persistence.persistence.services.session import Session, changed_text
from rdf_persistence.provenance.services.provenance import new_activity_id
from rdf_persistence.schema.services import vocabulary as v

log = logging.getLogger(__name__)

ASSIGNMENT_CLASS = "Assignment"

AccessOf = Callable[[str], Awaitable[CallerAccess]]


class Assignments:
    """What a caller may ask of the assignees of the aggregates of a tenant."""

    def __init__(
        self,
        session: Session,
        *,
        view: SchemaView,
        rules: AccessRules,
        iris: Iris,
        mapper: Mapper,
        caller: VerifiedCaller,
        access: CallerAccess,
        workflows: Workflows | None,
        access_of: AccessOf | None = None,
    ) -> None:
        self._session = session
        self._view = view
        self._rules = rules
        self._iris = iris
        self._mapper = mapper
        self._caller = caller
        self._access = access
        self._workflows = workflows
        self._access_of = access_of

    async def assign(
        self,
        iri: str,
        principals: list[str],
        *,
        if_version: str,
        command: Assignment | None = None,
    ) -> str:
        """Make ``principals`` the assignees of the aggregate ``iri``, if it still has ``if_version``;
        returns its new version, or ``if_version``'s own when the set is the stored one.

        The set is replaced as a whole, the empty one included. The change is stored with its
        activity, an ``Assignment`` (who, when, the principals added and those released), kept when
        the aggregate is deleted. ``command`` is the ``Assignment`` to store (a consumer's
        subclass, say); the aggregate and the principals it carries are overwritten by the computed
        ones. ``modify`` decides who may change the set; an assignee may also drop itself, and the
        holder of a role on an edge that leaves the current state may take the work.

        Raises:
            LookupError: The schema does not import the module rp_workflow, or a principal other
                than the caller is added and no reader of their access is wired.
            NotFound: The caller can see nothing of ``iri``, or ``iri`` has no graph.
            Forbidden: The caller may see ``iri`` but not read it; ``modify`` is prohibited on it;
                or the change is not one the caller may make.
            Conflict: The version of ``iri`` is not ``if_version`` (checked first, so it hides every
                refusal below it), or ``iri`` was removed meanwhile; nothing was stored.
            InvalidBody: A principal is not an absolute IRI; ``iri`` is under no workflow, or its
                workflow is not assignable and ``principals`` is not empty; or an added principal
                may not read ``iri`` (the first is named).
            StoredDataInvalid: ``iri`` holds more than one state, or classes under more than one
                workflow; nothing was stored.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        self._rules.require(self._caller, self._access, iri, Action.READ)
        if self._rules.prohibits(self._caller, self._access, iri, Action.MODIFY):
            raise Forbidden("modify is prohibited")
        graph, _, held = await self._session.get_graph(iri)
        if held != if_version:  # the caller read an older state: say so before anything about it
            raise Conflict(changed_text(iri, held), iris=(iri,))
        wanted = set(principals)
        for principal in sorted(wanted):
            if not is_absolute_iri(principal):
                raise InvalidBody(f"{principal[:SHOWN]!r} is not an absolute IRI")
        workflow = self._workflow_of(iri, graph)
        if wanted and not workflow.assignable:
            raise InvalidBody(f"the workflow {workflow.workflow_name} is not assignable")
        stored = {str(o) for o in graph.objects(URIRef(iri), v.WORKFLOW_ASSIGNEES)}
        added, removed = wanted - stored, stored - wanted
        if not added and not removed:
            return held
        self._require_authority(iri, graph, workflow, added, removed)
        await self._require_readers(iri, added)
        return await self._store(iri, graph, wanted, added, removed, if_version, command)

    async def assignments(self, iri: str) -> list[Assignment]:
        """The changes of the assignees of the aggregate ``iri``, oldest first, ties by IRI.

        A change whose aggregate was deleted is kept in the provenance graph and returned by no
        call; an aggregate added again at the same IRI shows the old changes.

        Raises:
            LookupError: The schema does not import the module rp_workflow.
            NotFound: The caller can see nothing of ``iri``, or ``iri`` has no graph.
            Forbidden: The caller may see ``iri`` but not read it.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        self._rules.require(self._caller, self._access, iri, Action.READ)
        if not await self._session.heads([iri]):  # an aggregate that is not stored has no changes
            raise NotFound(f"no graph for {iri}")
        return await activities_about(self._session, self._mapper, Assignment, v.ASSIGNMENT, iri)

    async def release_unreadable(self, record: CallerAccess) -> None:
        """Release, on every aggregate under a workflow, the assignees who may no longer read it by ``record``.

        ``record`` is the whole access record of the tenant (every principal's grants and
        prohibitions), taken after a change of grants; no query is made to test it. Each root that
        loses assignees is stored with an ``Assignment`` naming them as released and the caller of
        the session as its agent. The caller is not checked: this is a system act after the grants
        changed. A root that is refused, or that stays in conflict after one more try, is logged
        and left, and the release goes on with the next. Running it again changes nothing.

        Raises:
            LookupError: The schema does not import the module rp_workflow.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        if self._workflows is None:
            return
        for iri, graph in sorted((await self._session.graphs_with(v.WORKFLOW_ASSIGNEES)).items()):
            if self._workflows.of_types(graph.objects(URIRef(iri), RDF.type)) and self._unreadable(
                iri, graph, record
            ):
                await self._release_root(iri, record)

    def _unreadable(self, iri: str, graph: Graph, record: CallerAccess) -> set[str]:
        """The assignees of ``iri`` in ``graph`` who may not read it by ``record``."""
        return {
            principal
            for principal in (str(o) for o in graph.objects(URIRef(iri), v.WORKFLOW_ASSIGNEES))
            if not self._rules.may(
                VerifiedCaller(principal=principal, global_roles=[]), record, iri, Action.READ
            )
        }

    async def _release_root(self, iri: str, record: CallerAccess) -> None:
        """Store ``iri`` without the assignees who may not read it; once more after a conflict."""
        reason = ""
        for _ in range(2):
            try:
                graph, _, version = await self._session.get_graph(iri)
                dropped = self._unreadable(iri, graph, record)
                if not dropped:  # released meanwhile
                    return
                stored = {str(o) for o in graph.objects(URIRef(iri), v.WORKFLOW_ASSIGNEES)}
                await self._store(iri, graph, stored - dropped, set(), dropped, version, None)
                return
            except Conflict as error:
                reason = error_type(error)
            except Exception as error:  # noqa: BLE001 -- any refusal leaves the root, logged (D-6)
                reason = error_type(error)
                break
        log.warning(
            "left the assignees of an aggregate that lost its readers",
            extra=log_extra(LogContext(step="release-assignees", resource=iri, error_type=reason)),
        )

    def _require_module(self) -> None:
        if self._view.get_class(ASSIGNMENT_CLASS) is None:
            raise LookupError("the schema does not import the module rp_workflow")

    def _workflow_of(self, iri: str, graph: Graph) -> Workflow:
        found = (
            self._workflows.of_types(graph.objects(URIRef(iri), RDF.type))
            if self._workflows is not None
            else []
        )
        if not found:
            raise InvalidBody(f"{iri} is not under a workflow")
        if len(found) > 1:
            raise StoredDataInvalid(f"{iri} has classes under more than one workflow")
        return found[0]

    def _require_authority(
        self, iri: str, graph: Graph, workflow: Workflow, added: set[str], removed: set[str]
    ) -> None:
        """``modify``, or the caller dropping itself, or taking the work with a role on a leaving edge."""
        me = self._caller.principal
        if self._rules.may(self._caller, self._access, iri, Action.MODIFY):
            return
        if not added and removed == {me}:
            return
        if added == {me} and not removed:
            current = current_state(workflow, iri, graph)
            held = self._rules.roles(self._caller, self._access, iri)
            if any(
                state_iri(workflow, e.from_state) == current and set(e.transition_roles) & held
                for e in workflow.workflow_transitions or []
            ):
                return
        raise Forbidden("the caller may not make this change of assignees")

    async def _require_readers(self, iri: str, added: set[str]) -> None:
        """Each added principal, but the caller, may read ``iri`` by its stored grants (D-4)."""
        others = sorted(added - {self._caller.principal})
        if others and self._access_of is None:
            raise LookupError("no access reader is wired for assignees")
        for principal in others:
            assert self._access_of is not None
            access = await self._access_of(principal)
            reader = VerifiedCaller(principal=principal, global_roles=[])
            if not self._rules.may(reader, access, iri, Action.READ):
                raise InvalidBody(f"{principal[:SHOWN]!r} may not read {iri}")

    async def _store(
        self,
        iri: str,
        graph: Graph,
        wanted: set[str],
        added: set[str],
        removed: set[str],
        if_version: str,
        command: Assignment | None,
    ) -> str:
        slots = {
            "used_resource": iri,
            "assigned_principals": sorted(added) or None,
            "released_principals": sorted(removed) or None,
        }
        record = (
            Assignment(id=new_activity_id(), **slots)
            if command is None
            else command.replaced(**slots)
        )
        async with self._session.transaction(served=self._mapper.served(record)) as transaction:
            transaction._allow_assignees(iri, frozenset(wanted))
            version = await transaction.replace_graph(
                iri, _assigned(iri, graph, wanted), if_version
            )
        return version


def _assigned(iri: str, graph: Graph, wanted: set[str]) -> list[Triple]:
    """The stored triples with the assignees ``wanted`` in place of the ones held."""
    root = URIRef(iri)
    kept = cast(
        list[Triple], [t for t in graph if not (t[0] == root and t[1] == v.WORKFLOW_ASSIGNEES)]
    )
    return [*kept, *((root, v.WORKFLOW_ASSIGNEES, URIRef(p)) for p in sorted(wanted))]
