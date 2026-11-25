"""A TypeScript copy an earlier run wrote is removed once the owner writes the type (consumer-friction TC-6).

Before the value target wrote TypeScript, the technical target that imports its classes wrote a copy of
them. When the owner starts writing TypeScript, the next run removes the copy through the manifest.
"""

import shutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

TOY = Path(__file__).parents[2] / "fixtures" / "library"
OWNER_LINE = 'typescript = "web/src/domain/generated/values"\n'
COPY = Path("web/src/services/generated/loan_checks.ts")
OWNED = Path("web/src/domain/generated/values/loan_checks.ts")


@pytest.mark.slow
def test_the_old_copy_is_removed_once_the_owner_writes_typescript(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(
        TOY, project, ignore=shutil.ignore_patterns("__pycache__", "generated", "golden", "web")
    )
    pyproject = project / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")
    assert OWNER_LINE in original, "the toy's value target must write TypeScript: nothing to remove"

    pyproject.write_text(original.replace(OWNER_LINE, "", 1), encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the earlier run must generate"
    assert (project / COPY).is_file(), "the earlier run must write the copy, or the test is vacuous"
    assert not (project / OWNED).exists(), "the owner writes no TypeScript in the earlier run"

    pyproject.write_text(original, encoding="utf-8")
    assert main(["--project", str(pyproject)]) == 0, "the later run must generate"
    assert not (project / COPY).exists(), "the copy of the earlier run must be removed"
    assert (project / OWNED).is_file(), "the owner must now write the TypeScript"
