"""The import contracts that guard the ``core`` theme while two layouts coexist (thematic-structure PD-6, D-13).

Until stage 7 the unmoved modules sit at ``rdf_persistence.{domain,services,adapters,entrypoints}`` and are
outside every theme contract. ``core`` is the lowest theme and must import none of them, and its domain
must not reach a technical model. These tests read ``.importlinter`` and name the contract that does it.
"""

import configparser
import fnmatch
import subprocess
import sys
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
CORE_LAYERS = (
    "rdf_persistence.core.domain",
    "rdf_persistence.core.services",
    "rdf_persistence.core.adapters",
)


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


@pytest.mark.parametrize("core_layer", CORE_LAYERS)
@pytest.mark.parametrize("layer", OLD_LAYERS)
def test_a_contract_forbids_core_from_importing_each_old_layer(layer, core_layer):
    guarding = [
        name
        for name, options in _contracts().items()
        if options.get("type") == ["forbidden"]
        and any(_covers(source, core_layer) for source in options.get("source_modules", []))
        and any(
            forbidden == layer or _covers(forbidden, layer)
            for forbidden in options.get("forbidden_modules", [])
        )
    ]

    assert guarding, f"no contract stops rdf_persistence.core.* importing {layer}"


def test_the_technical_models_contract_covers_the_domain_of_core():
    contract = _contracts()["domain-never-imports-technical-models"]

    assert any(_covers(source, CORE_DOMAIN) for source in contract["source_modules"])


# --- the old layers never reach up into a moved theme (thematic-structure D-14 C1), on a scratch layout ---

DOMAIN_UP = "old-domain-imports-no-theme-upper-layer"
SERVICES_UP = "old-services-import-no-theme-adapters-or-entrypoints"
ADAPTERS_UP = "old-adapters-import-no-theme-entrypoints"
ENTRYPOINTS_SIDEWAYS = "old-entrypoints-import-no-theme-adapters"
OLD_VS_THEMES = (DOMAIN_UP, SERVICES_UP, ADAPTERS_UP, ENTRYPOINTS_SIDEWAYS)
SCRATCH_PACKAGES = (
    "",
    "domain",
    "services",
    "adapters",
    "entrypoints",
    "core",
    "core/domain",
    "core/services",
    "core/adapters",
    "core/entrypoints",
)


def _importing(*modules: str) -> str:
    return "".join(f"import rdf_persistence.{module}\n" for module in modules)


def _lint(tmp_path: Path, planted: dict[str, str]) -> tuple[int, list[str]]:
    """Run import-linter on a scratch package with only the contracts of ``OLD_VS_THEMES``."""
    files = {f"{package}/__init__.py".removeprefix("/"): "" for package in SCRATCH_PACKAGES}
    for rel, text in {**files, **planted}.items():
        path = tmp_path / "rdf_persistence" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    source = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    source.read(ROOT / ".importlinter", encoding="utf-8")
    scratch = configparser.ConfigParser(interpolation=None)
    scratch["importlinter"] = {"root_packages": "\nrdf_persistence"}
    for name in OLD_VS_THEMES:
        section = f"importlinter:contract:{name}"
        if source.has_section(section):
            scratch[section] = dict(source[section])
    config = tmp_path / "scratch.importlinter"
    with config.open("w", encoding="utf-8") as handle:
        scratch.write(handle)
    done = subprocess.run(
        [str(Path(sys.executable).parent / "lint-imports"), "--config", config.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, [line for line in done.stdout.splitlines() if line.endswith("BROKEN")]


@pytest.mark.parametrize(
    ("contract", "planted"),
    [
        pytest.param(
            DOMAIN_UP, {"domain/x.py": _importing("core.services")}, id="domain-to-core-services"
        ),
        pytest.param(
            DOMAIN_UP, {"domain/x.py": _importing("core.adapters")}, id="domain-to-core-adapters"
        ),
        pytest.param(
            DOMAIN_UP,
            {"domain/x.py": _importing("core.entrypoints")},
            id="domain-to-core-entrypoints",
        ),
        pytest.param(
            SERVICES_UP,
            {"services/x.py": _importing("core.adapters")},
            id="services-to-core-adapters",
        ),
        pytest.param(
            SERVICES_UP,
            {"services/x.py": _importing("core.entrypoints")},
            id="services-to-core-entrypoints",
        ),
        pytest.param(
            ADAPTERS_UP,
            {"adapters/x.py": _importing("core.entrypoints")},
            id="adapters-to-core-entrypoints",
        ),
        pytest.param(
            ENTRYPOINTS_SIDEWAYS,
            {"entrypoints/x.py": _importing("core.adapters")},
            id="entrypoints-to-core-adapters",
        ),
    ],
)
def test_an_old_layer_importing_up_into_a_theme_breaks_its_contract(tmp_path, contract, planted):
    code, broken = _lint(tmp_path, planted)
    name = _contracts()[contract]["name"][0]

    assert code != 0, "import-linter kept every contract"
    assert any(name in line for line in broken), broken


@pytest.mark.parametrize(
    "planted",
    [
        pytest.param({"domain/x.py": _importing("domain", "core.domain")}, id="domain"),
        pytest.param(
            {"services/x.py": _importing("services", "domain", "core.domain", "core.services")},
            id="services",
        ),
        pytest.param(
            {"adapters/x.py": _importing("adapters", "services", "core.services", "core.domain")},
            id="adapters",
        ),
        pytest.param(
            {"entrypoints/x.py": _importing("entrypoints", "services", "core.services")},
            id="entrypoints",
        ),
    ],
)
def test_an_old_layer_importing_itself_or_below_keeps_the_contracts(tmp_path, planted):
    code, broken = _lint(tmp_path, planted)

    assert (code, broken) == (0, []), broken
