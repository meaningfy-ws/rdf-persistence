"""Workflows: the files that define them, their validation at start-up, and the write guard's rule (PD-17, PD-19).

A workflow is configuration: one YAML file validated into the generated ``Workflow``, checked once
against the role definitions and the schema, so a bad file stops the service before it serves.
``Workflows`` maps each class that names a workflow (or inherits the name) to it.
"""

from collections.abc import Sequence
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError
from rdflib import RDF, BNode, Literal, URIRef

from rdf_persistence.domain.exceptions import Forbidden, InvalidWorkflow
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_core import RpAnnotation
from rdf_persistence.domain.generated.rp_workflow import Workflow
from rdf_persistence.domain.sparql import Triple
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.schema_structure import annotation_text
from rdf_persistence.services.session import Session

Object = URIRef | Literal | BNode  # what a triple's object can be
CHANGED_BY_TRANSITION = "the state is changed only by a transition"


def load_workflow(path: Path) -> Workflow:
    """The workflow in the YAML file ``path``, validated against ``rp_workflow``.

    Raises:
        InvalidWorkflow: The file cannot be read, is not YAML or not a mapping, or is not a valid
            workflow; the message names the file and the element.
    """
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as error:
        raise InvalidWorkflow(f"cannot read the workflow {path}: {error}") from error
    except yaml.YAMLError as error:
        raise InvalidWorkflow(f"{path} is not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise InvalidWorkflow(f"{path} must hold one workflow, a mapping")
    try:
        return Workflow.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']} (got {e['input']!r})"
            for e in error.errors()
        )
        raise InvalidWorkflow(f"{path}: {problems}") from error


def state_iri(workflow: Workflow, state: str) -> str:
    """The IRI of the state named ``state``: the workflow's identifier, a slash and the name."""
    return f"{workflow.id}/{state}"


class Workflows:
    """The workflows of a service, checked, and the class each one governs."""

    def __init__(
        self, definitions: Sequence[Workflow], view: SchemaView, rules: AccessRules
    ) -> None:
        """Raise ``InvalidWorkflow``, naming the workflow and the element, when a state, the initial
        state or a transition end is not among the states, a role is not defined, two transitions
        have the same ends, two workflows share a name, or a class names a workflow that is not given."""
        self._by_name = _by_name(definitions)
        for workflow in definitions:
            _check(workflow, rules)
        self._by_class = _by_class(view, self._by_name)
        self._by_iri = {
            URIRef(view.get_uri(name, expand=True)): workflow
            for name, workflow in self._by_class.items()
        }

    def for_class(self, name: str) -> Workflow | None:
        """The workflow the schema class ``name`` follows, if any."""
        return self._by_class.get(name)

    def for_iri(self, class_iri: str) -> Workflow | None:
        """The workflow the class with IRI ``class_iri`` follows, if any."""
        return self._by_iri.get(URIRef(class_iri))

    async def keep_state(
        self,
        session: Session,
        iri: str,
        triples: list[Triple],
        stored: Tracked | None,
        allowed_state: str | None,
    ) -> list[Triple]:
        """The triples to write for the root ``iri`` so that a plain write never changes its state (PD-19).

        A class with no workflow is returned as it is, with no query. An add gets the initial state;
        a replace without a state keeps the stored one (none stays none, PD-22). ``stored`` is
        ``None`` for an add. ``allowed_state`` is the one state this write may set (a transition's).

        Raises:
            Forbidden: The triples name a state that is not the initial one (add) or the stored one
                (replace), and ``allowed_state`` is not it.
        """
        root = URIRef(iri)
        workflow = self._of_root(root, triples)
        if workflow is None:
            return triples
        named = {o for s, p, o in triples if s == root and p == v.WORKFLOW_STATUS}
        if stored is None:
            return _added(workflow, root, triples, named)
        held = set(await session.objects_of(iri, v.WORKFLOW_STATUS))
        return _replaced(root, triples, named, held, allowed_state)

    def _of_root(self, root: URIRef, triples: list[Triple]) -> Workflow | None:
        types = (o for s, p, o in triples if s == root and p == RDF.type)
        return next((w for t in types if (w := self._by_iri.get(URIRef(str(t)))) is not None), None)


def _added(
    workflow: Workflow, root: URIRef, triples: list[Triple], named: set[Object]
) -> list[Triple]:
    initial = URIRef(state_iri(workflow, workflow.initial_state))
    if not named:
        return [*triples, (root, v.WORKFLOW_STATUS, initial)]
    if named != {initial}:
        raise Forbidden(CHANGED_BY_TRANSITION)
    return triples


def _replaced(
    root: URIRef,
    triples: list[Triple],
    named: set[Object],
    held: set[Object],
    allowed: str | None,
) -> list[Triple]:
    if not named:
        return [*triples, *((root, v.WORKFLOW_STATUS, state) for state in sorted(held))]
    permitted = [held] if allowed is None else [held, {URIRef(allowed)}]
    if named not in permitted:
        raise Forbidden(CHANGED_BY_TRANSITION)
    return triples


def _by_name(definitions: Sequence[Workflow]) -> dict[str, Workflow]:
    named: dict[str, Workflow] = {}
    for workflow in definitions:
        if workflow.workflow_name in named:
            raise InvalidWorkflow(f"workflow {workflow.workflow_name!r} is defined twice")
        named[workflow.workflow_name] = workflow
    return named


def _check(workflow: Workflow, rules: AccessRules) -> None:
    where = f"workflow {workflow.workflow_name!r}"
    states = set(workflow.workflow_states)
    if workflow.initial_state not in states:
        raise InvalidWorkflow(
            f"{where}: initial_state {workflow.initial_state!r} is not one of its states"
        )
    seen: set[tuple[str, str]] = set()
    for move in workflow.workflow_transitions or []:
        ends = (move.from_state, move.to_state)
        label = f"{where}: transition {ends[0]} -> {ends[1]}"
        for state in ends:
            if state not in states:
                raise InvalidWorkflow(f"{label} names {state!r}, which is not one of its states")
        if ends in seen:
            raise InvalidWorkflow(f"{label} is given twice")
        seen.add(ends)
        for role in move.transition_roles:
            if not rules.defines(role):
                raise InvalidWorkflow(f"{label} names role {role!r}, which no role definition has")


def _by_class(view: SchemaView, named: dict[str, Workflow]) -> dict[str, Workflow]:
    """Each class that names a workflow, or has an ancestor (by ``is_a``) that does, with that workflow."""
    found: dict[str, Workflow] = {}
    for name in view.all_classes():
        wanted = next(
            (
                text
                for ancestor in view.class_ancestors(name, mixins=False)
                if (text := annotation_text(view.get_class(ancestor), RpAnnotation.WORKFLOW))
            ),
            None,
        )
        if wanted is None:
            continue
        if wanted not in named:
            raise InvalidWorkflow(f"class {name} names workflow {wanted!r}, which no file defines")
        found[name] = named[wanted]
    return found
