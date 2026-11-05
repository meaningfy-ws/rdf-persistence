"""rp-metamodel scenario "an application imports only what it uses" (fixture partial.yaml)."""

import shutil
from pathlib import Path

from rdf_persistence.generation.cli import main

from .conftest import TOY


def test_a_partial_schema_generates_only_what_it_imports(tmp_path: Path) -> None:
    project = tmp_path / "partial"
    project.mkdir()
    shutil.copy(TOY / "partial.yaml", project)
    (project / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "partial.yaml"\npackage = "partial.generated"\n'
        'python = "generated"\n'
    )

    assert main(["--project", str(project / "pyproject.toml")]) == 0, "the run failed"

    code = (project / "generated" / "partial.py").read_text()
    assert "class Shelf(" in code, "the application's class is missing"
    for absent in ("TenantAccess", "Grant", "StoredFile", "Provenanced"):
        assert absent not in code, f"{absent} leaked in from a module the schema does not import"
