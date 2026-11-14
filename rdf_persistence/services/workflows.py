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
from rdflib.term import Node

from rdf_persistence.domain.exceptions import Forbidden, InvalidWorkflow
from rdf_persistence.domain.generated.rp_annotations import Tracked
from rdf_persistence.domain.generated.rp_workflow import Workflow
from rdf_persistence.domain.sparql import FORBIDDEN_IRI_CHARS, Triple
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.schema_structure import workflow_name_of
from rdf_persistence.services.session import Session

Object = URIRef | Literal | BNode  # what a triple's object can be
CHANGED_BY_TRANSITION = "the state is changed only by a transition"
KEEPS_A_CLASS = "an aggregate under a workflow keeps a class under it"
TAKES_A_CLASS = "an aggregate that takes a class under a workflow holds no state"
SEVERAL = "the classes of an aggregate name more than one workflow"
SHOWN = 200  # how much of a rejected input an error text echoes


def _shown(value: object) -> str:
    """The text of ``value`` for an error message, cut to ``SHOWN`` characters."""
    text = repr(value)
    return text if len(text) <= SHOWN else f"{text[:SHOWN]}..."


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
        raise InvalidWorkflow(f"{path} is not UTF-8 text: {str(error)[:SHOWN]}") from error
    except yaml.YAMLError as error:
        raise InvalidWorkflow(f"{path} is not valid YAML: {str(error)[:SHOWN]}") from error
    except RecursionError as error:
        raise InvalidWorkflow(f"{path} is nested too deeply to read") from error
    if not isinstance(data, dict):
        raise InvalidWorkflow(f"{path} must hold one workflow, a mapping")
    try:
        workflow = Workflow.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {str(e['msg'])[:SHOWN]} (got {_shown(e['input'])})"
            for e in error.errors()
        )
        raise InvalidWorkflow(f"{path}: {problems}") from error
    if problem := _file_problem(workflow):
        raise InvalidWorkflow(f"{path}: {problem}")
    return workflow


_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:.+")  # an absolute IRI starts so


def _file_problem(workflow: Workflow) -> str | None:
    """What a valid ``Workflow`` still gets wrong that the schema does not say, or None (PD-31 item 5, PD-32 item 4)."""
    if (
        not _SCHEME.fullmatch(workflow.id)
        or FORBIDDEN_IRI_CHARS.search(workflow.id)
        or workflow.id.endswith(("/", "#"))
    ):
        return (
            f"id {_shown(workflow.id)} must be an absolute IRI with none of the characters an IRI "
            'may not hold (as in SPARQL: space, < > " { } | \\ ^ `, control characters), '
            "and no slash or hash at the end"
        )
    states = workflow.workflow_states
    if twice := sorted({s for s in states if states.count(s) > 1}):
        return f"workflow_states lists {_shown(twice)} more than once"
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
        *,
        places: Sequence[str] = (),
    ) -> None:
        """Raise ``InvalidWorkflow``, naming the workflow and the element, when a state, the initial
        state or a transition end is not among the states, a role is not defined, two transitions
        have the same ends, two workflows share a name or an ``id``, a class names a workflow that
        is not given, or two classes with one class IRI name different workflows.

        ``places`` is where each definition came from (``Workflows.from_files`` gives the files);
        without it a definition is labelled by its name.
        """
        labels = [
            f"{places[n]} (workflow {w.workflow_name!r})"
            if n < len(places)
            else f"workflow {w.workflow_name!r}"
            for n, w in enumerate(definitions)
        ]
        self._by_name = _by_name(definitions, labels)
        for workflow, label in zip(definitions, labels, strict=True):
            _check(workflow, label, rules)
        self._by_class = _by_class(view, self._by_name, places)
        self._by_iri = _by_iri(view, self._by_class)

    @classmethod
    def from_files(cls, paths: Sequence[Path], view: SchemaView, rules: AccessRules) -> "Workflows":
        """The workflows in the YAML files ``paths``; an error names the file it came from.

        Raises:
            InvalidWorkflow: A file is no valid workflow (``load_workflow``), or the workflows are
                inconsistent (``Workflows``).
        """
        return cls(
            [load_workflow(path) for path in paths], view, rules, places=[str(p) for p in paths]
        )

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
        """The triples to write for the root ``iri`` so that a plain write never changes its state (PD-19, PD-32 item 1).

        S is the workflow of the stored root's types, N that of the written ones. A service with no
        class under a workflow writes as it is, with no query, as does any write with neither S nor N.
        An add (``stored`` is ``None``) reads nothing: under N a state is the initial one, which is
        set when none is written; with no N the triples are the application's own. A replace reads the
        stored types and state in one query: under S it keeps a class under S and, with no state
        written, the stored state (none stays none, PD-22); with no S but an N the aggregate holds
        and writes no state. ``allowed_state`` is the one state this write may set (a transition's).

        Raises:
            Forbidden: A set of types names two workflows; the state is not the initial one (add) or
                the stored one (replace) and ``allowed_state`` is not it; an aggregate under a workflow
                loses its class or takes one under another; an aggregate takes a class under a
                workflow and holds or writes a state.
        """
        if not self._by_iri:
            return triples
        root = URIRef(iri)
        named = _values(triples, root, v.WORKFLOW_STATUS)
        written = self._single(_values(triples, root, RDF.type))
        if stored is None:
            return _added(written, root, triples, named)
        read = await session.root_values(iri, [RDF.type, v.WORKFLOW_STATUS])
        held = self._single(read[RDF.type])
        return _replaced(
            held, written, root, triples, named, read[v.WORKFLOW_STATUS], allowed_state
        )

    def of_types(self, types: Iterable[Node]) -> list[Workflow]:
        """The distinct workflows the classes with these IRIs follow: none, one, or several (a fault)."""
        found = {
            w.workflow_name: w for t in types if (w := self._by_iri.get(URIRef(str(t)))) is not None
        }
        return list(found.values())

    def _single(self, types: Iterable[Object]) -> Workflow | None:
        found = self.of_types(types)
        if len(found) > 1:
            raise Forbidden(SEVERAL)
        return found[0] if found else None


def _values(triples: list[Triple], root: URIRef, predicate: URIRef) -> set[Object]:
    return {o for s, p, o in triples if s == root and p == predicate}


def _added(
    workflow: Workflow | None, root: URIRef, triples: list[Triple], named: set[Object]
) -> list[Triple]:
    if workflow is None:
        return triples  # the application's own adms:status is its own
    initial = URIRef(state_iri(workflow, workflow.initial_state))
    if not named:
        return [*triples, (root, v.WORKFLOW_STATUS, initial)]
    if named != {initial}:
        raise Forbidden(CHANGED_BY_TRANSITION)
    return triples


def _taking_a_class(
    written_flow: Workflow | None, triples: list[Triple], named: set[Object], held: set[Object]
) -> list[Triple]:
    """A replace of a root whose stored classes follow no workflow: its state stays the application's own,
    unless it takes a class under a workflow, which it may do only holding and writing no state."""
    if written_flow is not None and (held or named):
        raise Forbidden(TAKES_A_CLASS)
    return triples


def _replaced(
    stored_flow: Workflow | None,
    written_flow: Workflow | None,
    root: URIRef,
    triples: list[Triple],
    named: set[Object],
    held: set[Object],
    allowed: str | None,
) -> list[Triple]:
    if stored_flow is None:
        return _taking_a_class(written_flow, triples, named, held)
    if written_flow is None or written_flow.workflow_name != stored_flow.workflow_name:
        raise Forbidden(KEEPS_A_CLASS)
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
            raise InvalidWorkflow(f"{place} has the id {_shown(workflow.id)} of {ids[workflow.id]}")
        named[workflow.workflow_name] = workflow
        ids[workflow.id] = place
    return named


def _check(workflow: Workflow, where: str, rules: AccessRules) -> None:
    states = set(workflow.workflow_states)
    if workflow.initial_state not in states:
        raise InvalidWorkflow(
            f"{where}: initial_state {_shown(workflow.initial_state)} is not one of its states"
        )
    seen: set[tuple[str, str]] = set()
    for move in workflow.workflow_transitions or []:
        ends = (move.from_state, move.to_state)
        label = f"{where}: transition {ends[0][:SHOWN]} -> {ends[1][:SHOWN]}"
        for state in ends:
            if state not in states:
                raise InvalidWorkflow(
                    f"{label} names {_shown(state)}, which is not one of its states"
                )
        if ends in seen:
            raise InvalidWorkflow(f"{label} is given twice")
        seen.add(ends)
        for role in move.transition_roles:
            if not rules.defines(role):
                raise InvalidWorkflow(
                    f"{label} names role {_shown(role)}, which no role definition has"
                )


def _by_class(
    view: SchemaView, named: dict[str, Workflow], files: Sequence[str]
) -> dict[str, Workflow]:
    """Each class that names a workflow, or has an ancestor (by ``is_a``) that does, with that workflow."""
    found: dict[str, Workflow] = {}
    for name in view.all_classes():
        wanted = workflow_name_of(view, name)
        if wanted is None:
            continue
        if wanted not in named:
            raise InvalidWorkflow(
                f"class {name} names workflow {_shown(wanted)}, which no file defines "
                f"(files given: {', '.join(files) or 'none'})"
            )
        found[name] = named[wanted]
    return found


def _by_iri(view: SchemaView, by_class: dict[str, Workflow]) -> dict[URIRef, Workflow]:
    """Each class IRI with its workflow; two classes that share an IRI may not name different workflows."""
    found: dict[URIRef, Workflow] = {}
    for name, workflow in by_class.items():
        iri = URIRef(view.get_uri(name, expand=True))
        if (first := found.setdefault(iri, workflow)).workflow_name != workflow.workflow_name:
            raise InvalidWorkflow(
                f"class {name} shares the class IRI {iri} with a class of workflow "
                f"{first.workflow_name!r} but names workflow {workflow.workflow_name!r}"
            )
    return found
