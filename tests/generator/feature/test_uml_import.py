"""Steps of ``uml_import.feature``: ``rp-uml2linkml`` run on a ``.qea`` built in ``tmp_path`` (IT-3).

Each scenario carries its spec-delta scenario in a ``# spec:`` comment. A Given builds a small Enterprise
Architect model with ``QeaBuilder``; the When calls ``cli.main`` as the command line does; the Thens read
the written YAML, the report and the standard error, and one hands the output to ``rp-generate``'s checks.
"""

import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence.access.services.access import load_role_definitions
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.steps import BOUNDARY_STEP, LINT_STEP
from rdf_persistence_generation.uml.cli import main
from tests.generator.uml_library_stage2 import BOX, INSIDE, write_prefixes
from tests.generator.uml_qea import QeaBuilder

scenarios("uml_import.feature")

ROOT_NAME = "app"
LIBRARY_MODULE = f"{ROOT_NAME}_library"
PACKAGE = "uml_app"
PYPROJECT = f"""\
[tool.rp-generate]
schema = "{ROOT_NAME}.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""
TOOLKIT_NAMESPACE = "https://meaningfy.ws/ns/rdf-persistence#"
COUNTS = {"no": 0, "one": 1}
NONE = "none"


class World:
    """What one scenario has built and seen so far."""

    def __init__(self, folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self.folder = folder
        self.builder = QeaBuilder(folder / "model.qea")
        self.model = self.builder.package("MODEL")
        self.library = self.builder.package("library", parent=self.model, note="The library.")
        self.ids: dict[str, int] = {}
        self.qea: Path | None = None
        self.code: int | None = None
        self.capsys = capsys
        self.out = folder / "out"
        self.again = folder / "again"

    def prefixes(self) -> Path:
        """The library's prefixes plus ``rp``, which a drawn toolkit class (``rp:RoleDefinition``) needs."""
        path = write_prefixes(self.folder)
        path.write_text(
            path.read_text(encoding="utf-8") + f"  rp: {TOOLKIT_NAMESPACE}\n", encoding="utf-8"
        )
        return path

    def convert(self, out: Path, *options: str) -> None:
        self.qea = self.qea or self.builder.finish()
        self.code = main(
            [
                str(self.qea),
                "--package",
                "MODEL",
                "--prefixes",
                str(self.prefixes()),
                "--out",
                str(out),
                "--root-name",
                ROOT_NAME,
                *options,
            ]
        )

    def module(self, name: str = LIBRARY_MODULE) -> dict:
        return yaml.safe_load((self.out / f"{name}.yaml").read_text(encoding="utf-8"))

    def klass(self, name: str, module: str = LIBRARY_MODULE) -> dict:
        return self.module(module)["classes"][name]

    def report(self) -> list[list[str]]:
        text = (self.out / f"{ROOT_NAME}.uml-report.txt").read_text(encoding="utf-8")
        return [line.split("\t") for line in text.splitlines()]


@pytest.fixture
def world(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> World:
    """The scenario's state; it asks for ``capsys`` here so the capture is on before the When runs."""
    return World(tmp_path, capsys)


def _book(world: World, *, stereotype: str | None = None, note: str | None = "A book.") -> int:
    book = world.builder.cls(world.library, "lib:Book", stereotype=stereotype, note=note)
    world.ids["book"] = book
    return book


def _chapter(world: World) -> int:
    world.ids["chapter"] = world.builder.cls(world.library, "lib:Chapter", note="A chapter.")
    return world.ids["chapter"]


def _chapters(world: World, card: str | None, **options: object) -> int:
    return world.builder.association(
        world.ids["book"],
        world.ids["chapter"],
        "lib:chapters",
        card,
        note="The chapters.",
        **options,
    )


# --- Given ----------------------------------------------------------------------------------------------


@given("a library package where the book is a root that owns its chapters in one boundary")
def _root_with_part(world: World) -> None:
    book, chapter = _book(world, stereotype="root"), _chapter(world)
    world.builder.attribute(book, "dct:title", "xsd:string", "1", "1", note="The title.")
    _chapters(world, "1..*")
    world.builder.boundary(diagram=1, rect=BOX, members=[])
    world.builder.place(1, book, INSIDE)
    world.builder.place(1, chapter, (10, -10, 60, -40))


@given("two packages whose classes refer to each other")
def _cycle(world: World) -> None:
    builder = world.builder
    books = builder.package("books", parent=world.model, note="The books.")
    shelves = builder.package("shelves", parent=world.model, note="The shelves.")
    book = builder.cls(books, "lib:Book", stereotype="root", note="A book on a shelf.")
    shelf = builder.cls(shelves, "lib:Shelf", stereotype="root", note="A shelf with a book.")
    builder.association(book, shelf, "lib:shelf", "0..1", note="Its shelf.")
    builder.association(shelf, book, "lib:featured", "0..1", note="The featured book.")


@given("a book class with no note")
def _book_without_note(world: World) -> None:
    _book(world, note=None)


@given(parsers.parse('a book with an association to chapters whose multiplicity is "{card}"'))
def _multiplicity(world: World, card: str) -> None:
    _book(world)
    _chapter(world)
    _chapters(world, None if card == NONE else card)


@given("a book that depends on an enumeration with no literals")
def _empty_enumeration(world: World) -> None:
    book = _book(world)
    language = world.builder.cls(
        world.library, "lib:Language", object_type="Enumeration", note="The languages."
    )
    world.builder.dependency(book, language, "lib:language", note="Its language.")


@given(parsers.parse('a book with an attribute typed "{declared}"'))
def _typed_attribute(world: World, declared: str) -> None:
    book = _book(world)
    world.builder.attribute(book, "lib:summary", declared, "0", "1", note="Its summary.")


@given(
    parsers.parse(
        'a book associated to chapters in the direction "{direction}" with a source role "{role}"'
    )
)
def _direction(world: World, direction: str, role: str) -> None:
    _book(world)
    _chapter(world)
    connector = _chapters(world, "0..*", direction=direction)
    world.qea = world.builder.finish()
    if role != NONE:
        with sqlite3.connect(world.qea) as db:
            db.execute(
                "UPDATE t_connector SET SourceRole = ? WHERE Connector_ID = ?",
                (f"lib:{role}", connector),
            )


@given(parsers.parse('a class "{name}" stereotyped "{stereotype}"'))
def _stereotyped(world: World, name: str, stereotype: str) -> None:
    world.builder.cls(world.library, f"lib:{name}", stereotype=stereotype, note=f"The {name}.")


@given("a book and a chapter joined by an association class")
def _association_class(world: World) -> None:
    _book(world)
    _chapter(world)
    _chapters(world, "0..*", sub_type="Class")


@given(
    parsers.parse(
        'a loan that is a root tagged "{mixins}" and "{path}" with a started time of 1..1'
    )
)
def _loan(world: World, mixins: str, path: str) -> None:
    loan = world.builder.cls(world.library, "lib:Loan", stereotype="root", note="A book lent.")
    for written in (mixins, path):
        name, value = written.split("=", 1)
        world.builder.tag(loan, name, value)
    world.builder.attribute(
        loan, "prov:startedAtTime", "xsd:dateTime", "1", "1", note="When it started."
    )


@given(parsers.parse('a book root tagged "{written}"'))
def _tagged_book(world: World, written: str) -> None:
    name, value = written.split("=", 1)
    world.builder.tag(_book(world, stereotype="root"), name, value)


@given(
    parsers.parse(
        'a book root with the attribute "{name}" of type "{declared}" and multiplicity 1..1'
    )
)
def _identified_book(world: World, name: str, declared: str) -> None:
    world.builder.attribute(
        _book(world, stereotype="root"), name, declared, "1", "1", note="Its catalogue number."
    )


@given('a book associated to a loan in the package "circulation"')
def _excluded_loan(world: World) -> None:
    book = _book(world)
    circulation = world.builder.package("circulation", parent=world.model, note="The loans.")
    loan = world.builder.cls(circulation, "lib:Loan", note="A loan.")
    world.builder.association(book, loan, "lib:loan", "0..1", note="Its loan.")


def _role_object(world: World, name: str, role: str, level: str, actions: str) -> int:
    """An Object classified by the drawn ``rp:RoleDefinition``, its run state holding role, level and actions."""
    if "role_definition" not in world.ids:
        _book(world)  # the package also draws a domain class, as a real model does
        world.ids["role_definition"] = world.builder.cls(world.library, "rp:RoleDefinition")
    run_state = "".join(
        f"@VAR;Variable={variable};Value={value};Op==;@ENDVAR;"
        for variable, value in (("role", role), ("level", level), ("actions", actions))
    )
    return world.builder.object_(
        world.library, name, world.ids["role_definition"], run_state=run_state
    )


@given("three role definition objects with valid run-state values")
def _three_roles(world: World) -> None:
    _role_object(world, "librarian", "librarian", "tenant", "read,modify,delete,administer")
    _role_object(world, "member", "member", "tenant", "read,annotate")
    _role_object(world, "reader", "reader", "tenant", "read")


@given(parsers.parse('a role definition object "{name}" with the level "{level}"'))
def _role_with_level(world: World, name: str, level: str) -> None:
    _role_object(world, name, name, level, "read")


# --- When -----------------------------------------------------------------------------------------------


@when("the model is converted")
def _converted(world: World) -> None:
    world.convert(world.out)


@when("the model is converted again")
def _converted_again(world: World) -> None:
    world.convert(world.again)


@when(parsers.parse('the model is converted leaving out the package "{package}"'))
def _converted_without(world: World, package: str) -> None:
    world.convert(world.out, "--exclude-package", package)


# --- Then: the outcome ------------------------------------------------------------------------------------


@then("the conversion succeeds")
def _succeeds(world: World) -> None:
    assert world.code == 0, "the command must exit 0"


@then(parsers.parse('the conversion fails naming "{first}" and "{second}"'))
def _fails(world: World, first: str, second: str) -> None:
    error = world.capsys.readouterr().err
    assert world.code == 1, "the command must exit 1, the model having problems"
    assert first in error, f"the problems must name {first}: {error}"
    assert second in error, f"the problems must say {second}: {error}"


@then("nothing is written")
def _nothing_written(world: World) -> None:
    assert not world.out.exists() or not list(world.out.iterdir()), "no file may be written"


@then("the second output is byte-identical to the first")
def _identical(world: World) -> None:
    first = {file.name: file.read_bytes() for file in sorted(world.out.iterdir())}
    second = {file.name: file.read_bytes() for file in sorted(world.again.iterdir())}
    assert second == first, "a second conversion of an unchanged model must write the same bytes"


# --- Then: the classes and slots -----------------------------------------------------------------------


@then(parsers.parse('the book is an aggregate root with the path "{path}"'))
def _root(world: World, path: str) -> None:
    book = world.klass("Book")
    assert "AggregateRoot" in book["mixins"], "the book has the aggregate-root mixin"
    assert book["annotations"]["rp_path"]["value"] == path, "the book has its path"


@then("the book's chapters slot is owned and multivalued")
def _owned(world: World) -> None:
    slot = world.module()["slots"]["chapters"]
    assert slot["annotations"]["owned"]["value"] == "true", "the chapters are owned"
    assert slot["multivalued"] is True, "there are many chapters"


@then("the generator's lint and boundary checks accept the output")
def _accepted(world: World) -> None:
    project = world.folder / "project"
    shutil.copytree(world.out, project)
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("", encoding="utf-8")
    (project / PACKAGE / "domain" / "__init__.py").write_text("", encoding="utf-8")

    problems = generate(
        read_targets(project / "pyproject.toml"), project, (LINT_STEP, BOUNDARY_STEP), check=True
    )

    assert problems == [], "lint and the boundary check must accept the converted model"


@then(parsers.parse('both packages are written as the one module "{module}"'))
def _one_module(world: World, module: str) -> None:
    written = sorted(file.name for file in world.out.glob(f"{ROOT_NAME}_*.yaml"))
    assert written == [f"{module}.yaml"], "one module holds both packages"
    assert sorted(world.module(module)["classes"]) == ["Book", "Shelf"], "it holds both classes"


@then("the book has no description")
def _no_description(world: World) -> None:
    assert "description" not in world.klass("Book"), "no placeholder description is written"


@then(parsers.parse('the chapters slot is required "{required}" and multivalued "{many}"'))
def _required_and_many(world: World, required: str, many: str) -> None:
    slot = world.module()["slots"]["chapters"]
    assert bool(slot.get("required")) is (required == "yes"), (
        "required follows a lower bound of one"
    )
    assert bool(slot.get("multivalued")) is (many == "yes"), (
        "multivalued follows an upper bound > 1"
    )


@then(
    parsers.parse(
        'its minimum cardinality is "{minimum}" and its maximum cardinality is "{maximum}"'
    )
)
def _cardinalities(world: World, minimum: str, maximum: str) -> None:
    slot = world.module()["slots"]["chapters"]
    for found, wanted, what in (
        (slot.get("minimum_cardinality"), minimum, "minimum"),
        (slot.get("maximum_cardinality"), maximum, "maximum"),
    ):
        assert (None if wanted == NONE else int(wanted)) == found, f"the {what} cardinality"


@then(parsers.parse('the slot to the enumeration ranges over "{range_}"'))
def _slot_range(world: World, range_: str) -> None:
    assert world.module()["slots"]["language"]["range"] == range_, "the slot ranges over a URI"


@then(parsers.parse('the class "{name}" is abstract'))
def _abstract(world: World, name: str) -> None:
    assert world.klass(name)["abstract"] is True, f"{name} is abstract"


@then(
    parsers.parse(
        'the loan is an activity and an aggregate root with the mixins "{first}" and "{second}"'
    )
)
def _activity_root(world: World, first: str, second: str) -> None:
    loan = world.klass("Loan")
    assert loan["is_a"] == "Activity", "the loan is an Activity"
    assert loan["mixins"] == ["AggregateRoot", first, second], "the loan's mixins"


@then(parsers.parse('the loan\'s path is "{path}"'))
def _loan_path(world: World, path: str) -> None:
    assert world.klass("Loan")["annotations"]["rp_path"]["value"] == path, "the loan's path"


@then("the loan defines no slot of its own and narrows no slot")
def _loan_slots(world: World) -> None:
    loan = world.klass("Loan")
    assert not world.module().get("slots"), "no new slot is defined"
    assert "slot_usage" not in loan, "no toolkit slot is narrowed"
    assert not loan.get("slots"), "the loan lists no slot"


@then(parsers.parse('the book carries the annotation "{name}" with the value "{value}"'))
def _annotated(world: World, name: str, value: str) -> None:
    assert world.klass("Book")["annotations"][name]["value"] == value, f"the annotation {name}"


@then(parsers.parse('the book has the required string slot "{name}" with the IRI "{iri}"'))
def _identifier(world: World, name: str, iri: str) -> None:
    slot = world.module()["slots"][name]
    assert slot["slot_uri"] == iri, "the identifier's IRI"
    assert slot["range"] == "string", "the identifier is a string"
    assert slot["required"] is True, "the identifier is required"
    assert name in world.klass("Book")["slots"], "the book has the slot"


@then(parsers.parse('the library defines no slot "{name}"'))
def _no_slot(world: World, name: str) -> None:
    assert name not in world.module().get("slots", {}), f"no slot {name} is defined"


@then(parsers.parse('the book has no slot "{name}"'))
def _book_lacks(world: World, name: str) -> None:
    assert name not in world.klass("Book").get("slots", []), f"the book has no slot {name}"
    assert name not in world.module().get("slots", {}), f"no slot {name} is defined"


# --- Then: the roles file ------------------------------------------------------------------------------


@then(parsers.parse('the roles file holds the three roles "{first}", "{second}" and "{third}"'))
def _roles_file(world: World, first: str, second: str, third: str) -> None:
    found = yaml.safe_load((world.out / f"{ROOT_NAME}.roles.yaml").read_text(encoding="utf-8"))
    assert [each["role"] for each in found] == [first, second, third], "the three roles, sorted"


@then("the library's role loader reads the roles file")
def _loader_reads(world: World) -> None:
    loaded = load_role_definitions(world.out / f"{ROOT_NAME}.roles.yaml")
    assert len(loaded) == 3, "the loader accepts the file and finds the three roles"


# --- Then: the report ----------------------------------------------------------------------------------


@then(parsers.re(r'the report has an? "(?P<kind>[a-z-]+)" line naming "(?P<name>[^"]+)"'))
def _report_names(world: World, kind: str, name: str) -> None:
    lines = [line for line in world.report() if line[0] == kind and name in line[1]]
    assert lines, f"the report must have a {kind} line naming {name}: {world.report()}"


@then(
    parsers.parse('the report has a "{kind}" line that names the packages "{first}" and "{second}"')
)
def _report_packages(world: World, kind: str, first: str, second: str) -> None:
    lines = [
        line
        for line in world.report()
        if line[0] == kind and first in line[2] and second in line[2]
    ]
    assert len(lines) == 1, f"one {kind} line names both packages: {world.report()}"


@then(parsers.parse('the report has "{count}" "{kind}" lines'))
def _report_count(world: World, count: str, kind: str) -> None:
    found = [line for line in world.report() if line[0] == kind]
    assert len(found) == COUNTS[count], f"the number of {kind} lines: {found}"


@then(parsers.parse('the report names "{name}"'))
def _report_mentions(world: World, name: str) -> None:
    assert any(name in line[1] for line in world.report()), f"the report must name {name}"
