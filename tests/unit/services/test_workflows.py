"""Workflow files and their validation at start-up (PD-17, TC-69 to TC-75)."""

from pathlib import Path

import pytest
import yaml

from rdf_persistence import AccessRules, load_role_definitions
from rdf_persistence.domain.exceptions import InvalidWorkflow
from rdf_persistence.domain.generated.rp_workflow import WorkflowTransition
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from tests.toy import REVIEW_WORKFLOW, ROLES, TOY_SCHEMA
from tests.toy_service import ToyService
from tests.unit.services.test_collaboration_workflow_adversarial import copy_schema, edit

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
    assert workflow.workflow_name == "review", "the file defines the review workflow"
    assert workflows.for_class("Book") is workflow, "the annotated class"
    assert workflows.for_iri("http://purl.org/ontology/bibo/Book") is workflow, "its class IRI"
    assert workflows.for_class("Shelf") is None, "a class without the annotation"
    assert workflows.for_iri(f"{LIBRARY}Shelf") is None, "its class IRI too"


def test_a_state_is_the_workflow_id_a_slash_and_its_name():
    assert (
        state_iri(review(), "draft") == "https://example.org/ns/library/workflows/review/draft"
    ), "the id, a slash and the name"


def with_transitions(*moves: WorkflowTransition):
    return review().model_copy(update={"workflow_transitions": list(moves)})


# (id, the workflows, what the error must name)
REFUSED = [
    (
        "transition-to-an-unknown-state",
        [with_transitions(move("draft", "archived"))],
        [
            "review",
            "draft -> archived",
        ],  # the spec scenario "an undefined state" names the transition
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
    assert Workflows([only_draft], VIEW, RULES).for_class("Book") is only_draft, "it is accepted"


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
    assert ToyService().kit.workflows.for_class("Book") is not None, "the kit holds the workflows"


def written(folder: Path, *definitions) -> list[Path]:
    """One YAML file per workflow definition, named ``first.yaml``, ``second.yaml``."""
    paths = []
    for name, definition in zip(("first", "second"), definitions, strict=False):
        path = folder / f"{name}.yaml"
        path.write_text(yaml.safe_dump(definition.model_dump(mode="json", exclude_none=True)))
        paths.append(path)
    return paths


def test_two_workflows_with_one_id_are_refused_naming_both_files(tmp_path):  # PD-31 item 5
    twin = review().model_copy(update={"workflow_name": "twin"})
    with pytest.raises(InvalidWorkflow) as refused:
        Workflows.from_files(written(tmp_path, review(), twin), VIEW, RULES)
    assert "first.yaml" in str(refused.value), "the first file"
    assert "second.yaml" in str(refused.value), "the second file"


FILE_OF_THE_FAULT = [  # PD-31 item 6: (id, the definitions, the index of the one at fault)
    ("a-transition-end", [with_transitions(move("draft", "ghost"))], 0),
    ("a-role", [with_transitions(move("draft", "in_review", "ghost"))], 0),
    (
        "a-transition-twice",
        [with_transitions(move("draft", "in_review"), move("draft", "in_review"))],
        0,
    ),
    ("a-name-twice", [review(), review()], 1),
]


@pytest.mark.parametrize(
    ("definitions", "faulty"),
    [(d, f) for _, d, f in FILE_OF_THE_FAULT],
    ids=[i for i, _, _ in FILE_OF_THE_FAULT],
)
def test_a_check_of_the_workflows_names_the_file_of_the_workflow_at_fault(
    tmp_path, definitions, faulty
):
    files = written(tmp_path, *definitions)
    with pytest.raises(InvalidWorkflow) as refused:
        Workflows.from_files(files, VIEW, RULES)
    assert str(files[faulty]) in str(refused.value), "the file of the workflow at fault"


def test_a_class_naming_a_workflow_no_file_defines_names_the_class_and_the_files_given(tmp_path):
    [file] = written(tmp_path, review().model_copy(update={"workflow_name": "other"}))
    with pytest.raises(InvalidWorkflow) as refused:
        Workflows.from_files([file], VIEW, RULES)
    assert "Book" in str(refused.value), "the class"
    assert str(file) in str(refused.value), "the files given"


def test_from_files_gives_the_same_workflows_as_the_constructor(tmp_path):
    files = written(tmp_path, review())
    assert Workflows.from_files(files, VIEW, RULES).for_class("Book") == review(), "the review file"


# PD-32 item 4: the id rule of the SPARQL layer, a hash at the end, a long input cut short.
BAD_IDS = [
    "https://ex.org/{review}",
    "https://ex.org/a|b",
    "C:\\path",
    "https://ex.org/review#",
    "https://ex.org/review/",
    "https://ex.org/a^b",
    "https://ex.org/a`b",
    "review",
]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_a_workflow_id_that_makes_bad_state_iris_is_refused_naming_the_file(tmp_path, bad):
    [path] = written(tmp_path, review().model_copy(update={"id": bad}))
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert str(path) in str(refused.value), "the file is named"
    assert "id" in str(refused.value), "and the element"


def test_a_long_rejected_value_is_cut_short_in_the_message(tmp_path):
    long = "https://ex.org/" + "x" * 5000 + "|"
    [path] = written(tmp_path, review().model_copy(update={"id": long}))
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert len(str(refused.value)) < 1000, "the text does not echo the whole input"
    assert "x" * 5000 not in str(refused.value), "the input is cut"


TWIN_CLASS = (
    "  Twin:\n    title: Twin\n    description: A class with the IRI of Book.\n    is_a: Book\n"
    "    class_uri: bibo:Book\n    annotations:\n      rp_path: twins\n      workflow: other\n"
    "  Shelf:\n"
)


def test_two_classes_with_one_class_iri_naming_different_workflows_are_refused(tmp_path):
    folder = copy_schema(tmp_path)
    edit(folder, "books.yaml", "  Shelf:\n", TWIN_CLASS)
    other = review().model_copy(update={"workflow_name": "other", "id": "https://ex.org/other"})
    with pytest.raises(InvalidWorkflow, match="Twin") as refused:
        Workflows([review(), other], load_schema(folder / "library.yaml"), RULES)
    assert "other" in str(refused.value), "the workflow the class names"
    assert "review" in str(refused.value), "the workflow the other class names"


def test_two_classes_with_one_class_iri_naming_one_workflow_are_accepted(tmp_path):
    folder = copy_schema(tmp_path)
    edit(
        folder,
        "books.yaml",
        "  Shelf:\n",
        TWIN_CLASS.replace("workflow: other", "workflow: review"),
    )
    workflows = Workflows([review()], load_schema(folder / "library.yaml"), RULES)
    assert workflows.for_class("Twin") is not None, "the twin follows the workflow"


def test_a_long_value_the_model_rejects_is_cut_short_in_the_message(tmp_path):
    long = review().model_copy(update={"workflow_states": ["A" * 5000], "initial_state": "a"})
    [path] = written(tmp_path, long)
    with pytest.raises(InvalidWorkflow) as refused:
        load_workflow(path)
    assert "AAAA" in str(refused.value), "the value is echoed"
    assert "A" * 5000 not in str(refused.value), "but cut"


def test_a_long_state_a_transition_names_is_cut_short_in_the_message():
    long = with_transitions(move("draft", "a" * 5000))
    with pytest.raises(InvalidWorkflow) as refused:
        Workflows([long], VIEW, RULES)
    assert "a" * 5000 not in str(refused.value), "the state is cut"
