"""Step 6 (PD-25): the TypeScript types, one file per schema module plus an index, on the toy library."""

from pathlib import Path

import pytest

from rdf_persistence_generation.extensions import typescript
from rdf_persistence_generation.steps import TYPESCRIPT_STEP

from .conftest import ROOT_SCHEMA
from .golden import TOY_TARGET, assert_matches_golden, assert_matches_toy, run_toy


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_toy(TYPESCRIPT_STEP, tmp_path_factory.mktemp("typescript"))


@pytest.fixture(scope="module")
def staged(rendered: Path) -> Path:
    return rendered / str(TOY_TARGET.typescript)


def text(staged: Path, module: str) -> str:
    return (staged / f"{module}.ts").read_text(encoding="utf-8")


def test_the_output_equals_the_committed_tree(rendered: Path) -> None:
    assert_matches_toy(rendered, "web/src/domain/generated/*.ts")


def test_every_module_has_a_file_and_the_index_exports_them(staged: Path) -> None:
    index = text(staged, "index")
    for module in (
        "books",
        "scans",
        "library_tenant",
        "library_access",
        "rp_core",
        "rp_access",
        "rp_tenancy",
    ):
        assert (staged / f"{module}.ts").is_file(), f"no file for {module}"
        assert f'export * from "./{module}";' in index, f"the index skips {module}"


def test_an_enum_is_a_union_of_its_values(staged: Path) -> None:
    books = text(staged, "books")
    assert "export type Genre =" in books, "the enum is a type"
    assert all(f'| "{value}"' in books for value in ("fiction", "nonfiction", "poetry")), (
        "a value is missing"
    )
    assert "enum Genre" not in books, "an enum would need runtime code"


def test_dates_are_iso_strings_and_numbers_are_numbers(staged: Path) -> None:
    books = text(staged, "books")
    assert "published?: string;" in books, "a date travels as an ISO string"
    assert "number?: number;" in books, "an integer is a number"
    assert "Date" not in books.replace("Publication date", ""), "no Date objects"


def test_owned_parts_are_nested_and_references_are_iris(staged: Path) -> None:
    assert "chapters?: Chapter[];" in text(staged, "books"), "an owned part is nested"
    assert "scan_of?: string;" in text(staged, "scans"), "another aggregate is referred to by IRI"


def test_a_type_of_another_module_is_imported(staged: Path) -> None:
    access = text(staged, "library_access")
    assert 'import type { TenantState } from "./rp_tenancy";' in access, (
        "an enum of another module is imported"
    )
    assert "import type { Grant, Prohibition } from" in access, (
        "a class of another module is imported"
    )


def test_an_internal_slot_is_skipped(staged: Path) -> None:
    files = {p.name: p.read_text(encoding="utf-8") for p in staged.iterdir()}
    assert not [name for name, body in files.items() if "file_key" in body], "file_key is internal"
    assert "file_name?: string;" in files["scans.ts"], "the other file slots stay"


def test_an_unconfigured_target_writes_nothing(tmp_path: Path) -> None:
    run_toy(TYPESCRIPT_STEP, tmp_path, TOY_TARGET.model_copy(update={"typescript": None}))
    assert not list(tmp_path.iterdir()), "no TypeScript folder, no output"


def test_the_output_is_reproducible(staged: Path, tmp_path: Path) -> None:
    again = run_toy(TYPESCRIPT_STEP, tmp_path) / str(TOY_TARGET.typescript)
    first = {p.name: p.read_bytes() for p in staged.iterdir()}
    assert first == {p.name: p.read_bytes() for p in again.iterdir()}, "two runs differ"


def test_the_service_types_are_written_with_any_as_unknown(staged: Path) -> None:
    service = text(staged, "rp_service")
    for name in (
        "AccountSummary",
        "TenantSummary",
        "TenantCreate",
        "Page",
        "Problem",
        "GrantSet",
        "LabelUpdate",
    ):
        assert f"export interface {name} " in service, f"{name} is missing from rp_service.ts"
    assert "root: unknown;" in service, "a slot ranging over Any is unknown"
    assert "items: unknown[];" in service, "a multivalued slot ranging over Any is unknown[]"
    assert "interface Any" not in service, "Any has no interface of its own"


def test_the_merged_file_keeps_the_name_of_the_service_schema_whatever_comes_first(
    staged: Path,
) -> None:  # TC-07
    first = typescript.SERVED_SCHEMAS[0].stem
    assert first != typescript.SERVICE_MODULE, "a schema is served before the service schema"
    assert (staged / "rp_service.ts").is_file(), "the types of the served schemas are rp_service.ts"
    assert not (staged / f"{first}.ts").exists(), "no file named after the first served schema"
    assert "export type IdKind =" in text(staged, "rp_service"), (
        "the first schema's types are in it"
    )


def test_the_index_exports_the_service_types_once(staged: Path) -> None:
    index = text(staged, "index")
    assert index.count('export * from "./rp_service";') == 1, "the index exports rp_service once"


def test_the_toy_typescript_equals_the_golden_files(rendered: Path) -> None:  # TC-07
    assert_matches_golden("served_typescript", rendered / str(TOY_TARGET.typescript))


EXTRA_SERVED = """id: https://example.org/ns/library/extra_served
name: extra_served
title: Extra served
description: A second served technical module.
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
  ExtraPage:
    title: Extra page
    description: A class of the second served schema.
    attributes:
      extra_id:
        description: Identifier.
        identifier: true
"""


EXTRA_SERVED_DEPENDENT = (
    EXTRA_SERVED.replace("extra_served", "extra_dependent")
    .replace("  - linkml:types\n", "  - linkml:types\n  - extra_served\n")
    .replace("ExtraPage:", "DependentPage:")
)


def test_every_served_schema_is_merged_into_one_service_file_in_served_order(
    toy_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = toy_copy / "extra_served.yaml"
    extra.write_text(EXTRA_SERVED, encoding="utf-8")
    dependent = toy_copy / "extra_dependent.yaml"
    dependent.write_text(EXTRA_SERVED_DEPENDENT, encoding="utf-8")
    monkeypatch.setattr(
        typescript, "SERVED_SCHEMAS", (*typescript.SERVED_SCHEMAS, extra, dependent)
    )
    rendered_files = typescript.render(toy_copy / ROOT_SCHEMA)
    files = {f.name: f.text for f in rendered_files}
    service = files["rp_service.ts"]
    assert "extra_served.ts" not in files, "a served schema gets no file of its own"
    assert "extra_dependent.ts" not in files, "a served schema gets no file of its own"
    assert 'export * from "./extra_served";' not in files["index.ts"], (
        "the index names no such file"
    )
    assert files["index.ts"].count('export * from "./rp_service";') == 1, (
        "rp_service is exported once"
    )
    assert service.count("export interface ExtraPage ") == 1, "a type reached twice is written once"
    assert service.index("export interface AccountSummary ") < service.index(
        "export interface ExtraPage "
    ), "the served schemas keep their order inside rp_service.ts"
    assert service.index("export interface ExtraPage ") < service.index(
        "export interface DependentPage "
    ), "the served schemas keep their order inside rp_service.ts"
    assert service.count("Generated by rp-generate") == 1, "one header: it is one file"


USES_EXTRA = (
    EXTRA_SERVED.replace("extra_served", "uses_extra")
    .replace("  - linkml:types\n", "  - linkml:types\n  - extra_served\n")
    .replace("ExtraPage:", "Shelf:")
    .replace(
        "extra_id:\n        description: Identifier.\n        identifier: true",
        "shelf_id:\n        description: Identifier.\n        identifier: true\n"
        "      page:\n        description: A page of the second served schema.\n"
        "        range: ExtraPage\n        inlined: true",
    )
)


def test_a_module_that_names_a_served_type_imports_the_merged_file(
    toy_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:  # D-10
    # the served schema lives in another folder, as the toolkit's do: a schema beside the root that
    # names a served module is refused (the reserved names)
    (toy_copy / "served").mkdir()
    (toy_copy / "served" / "extra_served.yaml").write_text(EXTRA_SERVED, encoding="utf-8")
    (toy_copy / "uses_extra.yaml").write_text(
        USES_EXTRA.replace("  - extra_served\n", "  - served/extra_served\n"), encoding="utf-8"
    )
    root = toy_copy / ROOT_SCHEMA
    root.write_text(
        root.read_text(encoding="utf-8").replace("  - books\n", "  - books\n  - uses_extra\n", 1),
        encoding="utf-8",
    )
    served = (*typescript.SERVED_SCHEMAS, toy_copy / "served" / "extra_served.yaml")
    monkeypatch.setattr(typescript, "SERVED_SCHEMAS", served)

    files = {f.name: f.text for f in typescript.render(root)}

    shelf = files["uses_extra.ts"]
    assert 'import type { ExtraPage } from "./rp_service";' in shelf, (
        "the import points at the merged file"
    )
    assert "./extra_served" not in shelf, "no import of a file that is not written"


@pytest.mark.parametrize(
    "line",
    [
        "filters?: Filter[];",
        "conditions?: Condition[];",
        "caller_access: CallerAccess;",
        "iri_policy?: IriPolicy;",
    ],
)
def test_an_inlined_class_range_names_its_interface(staged: Path, line: str) -> None:
    assert line in text(staged, "rp_service"), f"{line!r} is missing: an inlined class is a string"
