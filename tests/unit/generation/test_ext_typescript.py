"""Step 6 (PD-25): the TypeScript types, one file per schema module plus an index, on the toy library."""

from pathlib import Path

import pytest

from rdf_persistence.generation.steps import TYPESCRIPT_STEP

from .golden import TOY_TARGET, assert_matches_toy, run_toy


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


def test_the_index_exports_the_service_types_once(staged: Path) -> None:
    index = text(staged, "index")
    assert index.count('export * from "./rp_service";') == 1, "the index exports rp_service once"
