"""The folders mypy is given when the targets' packages are not importable from the project (#301).

A value target lives in a folder under its domain target's (``domain/generated/values``); mypy named
both folders reports the inner package twice ("Duplicate module").
"""

from pathlib import Path

import pytest

from rdf_persistence_generation.checks.importable import _mypy_targets
from rdf_persistence_generation.generated.rp_generation import GenerationTarget


def _target(folder: str) -> GenerationTarget:
    return GenerationTarget(schema_file="m.yaml", package="no.such.package", python=folder)


@pytest.mark.parametrize(
    ("folders", "expected"),
    [
        (["domain/generated"], ["domain/generated"]),
        (["domain/generated", "services/generated"], ["domain/generated", "services/generated"]),
        (["domain/generated", "domain/generated/values"], ["domain/generated"]),
        (["domain/generated/values", "domain/generated"], ["domain/generated"]),
        (
            ["domain/generated", "domain/generated_other"],
            ["domain/generated", "domain/generated_other"],
        ),
        (["domain/generated", "domain/generated"], ["domain/generated"]),
    ],
    ids=[
        "one",
        "siblings",
        "nested",
        "nested-listed-first",
        "shared-prefix-is-not-nesting",
        "identical-listed-twice",
    ],
)
def test_a_folder_inside_another_listed_folder_is_left_out(
    tmp_path: Path, folders: list[str], expected: list[str]
) -> None:
    given = _mypy_targets([_target(f) for f in folders], tmp_path)

    assert sorted(given) == sorted(str((tmp_path / f).resolve()) for f in expected), (
        f"mypy would be given {given}"
    )
