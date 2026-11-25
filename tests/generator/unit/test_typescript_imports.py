"""The TypeScript step imports a module another target writes as TypeScript, and copies every other one.

consumer-friction PD-1 to PD-6: the owner of a module is found by its ``python_package`` in the
project's targets; the importer drops the module's file and points its imports at the owner's folder.
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.extensions import typescript
from rdf_persistence_generation.generated.rp_generation import GenerationTarget
from rdf_persistence_generation.steps import TYPESCRIPT_STEP

from .golden import TOY, assert_matches_toy, run_toy

VALUE_SCHEMA = "values/loan_checks.yaml"
TECHNICAL_SCHEMA = "services/loan_checks_response.yaml"
VALUE_PACKAGE = "tests.fixtures.library.domain.generated.values"


def toy_target(schema_file: str) -> GenerationTarget:
    return next(t for t in read_targets(TOY / "pyproject.toml") if t.schema_file == schema_file)


@pytest.fixture(scope="module")
def technical(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The staged folder of the technical target's TypeScript run."""
    target = toy_target(TECHNICAL_SCHEMA)
    staging = run_toy(TYPESCRIPT_STEP, tmp_path_factory.mktemp("technical"), target)
    return staging / str(target.typescript)


def test_an_imported_module_is_not_copied_and_is_imported_from_its_owner(
    technical: Path,
) -> None:  # TC-1
    assert not (technical / "loan_checks.ts").exists(), "the value module is the owner's file"
    response = (technical / "loan_checks_response.ts").read_text(encoding="utf-8")
    assert 'from "../../domain/generated/values/loan_checks"' in response, (
        "the import points at the owner's folder"
    )
    assert 'from "./loan_checks"' not in response, "no import of a file that is not written"
    index = (technical / "index.ts").read_text(encoding="utf-8")
    assert '"./loan_checks"' not in index, "the index exports no file that is not written"
    assert 'export * from "./loan_checks_response";' in index, "the target's own module is exported"


def test_the_technical_target_equals_the_committed_tree(tmp_path: Path) -> None:  # TC-2
    produced = run_toy(TYPESCRIPT_STEP, tmp_path, toy_target(TECHNICAL_SCHEMA))
    assert_matches_toy(produced, "web/src/services/generated/*.ts")


def test_the_value_target_equals_the_committed_tree(tmp_path: Path) -> None:  # TC-2
    produced = run_toy(TYPESCRIPT_STEP, tmp_path, toy_target(VALUE_SCHEMA))
    assert_matches_toy(produced, "web/src/domain/generated/values/*.ts")
    assert (produced / "web/src/domain/generated/values/loan_checks.ts").is_file(), (
        "the owner writes its own module"
    )


def files_of(folder: Path | None, owners: dict[str, Path]) -> dict[str, str]:
    schema = TOY / TECHNICAL_SCHEMA
    return {f.name: f.text for f in typescript.render(schema, folder=folder, owners=owners)}


def test_a_nested_owner_folder_gives_a_dotted_relative_specifier() -> None:  # TC-4
    files = files_of(
        Path("web/src/domain/generated"),
        {VALUE_PACKAGE: Path("web/src/domain/generated/values")},
    )
    assert 'from "./values/loan_checks"' in files["loan_checks_response.ts"], (
        "a folder below the importer's is reached with ./"
    )
    assert "loan_checks.ts" not in files, "the owner's module is not copied"


def test_with_no_owner_the_module_is_copied_and_exported() -> None:  # TC-5
    files = files_of(Path("web/src/services/generated"), {})
    assert "loan_checks.ts" in files, "no owner writes TypeScript, so the module is copied"
    assert 'from "./loan_checks"' in files["loan_checks_response.ts"], "the import stays local"
    assert 'export * from "./loan_checks";' in files["index.ts"], "the copy is exported"
