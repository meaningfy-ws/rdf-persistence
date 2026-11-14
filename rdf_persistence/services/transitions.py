"""Transitions: the one write that changes the state of an aggregate, and the records it leaves (PD-15, PD-20 to PD-22).

A transition moves an aggregate along an edge of its workflow. Who may make it is decided by the
roles on the edge, not by ``modify``; the aggregate, its record and the comment that goes with it are
written in one transaction. ``Transitions`` holds one ``Session`` and the caller it acts for;
``Collaboration`` hands ``transition`` and ``transitions`` over to it.
"""

from typing import cast

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.exceptions import Conflict, Forbidden, InvalidBody, StoredDataInvalid
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_discussion import Comment, Motivation
from rdf_persistence.domain.generated.rp_workflow import (
    TransitionRecord,
    Workflow,
    WorkflowTransition,
)
from rdf_persistence.domain.generated.service.rp_service import CallerAccess, VerifiedCaller
from rdf_persistence.domain.iris import Iris
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.discussion import decode_typed, mint_iri, moment_of
from rdf_persistence.services.mapper import Mapper
from rdf_persistence.services.session import Dependents, Session, changed_text
from rdf_persistence.services.workflows import SHOWN, Workflows, state_iri

RECORD = "TransitionRecord"
COMMENT = "Comment"


def dependents(view: SchemaView) -> Dependents:
    """The ``(class, link)`` pair a remove drops with the aggregate it points at: a record's ``prov:used``.

    None for a schema that does not import the workflow module.
    """
    return ((v.TRANSITION_RECORD, v.USED),) if view.get_class(RECORD) else ()


class Transitions:
    """What a caller may ask of the workflows of a tenant."""

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
    ) -> None:
        self._session = session
        self._view = view
        self._rules = rules
        self._iris = iris
        self._mapper = mapper
        self._caller = caller
        self._access = access
        self._workflows = workflows

    async def transition(
        self, iri: str, to: str, *, if_version: str, comment: str | None = None
    ) -> str:
        """Move the aggregate ``iri`` to the state named ``to``, if it still has ``if_version``;
        returns its new version.

        The state, a record of the move (who, when, from and to) and, with ``comment``, a comment in
        the thread of ``iri`` for everyone who reads it, are stored in one request. The roles on the
        edge decide who may make the move; a Prohibition of ``modify`` freezes the aggregate.

        Raises:
            LookupError: The schema does not import the module rp_workflow.
            NotFound: The caller can see nothing of ``iri``, or ``iri`` has no graph.
            Forbidden: The caller may see ``iri`` but not read it; ``modify`` is prohibited on it;
                ``annotate`` is prohibited on it and a comment that is not blank is given; or none
                of the roles on the edge is the caller's.
            InvalidBody: ``iri`` is under no workflow; or the edge needs a comment and ``comment``
                is none or blank.
            Conflict: The version of ``iri`` is not ``if_version`` (checked first, so it hides every
                refusal below it), or ``iri`` was removed meanwhile; or the workflow has no edge from
                the current state to ``to``, or ``to`` is no state of it (a stored state the file no
                longer lists has none); nothing was stored.
            StoredDataInvalid: ``iri`` holds more than one state, or classes under more than one
                workflow; nothing was stored.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        self._rules.require(self._caller, self._access, iri, Action.READ)
        if self._rules.prohibits(self._caller, self._access, iri, Action.MODIFY):
            raise Forbidden("modify is prohibited")
        comment = comment if comment and comment.strip() else None  # a blank one is none
        if comment and self._rules.prohibits(self._caller, self._access, iri, Action.ANNOTATE):
            raise Forbidden("annotate is prohibited")
        graph, _, held = await self._session.get_graph(iri)
        if held != if_version:  # the caller read an older state: say so before anything about it
            raise Conflict(changed_text(iri, held), iris=(iri,))
        workflow = self._workflow_of(iri, graph)
        current = _current(workflow, iri, graph)
        edge = self._edge(workflow, iri, current, to)
        if edge.comment_required and comment is None:
            raise InvalidBody(f"the move to {to} needs a comment")
        return await self._store(iri, graph, workflow, current, to, comment, if_version)

    async def transitions(self, iri: str) -> list[TransitionRecord]:
        """The records of the moves of the aggregate ``iri``, oldest first, ties by IRI.

        Raises:
            LookupError: The schema does not import the module rp_workflow.
            NotFound: The caller can see nothing of ``iri``.
            Forbidden: The caller may see ``iri`` but not read it.
            DatabaseGone: The tenant database does not exist.
        """
        self._require_module()
        self._rules.require(self._caller, self._access, iri, Action.READ)
        found = await self._session.graphs_with(v.USED, URIRef(iri))
        decoded = (self._decode(root, graph) for root, graph in found.items())
        return sorted(
            (r for r in decoded if r is not None),
            key=lambda r: (moment_of(r.started_at_time), r.id),
        )

    def _require_module(self) -> None:
        if self._view.get_class(RECORD) is None:
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

    def _edge(self, workflow: Workflow, iri: str, current: str, to: str) -> WorkflowTransition:
        """The edge from ``current`` to the state ``to`` that the caller may take."""
        if to not in workflow.workflow_states:
            raise Conflict(
                f"{to[:SHOWN]!r} is an unknown state of the workflow {workflow.workflow_name}"
            )
        edge = next(
            (
                e
                for e in workflow.workflow_transitions or []
                if state_iri(workflow, e.from_state) == current and e.to_state == to
            ),
            None,
        )
        if edge is None:
            raise Conflict(f"the workflow has no transition from {current} to {to}")
        if not set(edge.transition_roles) & self._rules.roles(self._caller, self._access, iri):
            raise Forbidden(f"the move to {to} needs one of the roles {edge.transition_roles}")
        return edge

    async def _store(
        self,
        iri: str,
        graph: Graph,
        workflow: Workflow,
        current: str,
        to: str,
        comment: str | None,
        if_version: str,
    ) -> str:
        entered = state_iri(workflow, to)
        record = self._mint(RECORD)
        posted = self._mint(COMMENT) if comment else None
        models: list[TransitionRecord | Comment] = [
            TransitionRecord(
                id=record,
                used_resource=iri,
                from_state_iri=current,
                to_state_iri=entered,
                started_at_time=self._session.now(),
                was_associated_with=[self._session.principal.id],
                transition_comment=posted,
            )
        ]
        if comment:
            models.append(
                Comment(
                    id=str(posted),
                    has_target=iri,
                    body_value=comment,
                    motivated_by=Motivation.COMMENTING,
                    from_state_iri=current,
                    to_state_iri=entered,
                )
            )
        async with self._session.transaction() as transaction:
            transaction._allow_state(iri, entered)
            version = await transaction.replace_graph(iri, _moved(iri, graph, entered), if_version)
            for model in models:
                await transaction.add_graph(model.id, self._mapper.to_triples(model))
        return version

    def _mint(self, class_name: str) -> str:
        return mint_iri(self._view.get_class(class_name), self._iris, self._access.tenant)

    def _decode(self, iri: str, graph: Graph) -> TransitionRecord | None:
        """The record at ``iri``, or None for a root that is not one (not typed so, or one the class refuses)."""
        return decode_typed(self._mapper, TransitionRecord, v.TRANSITION_RECORD, iri, graph)


def _current(workflow: Workflow, iri: str, graph: Graph) -> str:
    """The state IRI stored on ``iri``, or the initial state's when it has none (PD-22)."""
    stored = set(graph.objects(URIRef(iri), v.WORKFLOW_STATUS))
    if len(stored) > 1:
        raise StoredDataInvalid(f"{iri} has more than one stored state")
    return str(next(iter(stored))) if stored else state_iri(workflow, workflow.initial_state)


def _moved(iri: str, graph: Graph, entered: str) -> list[Triple]:
    """The stored triples with the state ``entered`` in place of the one held."""
    root = URIRef(iri)
    kept = cast(
        list[Triple], [t for t in graph if not (t[0] == root and t[1] == v.WORKFLOW_STATUS)]
    )
    return [*kept, (root, v.WORKFLOW_STATUS, URIRef(entered))]
