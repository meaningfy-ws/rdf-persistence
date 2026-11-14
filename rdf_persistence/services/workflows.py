"""Workflows: the files that define them, their validation at start-up, and the write guard's rule (PD-17, PD-19).

A workflow is configuration: one YAML file validated into the generated ``Workflow``, checked once
against the role definitions and the schema, so a bad file stops the service before it serves.
``Workflows`` maps each class that names a workflow (or inherits the name) to it.
"""

import re
from collections.abc import Iterable, Sequence
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
        InvalidWorkflow: The file cannot be read, is not UTF-8 or too deeply nested, is not YAML or
            not a mapping, or is not a valid workflow (an ``id`` that is not an absolute IRI or ends
            with a slash, a state listed twice, a transition with no roles included); the message
            names the file and the element.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InvalidWorkflow(f"cannot read the workflow {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise InvalidWorkflow(f"{path} is not UTF-8 text: {error}") from error
    except yaml.YAMLError as error:
        raise InvalidWorkflow(f"{path} is not valid YAML: {error}") from error
    except RecursionError as error:
        raise InvalidWorkflow(f"{path} is nested too deeply to read") from error
    if not isinstance(data, dict):
        raise InvalidWorkflow(f"{path} must hold one workflow, a mapping")
    try:
        workflow = Workflow.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']} (got {e['input']!r})"
            for e in error.errors()
        )
        raise InvalidWorkflow(f"{path}: {problems}") from error
    if problem := _file_problem(workflow):
        raise InvalidWorkflow(f"{path}: {problem}")
    return workflow


# an absolute IRI: a scheme, a colon, then something with no space, angle bracket, quote or control character
_IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s<>\"\x00-\x1f\x7f]+")


def _file_problem(workflow: Workflow) -> str | None:
    """What a valid ``Workflow`` still gets wrong that the schema does not say, or None (PD-31 item 5)."""
    if not _IRI.fullmatch(workflow.id) or workflow.id.endswith("/"):
        return (
            f"id {workflow.id!r} must be an absolute IRI with no space, <, >, quote or "
            "control character, and no slash at the end"
        )
    states = workflow.workflow_states
    if twice := sorted({s for s in states if states.count(s) > 1}):
        return f"workflow_states lists {twice} more than once"
    for move in workflow.workflow_transitions or []:
        if not move.transition_roles:
            return f"transition {move.from_state} -> {move.to_state} has no transition_roles"
    return None


def state_iri(workflow: Workflow, state: str) -> str:
    """The IRI of the state named ``state``: the workflow's identifier, a slash and the name."""
    return f"{workflow.id}/{state}"


class Workflows:
    """The workflows of a service, checked, and the class each one governs."""

    def __init__(
        self,
        definitions: Sequence[Workflow],
        view: SchemaView,
        rules: AccessRules,
        files: Sequence[Path] = (),
    ) -> None:
        """Raise ``InvalidWorkflow``, naming the file (``files[i]`` is where ``definitions[i]`` came
        from; the workflow's name when not given) and the element, when a state, the initial state or
        a transition end is not among the states, a role is not defined, two transitions have the
        same ends, two workflows share a name or an ``id``, or a class names a workflow that is not given."""
        places = [
            f"{files[n]} (workflow {w.workflow_name!r})"
            if n < len(files)
            else f"workflow {w.workflow_name!r}"
            for n, w in enumerate(definitions)
        ]
        self._by_name = _by_name(definitions, places)
        for workflow, place in zip(definitions, places, strict=True):
            _check(workflow, place, rules)
        self._by_class = _by_class(view, self._by_name, [str(f) for f in files])
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
        """The triples to write for the root ``iri`` so that a plain write never changes its state (PD-19, PD-31).

        A service with no class under a workflow writes as it is, with no query. An add costs no
        query: its workflow is that of the class it writes, and it gets the initial state. A replace
        reads the stored types and state in one query: its workflow is that of the stored class (the
        written one when the stored root has none), and without a state in the triples it keeps the
        stored one (none stays none, PD-22). ``stored`` is ``None`` for an add. ``allowed_state`` is
        the one state this write may set (a transition's).

        Raises:
            Forbidden: The triples name a state and the root is under no workflow, or the state is
                not the initial one (add) or the stored one (replace), and ``allowed_state`` is not it.
        """
        if not self._by_iri:
            return triples
        root = URIRef(iri)
        named = _values(triples, root, v.WORKFLOW_STATUS)
        written = self._of_types(_values(triples, root, RDF.type))
        if stored is None:
            return _added(written, root, triples, named)
        read = await session.root_values(iri, [RDF.type, v.WORKFLOW_STATUS])
        workflow = self._of_types(read[RDF.type]) or written
        return _replaced(workflow, root, triples, named, read[v.WORKFLOW_STATUS], allowed_state)

    def _of_types(self, types: Iterable[Object]) -> Workflow | None:
        return next((w for t in types if (w := self._by_iri.get(URIRef(str(t)))) is not None), None)


def _unguarded(triples: list[Triple], named: set[Object]) -> list[Triple]:
    """The triples of a root under no workflow: they may not carry a state."""
    if named:
        raise Forbidden(f"{CHANGED_BY_TRANSITION}, and a state needs a class under a workflow")
    return triples


def _values(triples: list[Triple], root: URIRef, predicate: URIRef) -> set[Object]:
    return {o for s, p, o in triples if s == root and p == predicate}


def _added(
    workflow: Workflow | None, root: URIRef, triples: list[Triple], named: set[Object]
) -> list[Triple]:
    if workflow is None:
        return _unguarded(triples, named)
    initial = URIRef(state_iri(workflow, workflow.initial_state))
    if not named:
        return [*triples, (root, v.WORKFLOW_STATUS, initial)]
    if named != {initial}:
        raise Forbidden(CHANGED_BY_TRANSITION)
    return triples


def _replaced(
    workflow: Workflow | None,
    root: URIRef,
    triples: list[Triple],
    named: set[Object],
    held: set[Object],
    allowed: str | None,
) -> list[Triple]:
    if workflow is None:
        return _unguarded(triples, named)
    if not named:
        return [*triples, *((root, v.WORKFLOW_STATUS, state) for state in sorted(held))]
    permitted = [held] if allowed is None else [held, {URIRef(allowed)}]
    if named not in permitted:
        raise Forbidden(CHANGED_BY_TRANSITION)
    return triples


def _by_name(definitions: Sequence[Workflow], places: Sequence[str]) -> dict[str, Workflow]:
    named: dict[str, Workflow] = {}
    ids: dict[str, str] = {}
    for workflow, place in zip(definitions, places, strict=True):
        if workflow.workflow_name in named:
            raise InvalidWorkflow(f"{place} is defined twice")
        if workflow.id in ids:
            raise InvalidWorkflow(f"{place} has the id {workflow.id!r} of {ids[workflow.id]}")
        named[workflow.workflow_name] = workflow
        ids[workflow.id] = place
    return named


def _check(workflow: Workflow, where: str, rules: AccessRules) -> None:
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


def _by_class(
    view: SchemaView, named: dict[str, Workflow], files: Sequence[str]
) -> dict[str, Workflow]:
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
            raise InvalidWorkflow(
                f"class {name} names workflow {wanted!r}, which no file defines "
                f"(files given: {', '.join(files) or 'none'})"
            )
        found[name] = named[wanted]
    return found
