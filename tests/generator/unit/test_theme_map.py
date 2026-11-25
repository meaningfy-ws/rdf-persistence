"""The theme map the generator's tests share is the toolkit's targets, read, not written (192-j2)."""

from tests.generator.theme_map import THEME_OF_ROOT

# The root stems of the domain targets of ``[tool.rp-generate]`` in ``pyproject.toml``, written down.
DOMAIN_ROOTS = {"rp", "rp_tenancy", "rp_provenance", "rp_files", "rp_collaboration"}


def test_the_theme_map_names_the_five_domain_roots_of_the_targets() -> None:
    """Only the targets whose package ends in ``.domain.generated`` are themes."""
    assert set(THEME_OF_ROOT) == DOMAIN_ROOTS, "one theme per domain target, no other target"


def test_the_metamodel_root_is_the_core_theme() -> None:
    assert THEME_OF_ROOT["rp"] == "core", "rp fills rdf_persistence.core.domain.generated"


def test_the_tenancy_root_is_the_access_theme() -> None:
    """The theme is the package's folder, not the root's name."""
    assert THEME_OF_ROOT["rp_tenancy"] == "access", "rp_tenancy fills the access package"
