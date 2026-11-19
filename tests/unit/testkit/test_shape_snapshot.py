"""The model-shape snapshot: a model change fails until `make refresh-snapshot` acknowledges it (PD-27)."""

import importlib
import json
import os
import pkgutil
import shutil
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from rdf_persistence.testkit.generated.rp_testkit import ClassShape, FieldFlags, SlotShape
from rdf_persistence.testkit.model_shape import model_schema_diff, model_shape_diff
from rdf_persistence.testkit.shape_snapshot import (
    class_shapes,
    read_snapshot,
    snapshot_diff,
    write_snapshot,
)

ROOT = Path(__file__).parents[3]
FIXTURES = ROOT / "tests" / "fixtures"
SNAPSHOT = FIXTURES / "model-shape.yaml"
METAMODEL = ROOT / "rdf_persistence" / "model" / "rp.yaml"
TOY = FIXTURES / "library" / "library.yaml"
SERVICE = ROOT / "rdf_persistence" / "model" / "technical" / "api" / "rp_api_entrypoints.yaml"
TESTKIT = ROOT / "rdf_persistence" / "model" / "technical" / "testkit" / "rp_testkit.yaml"
TOY_PACKAGE = "tests.fixtures.library.domain.generated"
# The metamodel's classes generate into one package per theme (domain-model-per-theme DEC-1).
METAMODEL_PACKAGE = tuple(
    f"rdf_persistence.{theme}.domain.generated"
    for theme in ("core", "access", "provenance", "files", "collaboration")
)
SERVICE_PACKAGE = "rdf_persistence.api.entrypoints.generated"
IRIS = ROOT / "rdf_persistence" / "model" / "technical" / "iris" / "rp_iris_services.yaml"
IRIS_PACKAGE = "rdf_persistence.iris.services.generated"
PERSISTENCE = (
    ROOT
    / "rdf_persistence"
    / "model"
    / "technical"
    / "persistence"
    / "rp_persistence_services.yaml"
)
PERSISTENCE_PACKAGE = "rdf_persistence.persistence.services.generated"
MIGRATIONS = (
    ROOT / "rdf_persistence" / "model" / "technical" / "migrations" / "rp_migrations_services.yaml"
)
MIGRATIONS_PACKAGE = "rdf_persistence.migrations.services.generated"
ACCESS = ROOT / "rdf_persistence" / "model" / "technical" / "access" / "rp_access_services.yaml"
ACCESS_PACKAGE = "rdf_persistence.access.services.generated"
TENANCY = ROOT / "rdf_persistence" / "model" / "technical" / "tenancy" / "rp_tenancy_services.yaml"
TENANCY_PACKAGE = "rdf_persistence.tenancy.services.generated"
EVENTS = ROOT / "rdf_persistence" / "model" / "technical" / "events" / "rp_events_services.yaml"
EVENTS_PACKAGE = "rdf_persistence.events.services.generated"
COLLABORATION = (
    ROOT
    / "rdf_persistence"
    / "model"
    / "technical"
    / "collaboration"
    / "rp_collaboration_services.yaml"
)
COLLABORATION_PACKAGE = "rdf_persistence.collaboration.services.generated"
TESTKIT_PACKAGE = "rdf_persistence.testkit.generated"
REFRESH = "RP_REFRESH_SNAPSHOT"


def slot(
    name: str, required: bool = False, multivalued: bool = False, range: str = "string"
) -> SlotShape:
    return SlotShape(name=name, required=required, multivalued=multivalued, range=range)


def shape(name: str, *slots: SlotShape) -> ClassShape:
    return ClassShape(class_name=name, slots=list(slots))


def generated_models(package: str | tuple[str, ...]) -> list[type[BaseModel]]:
    """The pydantic classes each module of a generated package (or of each of several) declares itself."""
    if isinstance(package, tuple):
        return [model for one in package for model in generated_models(one)]
    root = importlib.import_module(package)
    modules = [
        importlib.import_module(f"{package}.{info.name}")
        for info in pkgutil.iter_modules(root.__path__)
    ]
    return [
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == module.__name__
        and value.__name__ not in {"ConfiguredBaseModel", "LinkMLMeta"}
    ]


# --- the snapshot ---------------------------------------------------------------------------


@pytest.fixture
def toy_copy(tmp_path: Path) -> Path:
    """The toy library's schemas copied to ``tmp_path``; returns the folder."""
    folder = tmp_path / "library"
    shutil.copytree(TOY.parent, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    return folder


def test_the_current_shapes_equal_the_reviewed_snapshot() -> None:
    # every served schema, so a class of a theme the service schema does not import is in the snapshot too
    current = class_shapes(
        [
            METAMODEL,
            IRIS,
            PERSISTENCE,
            MIGRATIONS,
            ACCESS,
            TENANCY,
            EVENTS,
            COLLABORATION,
            SERVICE,
            TOY,
        ]
    )
    if os.environ.get(REFRESH):
        write_snapshot(SNAPSHOT, current)
    reviewed = read_snapshot(SNAPSHOT)
    lines = snapshot_diff(reviewed, current)
    assert not lines, (
        "the model changed since the snapshot was reviewed:\n  "
        + "\n  ".join(lines)
        + "\nrun `make refresh-snapshot` and review the diff"
    )


def test_a_slot_added_to_the_toy_schema_is_named_by_the_diff(toy_copy: Path) -> None:
    books = toy_copy / "books.yaml"
    text = books.read_text(encoding="utf-8")
    anchor = "    slots: [isbn, authors, published, genre, chapters, shelf, sequel_of]"
    assert anchor in text, "the planted fault would plant nothing"
    books.write_text(
        text.replace(
            anchor, "    slots: [isbn, authors, published, genre, chapters, shelf, sequel_of, city]"
        ),
        encoding="utf-8",
    )
    changed = class_shapes([METAMODEL, toy_copy / "library.yaml"])
    lines = snapshot_diff(read_snapshot(SNAPSHOT), changed)
    assert lines, "a model change must differ from the snapshot"
    assert any("Book" in line and "city" in line for line in lines), (
        f"no line names Book.city: {lines}"
    )


# --- class_shapes ---------------------------------------------------------------------------


def test_class_shapes_are_sorted_by_class_and_slot_name() -> None:
    shapes = class_shapes([TOY])
    names = [s.class_name for s in shapes]
    assert names == sorted(names), "classes must be in name order"
    for each in shapes:
        slot_names = [s.name for s in each.slots or []]
        assert slot_names == sorted(slot_names), f"{each.class_name}: slots must be in name order"


def test_class_shapes_include_mixins_and_the_imported_metamodel_classes() -> None:
    names = {s.class_name for s in class_shapes([TOY])}
    assert {"Book", "Described", "AggregateRoot", "TenantAccess"} <= names, (
        "mixins and imports are shapes too"
    )


def test_class_shapes_of_several_schemas_list_a_shared_class_once() -> None:
    names = [s.class_name for s in class_shapes([METAMODEL, TOY])]
    assert len(names) == len(set(names)), "a class in two closures must appear once"


def test_class_shapes_read_required_multivalued_and_range_from_induced_slots() -> None:
    book = next(s for s in class_shapes([TOY]) if s.class_name == "Book")
    by_name = {s.name: s for s in book.slots or []}
    assert by_name["id"].required, "id is required"
    assert by_name["authors"].multivalued, "authors is multivalued"
    assert not by_name["isbn"].required, "an unset required is False, not None"
    assert by_name["chapters"].range == "Chapter", "range is the name of the target class"


def test_class_shapes_are_deterministic() -> None:
    assert class_shapes([TOY]) == class_shapes([TOY]), "two runs must agree"


# --- the file ---------------------------------------------------------------------------------


def test_a_snapshot_survives_a_write_and_a_read(tmp_path: Path) -> None:
    shapes = [
        shape("A", slot("x", required=True), slot("y", multivalued=True, range="integer")),
        shape("B"),
    ]
    path = tmp_path / "s.yaml"
    write_snapshot(path, shapes)
    assert read_snapshot(path) == shapes, "the file must round-trip"


# --- snapshot_diff ------------------------------------------------------------------------------

OLD = [shape("A", slot("x"), slot("y", required=True)), shape("B", slot("z"))]


@pytest.mark.parametrize(
    ("new", "expected"),
    [
        pytest.param(OLD, [], id="same"),
        pytest.param(OLD + [shape("C")], ["class added: C"], id="class-added"),
        pytest.param(OLD[:1], ["class removed: B"], id="class-removed"),
        pytest.param(
            [shape("A", slot("x"), slot("y", required=True), slot("n")), OLD[1]],
            ["slot added: A.n (required=False, multivalued=False, range=string)"],
            id="slot-added",
        ),
        pytest.param(
            [shape("A", slot("x")), OLD[1]],
            ["slot removed: A.y"],
            id="slot-removed",
        ),
        pytest.param(
            [shape("A", slot("x"), slot("y", required=False, range="integer")), OLD[1]],
            ["slot changed: A.y: required True -> False, range string -> integer"],
            id="slot-changed",
        ),
        pytest.param(
            [shape("A", slot("x", multivalued=True), slot("y", required=True)), OLD[1]],
            ["slot changed: A.x: multivalued False -> True"],
            id="multivalued-changed",
        ),
    ],
)
def test_snapshot_diff_describes_each_kind_of_change(
    new: list[ClassShape], expected: list[str]
) -> None:
    assert snapshot_diff(OLD, new) == expected, (
        "the diff lines must name the class, the slot and the change"
    )


# --- the model-shape test (PD-27 item 5) -------------------------------------------------------


@pytest.mark.parametrize(
    ("schema", "package"),
    [
        pytest.param(METAMODEL, METAMODEL_PACKAGE, id="metamodel"),
        pytest.param(TOY, TOY_PACKAGE, id="toy"),
        pytest.param(IRIS, IRIS_PACKAGE, id="iris"),
        pytest.param(PERSISTENCE, PERSISTENCE_PACKAGE, id="persistence"),
        pytest.param(MIGRATIONS, MIGRATIONS_PACKAGE, id="migrations"),
        pytest.param(ACCESS, ACCESS_PACKAGE, id="access"),
        pytest.param(TENANCY, TENANCY_PACKAGE, id="tenancy"),
        pytest.param(EVENTS, EVENTS_PACKAGE, id="events"),
        pytest.param(COLLABORATION, COLLABORATION_PACKAGE, id="collaboration"),
        pytest.param(SERVICE, SERVICE_PACKAGE, id="service"),
        pytest.param(TESTKIT, TESTKIT_PACKAGE, id="testkit"),
    ],
)
def test_generated_classes_match_the_induced_slots(schema: Path, package: str) -> None:
    # the service schema imports the served schemas below it, whose classes are generated in their packages
    models = (
        generated_models(package)
        + generated_models(METAMODEL_PACKAGE)
        + generated_models(IRIS_PACKAGE)
        + generated_models(PERSISTENCE_PACKAGE)
        + generated_models(MIGRATIONS_PACKAGE)
        + generated_models(ACCESS_PACKAGE)
        + generated_models(TENANCY_PACKAGE)
        + generated_models(EVENTS_PACKAGE)
        + generated_models(COLLABORATION_PACKAGE)
    )
    shapes = class_shapes([schema])
    own = {m.__name__ for m in generated_models(package)}
    assert own, "the scan found no generated class"
    assert own <= {s.class_name for s in shapes}, "every generated class has a shape"
    assert model_shape_diff(shapes, models) == [], "generated code differs from the current schema"


def toy_models_and_shapes() -> tuple[list[ClassShape], list[type[BaseModel]]]:
    return class_shapes([TOY]), generated_models(TOY_PACKAGE) + generated_models(METAMODEL_PACKAGE)


def test_a_shape_with_a_slot_removed_is_detected() -> None:
    shapes, models = toy_models_and_shapes()
    book = next(s for s in shapes if s.class_name == "Book")
    book.slots = [s for s in book.slots or [] if s.name != "isbn"]
    lines = model_shape_diff(shapes, models)
    assert any("Book.isbn" in ln for ln in lines), f"missed the removed slot: {lines}"


def test_a_changed_required_flag_is_detected() -> None:
    shapes, models = toy_models_and_shapes()
    book = next(s for s in shapes if s.class_name == "Book")
    next(s for s in book.slots or [] if s.name == "isbn").required = True
    lines = model_shape_diff(shapes, models)
    assert any("Book.isbn" in ln and "required" in ln for ln in lines), f"missed the flag: {lines}"


def test_a_changed_multivalued_flag_is_detected() -> None:
    shapes, models = toy_models_and_shapes()
    book = next(s for s in shapes if s.class_name == "Book")
    next(s for s in book.slots or [] if s.name == "authors").multivalued = False
    lines = model_shape_diff(shapes, models)
    assert any("Book.authors" in ln and "multivalued" in ln for ln in lines), (
        f"missed the flag: {lines}"
    )


def test_a_shape_without_a_generated_class_is_detected() -> None:
    shapes, models = toy_models_and_shapes()
    lines = model_shape_diff([*shapes, shape("Ghost", slot("x"))], models)
    assert any("Ghost" in ln for ln in lines), f"missed the missing class: {lines}"


def toy_components() -> dict[str, dict]:
    path = FIXTURES / "library" / "domain" / "generated" / "openapi-components.json"
    return json.loads(path.read_text(encoding="utf-8"))["schemas"]


class Doc(BaseModel):
    id: str
    description: str = Field(...)


def test_the_toy_python_and_json_schema_agree_on_what_is_required() -> None:
    models = generated_models(TOY_PACKAGE) + generated_models(METAMODEL_PACKAGE)
    assert model_schema_diff(toy_components(), models) == [], "Python and JSON Schema disagree"


def test_a_required_field_the_json_schema_leaves_optional_is_detected() -> None:
    components = {"Doc": {"properties": {"id": {}, "description": {}}, "required": ["id"]}}
    assert model_schema_diff(components, [Doc]) == [
        "required differs: Doc.description: required True in code, False in schema"
    ], "one line naming the class and slot"


def test_an_optional_field_the_json_schema_requires_is_detected() -> None:
    class OptionalDoc(BaseModel):
        id: str
        description: str | None = None

    components = {
        "OptionalDoc": {
            "properties": {"id": {}, "description": {}},
            "required": ["id", "description"],
        }
    }
    assert model_schema_diff(components, [OptionalDoc]) == [
        "required differs: OptionalDoc.description: required False in code, True in schema"
    ], "the reverse direction is caught too"


def test_a_field_absent_from_the_component_is_skipped() -> None:
    components = {"Doc": {"properties": {"id": {}}, "required": ["id"]}}
    assert model_schema_diff(components, [Doc]) == [], "internal slots are not compared"


def test_an_unlabelled_class_does_not_require_its_label_in_the_json_schema() -> None:
    assert "label" not in toy_components()["Chapter"].get("required", []), "PD-8"


def test_the_flags_a_field_is_compared_by_are_a_generated_record() -> None:
    """PD-11: `FieldFlags` (required, multivalued) is generated, not a dict of two booleans."""
    assert list(FieldFlags.model_fields) == ["required", "multivalued"], "the two flags, in order"
    assert FieldFlags(required=True, multivalued=False) != FieldFlags(
        required=True, multivalued=True
    ), "a flag that differs makes the records differ"
