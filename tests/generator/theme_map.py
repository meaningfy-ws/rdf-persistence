"""The toolkit's themes by the root schema of their domain target, read from ``pyproject.toml`` (192-j2).

One source for the generator's tests: the theme map is what ``read_targets`` gives on the
repository's own targets, never a list written by hand.
"""

from pathlib import Path

from rdf_persistence_generation.config import read_targets

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"
DOMAIN_SUFFIX = ".domain.generated"


def theme_package(theme: str) -> str:
    """The Python package that holds the domain classes of ``theme``."""
    return f"rdf_persistence.{theme}{DOMAIN_SUFFIX}"


def _theme_of_root() -> dict[str, str]:
    return {
        Path(target.schema_file).stem: target.package.split(".")[1]
        for target in read_targets(PYPROJECT)
        if target.package.endswith(DOMAIN_SUFFIX)
    }


# Root schema stem to theme, in the order of the targets: ``rp`` is the ``core`` theme's.
THEME_OF_ROOT = _theme_of_root()
