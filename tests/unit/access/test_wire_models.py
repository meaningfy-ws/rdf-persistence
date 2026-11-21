"""The identity provider's wire shapes are technical models of the ``access`` theme's adapters (thematic-structure TC-50).

The ``Zitadel*`` records, ``JwtClaims``, ``DiscoveryDocument`` and ``BadRequestMeans`` are generated into
``rdf_persistence.access.adapters.generated``, where only the adapters of the theme and the testkit read them, and
no ``domain`` package of any theme declares one (PD-2, DEC-3).
"""

import ast
from importlib import import_module
from pathlib import Path

from tests.unit.package.test_theme_layout import PACKAGE, PLACED, ROOT

WIRE_PACKAGE = "rdf_persistence.access.adapters.generated"
WIRE_MODULE = f"{WIRE_PACKAGE}.rp_access_adapters"
WIRE_CLASSES = frozenset(
    name
    for placed in PLACED
    if (placed.theme, placed.layer, placed.group) == ("access", "adapters", "wire")
    for name in placed.classes
)


def _classes_declared_under_domains() -> dict[str, list[str]]:
    """Each wire class name that a ``.py`` file under a ``domain`` folder of the package declares."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / PACKAGE).rglob("*.py")):
        if "domain" not in path.relative_to(ROOT).parts:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and node.name in WIRE_CLASSES:
                found.setdefault(node.name, []).append(path.relative_to(ROOT).as_posix())
    return found


def test_the_placement_table_lists_the_zitadel_records_and_the_token_claims() -> None:
    assert {"JwtClaims", "DiscoveryDocument", "BadRequestMeans", "ZitadelUser"} <= WIRE_CLASSES, (
        "PLACED names the wire classes of the access adapters"
    )
    assert len(WIRE_CLASSES) > 30, "all the Zitadel records are named, not a sample"


def test_every_wire_class_is_generated_in_the_access_adapters_package() -> None:
    module = import_module(WIRE_MODULE)

    missing = sorted(name for name in WIRE_CLASSES if not hasattr(module, name))
    elsewhere = sorted(
        name
        for name in WIRE_CLASSES
        if hasattr(module, name) and getattr(module, name).__module__ != WIRE_MODULE
    )

    assert missing == [], f"not generated in {WIRE_MODULE}: {missing}"
    assert elsewhere == [], f"generated in another module, only imported here: {elsewhere}"


def test_no_domain_package_declares_a_wire_class() -> None:
    assert _classes_declared_under_domains() == {}, "a wire class sits in a domain folder"


def test_the_wire_package_stands_in_the_adapters_layer_of_the_access_theme() -> None:
    folder = Path(import_module(WIRE_PACKAGE).__path__[0]).relative_to(ROOT / PACKAGE)

    assert folder.parts == ("access", "adapters", "generated"), (
        "the wire models are in the adapters layer, which no domain imports"
    )
