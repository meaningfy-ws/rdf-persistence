"""Adversarial tests of the service types in the TypeScript output (PD-8), technical exemption (PD-9)."""

import re
from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import (
    API_ENTRYPOINTS_SCHEMA,
    SERVED_SCHEMAS,
    load_schema,
)
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.extensions import typescript
from rdf_persistence_generation.generated.rp_generation import GeneratedFile
from rdf_persistence_generation.manifest import current_inputs

from .conftest import ROOT_SCHEMA
from .test_boundary_check import add_api_module, problems_of

SERVICE_INPUT = "rdf_persistence/model/technical/api/rp_api_entrypoints.yaml"
EXPORT = re.compile(r'export \* from "\./(\w+)";')
IMPORT = re.compile(r'from "\./(\w+)";')
DECLARED = re.compile(r"export (?:interface|type) (\w+)")

ANY_MODULE = """id: https://example.org/ns/library/anyapi
name: anyapi
title: Any API
description: A technical module that uses linkml:Any.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
annotations:
  module_kind: technical

classes:
  Anything:
    title: Anything
    description: Any value.
    class_uri: linkml:Any
  SubAnything:
    title: Sub anything
    description: A class that is_a Anything.
    is_a: Anything
  Envelope:
    title: Envelope
    description: Carries free data.
    attributes:
      envelope_id:
        description: Identifier.
        identifier: true
      payload:
        description: One value.
        range: Anything
      items:
        description: Many values.
        range: Anything
        multivalued: true
      wrapped:
        description: A sub anything.
        range: SubAnything
"""


def service_enums() -> list[str]:
    """The enums `rp_api_entrypoints.yaml` itself defines (not the ones it imports)."""
    return list(load_schema(API_ENTRYPOINTS_SCHEMA).schema.enums)


def render_names(root: Path) -> list[GeneratedFile]:
    return typescript.render(root)


def by_name(files: list[GeneratedFile]) -> dict[str, str]:
    return {f.name: f.text for f in files}


def import_module(toy: Path, name: str, body: str) -> Path:
    (toy / f"{name}.yaml").write_text(body, encoding="utf-8")
    root = toy / ROOT_SCHEMA
    text = root.read_text(encoding="utf-8")
    root.write_text(text.replace("  - library_access\n", f"  - library_access\n  - {name}\n", 1))
    return root


def module_body(name: str, kind: str, classes: str, imports: str = "") -> str:
    return (
        f"id: https://example.org/ns/library/{name}\nname: {name}\ntitle: {name}\n"
        f"description: A test module.\nprefixes:\n  lib: https://example.org/ns/library#\n"
        f"  linkml: https://w3id.org/linkml/\ndefault_prefix: lib\ndefault_range: string\n"
        f"imports:\n  - linkml:types\n{imports}annotations:\n  module_kind: {kind}\n\n"
        f"classes:\n{classes}"
    )


def technical_project(folder: Path, name: str, body: str, typescript: bool = True) -> Path:
    """A project of one technical module and nothing else (PD-2: a mixed target is refused); its pyproject."""
    (folder / f"{name}.yaml").write_text(body, encoding="utf-8")
    project = folder / "pyproject.toml"
    project.write_text(
        f'[tool.rp-generate]\nschema = "{name}.yaml"\npackage = "app.services.generated"\n'
        'python = "app/services/generated"\n' + ('typescript = "web"\n' if typescript else ""),
        encoding="utf-8",
    )
    return project


def simple_class(name: str, extra: str = "") -> str:
    return (
        f"  {name}:\n    title: {name}\n    description: A test class.\n    attributes:\n"
        f"      {name.lower()}_id:\n        title: Id\n        description: Identifier.\n        identifier: true\n{extra}"
    )


# --- PD-8: name collisions and output integrity ------------------------------------------------


def test_the_toy_index_lists_each_module_once_in_sorted_order(toy_copy: Path) -> None:
    files = by_name(render_names(toy_copy / ROOT_SCHEMA))
    exported = EXPORT.findall(files["index.ts"])
    assert exported == sorted(set(exported)), f"index.ts is not sorted and unique: {exported}"


def test_every_import_of_every_file_names_a_file_that_is_written(toy_copy: Path) -> None:
    files = by_name(render_names(toy_copy / ROOT_SCHEMA))
    written = {name.removesuffix(".ts") for name in files}
    for name, text in files.items():
        dangling = set(IMPORT.findall(text)) - written
        assert not dangling, f"{name} imports modules that are not written: {sorted(dangling)}"


def test_no_declared_type_name_is_exported_by_two_files(toy_copy: Path) -> None:
    files = by_name(render_names(toy_copy / ROOT_SCHEMA))
    seen: dict[str, str] = {}
    for name, text in files.items():
        for declared in DECLARED.findall(text):
            assert declared not in seen, (
                f"{declared} is declared in {seen[declared]} and {name}; export * clashes"
            )
            seen[declared] = name


@pytest.mark.slow
@pytest.mark.parametrize("clash", ["Page"])  # one class: a reserved class name
def test_a_consumer_class_named_like_a_service_type_is_refused_naming_the_clash(
    tmp_path: Path, clash: str, capsys: pytest.CaptureFixture[str]
) -> None:
    body = module_body("mine", "technical", simple_class(clash))
    assert main(["--project", str(technical_project(tmp_path, "mine", body))]) == 1, (
        "a clash must fail"
    )
    error = capsys.readouterr().err
    assert clash in error, f"the clash is not named: {error}"
    assert "rp_service" in error, f"the clash is not named: {error}"
    assert "Traceback" not in error, f"a clash is a problem line, not a traceback: {error}"


def test_a_consumer_enum_named_like_a_service_enum_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    enum = next(iter(service_enums()))
    body = module_body("mine", "technical", simple_class("Mine")) + (
        f"\nenums:\n  {enum}:\n    description: Clash.\n    permissible_values:\n      a:\n"
        "        description: A.\n"
    )
    project = technical_project(tmp_path, "mine", body)
    assert main(["--project", str(project)]) == 1, "an enum clash must fail"
    assert enum in capsys.readouterr().err, "the clashing enum is not named"


@pytest.mark.slow
def test_a_consumer_module_named_rp_service_is_refused_naming_the_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = module_body("rp_service", "technical", simple_class("Mine"))
    project = technical_project(tmp_path, "rp_service", body)
    assert main(["--project", str(project)]) == 1, "the module name is reserved"
    error = capsys.readouterr().err
    assert "rp_service" in error, f"the reason is not given: {error}"
    assert "reserved" in error, f"the reason is not given: {error}"


@pytest.mark.slow
def test_a_clashing_name_is_allowed_when_the_target_renders_no_typescript(
    tmp_path: Path,
) -> None:
    body = module_body("mine", "technical", simple_class("Page"))
    pyproject = technical_project(tmp_path, "mine", body, typescript=False)
    assert main(["--project", str(pyproject)]) == 0, "no TypeScript, no reserved names"


def test_rp_service_ts_imports_only_files_a_consumer_run_writes(toy_copy: Path) -> None:
    files = by_name(render_names(toy_copy / ROOT_SCHEMA))
    wanted = set(IMPORT.findall(files["rp_service.ts"]))
    assert wanted <= {n.removesuffix(".ts") for n in files}, f"dangling: {sorted(wanted)}"


def test_rendering_a_consumer_with_no_rp_core_import_still_resolves_rp_service_imports(
    toy_copy: Path,
) -> None:
    body = module_body("lonely", "technical", simple_class("Lonely"))
    (toy_copy / "lonely.yaml").write_text(body, encoding="utf-8")
    files = by_name(render_names(toy_copy / "lonely.yaml"))
    written = {n.removesuffix(".ts") for n in files}
    for name, text in files.items():
        dangling = set(IMPORT.findall(text)) - written
        assert not dangling, f"{name} imports {sorted(dangling)}, which no file provides"


# --- PD-8: rendering the service schema itself -------------------------------------------------


def test_rendering_the_service_schema_equals_its_own_module_files() -> None:
    """Its own files, but for the other served schemas', which are in ``rp_service.ts``."""
    served_elsewhere = {
        f"{load_schema(path).schema.name}.ts"
        for path in SERVED_SCHEMAS
        if path != API_ENTRYPOINTS_SCHEMA
    }
    # a module that two served schemas import (the metamodel's) is one file in the output
    kept = {
        f.name: f
        for f in typescript._module_files(API_ENTRYPOINTS_SCHEMA)
        if f.name not in served_elsewhere
    }
    # the schema's own module is written as ``rp_service.ts`` whatever the schema is called (TC-07)
    own_file = f"{load_schema(API_ENTRYPOINTS_SCHEMA).schema.name}.ts"
    merged_file = f"{typescript.SERVICE_MODULE}.ts"
    names = [merged_file if name == own_file else name for name in kept]
    assert sorted(f.name for f in typescript.render(API_ENTRYPOINTS_SCHEMA)) == sorted(
        [*names, "index.ts"]
    ), "rendering the service schema adds nothing to its own files"


def test_a_relative_path_to_the_service_schema_is_the_same_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(API_ENTRYPOINTS_SCHEMA.parent)
    names = [f.name for f in typescript.render(Path(API_ENTRYPOINTS_SCHEMA.name))]
    assert len(names) == len(set(names)), f"duplicate files for a relative path: {names}"


def test_a_symlink_to_the_service_schema_is_the_same_file(tmp_path: Path) -> None:
    # the service schema imports the other served schemas by a relative path, so the link keeps them
    (tmp_path / "service").mkdir()
    for neighbour in (path for path in SERVED_SCHEMAS if path != API_ENTRYPOINTS_SCHEMA):
        (tmp_path / neighbour.parent.name).mkdir(exist_ok=True)
        (tmp_path / neighbour.parent.name / neighbour.name).symlink_to(neighbour)
    link = tmp_path / "service" / "linked_service.yaml"
    link.symlink_to(API_ENTRYPOINTS_SCHEMA)
    names = [f.name for f in typescript.render(link)]
    assert len(names) == len(set(names)), f"duplicate files for a symlink: {names}"


# --- PD-8: linkml:Any in a consumer's own schema -----------------------------------------------


@pytest.fixture
def any_files(toy_copy: Path) -> dict[str, str]:
    root = import_module(toy_copy, "anyapi", ANY_MODULE)
    return by_name(render_names(root))


def test_a_consumer_any_slot_is_unknown(any_files: dict[str, str]) -> None:
    assert "payload?: unknown;" in any_files["anyapi.ts"], "single-valued Any is unknown"


def test_a_consumer_multivalued_any_slot_is_unknown_array(any_files: dict[str, str]) -> None:
    assert "items?: unknown[];" in any_files["anyapi.ts"], "multivalued Any is unknown[]"


def test_a_consumer_any_class_has_no_interface(any_files: dict[str, str]) -> None:
    assert "interface Anything" not in any_files["anyapi.ts"], "Any gets no interface"


def test_a_class_that_is_a_any_does_not_extend_a_missing_interface(
    any_files: dict[str, str],
) -> None:
    text = any_files["anyapi.ts"]
    assert "extends Anything" not in text, "extends an interface that is never declared"


def test_a_slot_ranging_over_a_subclass_of_any_names_a_declared_type(
    any_files: dict[str, str],
) -> None:
    text = any_files["anyapi.ts"]
    declared = set(DECLARED.findall(text))
    assert "SubAnything" in declared or "wrapped?: unknown" in text, (
        "wrapped names a type that is not declared"
    )


# --- PD-9: the technical exemption --------------------------------------------------------------


def test_a_technical_class_used_as_the_range_of_a_domain_class_is_still_a_reference_problem(
    toy_copy: Path,
) -> None:
    add_api_module(toy_copy, "technical")
    books = toy_copy / "books.yaml"
    text = books.read_text(encoding="utf-8")
    books.write_text(
        text.replace(
            "slots: [number, notes]",
            "slots: [number, notes, account]",
            1,
        ).replace(
            "slots:\n",
            "slots:\n  account:\n    description: Leak.\n    range: Account\n",
            1,
        ),
        encoding="utf-8",
    )
    found = problems_of(toy_copy / ROOT_SCHEMA)
    assert any("[reference]" in p and "Account" in p for p in found), (
        f"a domain class may not point at a technical class: {found}"
    )


def test_a_technical_class_pointing_at_a_class_has_no_reference_problem(toy_copy: Path) -> None:
    body = module_body(
        "tech",
        "technical",
        simple_class(
            "Holder", "      chapter:\n        description: Bad.\n        range: Chapter\n"
        ),
        imports="  - books\n",
    )
    root = import_module(toy_copy, "tech", body)
    found = problems_of(root)
    assert not any("[reference]" in p for p in found), (
        f"D-49: a technical class is never stored, so the reference rule skips it: {found}"
    )


def test_a_domain_class_named_like_a_technical_class_does_not_escape_ownership(
    toy_copy: Path,
) -> None:
    body = module_body("tech", "technical", simple_class("Orphan"))
    import_module(toy_copy, "tech", body)
    domain = module_body("lost", "domain", simple_class("Orphan"))
    (toy_copy / "lost.yaml").write_text(domain, encoding="utf-8")
    root = toy_copy / ROOT_SCHEMA
    root.write_text(
        root.read_text(encoding="utf-8").replace("  - tech\n", "  - tech\n  - lost\n", 1)
    )
    found = problems_of(root)
    assert any("[ownership] Orphan" in p for p in found), (
        f"the same-named domain class escaped through the technical name: {found}"
    )


def test_the_annotation_value_is_read_case_insensitively(toy_copy: Path) -> None:
    root = add_api_module(toy_copy, "Technical")
    assert problems_of(root) == [], (
        "annotation values are lower-cased everywhere, so Technical is technical"
    )


def test_without_the_technical_twin_the_same_domain_class_is_reported(toy_copy: Path) -> None:
    domain = module_body("lost", "domain", simple_class("Orphan"))
    root = import_module(toy_copy, "lost", domain)
    found = problems_of(root)
    assert any("[ownership] Orphan" in p for p in found), f"control case failed: {found}"


def test_a_technical_module_importing_a_domain_module_is_exempt_and_clean(toy_copy: Path) -> None:
    body = module_body("tech", "technical", simple_class("Helper"), imports="  - books\n")
    root = import_module(toy_copy, "tech", body)
    assert problems_of(root) == [], "a technical module may import a domain module"


def test_a_module_without_kind_is_not_exempt(toy_copy: Path) -> None:
    body = module_body("nokind", "technical", simple_class("Loose")).replace(
        "annotations:\n  module_kind: technical\n", ""
    )
    root = import_module(toy_copy, "nokind", body)
    found = problems_of(root)
    assert any("[ownership] Loose" in p for p in found), f"no kind, no exemption: {found}"


def test_a_domain_module_importing_a_technical_one_is_still_a_module_kind_problem(
    toy_copy: Path,
) -> None:
    add_api_module(toy_copy, "technical")
    books = toy_copy / "books.yaml"
    books.write_text(
        books.read_text(encoding="utf-8").replace(
            "  - rdf_persistence/model/rp_annotations\n",
            "  - rdf_persistence/model/rp_annotations\n  - api\n",
            1,
        ),
        encoding="utf-8",
    )
    found = problems_of(toy_copy / ROOT_SCHEMA)
    assert any("[module_kind]" in p for p in found), f"the import rule must still apply: {found}"


# --- freshness ----------------------------------------------------------------------------------


def test_the_service_schema_is_an_input_of_the_toy_manifest() -> None:
    toy = Path(__file__).parents[2] / "fixtures" / "library"
    target = read_targets(toy / "pyproject.toml")[0]
    paths = {e.path for e in current_inputs(target, toy)}
    assert SERVICE_INPUT in paths, (
        "rp_service.ts is generated from rp_api_entrypoints.yaml, but a change to it would not make the toy stale"
    )


@pytest.mark.slow
def test_a_toy_generation_writes_rp_service_ts(toy_copy: Path) -> None:
    assert main(["--project", str(toy_copy / "pyproject.toml")]) == 0, "must generate"
    written = list(toy_copy.rglob("rp_service.ts"))
    assert len(written) == 1, f"expected one rp_service.ts: {written}"
