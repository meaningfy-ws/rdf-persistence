"""rp-metamodel scenario "an application imports only what it uses" (fixture partial.yaml)."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main

from .conftest import TOY

LEAKED = ("TenantAccess", "Grant", "StoredFile", "Provenanced")
OUTPUTS = {
    "classes": "generated/partial.py",
    "shapes": "generated/shapes.ttl",
    "context": "generated/context.jsonld",
    "typescript": "web/partial.ts",
}


@pytest.fixture(scope="module")
def partial(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The partial schema generated with every artefact; returns the project folder."""
    project = tmp_path_factory.mktemp("partial") / "partial"
    project.mkdir()
    shutil.copy(TOY / "partial.yaml", project)
    (project / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "partial.yaml"\npackage = "partial.generated"\n'
        'python = "generated"\ntypescript = "web"\n'
    )
    assert main(["--project", str(project / "pyproject.toml")]) == 0, "the run failed"
    return project


def test_the_application_class_is_generated(partial: Path) -> None:
    assert "class Shelf(" in (partial / OUTPUTS["classes"]).read_text(), "the class is missing"


@pytest.mark.parametrize("artefact", OUTPUTS)
@pytest.mark.parametrize("absent", LEAKED)
def test_no_class_of_a_module_the_schema_does_not_import_is_in_any_artefact(
    partial: Path, artefact: str, absent: str
) -> None:
    text = (partial / OUTPUTS[artefact]).read_text()
    assert absent not in text, f"{absent} leaked into the {artefact} from a module not imported"
