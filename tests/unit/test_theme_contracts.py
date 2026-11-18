"""The import contracts that guard the turned-on themes while two layouts coexist (thematic-structure PD-6, D-13, D-16).

Until stage 7 the unmoved modules sit at ``rdf_persistence.{domain,services,adapters,entrypoints}`` and are
outside every theme contract. A turned-on theme must import none of them, and its domain must not reach a
technical model. These tests read ``.importlinter`` and name the contract that does it; the themes come from
``TURNED_ON`` of ``test_theme_layout``, so a stage that turns a theme on is checked without an edit here.
"""

import configparser
import fnmatch
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_theme_layout import TURNED_ON

ROOT = Path(__file__).resolve().parents[2]
THEMES = tuple(sorted(TURNED_ON))
THEME_LAYERS = ("domain", "services", "adapters", "entrypoints")
OLD_LAYERS = (
    "rdf_persistence.domain",
    "rdf_persistence.services",
    "rdf_persistence.adapters",
    "rdf_persistence.entrypoints",
)
OLD_LAYOUT = "themes-never-import-the-old-layout"
TECHNICAL_MODELS = "domain-never-imports-technical-models"


def _contracts(text: str | None = None) -> dict[str, dict[str, list[str]]]:
    """The contracts of ``.importlinter``, or of ``text`` when given."""
    parser = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    parser.read_string(text if text is not None else (ROOT / ".importlinter").read_text("utf-8"))
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


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("theme_layer", THEME_LAYERS)
@pytest.mark.parametrize("layer", OLD_LAYERS)
def test_a_contract_forbids_each_turned_on_theme_from_importing_each_old_layer(
    layer, theme_layer, theme
):
    module = f"rdf_persistence.{theme}.{theme_layer}"
    guarding = [
        name
        for name, options in _contracts().items()
        if options.get("type") == ["forbidden"]
        and any(_covers(source, module) for source in options.get("source_modules", []))
        and any(
            forbidden == layer or _covers(forbidden, layer)
            for forbidden in options.get("forbidden_modules", [])
        )
    ]

    assert guarding, f"no contract stops {module} importing {layer}"


@pytest.mark.parametrize("theme", THEMES)
def test_the_old_layout_contract_names_every_turned_on_theme_as_a_source(theme):
    sources = _contracts()[OLD_LAYOUT]["source_modules"]

    assert f"rdf_persistence.{theme}" in sources, f"{OLD_LAYOUT} has no source {theme}: {sources}"


@pytest.mark.parametrize("theme", THEMES)
def test_the_technical_models_contract_covers_the_domain_of_each_turned_on_theme(theme):
    contract = _contracts()[TECHNICAL_MODELS]

    assert any(
        _covers(source, f"rdf_persistence.{theme}.domain") for source in contract["source_modules"]
    ), f"{TECHNICAL_MODELS} does not cover the domain of {theme}"


# --- the old layers never reach up into a moved theme (thematic-structure D-14 C1), on a scratch layout ---

DOMAIN_UP = "old-domain-imports-no-theme-upper-layer"
SERVICES_UP = "old-services-import-no-theme-adapters-or-entrypoints"
ADAPTERS_UP = "old-adapters-import-no-theme-entrypoints"
ENTRYPOINTS_SIDEWAYS = "old-entrypoints-import-no-theme-adapters"
OLD_VS_THEMES = (DOMAIN_UP, SERVICES_UP, ADAPTERS_UP, ENTRYPOINTS_SIDEWAYS)
THEME_CONTRACTS = (
    "themes-ordered",
    "domain-of-a-theme-imports-no-upper-layer",
    OLD_LAYOUT,
)
SCRATCH_PACKAGES = (
    "",
    "domain",
    "services",
    "adapters",
    "entrypoints",
    *(theme for theme in THEMES),
    *(f"{theme}/{layer}" for theme in THEMES for layer in THEME_LAYERS),
    "iris/services/generated",
)


def _importing(*modules: str) -> str:
    return "".join(f"import rdf_persistence.{module}\n" for module in modules)


def _lint(
    tmp_path: Path, planted: dict[str, str], contracts: tuple[str, ...] = OLD_VS_THEMES
) -> tuple[int, list[str]]:
    """Run import-linter on a scratch package with only the named contracts of ``.importlinter``."""
    files = {f"{package}/__init__.py".removeprefix("/"): "" for package in SCRATCH_PACKAGES}
    for rel, text in {**files, **planted}.items():
        path = tmp_path / "rdf_persistence" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    source = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    source.read(ROOT / ".importlinter", encoding="utf-8")
    scratch = configparser.ConfigParser(interpolation=None)
    scratch["importlinter"] = {"root_packages": "\nrdf_persistence"}
    for name in contracts:
        section = f"importlinter:contract:{name}"
        assert source.has_section(section), f"contract {name} is gone from .importlinter"
        # the scratch name is the contract's key: a long name wraps over two lines of the report
        scratch[section] = {**source[section], "name": name}
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

    assert code != 0, "import-linter kept every contract"
    assert any(contract in line for line in broken), broken


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


# --- a turned-on theme never reaches the old layout; the themes keep their order (D-13 C1, D-16 C1, W2, S1) ---


def _breaks(tmp_path: Path, contract: str, planted: dict[str, str]) -> bool:
    code, broken = _lint(tmp_path, planted, (contract,))
    return code != 0 and any(contract in line for line in broken)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("old", [layer.rsplit(".", 1)[1] for layer in OLD_LAYERS])
def test_a_turned_on_theme_importing_an_old_layer_breaks_the_old_layout_contract(
    tmp_path, theme, old
):
    planted = {f"{theme}/services/x.py": _importing(old)}

    assert _breaks(tmp_path, OLD_LAYOUT, planted), f"{theme} imports rdf_persistence.{old} freely"


@pytest.mark.parametrize(
    ("contract", "where", "imports"),
    [
        pytest.param(
            "themes-ordered", "files/services/x.py", "provenance.services", id="files-to-provenance"
        ),
        pytest.param(
            "themes-ordered", "iris/services/x.py", "schema.services", id="iris-to-schema"
        ),
        pytest.param(
            "domain-of-a-theme-imports-no-upper-layer",
            "iris/domain/x.py",
            "iris.services.generated",
            id="iris-domain-to-iris-generated",
        ),
    ],
)
def test_a_planted_import_between_the_new_themes_breaks_its_contract(
    tmp_path, contract, where, imports
):  # TC-35
    assert _breaks(tmp_path, contract, {where: _importing(imports)})


@pytest.mark.parametrize(
    ("contract", "where", "imports"),
    [
        pytest.param(DOMAIN_UP, "domain/x.py", "schema.services", id="old-domain-to-schema"),
        pytest.param(SERVICES_UP, "services/x.py", "files.adapters", id="old-services-to-files"),
        pytest.param(
            ADAPTERS_UP, "adapters/x.py", "provenance.entrypoints", id="old-adapters-to-provenance"
        ),
        pytest.param(
            ENTRYPOINTS_SIDEWAYS, "entrypoints/x.py", "iris.adapters", id="old-entrypoints-to-iris"
        ),
    ],
)
def test_an_old_layer_importing_up_into_a_new_theme_breaks_its_contract(
    tmp_path, contract, where, imports
):
    assert _breaks(tmp_path, contract, {where: _importing(imports)})


# --- the theme contracts name every turned-on theme (thematic-structure D-17 W2), on a modified config text ---

LAYERED = "themes-layered"
ORDERED = "themes-ordered"


def _config_text() -> str:
    return (ROOT / ".importlinter").read_text(encoding="utf-8")


def _themes_missing_from_the_theme_contracts(text: str) -> list[str]:
    """The ``contract: theme`` pairs where a turned-on theme is absent from the containers or the layers."""
    contracts = _contracts(text)
    containers = set(contracts[LAYERED].get("containers", []))
    ordered = {
        module.strip()
        for line in contracts[ORDERED].get("layers", [])
        for module in line.split("|")
    }
    return [
        f"{name}: {theme}"
        for theme in THEMES
        for name, present in ((LAYERED, containers), (ORDERED, ordered))
        if f"rdf_persistence.{theme}" not in present
    ]


def _without_line(text: str, section: str, line: str) -> str:
    """``text`` with the one ``line`` of the contract ``section`` removed."""
    start = text.index(f"[importlinter:contract:{section}]")
    end = text.find("\n[importlinter:contract:", start + 1)
    block = text[start : end if end != -1 else len(text)]
    assert block.count(line) == 1, f"{line!r} is not once in {section}"
    return text[:start] + block.replace(line, "", 1) + (text[end:] if end != -1 else "")


def test_the_theme_contracts_name_every_turned_on_theme():
    assert _themes_missing_from_the_theme_contracts(_config_text()) == []


@pytest.mark.parametrize("theme", THEMES)
def test_a_turned_on_theme_missing_from_the_containers_is_found(theme):
    text = _without_line(_config_text(), LAYERED, f"    rdf_persistence.{theme}\n")

    assert _themes_missing_from_the_theme_contracts(text) == [f"{LAYERED}: {theme}"]


@pytest.mark.parametrize("theme", THEMES)
def test_a_turned_on_theme_missing_from_the_ordered_layers_is_found(theme):
    text = _config_text()
    module = f"rdf_persistence.{theme}"
    start = text.index(f"[importlinter:contract:{ORDERED}]")
    block = text[start:]
    line = next(
        entry
        for entry in block.splitlines()
        if entry.startswith("    ") and module in (m.strip() for m in entry.split("|"))
    )
    kept = " | ".join(m.strip() for m in line.split("|") if m.strip() != module)
    text = text[:start] + block.replace(line + "\n", f"    {kept}\n" if kept else "", 1)

    assert _themes_missing_from_the_theme_contracts(text) == [f"{ORDERED}: {theme}"]
