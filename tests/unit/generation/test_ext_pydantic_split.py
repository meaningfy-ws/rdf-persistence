"""Golden test and behaviour of the split gen-pydantic extension (PD-24, PD-25)."""

import ast
import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence.domain.generated.rp_files import StoredFile
from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.extensions.pydantic_split import (
    TOOLKIT_PACKAGE,
    metamodel_module,
)
from rdf_persistence.generation.extensions.pydantic_split import render as render_modules
from rdf_persistence.generation.steps import PYTHON_STEP

from .golden import assert_matches_toy, run_toy

TOY_MODULES = [
    "__init__.py",
    "books.py",
    "books_activities.py",
    "library.py",
    "library_access.py",
    "library_tenant.py",
    "scans.py",
    "templates.py",
]


def parse(folder: Path, module: str) -> ast.Module:
    return ast.parse((folder / module).read_text(encoding="utf-8"))


def imports_from(tree: ast.Module, module: str) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and "." * node.level + (node.module or "") == module
        for alias in node.names
    }


def enum_members(tree: ast.Module, enum: str) -> list[str]:
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == enum)
    return [t.id for n in cls.body if isinstance(n, ast.Assign) for t in n.targets]  # type: ignore[union-attr]


def test_the_toy_python_output_equals_the_committed_tree(tmp_path: Path) -> None:
    assert_matches_toy(run_toy(PYTHON_STEP, tmp_path), "generated/*.py")


@pytest.mark.slow
def test_one_module_is_written_per_schema_module(generated_toy: Path) -> None:
    written = sorted(p.name for p in generated_toy.glob("*.py"))
    assert written == TOY_MODULES, "the split run must write one module per schema module"


def test_a_class_stays_in_the_module_that_declares_it(generated_toy: Path) -> None:
    declared = {
        n.name for n in parse(generated_toy, "books.py").body if isinstance(n, ast.ClassDef)
    }
    assert {"Book", "Chapter", "Note"} <= declared, "Book, Chapter and Note belong in books.py"


def test_a_class_of_a_sibling_module_is_imported_relatively(generated_toy: Path) -> None:
    assert "Book" in imports_from(parse(generated_toy, "scans.py"), ".books"), (
        "scans.py must import Book from its sibling module"
    )


def test_an_application_imports_the_metamodel_from_the_top_level_package(
    generated_toy: Path,
) -> None:
    names = imports_from(parse(generated_toy, "scans.py"), "rdf_persistence")
    assert {"AggregateRoot", "Described", "StoredFile", "Tracked"} <= names, (
        "an application's metamodel imports must come from the public package (DEC-6)"
    )


@pytest.mark.parametrize(
    ("name", "toolkit", "expected"),
    [
        ("rp_core", True, f"{TOOLKIT_PACKAGE}.rp_core"),
        ("rp_core", False, "rdf_persistence"),
    ],
)
def test_the_metamodel_module_to_import_from(name: str, toolkit: bool, expected: str) -> None:
    assert metamodel_module(name, toolkit=toolkit) == expected, (
        f"{name} in a {'toolkit' if toolkit else 'application'} run"
    )


@pytest.mark.parametrize(
    ("module", "enum", "members"),
    [
        ("books.py", "Genre", ["FICTION", "NONFICTION", "POETRY"]),
    ],
)
def test_enum_members_are_the_permissible_value_keys_in_upper_snake_case(
    generated_toy: Path, module: str, enum: str, members: list[str]
) -> None:
    assert enum_members(parse(generated_toy, module), enum) == members, (
        f"{enum} members must come from the keys, not the titles"
    )


def test_an_enum_member_keeps_the_value_of_its_key() -> None:
    from rdf_persistence.domain.generated.rp_core import RegistryKind

    assert RegistryKind.LOADED_GRAPH.value == "loaded_graph", "the stored value is the key"


def test_an_internal_slot_is_marked_for_the_api_layer() -> None:
    extra = StoredFile.model_fields["file_key"].json_schema_extra
    assert extra == {"rp_internal": True}, "an internal slot must carry the marker"


def test_an_internal_slot_is_still_dumped_for_the_mapper() -> None:
    dumped = StoredFile(file_key="k").model_dump()
    assert dumped["file_key"] == "k", "the mapper must still persist internal slots"


def test_a_slot_that_is_not_internal_has_no_marker() -> None:
    assert StoredFile.model_fields["file_name"].json_schema_extra is None, (
        "only internal slots are marked"
    )


@pytest.fixture
def toy_package(generated_toy: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The generated toy folder made importable as the package ``rp_toy_generated``."""
    link = generated_toy.parent / "rp_toy_generated"
    link.symlink_to(generated_toy, target_is_directory=True)
    monkeypatch.syspath_prepend(str(generated_toy.parent))
    yield "rp_toy_generated"
    for name in [m for m in sys.modules if m.split(".")[0] == "rp_toy_generated"]:
        del sys.modules[name]
    link.unlink()


def test_the_generated_modules_import_and_build_models(toy_package: str) -> None:
    library = importlib.import_module(f"{toy_package}.library")
    chapter = library.Chapter(id="https://example.org/c1", number=1)
    assert chapter.label is None, "an unlabelled chapter needs no label"
    with pytest.raises(ValidationError, match="label"):
        library.Note(id="https://example.org/n1", text="x")


ENUM_MODULE = """
id: https://example.org/ns/colours
name: colours
title: Colours
description: A module with an enum.
prefixes: {c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}
default_prefix: c
imports: [linkml:types]
enums:
  Colour:
    title: Colour
    description: A colour.
    permissible_values:
      light_red: {title: Light red, description: Light red., meaning: "c:LightRed"}
"""

USER_MODULE = """
id: https://example.org/ns/paint
name: paint
title: Paint
description: A module using the enum of another.
prefixes: {c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}
default_prefix: c
imports: [linkml:types, colours]
classes:
  Paint:
    title: Paint
    description: A paint.
    attributes:
      colour: {range: Colour, title: Colour, description: Its colour.}
"""


def test_an_enum_declared_in_another_module_is_imported_not_repeated(tmp_path: Path) -> None:
    (tmp_path / "colours.yaml").write_text(ENUM_MODULE, encoding="utf-8")
    (tmp_path / "paint.yaml").write_text(USER_MODULE, encoding="utf-8")
    files = {f.name: f.text for f in render_modules(tmp_path / "paint.yaml")}
    tree = ast.parse(files["paint.py"])
    declared = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "Colour" in imports_from(tree, ".colours"), "the enum must be imported from its module"
    assert "Colour" not in declared, "the enum must not be declared again"
    assert enum_members(ast.parse(files["colours.py"]), "Colour") == ["LIGHT_RED"], (
        "the member comes from the key, not the title"
    )


@pytest.mark.parametrize(
    ("slot", "ignored"),
    [("label", True), ("description", False), ("id", False)],
)
def test_a_field_an_unlabelled_class_relaxes_carries_a_type_ignore(
    generated_toy: Path, slot: str, ignored: bool
) -> None:
    """Chapter makes the label of ``Described`` optional (PD-11); mypy needs the override marked."""
    lines = (generated_toy / "books.py").read_text(encoding="utf-8").splitlines()
    chapter = lines[lines.index("class Chapter(Described):") :]
    line = next(line for line in chapter if line.startswith(f"    {slot}:"))
    assert line.endswith("# type: ignore[assignment]") is ignored, (
        f"Chapter.{slot}: the ignore belongs on a field that loosens its base class's, and only there"
    )


TERM_MODULE = """
id: https://example.org/ns/terms
name: terms
title: Terms
description: A module whose type is a Python class of the toolkit.
prefixes: {t: "https://example.org/ns/t#", linkml: "https://w3id.org/linkml/"}
default_prefix: t
imports: [linkml:types]
types:
  sparql_term:
    typeof: string
    description: A rendered SPARQL term.
    repr: SparqlTerm
    annotations:
      python_import: rdf_persistence.domain.sparql
classes:
  Bundle:
    title: Bundle
    description: A bundle of terms.
    attributes:
      subject: {range: sparql_term, required: true, title: Subject, description: A term.}
"""


def test_a_type_with_a_repr_and_a_python_import_is_imported_and_used_as_the_field_type(
    tmp_path: Path,
) -> None:
    """TC-16 (RISK-4: the generator relies on the stock use of a type's ``repr``)."""
    (tmp_path / "terms.yaml").write_text(TERM_MODULE, encoding="utf-8")
    text = {f.name: f.text for f in render_modules(tmp_path / "terms.yaml")}["terms.py"]
    tree = ast.parse(text)
    compile(text, "terms.py", "exec")
    assert "SparqlTerm" in imports_from(tree, "rdf_persistence.domain.sparql"), (
        "the module must import SparqlTerm from the annotation's module"
    )
    field = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == "subject"
    )
    assert ast.unparse(field.annotation) == "SparqlTerm", "the field is typed by the type's repr"


GROUP_MODULE = """
id: https://example.org/ns/groups
name: groups
title: Groups
description: A class that holds a group of its own.
prefixes: {g: "https://example.org/ns/g#", linkml: "https://w3id.org/linkml/"}
default_prefix: g
default_range: string
imports: [linkml:types]
classes:
  Group:
    title: Group
    description: A group of values.
    slots: [size]
  Holder:
    title: Holder
    description: Holds a default group and an optional one.
    slots: [group, other]
slots:
  size:
    title: Size
    description: A count.
    range: integer
    ifabsent: int(3)
  group:
    title: Group slot
    description: The group, never absent.
    range: Group
    annotations:
      default_instance: 'true'
  other:
    title: Other slot
    description: A group that may be absent.
    range: Group
"""


def test_a_slot_with_default_instance_builds_a_fresh_default_of_its_range(tmp_path: Path) -> None:
    """TC-56's generator half: `Field(default_factory=Group)` for the annotated slot, `None` for the other."""
    (tmp_path / "groups.yaml").write_text(GROUP_MODULE, encoding="utf-8")
    text = {f.name: f.text for f in render_modules(tmp_path / "groups.yaml")}["groups.py"]
    lines = {line.strip().split(":")[0]: line for line in text.splitlines()}
    assert "default_factory=Group" in lines["group"], lines["group"]
    assert "default=None" in lines["other"], "an unannotated slot keeps the stock default"
    namespace: dict[str, object] = {}
    exec(compile(text, "groups.py", "exec"), namespace)
    holder = namespace["Holder"]
    first, second = holder(), holder()  # type: ignore[operator]
    assert first.group.size == 3, "the group holds its own defaults"
    assert first.group is not second.group, "each instance gets a group of its own"
    assert first.other is None, "the slot without the annotation stays absent"


LIST_MODULE = """
id: https://example.org/ns/names
name: names
title: Names
description: A class with a list that has a default.
prefixes: {n: "https://example.org/ns/n#", linkml: "https://w3id.org/linkml/"}
default_prefix: n
default_range: string
imports: [linkml:types]
classes:
  Names:
    title: Names
    description: Holds a list.
    slots: [names]
slots:
  names:
    title: Names slot
    description: The names; the default is the two given.
    multivalued: true
    required: true
    minimum_cardinality: 1
    ifabsent: string(RS256, ES256)
"""


def test_a_multivalued_slot_with_ifabsent_defaults_to_the_list_of_its_names(tmp_path: Path) -> None:
    """PD-6: the stock generator writes the scalar `"RS256, ES256"`; the list is `string(a, b)`'s meaning."""
    (tmp_path / "names.yaml").write_text(LIST_MODULE, encoding="utf-8")
    text = {f.name: f.text for f in render_modules(tmp_path / "names.yaml")}["names.py"]
    namespace: dict[str, object] = {}
    exec(compile(text, "names.py", "exec"), namespace)
    names = namespace["Names"]
    first, second = names(), names()  # type: ignore[operator]
    assert first.names == ["RS256", "ES256"], "the default is the list, not the text"
    first.names.append("EdDSA")
    assert second.names == ["RS256", "ES256"], "each instance gets a list of its own"


@pytest.mark.parametrize("ifabsent", ["int(3)", "RS256"])
def test_a_multivalued_slot_whose_ifabsent_is_not_a_list_of_names_is_refused_naming_it(
    tmp_path: Path, ifabsent: str
) -> None:
    """D-31/D-40: the work-around refuses what it cannot read as `string(a, b, ...)`, naming the slot."""
    module = LIST_MODULE.replace("string(RS256, ES256)", ifabsent)
    (tmp_path / "names.yaml").write_text(module, encoding="utf-8")
    with pytest.raises(SchemaGenerationError, match="names is multivalued"):
        render_modules(tmp_path / "names.yaml")


_REPR_LINE = "    repr: SparqlTerm\n"
_IMPORT_LINES = "    annotations:\n      python_import: rdf_persistence.domain.sparql\n"


@pytest.mark.parametrize(
    "half",
    [
        pytest.param(_IMPORT_LINES, id="a-repr-without-a-python_import"),
        pytest.param(_REPR_LINE, id="a-python_import-without-a-repr"),
    ],
)
def test_a_type_with_only_one_of_repr_and_python_import_yields_no_broken_import(
    tmp_path: Path, half: str
) -> None:
    """Attacks the error-matrix row "``repr`` with no ``python_import``" and its mirror: no ``import None``."""
    assert half in TERM_MODULE, "the fixture still holds the half this case removes"
    (tmp_path / "terms.yaml").write_text(TERM_MODULE.replace(half, ""), encoding="utf-8")
    text = {f.name: f.text for f in render_modules(tmp_path / "terms.yaml")}["terms.py"]
    compile(text, "terms.py", "exec")
    modules = {str(n.module) for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom)}
    assert "None" not in modules, "no import of the object None"
    assert "rdf_persistence.domain.sparql" not in modules, "an import needs both halves"


ALIAS_MODULE = """\
id: https://example.org/aliases
name: aliases
prefixes:
  ex: https://example.org/
  linkml: https://w3id.org/linkml/
default_prefix: ex
default_range: string
imports:
  - linkml:types
slots:
  step: {alias: rp.step, required: true}
  tenant_id: {alias: rp.tenant.id}
  wire_name: {alias: wireName}
  plain: {}
classes:
  Aliased:
    slots: [step, tenant_id, wire_name, plain]
"""


def _aliased_fields(tmp_path: Path) -> dict[str, str | None]:
    (tmp_path / "aliases.yaml").write_text(ALIAS_MODULE, encoding="utf-8")
    text = {f.name: f.text for f in render_modules(tmp_path / "aliases.yaml")}["aliases.py"]
    cls = next(
        n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == "Aliased"
    )
    fields: dict[str, str | None] = {}
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call):
            alias = next((k.value for k in node.value.keywords if k.arg == "alias"), None)
            fields[ast.unparse(node.target)] = ast.literal_eval(alias) if alias else None
    return fields


def test_a_slot_with_a_dotted_alias_is_named_after_the_slot_and_keeps_the_alias(
    tmp_path: Path,
) -> None:
    fields = _aliased_fields(tmp_path)

    assert fields["step"] == "rp.step"
    assert fields["tenant_id"] == "rp.tenant.id"


def test_a_slot_with_an_identifier_alias_keeps_the_alias_as_its_name(tmp_path: Path) -> None:
    fields = _aliased_fields(tmp_path)

    assert fields["wireName"] is None
    assert "wire_name" not in fields
