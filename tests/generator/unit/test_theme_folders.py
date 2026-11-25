"""The generated domain folder of each theme holds the modules its target generates, no more (192-k)."""

from pathlib import Path

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import generated_schemas
from rdf_persistence_generation.config import read_targets

REPO = Path(__file__).parents[3]
THEME_FOLDER_SUFFIX = ".domain.generated"


def _modules_generated_by(schema_file: str) -> set[str]:
    """The stems of the schemas the target of ``schema_file`` writes Python for: those with a class."""
    root = REPO / schema_file
    return {s.name for s in generated_schemas(load_schema(root), root.parent) if s.classes}


def test_each_theme_domain_generated_folder_holds_exactly_its_modules() -> None:
    """A stray module in a theme's folder, or a missing one, is a drift from the target that writes it."""
    targets = [
        t for t in read_targets(REPO / "pyproject.toml") if t.package.endswith(THEME_FOLDER_SUFFIX)
    ]
    assert len(targets) > 1, "the toolkit's domain targets were read"
    for target in targets:
        folder = REPO.joinpath(*target.package.split("."))
        found = {p.stem for p in folder.glob("*.py") if p.name != "__init__.py"}
        assert found == _modules_generated_by(target.schema_file), (
            f"the modules of {folder.relative_to(REPO)}"
        )
