"""Golden test and behaviour of the split gen-pydantic extension (PD-24, PD-25)."""

import ast
import importlib
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence.core.domain.generated.rp_files import StoredFile
from rdf_persistence.services.schema import load_schema
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.extensions import pydantic_split
from rdf_persistence_generation.extensions.pydantic_split import (
    METAMODEL_DIR,
    metamodel_module,
    public_package,
)
from rdf_persistence_generation.extensions.pydantic_split import render as render_modules
from rdf_persistence_generation.manifest import current_inputs
from rdf_persistence_generation.steps import PYTHON_STEP

from .golden import assert_matches_toy, run_toy

TOOLKIT_DOMAIN = "rdf_persistence.core.domain.generated"
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


@pytest.fixture
def metamodel_copy(tmp_path: Path) -> Callable[[str, str], Path]:
    """A function that copies the metamodel's folder and rewrites one module's ``python_package``."""

    def copy(module: str, package: str) -> Path:
        folder = tmp_path / "model"
        shutil.copytree(METAMODEL_DIR, folder, ignore=shutil.ignore_patterns("migrations"))
        path = folder / f"{module}.yaml"
        text = path.read_text(encoding="utf-8")
        assert f"python_package: {TOOLKIT_DOMAIN}" in text, f"{module} carries no python_package"
        path.write_text(
            text.replace(f"python_package: {TOOLKIT_DOMAIN}", f"python_package: {package}", 1),
            encoding="utf-8",
        )
        return folder

    return copy


def test_a_toolkit_run_imports_a_metamodel_class_from_the_package_its_module_says() -> None:
    """TC-32"""
    schema = load_schema(METAMODEL_DIR / "rp_core.yaml").schema
    assert metamodel_module(schema, toolkit=True) == f"{TOOLKIT_DOMAIN}.rp_core", (
        "the module's python_package, then its name"
    )


def test_an_application_run_imports_a_metamodel_class_from_the_public_package() -> None:
    """TC-33: the public package is read from rp.yaml's public_package."""
    schema = load_schema(METAMODEL_DIR / "rp_core.yaml").schema
    assert metamodel_module(schema, toolkit=False) == "rdf_persistence", "rp.yaml's public_package"


def test_a_moved_metamodel_module_is_imported_from_where_it_says_it_lives(
    metamodel_copy: Callable[[str, str], Path],
) -> None:
    """TC-34: no code names the package; the annotation does."""
    folder = metamodel_copy("rp_core", "rdf_persistence.kernel.generated")
    schema = load_schema(folder / "rp_core.yaml").schema
    assert metamodel_module(schema, toolkit=True) == "rdf_persistence.kernel.generated.rp_core", (
        "the copy's python_package"
    )


def test_an_application_run_ignores_the_python_package_of_a_moved_module(
    metamodel_copy: Callable[[str, str], Path],
) -> None:
    """TC-37 (import side): an application imports from the public package, wherever the module is."""
    folder = metamodel_copy("rp_core", "x.generated")
    schema = load_schema(folder / "rp_core.yaml").schema
    assert metamodel_module(schema, toolkit=False) == "rdf_persistence", "the public package"


def test_a_metamodel_without_public_package_is_a_clear_error(
    metamodel_copy: Callable[[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An application run on a metamodel whose root lacks public_package names the annotation."""
    folder = metamodel_copy("rp_core", TOOLKIT_DOMAIN)
    root = folder / "rp.yaml"
    text = root.read_text(encoding="utf-8")
    assert "public_package: rdf_persistence" in text
    root.write_text(
        text.replace("public_package: rdf_persistence", "other: note", 1), encoding="utf-8"
    )
    monkeypatch.setattr(pydantic_split, "METAMODEL_DIR", folder)
    schema = load_schema(folder / "rp_core.yaml").schema
    public_package.cache_clear()  # the lookup is cached for the process
    try:
        with pytest.raises(SchemaGenerationError, match="public_package"):
            metamodel_module(schema, toolkit=False)
    finally:
        public_package.cache_clear()


def test_the_generator_does_not_name_the_metamodels_packages() -> None:
    """TC-39: the two constants are gone; the metamodel says where its classes live (DEC-7).

    A name check, not a text one: the generated ``GenerationAnnotation.PUBLIC_PACKAGE`` member is
    the annotation's key, and stays.
    """
    folder = Path(__file__).parents[3] / "rdf_persistence_generation"
    constants = {"TOOLKIT_PACKAGE", "PUBLIC_PACKAGE"}
    found = []
    for path in folder.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module_level = [  # a module-level assignment or import; a class's own members are not
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        ] + [
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        ]
        used = [
            n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        ]
        found += [f"{path.name}: {name}" for name in (*module_level, *used) if name in constants]
    assert found == [], "the generator still names a metamodel package as a constant"


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
    from rdf_persistence.core.domain.generated.rp_core import RegistryKind

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
      python_import: rdf_persistence.core.domain.sparql
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
    assert "SparqlTerm" in imports_from(tree, "rdf_persistence.core.domain.sparql"), (
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
_IMPORT_LINES = "    annotations:\n      python_import: rdf_persistence.core.domain.sparql\n"


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
    assert "rdf_persistence.core.domain.sparql" not in modules, "an import needs both halves"


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
  schema_file: {alias: schema, annotations: {field_name: slot}}
  plain: {}
classes:
  Aliased:
    slots: [step, tenant_id, wire_name, schema_file, plain]
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


def test_a_slot_annotated_field_name_slot_is_named_after_the_slot_and_keeps_the_alias(
    tmp_path: Path,
) -> None:
    """D-52: the opt-in rule: the field is the slot's name, ``alias=`` carries the wire name."""
    fields = _aliased_fields(tmp_path)

    assert fields["schema_file"] == "schema", "the annotated slot must keep its alias"
    assert "schema" not in fields, "the alias named the field"


CROSS_TARGET = Path(__file__).parents[2] / "fixtures" / "cross_target"
A_PACKAGE = "xt.a.generated"


def _cross_target_b() -> Path:
    return CROSS_TARGET / "b" / "b.yaml"


def _class_names(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, ast.ClassDef)}


def _a_without_python_package() -> str:
    text = (CROSS_TARGET / "a" / "a.yaml").read_text(encoding="utf-8")
    assert f"python_package: {A_PACKAGE}" in text, "the fixture's module a names its package"
    return text.replace(f"python_package: {A_PACKAGE}", "note: none")


def test_a_class_of_another_targets_module_is_imported_from_that_targets_package() -> None:
    """TC-10: B imports module ``a`` of target A, whose ``python_package`` says where it lives."""
    files = {f.name: f.text for f in render_modules(_cross_target_b())}
    tree = ast.parse(files["b.py"])
    assert "Thing" in imports_from(tree, f"{A_PACKAGE}.a"), "Thing comes from A's package"
    assert "Thing" not in _class_names(tree), "Thing is not generated into B"
    assert "a.py" not in files, "B writes no module for A's schema"


def test_the_manifest_of_the_importing_target_lists_the_imported_module_as_an_input() -> None:
    """TC-10: a change to ``a.yaml`` makes B stale."""
    target = read_targets(CROSS_TARGET / "pyproject.toml")[1]
    inputs = {entry.path for entry in current_inputs(target, CROSS_TARGET)}
    assert {"a/a.yaml", "b/b.yaml"} <= inputs, "both schemas are inputs of B"


def test_a_module_without_python_package_beside_the_importer_is_generated_into_it(
    tmp_path: Path,
) -> None:
    """TC-11: as before, a module of the closure kept beside the root schema is part of this target."""
    (tmp_path / "a.yaml").write_text(_a_without_python_package(), encoding="utf-8")
    (tmp_path / "b.yaml").write_text(
        _cross_target_b().read_text(encoding="utf-8").replace("../a/a", "a"), encoding="utf-8"
    )
    files = {f.name: f.text for f in render_modules(tmp_path / "b.yaml")}
    assert "Thing" in _class_names(ast.parse(files["a.py"])), "Thing is generated into B"
    assert "Thing" in imports_from(ast.parse(files["b.py"]), ".a"), "B imports it from its sibling"


def test_a_module_of_another_folder_without_python_package_is_still_refused(
    tmp_path: Path,
) -> None:
    """TC-11: nothing says where its classes live, so there is nothing to import from."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "a.yaml").write_text(_a_without_python_package(), encoding="utf-8")
    shutil.copy(_cross_target_b(), tmp_path / "b" / "b.yaml")
    with pytest.raises(SchemaGenerationError, match="python_package"):
        render_modules(tmp_path / "b" / "b.yaml")


@pytest.mark.parametrize(
    "package", ["", "   ", "not a package", "xt.a.generated.", ".xt.a", "xt..a"]
)
def test_a_malformed_python_package_of_another_target_is_refused_naming_its_module(
    tmp_path: Path, package: str
) -> None:
    """A cross-target import must not turn an empty or odd package into a relative or broken import."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    text = (CROSS_TARGET / "a" / "a.yaml").read_text(encoding="utf-8")
    (tmp_path / "a" / "a.yaml").write_text(
        text.replace(f"python_package: {A_PACKAGE}", f'python_package: "{package}"'),
        encoding="utf-8",
    )
    shutil.copy(_cross_target_b(), tmp_path / "b" / "b.yaml")
    with pytest.raises(SchemaGenerationError, match=r"\ba\b.*python_package"):
        render_modules(tmp_path / "b" / "b.yaml")


def test_a_malformed_python_package_of_the_metamodel_is_refused_on_the_base_model_line(
    metamodel_copy: Callable[[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``RpModel`` import is written beside the metamodel's package: a hole in it is refused."""
    folder = metamodel_copy("rp", "a..generated")
    monkeypatch.setattr(pydantic_split, "METAMODEL_DIR", folder)
    pydantic_split.toolkit_base_module.cache_clear()
    try:
        with pytest.raises(SchemaGenerationError, match="rp.*python_package"):
            pydantic_split.toolkit_base_module()
    finally:
        pydantic_split.toolkit_base_module.cache_clear()
