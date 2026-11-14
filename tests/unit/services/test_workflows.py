"""Workflow files and their validation at start-up (PD-17, TC-69 to TC-75)."""

import pytest

from rdf_persistence import AccessRules, load_role_definitions
from rdf_persistence.domain.exceptions import InvalidWorkflow
from rdf_persistence.domain.generated.rp_workflow import WorkflowTransition
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from tests.toy import REVIEW_WORKFLOW, ROLES, TOY_SCHEMA
from tests.toy_service import ToyService

LIBRARY = "https://example.org/ns/library#"
VIEW = load_schema(TOY_SCHEMA)
RULES = AccessRules(load_role_definitions(ROLES))


def review():
    return load_workflow(REVIEW_WORKFLOW)


def move(from_state: str, to_state: str, *roles: str) -> WorkflowTransition:
    return WorkflowTransition(
        from_state=from_state, to_state=to_state, transition_roles=list(roles or ["librarian"])
    )


def test_the_review_file_is_loaded_and_book_maps_to_it():  # TC-69
    workflow = review()
    workflows = Workflows([workflow], VIEW, RULES)
    assert workflow.workflow_name == "review"
    assert workflows.for_class("Book") is workflow, "the annotated class"
    assert workflows.for_iri("http://purl.org/ontology/bibo/Book") is workflow, "its class IRI"
    assert workflows.for_class("Shelf") is None, "a class without the annotation"
    assert workflows.for_iri(f"{LIBRARY}Shelf") is None


def test_a_state_is_the_workflow_id_a_slash_and_its_name():
    assert state_iri(review(), "draft") == "https://example.org/ns/library/workflows/review/draft"


def with_transitions(*moves: WorkflowTransition):
    return review().model_copy(update={"workflow_transitions": list(moves)})


# (id, the workflows, what the error must name)
REFUSED = [
    (
        "transition-to-an-unknown-state",
        [with_transitions(move("draft", "archived"))],
        ["review", "archived"],
    ),
    (
        "transition-from-an-unknown-state",
        [with_transitions(move("lost", "draft"))],
        ["review", "lost"],
    ),
    (
        "initial-state-unknown",
        [review().model_copy(update={"initial_state": "archived"})],
        ["review", "initial_state", "archived"],
    ),
    (
        "role-the-role-file-lacks",
        [with_transitions(move("draft", "in_review", "editor"))],
        ["review", "editor"],
    ),
    (
        "same-ends-twice",
        [with_transitions(move("draft", "in_review"), move("draft", "in_review"))],
        ["review", "draft", "in_review", "twice"],
    ),
    ("same-name-twice", [review(), review()], ["review", "twice"]),
    ("no-workflow-for-the-annotation", [], ["Book", "review"]),
]


@pytest.mark.parametrize(
    ("definitions", "named"), [(d, n) for _, d, n in REFUSED], ids=[i for i, _, _ in REFUSED]
)
def test_a_workflow_that_is_inconsistent_is_refused_naming_the_element(definitions, named):
    # TC-70 to TC-73
    with pytest.raises(InvalidWorkflow) as refused:
        Workflows(definitions, VIEW, RULES)
    for name in named:
        assert name in str(refused.value), f"{name!r} is named in {refused.value}"


def test_a_workflow_that_leaves_a_state_without_transitions_is_valid():
    only_draft = review().model_copy(update={"workflow_transitions": None})
    assert Workflows([only_draft], VIEW, RULES).for_class("Book") is only_draft


# (id, file text, what the error must name)
BAD_FILES = [
    ("not-yaml", "id: [\n", ["YAML"]),
    ("a-list-for-a-mapping", "- draft\n- accepted\n", ["mapping"]),
    (
        "states-missing",
        "id: https://example.org/w/review\nworkflow_name: review\ninitial_state: draft\n",
        ["workflow_states"],
    ),
    (
        "state-pattern",
        "id: https://example.org/w/review\nworkflow_name: review\nworkflow_states: [Draft]\n"
        "initial_state: Draft\n",
        ["workflow_states"],
    ),
]


@pytest.mark.parametrize(
    ("text", "named"), [(t, n) for _, t, n in BAD_FILES], ids=[i for i, _, _ in BAD_FILES]
)
def test_a_file_that_is_no_workflow_is_refused_naming_the_file(tmp_path, text, named):
    path = tmp_path / "bad.workflow.yaml"
    path.write_text(text)
    with pytest.raises(InvalidWorkflow) as refused:  # TC-75
        load_workflow(path)
    for name in [str(path), *named]:
        assert name in str(refused.value), f"{name!r} is named in {refused.value}"


def test_a_file_that_cannot_be_read_is_refused_naming_the_file(tmp_path):
    with pytest.raises(InvalidWorkflow, match="missing.workflow.yaml"):
        load_workflow(tmp_path / "missing.workflow.yaml")


def test_a_kit_for_a_schema_with_a_workflow_class_and_no_workflow_file_refuses_to_start():
    with pytest.raises(InvalidWorkflow, match="review"):  # TC-74
        ToyService(workflows=())


def test_a_kit_given_a_bad_workflow_file_refuses_to_start_naming_the_file(tmp_path):
    bad = tmp_path / "bad.workflow.yaml"
    bad.write_text("- nope\n")
    with pytest.raises(InvalidWorkflow, match="bad.workflow.yaml"):
        ToyService(workflows=(bad,))


def test_the_kit_keeps_its_workflows():
    assert ToyService().kit.workflows.for_class("Book") is not None
