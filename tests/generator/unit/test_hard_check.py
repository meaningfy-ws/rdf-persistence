"""The hard check (task 1.6, PD-11, PD-23): IRIs, titles, descriptions, meanings, paths, mixins."""

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import (
    aggregate_keys,
    annotation_text,
    keyed_slots,
)
from rdf_persistence_generation import steps
from rdf_persistence_generation.checks.application import ROWS
from rdf_persistence_generation.checks.hard import (
    ALLOWED_ANNOTATIONS,
    METAMODEL_ANNOTATIONS,
    PATTERNED_ANNOTATIONS,
    hard_problems,
    stored_schema_problems,
)
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.generated.rp_generation import (
    GenerationAnnotation,
    GenerationTarget,
    HardRule,
)
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.problems import format_problem

from .conftest import (
    ROOT_SCHEMA,
    TOOLKIT_DOMAIN,
    Breaker,
    theme_package,
    toolkit_domain_targets,
)

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"
GENERATION_MODEL = (
    Path(__file__).parents[3] / "rdf_persistence_generation" / "model" / "rp_generation.yaml"
)


def problems_of(root: Path) -> list[str]:
    return [format_problem(p) for p in hard_problems(load_schema(root), root.parent)]


ACTIVITIES = "books_activities.yaml"
SHELVE_SLOTS = "    slots: [used_resource, shelf_note]\n"
PAYLOAD_REQUIRED = (
    "    slot_usage:\n      shelf_note:\n        required: true\n        annotations:\n"
    "          payload: true\n"
)
PAYLOAD_OPTIONAL = PAYLOAD_REQUIRED.replace("        required: true\n", "")


@dataclass(frozen=True)
class Fault:
    """One planted fault: replace ``old`` by ``new`` in ``module``; ``rule`` must name ``element``."""

    rule: HardRule
    module: str
    old: str
    new: str
    element: str


FAULTS = (
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "    description: The International Standard Book Number of the book.\n",
        "",
        "isbn",
    ),
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "        description: Invented narrative.\n",
        "",
        "fiction",
    ),
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "    description: The literary genres a book can belong to.\n",
        "",
        "Genre",
    ),
    Fault(HardRule.TITLE, "books.yaml", "    title: Book\n", "", "Book"),
    Fault(HardRule.TITLE, "books.yaml", "    title: Publication date\n", "", "published"),
    # TC-103 and TC-103a: a use case does not fill the slots the toolkit fills, nor require a payload
    Fault(
        HardRule.TOOLKIT_FILLED,
        ACTIVITIES,
        SHELVE_SLOTS,
        SHELVE_SLOTS + "    slot_usage:\n      started_at_time:\n        required: true\n",
        "ShelveBooks",
    ),
    Fault(
        HardRule.TOOLKIT_FILLED,
        ACTIVITIES,
        SHELVE_SLOTS,
        SHELVE_SLOTS + "    slot_usage:\n      ended_at_time:\n        ifabsent: datetime(0)\n",
        "ShelveBooks",
    ),
    Fault(
        HardRule.TOOLKIT_FILLED,
        ACTIVITIES,
        SHELVE_SLOTS,
        SHELVE_SLOTS
        + "    attributes:\n      started_at_time:\n        description: Its own.\n        range: string\n",
        "ShelveBooks",
    ),
    Fault(
        HardRule.TOOLKIT_FILLED,
        ACTIVITIES,
        SHELVE_SLOTS,
        SHELVE_SLOTS + PAYLOAD_REQUIRED,
        "ShelveBooks",
    ),
    Fault(
        HardRule.DEFAULT_INSTANCE,
        "books.yaml",
        "        annotations:\n          owned: false\n",
        "        annotations:\n          owned: false\n          default_instance: 'true'\n",
        "shade",
    ),
    Fault(HardRule.MEANING, "books.yaml", "        meaning: schema:Fiction\n", "", "fiction"),
    Fault(HardRule.IRI, "books.yaml", "default_prefix: lib\n", "", "Genre"),
    Fault(HardRule.RP_PATH, "books.yaml", "      rp_path: books\n", "", "Book"),
    Fault(HardRule.RP_PATH, "scans.yaml", "      rp_path: scans\n", "", "Scan"),
    Fault(
        HardRule.DESCRIBED,
        "books.yaml",
        "    mixins: [Described]\n    slots: [text, about]",
        "    slots: [text, about]",
        "Note",
    ),
    Fault(
        HardRule.DESCRIBED,
        "scans.yaml",
        "[AggregateRoot, Described, Tracked, StoredFile]",
        "[AggregateRoot, Tracked, StoredFile]",
        "Scan",
    ),
    Fault(HardRule.ANNOTATION, "books.yaml", "database: tenant", "database: sytem", "Book"),
    # allowed-value check: one row per element kind (class Book, schema, slot, attribute shade)
    Fault(
        HardRule.ANNOTATION, "books.yaml", "module_kind: domain", "module_kind: dommain", "books"
    ),
    Fault(HardRule.ANNOTATION, "books.yaml", "owned: true", "owned: maybe", "chapters"),
    Fault(HardRule.ANNOTATION, "books.yaml", "rp_path: books", "rp_path: Books", "Book"),
    Fault(HardRule.ANNOTATION, "books.yaml", "rp_path: books", "rp_path: ''", "Book"),
    Fault(  # T-9: there is no value that opts a file root back into generic writes
        HardRule.ANNOTATION,
        "scans.yaml",
        "rp_path: scans",
        "rp_path: scans\n      rp_writes: generic",
        "Scan",
    ),
    Fault(
        HardRule.ANNOTATION,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: Bk",
        "Book",
    ),
    # TC-47: the toolkit's own roots use the rp- prefix, so an application's may not
    Fault(HardRule.RESERVED_SEGMENT, "books.yaml", "rp_path: books", "rp_path: rp-notes", "Book"),
    Fault(
        HardRule.RESERVED_SEGMENT,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: rp-book",
        "Book",
    ),
    # TC-65 to TC-68a: the workflow annotation and the mixin go together on a root
    Fault(  # TC-65: a root annotated, without the mixin
        HardRule.WORKFLOW,
        "books.yaml",
        "rp_path: shelves",
        "rp_path: shelves\n      workflow: review",
        "Shelf",
    ),
    Fault(  # an owned class is no aggregate root
        HardRule.WORKFLOW,
        "books.yaml",
        "rp_unlabelled: true",
        "rp_unlabelled: true\n      workflow: review",
        "Chapter",
    ),
    Fault(  # TC-66: a root with the mixin and no annotation
        HardRule.WORKFLOW, "books.yaml", "      workflow: review\n", "", "Book"
    ),
    Fault(  # TC-67: the name follows the url_segment pattern
        HardRule.ANNOTATION, "books.yaml", "workflow: review", "workflow: Review", "Book"
    ),
    Fault(  # TC-68a: the tenant root lives in the meta graph, outside the workflows
        HardRule.WORKFLOW,
        "library_tenant.yaml",
        "graph: meta",
        "graph: meta\n      workflow: review",
        "Library",
    ),
    # an owned class and a root with one type, and a reserved type
    Fault(
        HardRule.IRI_TYPE,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: chapter",
        "Book",
    ),
    Fault(
        HardRule.IRI_TYPE,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: graph",
        "Book",
    ),
    # an attribute of a class (Note.shade) gets the rules of a slot
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "        description: The colour of the note's paper.\n",
        "",
        "shade",
    ),
    Fault(HardRule.TITLE, "books.yaml", "        title: Shade\n", "", "shade"),
    Fault(HardRule.IRI, "books.yaml", "default_prefix: lib\n", "", "shade"),
    Fault(HardRule.ANNOTATION, "books.yaml", "owned: false", "owned: maybe", "shade"),
    Fault(
        HardRule.UNIQUE_KEY,
        "books.yaml",
        "    slots: [text, about]\n",
        "    slots: [text, about]\n    unique_keys:\n      bad key:\n        unique_key_slots: [text]\n",
        "Note",
    ),
    Fault(
        HardRule.UNIQUE_KEY,
        "books.yaml",
        "    slots: [text, about]\n",
        "    slots: [text, about]\n    unique_keys:\n      a-b:\n        unique_key_slots: [text]\n",
        "Note",
    ),
)


def test_the_toy_library_passes(toy_copy: Path) -> None:
    assert problems_of(toy_copy / ROOT_SCHEMA) == [], "the toy library must pass its own hard check"


@pytest.mark.parametrize("root", [METAMODEL, GENERATION_MODEL], ids=["metamodel", "generation"])
def test_the_toolkits_own_schemas_pass(root: Path) -> None:
    assert problems_of(root) == [], f"{root.name} must pass the hard check"


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f"{f.rule}-{f.element}")
def test_a_planted_fault_is_reported_with_its_rule_and_element(
    break_toy: Breaker, fault: Fault
) -> None:
    root = break_toy(fault.module, fault.old, fault.new)
    problems = problems_of(root)
    expected = f"[{fault.rule.value}] {fault.element}:"
    assert any(expected in problem for problem in problems), f"{expected!r} not in {problems}"


@pytest.mark.parametrize(
    ("edit", "slot"),
    [
        ("    slot_usage:\n      started_at_time:\n        required: true\n", "started_at_time"),
        (PAYLOAD_REQUIRED, "shelf_note"),
    ],
    ids=["slot_usage", "payload-and-required"],
)
def test_a_toolkit_filled_problem_names_the_class_and_the_slot(
    break_toy: Breaker, edit: str, slot: str
) -> None:
    """TC-103, TC-103a"""
    root = break_toy(ACTIVITIES, SHELVE_SLOTS, SHELVE_SLOTS + edit)
    found = [p for p in problems_of(root) if f"[{HardRule.TOOLKIT_FILLED.value}]" in p]
    assert len(found) == 1, f"one planted fault, one problem: {found}"
    assert "ShelveBooks" in found[0], f"the class is not named in {found[0]}"
    assert slot in found[0], f"the slot is not named in {found[0]}"


def test_a_slot_that_aliases_a_toolkit_filled_slot_is_refused(break_toy: Breaker) -> None:
    """D-11 e: another name for the slot the toolkit fills would let a caller write it too."""
    root = break_toy(
        ACTIVITIES,
        "    slot_uri: lib:shelfNote\n",
        "    slot_uri: http://www.w3.org/ns/prov#startedAtTime\n",
    )
    found = [p for p in problems_of(root) if f"[{HardRule.TOOLKIT_FILLED.value}]" in p]
    assert len(found) == 1, f"one planted fault, one problem: {found}"
    assert "ShelveBooks" in found[0], f"the class is not named in {found[0]}"
    assert "shelf_note" in found[0], f"the slot is not named in {found[0]}"
    assert "started_at_time" in found[0], f"the toolkit-filled slot is not named in {found[0]}"


DEFAULT_INSTANCE_SCHEMA = """
id: https://example.org/ns/groups
name: groups
title: Groups
description: A settings class that holds a group of its own.
prefixes: {{g: "https://example.org/ns/g#", linkml: "https://w3id.org/linkml/"}}
default_prefix: g
default_range: string
imports: [linkml:types]
classes:
  Group:
    title: Group
    description: A group of values.
    slots: [size, name]
    slot_usage:
      size: {{ifabsent: "int(3)"}}
      name: {{required: {name_required}{name_default}}}
  Holder:
    title: Holder
    description: Holds a group.
    slots: [group, label]
slots:
  size:
    title: Size
    description: A count.
    range: integer
  name:
    title: Name
    description: A name.
  group:
    title: Group slot
    description: The group.
    range: Group
    annotations:
      default_instance: 'true'
  label:
    title: Label
    description: A label.
    annotations:
      default_instance: 'true'
"""


def _default_instance_problems(
    tmp_path: Path, *, name_required: str = "false", name_default: str = ""
) -> list[str]:
    root = tmp_path / "groups.yaml"
    root.write_text(
        DEFAULT_INSTANCE_SCHEMA.format(name_required=name_required, name_default=name_default),
        encoding="utf-8",
    )
    return [p for p in problems_of(root) if f"[{HardRule.DEFAULT_INSTANCE.value}]" in p]


def _class_rule_problems(tmp_path: Path, module_kind: str) -> list[str]:
    """The root and owned-class rules on `Holder.group`, which ranges over `Group` and is `owned`."""
    text = DEFAULT_INSTANCE_SCHEMA.format(name_required="false", name_default="").replace(
        "imports: [linkml:types]\n",
        f"imports: [linkml:types]\nannotations: {{module_kind: {module_kind}}}\n",
        1,
    )
    root = tmp_path / "groups.yaml"
    root.write_text(
        text.replace(
            "      default_instance: 'true'\n  label",
            "      default_instance: 'true'\n      owned: 'true'\n  label",
        ),
        encoding="utf-8",
    )
    return [p for p in problems_of(root) if f"[{HardRule.DESCRIBED.value}]" in p]


def test_the_class_rules_skip_the_classes_of_a_technical_module(tmp_path: Path) -> None:
    """D-49: a technical class is never stored, so its owned class need not include `Described`."""
    assert _class_rule_problems(tmp_path, "technical") == [], "a technical class is never stored"


def test_the_class_rules_still_bind_the_classes_of_a_domain_module(tmp_path: Path) -> None:
    """D-49's counterpart: a domain module keeps the rule, so the exemption is by module kind."""
    found = _class_rule_problems(tmp_path, "domain")
    assert any("Group" in p for p in found), f"a domain module lost the Described rule: {found}"


def test_default_instance_on_a_slot_ranging_over_a_type_is_refused_naming_the_slot(
    tmp_path: Path,
) -> None:
    """TC-58: `label` ranges over string."""
    found = _default_instance_problems(tmp_path)
    assert len(found) == 1, f"one slot over a type, one problem: {found}"
    assert "label" in found[0], f"the slot is not named in {found[0]}"


def test_default_instance_on_a_class_with_a_required_slot_without_default_is_refused(
    tmp_path: Path,
) -> None:
    """TC-58: `Group.name` is required and has no `ifabsent`."""
    found = _default_instance_problems(tmp_path, name_required="true")
    named = [p for p in found if "] group:" in p]
    assert len(named) == 1, f"the slot `group` is the one to name: {found}"
    assert "name" in named[0], f"the required slot is not named in {named[0]}"


def test_default_instance_on_a_class_whose_required_slots_all_default_passes(
    tmp_path: Path,
) -> None:
    """TC-58's counterpart: a required slot with an `ifabsent` does not block the default instance."""
    found = _default_instance_problems(
        tmp_path, name_required="true", name_default=', ifabsent: "string(x)"'
    )
    assert [p for p in found if "] group:" in p] == [], f"the group has defaults: {found}"


def test_default_instance_on_a_multivalued_slot_is_refused_naming_the_slot(tmp_path: Path) -> None:
    """D-32 (3): a list of groups has no one default instance; the check names the slot `groups`."""
    text = DEFAULT_INSTANCE_SCHEMA.format(name_required="false", name_default="")
    text = text.replace("slots: [group, label]", "slots: [group, label, groups]")
    text += (
        "  groups:\n    title: Groups\n    description: Many groups.\n    range: Group\n"
        "    multivalued: true\n    annotations:\n      default_instance: 'true'\n"
    )
    root = tmp_path / "groups.yaml"
    root.write_text(text, encoding="utf-8")
    found = [p for p in problems_of(root) if f"[{HardRule.DEFAULT_INSTANCE.value}] groups:" in p]
    assert len(found) == 1, f"the multivalued slot `groups` is the one to name: {found}"
    assert "multivalued" in found[0], f"the reason is not given in {found[0]}"


def test_default_instance_over_a_class_declared_after_the_holder_is_refused(
    tmp_path: Path,
) -> None:
    """The generated module would name the range class before it exists, and fail on import."""
    text = DEFAULT_INSTANCE_SCHEMA.format(name_required="false", name_default="")
    group, holder = (
        text.split("  Holder:\n")[0].split("  Group:\n")[1],
        text.split("  Holder:\n")[1],
    )
    holder_block, slots = holder.split("slots:\n", 1)
    swapped = (
        text.split("classes:\n")[0]
        + "classes:\n  Holder:\n"
        + holder_block
        + "  Group:\n"
        + group
        + "slots:\n"
        + slots
    )
    root = tmp_path / "groups.yaml"
    root.write_text(swapped, encoding="utf-8")
    found = [p for p in problems_of(root) if f"[{HardRule.DEFAULT_INSTANCE.value}] group:" in p]
    assert len(found) == 1, f"the slot `group` is the one to name: {found}"
    assert "Holder" in found[0], f"the class that holds it is not named in {found[0]}"


def test_a_run_with_a_default_instance_over_a_type_exits_1_naming_the_slot_and_writes_nothing(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-58: `rp-generate` itself fails."""
    root = break_toy(
        "books.yaml",
        "        annotations:\n          owned: false\n",
        "        annotations:\n          owned: false\n          default_instance: 'true'\n",
    )
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "shade" in capsys.readouterr().err, "the slot is not named"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


def test_a_comment_subclass_that_narrows_a_state_slot_is_refused(break_toy: Breaker) -> None:
    """D-11 j: the slots a comment carries from a transition are the toolkit's too."""
    break_toy(
        ACTIVITIES,
        "  - rdf_persistence/model/rp_workflow\n",
        "  - rdf_persistence/model/rp_workflow\n  - rdf_persistence/model/rp_discussion\n",
    )
    root = break_toy(
        ACTIVITIES,
        "classes:\n",
        "classes:\n  Remark:\n    title: Remark\n    description: A comment of this library.\n"
        "    class_uri: lib:Remark\n    is_a: Comment\n    slot_usage:\n      from_state_iri:\n"
        "        required: true\n",
    )
    found = [p for p in problems_of(root) if f"[{HardRule.TOOLKIT_FILLED.value}] Remark:" in p]
    assert len(found) == 1, f"the narrowed state slot is the one problem of Remark: {found}"
    assert "from_state_iri" in found[0], f"the slot is not named in {found[0]}"


@pytest.mark.parametrize(
    "edit",
    [
        "    slot_usage:\n      used_resource:\n        required: true\n",
        PAYLOAD_OPTIONAL,
    ],
    ids=["a slot the toolkit does not fill", "an optional payload"],
)
def test_a_use_case_may_narrow_its_own_slots_and_declare_an_optional_payload(
    break_toy: Breaker, edit: str
) -> None:
    """TC-102's counterpart for the toolkit_filled rule."""
    root = break_toy(ACTIVITIES, SHELVE_SLOTS, SHELVE_SLOTS + edit)
    assert problems_of(root) == [], "this variant is allowed"


def test_a_reserved_segment_is_refused_with_the_fix_and_one_without_the_dash_passes(
    break_toy: Breaker,
) -> None:
    """TC-47"""
    reserved = problems_of(break_toy("books.yaml", "rp_path: books", "rp_path: rp-notes"))
    named = f"[{HardRule.RESERVED_SEGMENT.value}] Book:"
    assert any(named in p and "rp-notes" in p and "rename" in p for p in reserved), reserved
    assert problems_of(break_toy("books.yaml", "rp_path: rp-notes", "rp_path: rpnotes")) == [], (
        "a path without the dash raises no problem"
    )


SUBCLASS = """  Novel:
    title: Novel
    description: A book of fiction, which follows the workflow of its parent.
    is_a: Book
    class_uri: lib:Novel
  Shelf:
"""


def test_a_workflow_problem_carries_the_fix_hint(break_toy: Breaker) -> None:
    """PD-18: the problem says what to change."""
    root = break_toy("books.yaml", "      workflow: review\n", "")
    named = f"[{HardRule.WORKFLOW.value}] Book:"
    assert any(
        named in p and "add the annotation workflow: <name>" in p for p in problems_of(root)
    ), "a root under the mixin with no annotation is told to add one"
    root = break_toy("books.yaml", "rp_path: shelves", "rp_path: shelves\n      workflow: review")
    assert any(
        f"[{HardRule.WORKFLOW.value}] Shelf:" in p and "include UnderWorkflow" in p
        for p in problems_of(root)
    ), "an annotated root without the mixin is told to include it"


def test_a_workflow_on_a_class_that_is_no_root_says_what_to_remove_or_include(
    break_toy: Breaker,
) -> None:
    """PD-32 item 6: the hint of this branch only."""
    root = break_toy(
        "books.yaml",
        "      rp_unlabelled: true\n  Note:",
        "      rp_unlabelled: true\n      workflow: review\n  Note:",
    )
    named = f"[{HardRule.WORKFLOW.value}] Chapter:"
    [problem] = [p for p in problems_of(root) if named in p]
    assert (
        "a workflow goes only on an aggregate root (not the tenant root): "
        "remove workflow or include AggregateRoot"
    ) in problem, problem


def test_a_subclass_of_an_annotated_root_inherits_the_annotation(break_toy: Breaker) -> None:
    """TC-68"""
    root = break_toy("books.yaml", "  Shelf:\n", SUBCLASS)
    assert problems_of(root) == [], "the subclass is a root under the workflow, inherited"


def test_a_fault_names_only_the_broken_element(break_toy: Breaker) -> None:
    root = break_toy(
        "books.yaml", "    description: The International Standard Book Number of the book.\n", ""
    )
    assert len(problems_of(root)) == 1, "one planted fault must give one problem"


def test_every_rule_has_a_row_in_the_table() -> None:
    # the stored-schema rules need the target's settings, the package rules a toolkit target
    planted = {f.rule for f in FAULTS} | STORED_SCHEMA_RULES | PACKAGE_RULES
    assert planted == set(HardRule), "a hard rule has no planted fault"


def test_an_unlabelled_class_still_needs_the_described_mixin(break_toy: Breaker) -> None:
    root = break_toy(
        "books.yaml",
        "    mixins: [Described]\n    slots: [number, notes]",
        "    slots: [number, notes]",
    )
    expected = f"[{HardRule.DESCRIBED.value}] Chapter:"
    assert any(expected in p for p in problems_of(root)), "rp_unlabelled only relaxes the label"


def test_a_missing_default_prefix_names_only_elements_without_an_explicit_uri(
    break_toy: Breaker,
) -> None:
    problems = problems_of(break_toy("books.yaml", "default_prefix: lib\n", ""))
    assert len(problems) == 2, f"only the enum and the attribute have no explicit URI: {problems}"


ISBN_DESCRIPTION = "    description: The International Standard Book Number of the book.\n"


def test_the_step_reports_a_slot_without_a_description_by_name(break_toy: Breaker) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    target = GenerationTarget(
        schema_file=ROOT_SCHEMA, package="app.domain.generated", migrations="migrations"
    )
    found = generate([target], root.parent, (steps.HARD_STEP,), check=True)
    assert len(found) == 1, f"one broken slot, one line: {found}"
    line = format_problem(found[0])
    assert "hard check" in line, "the line names the step"
    assert "isbn" in line, "the line names the slot"


def test_a_run_with_a_missing_description_exits_1_and_writes_nothing(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "isbn" in capsys.readouterr().err, "the slot is not named"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


def test_the_rp_path_pattern_is_checked_when_the_schema_does_not_import_the_metamodel(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bare.yaml"
    root.write_text(
        "id: https://example.org/bare\nname: bare\nprefixes:\n  linkml: https://w3id.org/linkml/\n"
        "imports:\n  - linkml:types\nclasses:\n  Thing:\n    annotations:\n      rp_path: Not A Path\n",
        encoding="utf-8",
    )
    problems = problems_of(root)
    assert any(f"[{HardRule.ANNOTATION.value}] Thing:" in p for p in problems), problems


def _bare_schema(tmp_path: Path, classes: dict[str, str | None]) -> Path:
    """A schema that does not import the metamodel, with the given root classes (name -> rp_iri_type)."""
    body = ""
    for name, iri_type in classes.items():
        tag = f"      rp_iri_type: {iri_type}\n" if iri_type else ""
        body += (
            f"  {name}:\n    title: {name}\n    description: A {name}.\n"
            f"    is_a: AggregateRoot\n    annotations:\n      rp_path: {name.lower()}\n{tag}"
        )
    root = tmp_path / "bare.yaml"
    root.write_text(
        "id: https://example.org/bare\nname: bare\ndefault_prefix: ex\ntitle: Bare\n"
        "description: A bare schema.\nprefixes:\n  linkml: https://w3id.org/linkml/\n"
        "  ex: https://example.org/bare/\nimports:\n  - linkml:types\nclasses:\n"
        "  AggregateRoot:\n    title: Root\n    description: A root.\n    abstract: true\n" + body,
        encoding="utf-8",
    )
    return root


def _iri_type_problems(root: Path) -> list[str]:
    return [p for p in problems_of(root) if f"[{HardRule.IRI_TYPE.value}]" in p]


def test_two_classes_with_one_explicit_type_are_refused_naming_both(tmp_path: Path) -> None:
    problems = _iri_type_problems(_bare_schema(tmp_path, {"Alpha": "thing", "Beta": "thing"}))
    assert len(problems) == 1, problems
    assert "Alpha" in problems[0], problems
    assert "Beta" in problems[0], problems


def test_a_type_equal_to_another_classes_kebab_name_is_refused(tmp_path: Path) -> None:
    problems = _iri_type_problems(
        _bare_schema(tmp_path, {"OntologyFile": None, "Other": "ontology-file"})
    )
    assert len(problems) == 1, problems
    assert "OntologyFile" in problems[0], problems
    assert "Other" in problems[0], problems


@pytest.mark.parametrize("word", ["content", "graph", "parts", "access", "meta", "registry"])
def test_a_reserved_type_is_refused(tmp_path: Path, word: str) -> None:
    problems = _iri_type_problems(_bare_schema(tmp_path, {"Alpha": word}))
    assert len(problems) == 1, problems
    assert "Alpha" in problems[0], problems
    assert word in problems[0], problems


def test_a_class_named_like_a_reserved_word_is_refused(tmp_path: Path) -> None:
    assert len(_iri_type_problems(_bare_schema(tmp_path, {"Graph": None}))) == 1, (
        "a class named like a reserved word gives exactly one problem"
    )


def test_distinct_types_pass(tmp_path: Path) -> None:
    root = _bare_schema(tmp_path, {"OntologyFile": None, "Alpha": "alpha-1"})
    kinds = (HardRule.IRI_TYPE.value, HardRule.ANNOTATION.value)
    assert [p for p in problems_of(root) if p.startswith(tuple(f"[{k}]" for k in kinds))] == [], (
        "distinct types raise no problem of these kinds"
    )


def test_a_bad_iri_type_pattern_is_refused_when_the_schema_does_not_import_the_metamodel(
    tmp_path: Path,
) -> None:
    problems = problems_of(_bare_schema(tmp_path, {"Alpha": "Not A Type"}))
    assert any(f"[{HardRule.ANNOTATION.value}] Alpha:" in p for p in problems), problems


# Keys across aggregates (cross-aggregate-unique-keys PD-2): the toy's Book declares isbn_key.
KEY_SLOTS = "unique_key_slots: [isbn]"
KEY_SCOPE = "        annotations:\n          rp_unique_scope: tenant\n"
UNIQUE_KEY = f"[{HardRule.UNIQUE_KEY.value}]"


def _planted(break_toy: Breaker, module: str, old: str, new: str) -> list[str]:
    return problems_of(break_toy(module, old, new))


@pytest.mark.parametrize("slot", ["chapters", "authors", "id", "created", "binding"])
def test_a_key_over_a_slot_that_cannot_be_keyed_names_class_key_and_slot(
    break_toy: Breaker, slot: str
) -> None:
    """TC-04: an owned part, a multivalued slot, the identifier, bookkeeping, a slot Book lacks."""
    problems = _planted(break_toy, "books.yaml", KEY_SLOTS, f"unique_key_slots: [{slot}]")
    named = f"{UNIQUE_KEY} Book: unique key 'isbn_key': slot '{slot}' "
    assert any(p.startswith(named) for p in problems), problems


def test_a_scope_other_than_tenant_is_refused_naming_the_value_and_the_allowed_one(
    break_toy: Breaker,
) -> None:
    """TC-05"""
    problems = _planted(
        break_toy, "books.yaml", "rp_unique_scope: tenant", "rp_unique_scope: world"
    )
    named = f"[{HardRule.UNIQUE_KEY.value}] Book: unique key 'isbn_key': "
    assert any(p.startswith(named) and "'world'" in p and "tenant" in p for p in problems), problems


@pytest.mark.parametrize(
    ("module", "old", "slot", "cls"),
    [
        ("books.yaml", "    slots: [number, notes]\n", "number", "Chapter"),
        ("library_tenant.yaml", "    slots: [city]\n", "city", "Library"),
        ("library_access.yaml", "    is_a: TenantAccess\n", "database_name", "LibraryAccess"),
    ],
    ids=["owned-part", "tenant-root", "system-root"],
)
def test_a_key_on_a_class_that_is_no_tenant_database_root_is_refused(
    break_toy: Breaker, module: str, old: str, slot: str, cls: str
) -> None:
    """TC-06"""
    key = f"    unique_keys:\n      stray_key:\n        unique_key_slots: [{slot}]\n{KEY_SCOPE}"
    problems = _planted(break_toy, module, old, old + key)
    named = f"{UNIQUE_KEY} {cls}: unique key 'stray_key': "
    assert any(p.startswith(named) for p in problems), problems


def test_an_unscoped_key_on_a_root_is_refused_with_the_fix(break_toy: Breaker) -> None:
    """TC-07"""
    problems = _planted(break_toy, "books.yaml", KEY_SCOPE, "")
    assert any(
        p.startswith(f"{UNIQUE_KEY} Book:") and "isbn_key" in p and "rp_unique_scope: tenant" in p
        for p in problems
    ), problems


NULLS_NEED_TENANT = "consider_nulls_inequal: false needs rp_unique_scope: tenant"


@pytest.mark.parametrize(
    ("scope", "option", "refused"),
    [
        ("tenant", "false", False),
        ("world", "false", True),
        ("tenant", "true", False),
        ("tenant", None, False),
    ],
    ids=["false-at-tenant", "false-at-another-scope", "true", "unset"],
)
def test_counting_absent_values_as_equal_needs_the_tenant_scope(
    break_toy: Breaker, scope: str, option: str | None, refused: bool
) -> None:
    """TC-08: false is allowed at the tenant scope only; true or unset adds no problem."""
    line = "" if option is None else f"        consider_nulls_inequal: {option}\n"
    new = KEY_SCOPE.replace("tenant", scope) + line
    problems = _planted(break_toy, "books.yaml", KEY_SCOPE, new)
    named = f"{UNIQUE_KEY} Book: unique key 'isbn_key': {NULLS_NEED_TENANT}"
    if refused:
        assert any(p.startswith(named) for p in problems), problems
    else:
        assert problems == [], "no problem for this option at this scope"


MIXIN = """  Keyed:
    title: Keyed
    description: A mixin whose label is the key of whatever uses it.
    class_uri: lib:Keyed
    mixin: true
    unique_keys:
      label_key:
        unique_key_slots: [label]
  Chapter:
    title: Chapter
"""


def test_an_unscoped_key_a_root_only_inherits_is_not_refused(break_toy: Breaker) -> None:
    """TC-08a: Keyed types a root and an owned part; on the part it is an in-aggregate key."""
    root = break_toy("books.yaml", "  Chapter:\n    title: Chapter\n", MIXIN)
    break_toy(
        "books.yaml",
        "mixins: [AggregateRoot, Described, Tracked, UnderWorkflow]",
        "mixins: [AggregateRoot, Described, Tracked, UnderWorkflow, Keyed]",
    )
    break_toy(
        "books.yaml",
        "    mixins: [Described]\n    slots: [number, notes]",
        "    mixins: [Described, Keyed]\n    slots: [number, notes]",
    )
    assert problems_of(root) == [], "an inherited unscoped key is no root key (PD-2)"
    view = load_schema(root)
    assert "label_key" not in {k.key_name for k in aggregate_keys(view)}, (
        "Book gets no key across aggregates"
    )
    chapters = [(s.name, k.unique_key_name) for s, k in keyed_slots(view, view.get_class("Book"))]
    assert ("chapters", "label_key") in chapters, "the key stays in-aggregate on Chapter"


def test_a_run_with_a_bad_key_exits_1_naming_the_slot_and_writes_nothing(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", KEY_SLOTS, "unique_key_slots: [chapters]")
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    err = capsys.readouterr().err
    assert "Book" in err, err
    assert "isbn_key" in err, err
    assert "chapters" in err, err
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


@dataclass(frozen=True)
class ApplicationRow:
    """One PD-5 row: a schema body that breaks it and nothing else, and how its message ends."""

    name: str
    classes: str
    element: str
    ending: str


_APP = "    annotations:\n      database: application\n      rp_path: tpl\n"
_ROOT = "    is_a: AggregateRoot\n"
APPLICATION_ROWS = (
    ApplicationRow(
        "tenant-root",
        "  Tpl:\n    annotations:\n      database: application\n      graph: meta\n",
        "Tpl",
        "an application class cannot be the tenant root",
    ),
    ApplicationRow(
        "owned",
        "  Owner:\n" + _ROOT + "    annotations:\n      rp_path: owner\n    attributes:\n"
        "      part:\n        range: Tpl\n        annotations:\n          owned: true\n"
        "  Tpl:\n    annotations:\n      database: application\n",
        "Tpl",
        "an application class cannot be owned; its owner decides the database",
    ),
    ApplicationRow(
        "not-a-root",
        "  Tpl:\n    annotations:\n      database: application\n",
        "Tpl",
        "only an aggregate root can be application-level",
    ),
    ApplicationRow(
        "stored-file",
        "  StoredFile:\n    class_uri: rp:StoredFile\n    mixin: true\n  Tpl:\n"
        + _ROOT
        + "    mixins: [StoredFile]\n"
        + _APP,
        "Tpl",
        "an application class cannot be a stored file: the application space has no bucket",
    ),
    ApplicationRow(
        "shared-class-iri",
        "  Other:\n" + _ROOT + "    class_uri: ex:Same\n    annotations:\n      rp_path: other\n"
        "  Tpl:\n" + _ROOT + "    class_uri: ex:Same\n" + _APP,
        "Tpl",
        "an application class cannot share its class IRI with Other",
    ),
    ApplicationRow(
        "mixin",
        "  Tpl:\n    mixin: true\n    annotations:\n      database: application\n",
        "Tpl",
        "the database annotation is not inherited through a mixin",
    ),
)
VALID_APPLICATION = "  Tpl:\n" + _ROOT + _APP


def _annotation_problems(tmp_path: Path, classes: str) -> list[str]:
    """The ``annotation`` problems of a schema with an abstract ``AggregateRoot`` and ``classes``."""
    root = _bare_schema(tmp_path, {})
    root.write_text(root.read_text(encoding="utf-8") + classes, encoding="utf-8")
    return [p for p in problems_of(root) if p.startswith(f"[{HardRule.ANNOTATION.value}]")]


@pytest.mark.parametrize("row", APPLICATION_ROWS, ids=lambda r: r.name)
def test_an_application_class_that_breaks_a_row_gets_that_rows_problem(
    tmp_path: Path, row: ApplicationRow
) -> None:
    problems = _annotation_problems(tmp_path, row.classes)
    assert len(problems) == 1, f"first row wins, one problem: {problems}"
    assert problems[0].startswith(f"[annotation] {row.element}: "), problems
    assert problems[0].endswith(row.ending), problems


def test_every_application_row_has_a_case() -> None:
    endings = [row.ending for row in APPLICATION_ROWS]
    for message in ROWS:
        cases = [ending for ending in endings if ending.startswith(message)]
        assert len(cases) == 1, f"one case for the row {message!r}, found {cases}"
    assert len(endings) == len(ROWS), "and no case for a row the check does not define"


@pytest.mark.parametrize("tag", list(ALLOWED_ANNOTATIONS), ids=lambda t: t.value)
def test_a_value_outside_the_allowed_ones_is_refused_for_every_annotation_the_toolkit_reads(
    tmp_path: Path, tag: RpAnnotation
) -> None:
    classes = f"  Probe:\n    annotations:\n      {tag.value}: not-a-value\n"

    problems = _annotation_problems(tmp_path, classes)

    assert [p for p in problems if f"Probe: {tag.value}: 'not-a-value' is not one of" in p], (
        f"a bad {tag.value} value is not refused: {problems}"
    )


def test_a_field_name_annotation_other_than_slot_is_refused_naming_the_slot(tmp_path: Path) -> None:
    """D-52: `field_name` takes the one value `slot`."""
    tag = GenerationAnnotation.FIELD_NAME
    classes = f"  Probe:\n    annotations:\n      {tag.value}: not-a-value\n"

    problems = _annotation_problems(tmp_path, classes)

    assert [
        p for p in problems if f"Probe: {tag.value}: 'not-a-value' is not one of ('slot',)" in p
    ], f"a bad field_name value is not refused: {problems}"


def test_every_annotation_the_toolkit_reads_has_an_allowed_value_rule_or_a_pattern() -> None:
    checked = set(ALLOWED_ANNOTATIONS) | set(PATTERNED_ANNOTATIONS) | set(METAMODEL_ANNOTATIONS)

    assert checked == set(RpAnnotation), "an annotation has neither allowed values nor a pattern"


def test_a_valid_application_root_passes(tmp_path: Path) -> None:
    assert _annotation_problems(tmp_path, VALID_APPLICATION) == [], "a path and a root: no problem"


def test_an_abstract_application_class_is_skipped(tmp_path: Path) -> None:
    classes = "  Tpl:\n    abstract: true\n    annotations:\n      database: application\n"
    assert _annotation_problems(tmp_path, classes) == [], "abstract classes are not reported"


def test_an_unknown_database_lists_the_three_kinds(tmp_path: Path) -> None:
    classes = "  Tpl:\n" + _ROOT + "    annotations:\n      database: elsewhere\n      rp_path: t\n"
    problems = _annotation_problems(tmp_path, classes)
    assert len(problems) == 1, problems
    assert "('tenant', 'system', 'application')" in problems[0], problems


# ---- the migrations folder and the version (PD-1, PD-14, TC-10) -----------------------------------

REPO = Path(__file__).parents[3]
TOY_VERSION = 'version: "1"\n'


STORED_SCHEMA_RULES = {HardRule.MIGRATIONS_FOLDER, HardRule.QUOTED_VERSION}


def _stored_schema_problems(root: Path, migrations: str | None) -> list[str]:
    target = GenerationTarget(
        schema_file=ROOT_SCHEMA, package="app.domain.generated", migrations=migrations
    )
    found = generate([target], root.parent, (steps.HARD_STEP,), check=True)
    return [format_problem(p) for p in found]


def test_a_target_with_root_classes_and_no_migrations_folder_is_refused(toy_copy: Path) -> None:
    """TC-10"""
    found = _stored_schema_problems(toy_copy / ROOT_SCHEMA, None)
    assert len(found) == 1, found
    line = found[0]
    assert f"[{HardRule.MIGRATIONS_FOLDER.value}]" in line, "the rule is named"
    assert "Book" in line, "the root is named"
    assert "migrations" in line, "the setting is named"
    assert ROOT_SCHEMA in line, "the schema of the target is named"


def test_a_target_with_migrations_and_no_version_is_refused(break_toy: Breaker) -> None:
    """TC-10"""
    root = break_toy(ROOT_SCHEMA, TOY_VERSION, "")
    found = _stored_schema_problems(root, "migrations")
    assert len(found) == 1, found
    assert f"[{HardRule.QUOTED_VERSION.value}]" in found[0], "the rule is named"
    assert "version" in found[0], "the key is named"
    assert ROOT_SCHEMA in found[0], "the schema is named"


@pytest.mark.parametrize("written", ["1.10", "1", "true", "v1"])
def test_an_unquoted_version_is_refused(break_toy: Breaker, written: str) -> None:
    """TC-10: `version: 1.10` is read as 1.1, so every spelling is quoted."""
    root = break_toy(ROOT_SCHEMA, TOY_VERSION, f"version: {written}\n")
    found = _stored_schema_problems(root, "migrations")
    assert len(found) == 1, found
    assert f"[{HardRule.QUOTED_VERSION.value}]" in found[0], "the rule is named"
    assert "quoted" in found[0], "the fix is named"
    assert ROOT_SCHEMA in found[0], "the schema is named"


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("written", ["1.10", "1", "true", "v1"])
def test_a_quoted_version_passes(break_toy: Breaker, written: str, quote: str) -> None:
    root = break_toy(ROOT_SCHEMA, TOY_VERSION, f"version: {quote}{written}{quote}\n")
    assert _stored_schema_problems(root, "migrations") == [], f"{quote}{written}{quote} is quoted"


def test_a_root_schema_that_is_not_a_mapping_gives_a_problem(toy_copy: Path) -> None:
    """PD-22.10: the view was loaded before the file changed; the check reads the file."""
    view = load_schema(toy_copy / ROOT_SCHEMA)
    (toy_copy / ROOT_SCHEMA).write_text("- a\n- list\n", encoding="utf-8")
    [problem] = stored_schema_problems(view, toy_copy, Path("migrations"))
    assert problem.rule == HardRule.QUOTED_VERSION.value, "the rule is named"
    assert problem.element == ROOT_SCHEMA, "the schema is named"


def test_a_schema_with_no_source_file_gives_a_problem(toy_copy: Path) -> None:
    view = load_schema(toy_copy / ROOT_SCHEMA)
    view.schema.source_file = None
    [problem] = stored_schema_problems(view, toy_copy, Path("migrations"))
    assert problem.rule == HardRule.QUOTED_VERSION.value, "the rule is named"
    assert "source" in problem.message, "the missing file is the reason"


def test_the_toy_with_migrations_and_a_quoted_version_passes(toy_copy: Path) -> None:
    assert _stored_schema_problems(toy_copy / ROOT_SCHEMA, "migrations") == [], "the toy is stored"


def _combined_target_stores_its_migrations(project: Path) -> None:
    """Give the ``rp.yaml`` target its ``migrations`` folder; the four theme targets set none (PD-4)."""
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "openapi = false\n", 'openapi = false\nmigrations = "model/migrations"\n', 1
        ),
        encoding="utf-8",
    )


def _hard_problems_of_all(project: Path) -> list[str]:
    targets = read_targets(project / "pyproject.toml")
    found = generate(targets, project, (steps.HARD_STEP,), check=True)
    return [format_problem(p) for p in found]


def test_a_theme_target_that_generates_a_tenant_root_needs_no_migrations_folder(
    toolkit_project: Path,
) -> None:
    """E-6: the access target generates ``TenantAccess`` and sets no `migrations`: `rp.yaml` is where it is checked (PD-4)."""
    _combined_target_stores_its_migrations(toolkit_project)
    assert _hard_problems_of_all(toolkit_project) == [], "the five domain targets pass"


def test_a_theme_target_that_generates_an_aggregate_root_needs_no_migrations_folder(
    toolkit_project: Path,
) -> None:
    """E-7: the collaboration target generates ``Comment`` and sets no `migrations`."""
    _combined_target_stores_its_migrations(toolkit_project)
    found = _hard_problems_of_all(toolkit_project)
    assert [p for p in found if "rp_collaboration" in p or "Comment" in p] == [], found


def test_the_target_of_rp_yaml_still_needs_migrations_for_the_roots_of_every_theme(
    toolkit_project: Path,
) -> None:
    """PD-4: the combined target is the one that is checked, so dropping its folder is refused."""
    found = _hard_problems_of_all(toolkit_project)
    assert len(found) == 1 and "TenantAccess" in found[0], found  # noqa: PT018
    assert HardRule.MIGRATIONS_FOLDER.value in found[0], "the rule is named"


def test_a_toolkit_target_other_than_rp_yaml_that_stores_roots_without_migrations_is_still_refused(
    toolkit_project: Path,
) -> None:
    """D-5: only a target whose roots `rp.yaml` already checks may skip the stored-schema rules; a new one with its own root may not."""
    model = toolkit_project / "model"
    (model / "rp_extra.yaml").write_text(
        "id: https://meaningfy.ws/ns/rdf-persistence/extra\nname: rp_extra\n"
        "title: Extra\ndescription: A target that defines a root.\n"
        "prefixes: {rp: 'https://meaningfy.ws/ns/rdf-persistence#', linkml: 'https://w3id.org/linkml/'}\n"
        "default_prefix: rp\ndefault_range: string\n"
        "imports: [linkml:types, rp_core]\n"
        f"annotations:\n  python_package: {TOOLKIT_DOMAIN}.extra\n"
        "classes:\n  Lone:\n    title: Lone\n    description: A root.\n"
        "    mixins: [AggregateRoot]\n    attributes:\n"
        "      label: {title: Label, description: Its label.}\n",
        encoding="utf-8",
    )
    pyproject = toolkit_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + f'\n[[tool.rp-generate]]\nschema = "model/rp_extra.yaml"\npackage = "{TOOLKIT_DOMAIN}.extra"\n'
        'regenerate-command = "make generate"\nopenapi = false\n',
        encoding="utf-8",
    )
    extra = [t for t in read_targets(pyproject) if t.schema_file == "model/rp_extra.yaml"]
    found = [
        format_problem(p) for p in generate(extra, toolkit_project, (steps.HARD_STEP,), check=True)
    ]
    assert any(HardRule.MIGRATIONS_FOLDER.value in p and "Lone" in p for p in found), found


def test_a_theme_target_that_sets_migrations_keeps_the_version_rule(toolkit_project: Path) -> None:
    """D-10: the stored-schema rules are skipped only for a target without `migrations`; one that sets them is checked."""
    tenancy = toolkit_project / "model" / "rp_tenancy.yaml"
    text = tenancy.read_text(encoding="utf-8")
    tenancy.write_text(text.replace("name: rp_tenancy\n", "name: rp_tenancy\nversion: 1.10\n", 1))
    pyproject = toolkit_project / "pyproject.toml"
    entry = 'schema = "model/rp_tenancy.yaml"\n'
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            f"{entry}", f'{entry}migrations = "model/tenancy-migrations"\n', 1
        ),
        encoding="utf-8",
    )
    found = _hard_problems_of_all(toolkit_project)
    assert any(
        HardRule.QUOTED_VERSION.value in p and "rp_tenancy.yaml" in p and "quoted" in p
        for p in found
    ), found


def test_the_toolkits_seven_targets_pass_the_hard_check_with_their_own_settings() -> None:
    """TC-10: rp_service, rp_templates, rp_telemetry, rp_settings, rp_wire, rp_testkit and rp_generation need no migrations folder; rp.yaml has one.

    The name says seven; `rp_testkit` is the eighth target (PD-11), and the `iris` theme's two schemas,
    `rp_iris_services` and `rp_iris_templates`, are the ninth and the tenth (thematic-structure 3.1); the
    `persistence` theme's three (`rp_persistence_services`, `_settings`, `_adapters`) and the `migrations`
    theme's one are the eleventh to the fourteenth (4.2). `rp_wire` is the `access` theme's
    `rp_access_adapters` from stage 5, beside `rp_access_services`, `rp_access_settings` and the
    `tenancy` theme's `rp_tenancy_services`: seventeen in all (5.1). The `events` theme's two
    (`rp_events_services`, `rp_events_settings`) and the `collaboration` theme's one
    (`rp_collaboration_services`) make twenty (6.1). The four theme targets of the domain model
    (`rp_tenancy`, `rp_provenance`, `rp_files`, `rp_collaboration`; domain-model-per-theme 2.1) make
    twenty-four.
    """
    targets = read_targets(REPO / "pyproject.toml")
    assert len(targets) == 24, [t.schema_file for t in targets]
    found = generate(targets, REPO, (steps.HARD_STEP,), check=True)
    assert [format_problem(p) for p in found] == [], "the toolkit's 24 targets raise no problem"


def _flag_problems(tmp_path: Path, written: str) -> list[str]:
    """The problems about `group` when its `default_instance` annotation is written as ``written``."""
    text = DEFAULT_INSTANCE_SCHEMA.format(name_required="false", name_default="").replace(
        "default_instance: 'true'\n  label", f"default_instance: {written}\n  label", 1
    )
    root = tmp_path / "groups.yaml"
    root.write_text(text, encoding="utf-8")
    return [p for p in problems_of(root) if "group" in p]


@pytest.mark.parametrize("written", ["true", "'true'", "'True'", "false", "'false'", "'False'"])
def test_default_instance_reads_a_boolean_in_either_form_without_a_problem(
    tmp_path: Path, written: str
) -> None:
    """D-55 (5): YAML `true`, `'true'` and `'True'` are the flag, `false` is off; none is refused."""
    assert _flag_problems(tmp_path, written) == [], f"{written} is a boolean"


@pytest.mark.parametrize("written", ["'yes'", "1", "'maybe'", "'on'"])
def test_default_instance_that_is_not_a_boolean_is_refused_naming_the_slot(
    tmp_path: Path, written: str
) -> None:
    """D-55 (5): a value that is not a boolean is no silent off; the problem names `group`."""
    found = _flag_problems(tmp_path, written)
    assert any("default_instance" in p and "group" in p for p in found), f"{written}: {found}"


# ---- where the metamodel's classes live (DEC-7, PD-6, TC-35 to TC-38) ------------------------------

PACKAGE_CHECK = "rdf_persistence_generation.checks.python_package"
MODEL_COPY = "model"
PACKAGE_RULES = {HardRule.PYTHON_PACKAGE, HardRule.PYTHON_PACKAGE_MISMATCH}  # need a toolkit target


@pytest.fixture
def toolkit_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the metamodel's folder that the generator treats as the toolkit's own."""
    shutil.copytree(
        METAMODEL.parent, tmp_path / MODEL_COPY, ignore=shutil.ignore_patterns("migrations")
    )
    monkeypatch.setattr(f"{PACKAGE_CHECK}.TOOLKIT_ROOTS", (tmp_path.resolve(),))
    monkeypatch.setattr("rdf_persistence_generation.steps.TOOLKIT_ROOTS", (tmp_path.resolve(),))
    (tmp_path / "pyproject.toml").write_text(toolkit_domain_targets(), encoding="utf-8")
    return tmp_path


def _rewrite(base: Path, module: str, old: str, new: str) -> None:
    path = base / MODEL_COPY / f"{module}.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {module}: the planted fault would plant nothing"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _package_rules() -> set[str]:
    return {rule.value for rule in PACKAGE_RULES}


def _package_problems(base: Path) -> list[str]:
    """The problems of the two python_package rules of the toolkit target over the copy."""
    target = GenerationTarget(schema_file=f"{MODEL_COPY}/rp.yaml", package=TOOLKIT_DOMAIN)
    found = generate([target], base, (steps.HARD_STEP,), check=True)
    return [format_problem(p) for p in found if p.rule in _package_rules()]


def test_the_metamodel_copy_passes_both_python_package_rules(toolkit_copy: Path) -> None:
    """The control of TC-35 and TC-36: the copy as it is raises no problem."""
    assert _package_problems(toolkit_copy) == [], "the unbroken copy"


def test_a_toolkit_module_without_python_package_is_refused_naming_it(toolkit_copy: Path) -> None:
    """TC-35"""
    _rewrite(
        toolkit_copy, "rp_files", f"python_package: {theme_package('files')}", "unrelated: note"
    )
    [line] = _package_problems(toolkit_copy)
    assert f"[{HardRule.PYTHON_PACKAGE.value}]" in line, "rule (a) is named"
    assert "rp_files" in line, "the module is named"
    assert "python_package" in line, "the missing annotation is named"


def test_a_module_in_another_package_than_its_target_is_refused_naming_both(
    toolkit_copy: Path,
) -> None:
    """TC-36: the root's package is the reference, so a root that disagrees with its target is the case."""
    _rewrite(toolkit_copy, "rp", f"python_package: {TOOLKIT_DOMAIN}", "python_package: x.generated")
    lines = _package_problems(toolkit_copy)
    [line] = [line for line in lines if "rp:" in line]
    assert f"[{HardRule.PYTHON_PACKAGE_MISMATCH.value}]" in line, "rule (b) is named"
    for named in ("rp", "x.generated", TOOLKIT_DOMAIN):
        assert named in line, f"{named} is named"


def test_an_application_run_never_checks_the_package_of_its_target(toy_copy: Path) -> None:
    """TC-37: the toy is no toolkit schema, has no python_package, and its package is its own."""
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.domain.generated")
    found = generate([target], toy_copy, (steps.HARD_STEP,), check=True)
    assert [p for p in found if p.rule in _package_rules()] == [], (
        "a consumer's run reads, never checks"
    )


TOOLKIT_PACKAGES = [
    ("rdf_persistence/model/rp_core.yaml", TOOLKIT_DOMAIN),
    ("rdf_persistence/model/rp_access.yaml", theme_package("access")),
    ("rdf_persistence/model/rp_tenancy.yaml", theme_package("access")),
    ("rdf_persistence/model/rp_provenance.yaml", theme_package("provenance")),
    ("rdf_persistence/model/rp_files.yaml", theme_package("files")),
    ("rdf_persistence/model/rp_collections.yaml", theme_package("collaboration")),
    ("rdf_persistence/model/rp_discussion.yaml", theme_package("collaboration")),
    ("rdf_persistence/model/rp_workflow.yaml", theme_package("collaboration")),
    ("rdf_persistence/model/rp_collaboration.yaml", theme_package("collaboration")),
    (
        "rdf_persistence/model/technical/access/rp_access_adapters.yaml",
        "rdf_persistence.access.adapters.generated",
    ),
    (
        "rdf_persistence/model/technical/access/rp_access_services.yaml",
        "rdf_persistence.access.services.generated",
    ),
    (
        "rdf_persistence/model/technical/access/rp_access_settings.yaml",
        "rdf_persistence.access.services.generated.settings",
    ),
    (
        "rdf_persistence/model/technical/tenancy/rp_tenancy_services.yaml",
        "rdf_persistence.tenancy.services.generated",
    ),
    (
        "rdf_persistence/model/technical/events/rp_events_services.yaml",
        "rdf_persistence.events.services.generated",
    ),
    (
        "rdf_persistence/model/technical/events/rp_events_settings.yaml",
        "rdf_persistence.events.services.generated.settings",
    ),
    (
        "rdf_persistence/model/technical/collaboration/rp_collaboration_services.yaml",
        "rdf_persistence.collaboration.services.generated",
    ),
    (
        "rdf_persistence/model/technical/api/rp_api_entrypoints.yaml",
        "rdf_persistence.api.entrypoints.generated",
    ),
    (
        "rdf_persistence/model/technical/api/rp_api_settings.yaml",
        "rdf_persistence.api.entrypoints.generated.settings",
    ),
    (
        "rdf_persistence/model/technical/testkit/rp_testkit.yaml",
        "rdf_persistence.testkit.generated",
    ),
    ("rdf_persistence_generation/model/rp_generation.yaml", "rdf_persistence_generation.generated"),
]


@pytest.mark.parametrize(("schema", "expected"), TOOLKIT_PACKAGES)
def test_a_toolkit_schema_says_the_package_it_is_generated_into(schema: str, expected: str) -> None:
    """TC-38"""
    module = load_schema(REPO / schema).schema
    found = annotation_text(module, GenerationAnnotation.PYTHON_PACKAGE)
    assert found == expected, f"python_package of {schema}"


def test_the_public_package_is_named_by_the_root_of_the_metamodel() -> None:
    """TC-33's source: rp.yaml carries public_package."""
    module = load_schema(METAMODEL).schema
    assert annotation_text(module, GenerationAnnotation.PUBLIC_PACKAGE) == "rdf_persistence", (
        "public_package of rp.yaml"
    )


def test_every_toolkit_target_is_generated_into_the_package_its_modules_say() -> None:
    """TC-38: each [[tool.rp-generate]] entry of the toolkit's pyproject raises neither rule."""
    targets = read_targets(REPO / "pyproject.toml")
    found = generate(targets, REPO, (steps.HARD_STEP,), check=True)
    assert [format_problem(p) for p in found if p.rule in _package_rules()] == [], (
        "no package problem"
    )
