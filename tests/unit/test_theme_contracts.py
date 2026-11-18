"""The import contracts that guard the ``core`` theme while two layouts coexist (thematic-structure PD-6, D-13).

Until stage 7 the unmoved modules sit at ``rdf_persistence.{domain,services,adapters,entrypoints}`` and are
outside every theme contract. ``core`` is the lowest theme and must import none of them, and its domain
must not reach a technical model. These tests read ``.importlinter`` and name the contract that does it.
"""

import configparser
import fnmatch
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OLD_LAYERS = (
    "rdf_persistence.domain",
    "rdf_persistence.services",
    "rdf_persistence.adapters",
    "rdf_persistence.entrypoints",
)
CORE_DOMAIN = "rdf_persistence.core.domain"


def _contracts() -> dict[str, dict[str, list[str]]]:
    parser = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    parser.read(ROOT / ".importlinter", encoding="utf-8")
    return {
        section.removeprefix("importlinter:contract:"): {
            key: [
                line.strip()
                for line in value.splitlines()
                if line.strip() and not line.strip().startswith(";")
            ]
            for key, value in parser.items(section)
        }
        for section in parser.sections()
        if section.startswith("importlinter:contract:")
    }


def _covers(source: str, module: str) -> bool:
    """Whether a contract source expression covers ``module`` (a package covers its descendants)."""
    parts = source.split(".")
    head = ".".join(module.split(".")[: len(parts)])
    return fnmatch.fnmatchcase(head, source)


@pytest.mark.parametrize("layer", OLD_LAYERS)
def test_a_contract_forbids_core_from_importing_each_old_layer(layer):
    guarding = [
        name
        for name, options in _contracts().items()
        if options.get("type") == ["forbidden"]
        and any(_covers(source, CORE_DOMAIN) for source in options.get("source_modules", []))
        and any(
            forbidden == layer or _covers(forbidden, layer)
            for forbidden in options.get("forbidden_modules", [])
        )
    ]

    assert guarding, f"no contract stops rdf_persistence.core.* importing {layer}"


def test_the_technical_models_contract_covers_the_domain_of_core():
    contract = _contracts()["domain-never-imports-technical-models"]

    assert any(_covers(source, CORE_DOMAIN) for source in contract["source_modules"])
