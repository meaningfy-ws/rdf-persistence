"""The import contracts that guard the themes (thematic-structure PD-6, D-16, D-17).

The themes keep their order and a domain reaches no technical model. These tests read ``.importlinter``
and name the contract that does it; the themes come from
``TURNED_ON`` of ``test_theme_layout``, so a stage that turns a theme on is checked without an edit here.

Each probe plants one import in a scratch package whose theme folders are the turned-on themes, runs the
repository's own contract on it (copied from ``.importlinter``, re-rooted), and expects it to be named
BROKEN (TC-60, TC-61 included); a control run on the unplanted layout is KEPT, so a broken run is the
plant's doing.
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
DOMAIN_CONTRACT = "domain-of-a-theme-imports-no-upper-layer"
EVENT_BUS_LIBRARIES = "event-bus-libraries-in-one-module"
FASTSTREAM = "faststream"
API_NO_BUS = "api-services-never-import-the-bus"
# The `api` services modules `api-services-never-import-the-bus` names; `api` sits above `messaging`, so
# the theme order does not keep them off the bus.
API_SERVICES = ("aggregates", "components", "documents", "file_removal")


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
def test_the_domain_contract_covers_the_domain_of_each_turned_on_theme(theme):
    contract = _contracts()[DOMAIN_CONTRACT]

    assert any(
        _covers(source, f"rdf_persistence.{theme}.domain") for source in contract["source_modules"]
    ), f"{DOMAIN_CONTRACT} does not cover the domain of {theme}"


# --- the scratch layout the probes run on ---

SCRATCH_PACKAGES = (
    "",
    *(theme for theme in THEMES),
    *(f"{theme}/{layer}" for theme in THEMES for layer in THEME_LAYERS),
    "iris/services/generated",
    "access/adapters/generated",
)
# Modules the event bus contract needs on the scratch layout: the one module that may import faststream
# (the contract's ``ignore_imports`` names it), and the bus, workflow and relay modules the plants aim at.
SCRATCH_MODULES = {
    "messaging/services/messagebus.py": "",
    "collaboration/services/workflows.py": "",
    "events/services/relay.py": "",
    "events/adapters/redis_events.py": f"import {FASTSTREAM}\n",
    **{f"api/services/{module}.py": "" for module in API_SERVICES},
    **{f"services/{module}.py": "" for module in API_SERVICES},
}


def _importing(*modules: str) -> str:
    return "".join(f"import rdf_persistence.{module}\n" for module in modules)


def _lint(
    tmp_path: Path, planted: dict[str, str], contracts: tuple[str, ...]
) -> tuple[int, list[str]]:
    """Run import-linter on a scratch package with only the named contracts of ``.importlinter``."""
    files = {f"{package}/__init__.py".removeprefix("/"): "" for package in SCRATCH_PACKAGES}
    files |= SCRATCH_MODULES
    for rel, text in {**files, **planted}.items():
        path = tmp_path / "rdf_persistence" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    source = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None)
    source.read(ROOT / ".importlinter", encoding="utf-8")
    scratch = configparser.ConfigParser(interpolation=None)
    scratch["importlinter"] = {
        "root_packages": "\nrdf_persistence",
        "include_external_packages": "True",
    }
    for name in contracts:
        section = f"importlinter:contract:{name}"
        assert source.has_section(section), f"contract {name} is gone from .importlinter"
        # the scratch name is the contract's key: a long name wraps over two lines of the report
        scratch[section] = {**source[section], "name": name}
    if EVENT_BUS_LIBRARIES in contracts:  # the scratch layout has no generator package
        scratch[f"importlinter:contract:{EVENT_BUS_LIBRARIES}"]["source_modules"] = (
            "\nrdf_persistence"
        )
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


# --- the themes keep their order and their domain stays pure (D-16 C1, W2, S1) ---


def _breaks(tmp_path: Path, contract: str, planted: dict[str, str]) -> bool:
    code, broken = _lint(tmp_path, planted, (contract,))
    return code != 0 and any(contract in line for line in broken)


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
        pytest.param(
            "themes-ordered",
            "persistence/services/x.py",
            "migrations.services",
            id="persistence-to-migrations",
        ),
        pytest.param(
            "themes-ordered",
            "persistence/services/x.py",
            "access.services",
            id="persistence-to-access",
        ),  # TC-45
    ],
)
def test_a_planted_import_between_the_new_themes_breaks_its_contract(
    tmp_path, contract, where, imports
):  # TC-35
    assert _breaks(tmp_path, contract, {where: _importing(imports)})


SERVICES_NO_ADAPTERS = "services-of-a-theme-import-no-adapters-or-entrypoints"


def test_a_service_of_a_theme_importing_a_wire_model_of_a_theme_breaks_layers_across_themes(
    tmp_path,
):  # TC-51
    planted = {"tenancy/services/x.py": _importing("access.adapters.generated")}

    assert _breaks(tmp_path, SERVICES_NO_ADAPTERS, planted)


def test_a_service_of_a_theme_importing_an_adapter_of_a_theme_breaks_layers_across_themes(tmp_path):
    planted = {"persistence/services/x.py": _importing("access.adapters")}

    assert _breaks(tmp_path, SERVICES_NO_ADAPTERS, planted)


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


# --- the bus sits above collaboration; only the Redis adapter imports the event bus libraries (TC-60, TC-61) ---

STAGE_CONTRACTS = (ORDERED, EVENT_BUS_LIBRARIES)


def test_the_scratch_layout_itself_keeps_both_contracts(tmp_path):
    """The control: the Redis adapter at its theme path imports faststream, which ``ignore_imports`` allows."""
    code, broken = _lint(tmp_path, {}, STAGE_CONTRACTS)

    assert (code, broken) == (0, []), broken


def test_collaboration_importing_the_message_bus_breaks_the_theme_order(tmp_path):
    """TC-60: the bus is in ``messaging``, above ``collaboration``, which it runs."""
    planted = {"collaboration/services/workflows.py": _importing("messaging.services.messagebus")}

    assert _breaks(tmp_path, ORDERED, planted)


def test_events_importing_collaboration_breaks_the_theme_order(tmp_path):
    """Same rank: ``events`` and ``collaboration`` are beside each other, so neither imports the other."""
    planted = {"events/services/relay.py": _importing("collaboration.services.workflows")}

    assert _breaks(tmp_path, ORDERED, planted)


@pytest.mark.parametrize("module", API_SERVICES)
def test_an_api_services_module_importing_the_message_bus_breaks_its_contract(tmp_path, module):
    """The four ``api`` services modules stay off the bus, which the theme order cannot say."""
    planted = {f"api/services/{module}.py": _importing("messaging.services.messagebus")}

    assert _breaks(tmp_path, API_NO_BUS, planted)


def test_the_api_services_modules_exist_where_the_bus_contract_names_them():
    sources = _contracts()[API_NO_BUS]["source_modules"]
    for module in API_SERVICES:
        assert f"rdf_persistence.api.services.{module}" in sources, module
        assert (ROOT / "rdf_persistence" / "api" / "services" / f"{module}.py").is_file(), module


def test_a_services_module_of_events_importing_faststream_breaks_the_one_module_rule(tmp_path):
    """TC-61: only the Redis adapter may import the event bus libraries."""
    planted = {"events/services/relay.py": f"import {FASTSTREAM}\n"}

    assert _breaks(tmp_path, EVENT_BUS_LIBRARIES, planted)
