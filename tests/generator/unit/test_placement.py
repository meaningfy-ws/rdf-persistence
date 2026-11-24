"""rp-generation scenario "placement from the table": each artefact goes where the table says."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

from .golden import TOY


def _files(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


@pytest.mark.slow
def test_typescript_goes_to_the_declared_folder_and_nowhere_else(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(TOY, project, ignore=shutil.ignore_patterns("generated", "golden", "web"))

    assert main(["--project", str(project / "pyproject.toml")]) == 0, "the run failed"

    typescript = {f for f in _files(project) if f.endswith(".ts")}
    assert typescript, "no TypeScript was written"
    assert all(f.startswith("web/src/domain/generated/") for f in typescript), (
        f"TypeScript outside the declared folder: {sorted(typescript)}"
    )
    assert any(f.startswith("domain/generated/diagrams/") for f in _files(project)), (
        "no diagram in the declared folder"
    )
    assert (project / "domain" / "generated" / "books.py").is_file(), (
        "the classes are not in the python folder"
    )


@pytest.mark.slow
def test_a_flag_overrides_the_table(tmp_path: Path) -> None:
    project = tmp_path / "library"
    shutil.copytree(TOY, project, ignore=shutil.ignore_patterns("generated", "golden", "web"))

    # a flag needs one entry: keep the toy's first target, the library's domain
    table = project / "pyproject.toml"
    table.write_text(
        table.read_text(encoding="utf-8").split("\n# A value module")[0], encoding="utf-8"
    )

    code = main(["--project", str(table), "--typescript-out", "client/types"])

    assert code == 0, "the run failed"
    assert (project / "client" / "types" / "index.ts").is_file(), "the flag was not used"
    assert not (project / "web").exists(), "the table's folder was used despite the flag"
