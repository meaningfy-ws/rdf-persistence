"""rp-generation scenario "placement from the table": each artefact goes where the table says."""

import shutil
from pathlib import Path

from rdf_persistence.generation.cli import main

from .conftest import TOY


def _files(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


def test_typescript_goes_to_the_declared_folder_and_nowhere_else(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(TOY, project, ignore=shutil.ignore_patterns("generated", "golden", "web"))

    assert main(["--project", str(project / "pyproject.toml")]) == 0, "the run failed"

    typescript = {f for f in _files(project) if f.endswith(".ts")}
    assert typescript, "no TypeScript was written"
    assert all(f.startswith("web/src/domain/generated/") for f in typescript), (
        f"TypeScript outside the declared folder: {sorted(typescript)}"
    )
    assert any(f.startswith("generated/diagrams/") for f in _files(project)), (
        "no diagram in the declared folder"
    )
    assert (project / "generated" / "books.py").is_file(), "the classes are not in the python folder"


def test_a_flag_overrides_the_table(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(TOY, project, ignore=shutil.ignore_patterns("generated", "golden", "web"))

    code = main(
        ["--project", str(project / "pyproject.toml"), "--typescript-out", "client/types"]
    )

    assert code == 0, "the run failed"
    assert (project / "client" / "types" / "index.ts").is_file(), "the flag was not used"
    assert not (project / "web").exists(), "the table's folder was used despite the flag"
