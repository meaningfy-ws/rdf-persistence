"""The theme map the generator's tests share is the toolkit's targets, read, not written (192-j2)."""

from pathlib import Path

from rdf_persistence_generation.config import read_targets
from tests.generator.theme_map import THEME_OF_ROOT

PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"


def test_the_theme_map_is_read_from_the_targets() -> None:
    """Each domain target's root schema stem names the theme whose ``domain.generated`` package it fills."""
    expected = {
        Path(t.schema_file).stem: t.package.split(".")[1]
        for t in read_targets(PYPROJECT)
        if t.package.endswith(".domain.generated")
    }
    assert expected == THEME_OF_ROOT, "the map of the helper is the targets' own"
