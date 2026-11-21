"""The technical schemas live under ``model/technical/`` and generate outside the domain (technical-models stage 1).

TC-06..TC-10 and TC-53: the folder holds only technical modules, the domain folder none, the
generated service models sit in ``services``, and the import contracts refuse the domain's reach
into them (PD-1, PD-2).
"""

import ast
import configparser
import re
import subprocess
import sys
import tomllib
from importlib import import_module
from pathlib import Path

import pytest
import yaml

from tests.unit.import_contracts import (
    CONTRACT_DOMAIN,
    CONTRACT_ENTRYPOINTS,
    CONTRACT_RUNTIME,
    CONTRACT_SERVICES,
    lint_scratch,
)

ROOT = Path(__file__).parents[3]
PACKAGE = ROOT / "rdf_persistence"
MODEL = PACKAGE / "model"
TECHNICAL = MODEL / "technical"
KIND_KEY, TECHNICAL_KIND = "module_kind", "technical"
SERVICE_SCHEMA_PACKAGE = "rdf_persistence.api.entrypoints.generated"


def _module_kind(path: Path) -> str | None:
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    return (schema.get("annotations") or {}).get(KIND_KEY)


def test_every_schema_under_model_technical_is_annotated_technical():  # TC-06
    schemas = sorted(TECHNICAL.rglob("*.yaml"))
    assert schemas, "the technical folder holds the service and wire schemas"
    wrong = [p.name for p in schemas if _module_kind(p) != TECHNICAL_KIND]
    assert wrong == [], f"schemas under model/technical/ not annotated technical: {wrong}"


def test_no_schema_directly_under_model_is_annotated_technical():  # TC-07
    wrong = [p.name for p in sorted(MODEL.glob("*.yaml")) if _module_kind(p) == TECHNICAL_KIND]
    assert wrong == [], f"domain schemas annotated technical: {wrong}"


def test_the_service_models_generate_outside_the_domain():  # TC-08
    domain_generated = import_module("rdf_persistence.core.domain.generated")
    assert not (Path(domain_generated.__path__[0]) / "service").exists(), (
        "no service subpackage is left under domain.generated"
    )
    service = import_module(f"{SERVICE_SCHEMA_PACKAGE}.rp_api_entrypoints")
    wire = import_module("rdf_persistence.access.adapters.generated.rp_access_adapters")
    assert hasattr(service, "Problem"), "api.entrypoints.generated defines Problem"
    assert hasattr(wire, "JwtClaims"), "access.adapters.generated defines JwtClaims"


# --- the import contracts, run on a scratch copy of the layout (TC-09, TC-10, TC-53) ---------------


def _lint(tmp_path: Path, planted: dict[str, str]) -> tuple[int, list[str]]:
    """``(exit code, keys of the broken contracts)`` of the kept contracts on the scratch layout."""
    linted = lint_scratch(tmp_path, planted)
    return linted.code, linted.broken


def test_the_scratch_layout_itself_keeps_every_contract(tmp_path):
    assert _lint(tmp_path, {}) == (0, [])


def test_a_domain_module_importing_the_service_models_breaks_the_domain_contract(tmp_path):  # TC-09
    code, broken = _lint(
        tmp_path,
        {"core/domain/generated/rp_core.py": f"import {SERVICE_SCHEMA_PACKAGE}\n"},
    )
    assert code != 0, broken
    assert CONTRACT_DOMAIN in broken, broken


def test_a_service_module_importing_the_wire_models_breaks_the_services_contract(tmp_path):  # TC-10
    code, broken = _lint(
        tmp_path,
        {"persistence/services/session.py": f"import {WIRE}\n"},
    )
    assert code != 0, broken
    assert CONTRACT_SERVICES in broken, broken


def test_the_policy_free_layout_importing_the_service_models_breaks_the_domain_contract(
    tmp_path,
):  # TC-53
    code, broken = _lint(
        tmp_path,
        {"iris/domain/layout.py": f"import {SERVICE_SCHEMA_PACKAGE}\n"},
    )
    assert code != 0, broken
    assert CONTRACT_DOMAIN in broken, broken


WIRE = "rdf_persistence.access.adapters.generated.rp_access_adapters"
TESTKIT_MODELS = "rdf_persistence.testkit.generated"
PLANT_TESTKIT = {"testkit/__init__.py": "", "testkit/generated/__init__.py": ""}
HELPER = "from rdf_persistence.{theme}.{layer} import helper\n"


@pytest.mark.parametrize(
    ("planted", "contract"),
    [
        pytest.param(
            {
                "core/domain/generated/rp_core.py": HELPER.format(theme="core", layer="domain"),
                "core/domain/helper.py": f"from {WIRE} import JwtClaims\n",
            },
            CONTRACT_DOMAIN,
            id="indirect-to-the-wire-models",
        ),
        pytest.param(
            {"iris/domain/layout.py": f"import {TESTKIT_MODELS}\n", **PLANT_TESTKIT},
            CONTRACT_RUNTIME,
            id="testkit-generated-direct",
        ),
        pytest.param(
            {
                "iris/domain/layout.py": HELPER.format(theme="iris", layer="domain"),
                "iris/domain/helper.py": f"import {TESTKIT_MODELS}\n",
                **PLANT_TESTKIT,
            },
            CONTRACT_RUNTIME,
            id="testkit-generated-indirect",
        ),
    ],
)
def test_a_domain_module_reaching_a_technical_model_indirectly_breaks_a_contract(
    tmp_path, planted, contract
):
    """Row 3: probe of PD-1; a chain through a helper, and the testkit's generated models.

    The domain never imports a technical model of an upper layer (``layers-across-themes``) nor the
    testkit's (``runtime-without-extras``), which replace ``domain-never-imports-technical-models``.
    """
    code, broken = _lint(tmp_path, planted)
    assert code != 0, broken
    assert contract in broken, broken


@pytest.mark.parametrize(
    ("planted", "contract"),
    [
        pytest.param(
            {
                "persistence/services/session.py": HELPER.format(
                    theme="persistence", layer="services"
                ),
                "persistence/services/helper.py": f"import {WIRE}\n",
            },
            CONTRACT_SERVICES,
            id="service-through-a-helper",
        ),
        pytest.param(
            {"api/entrypoints/router.py": f"import {WIRE}\n"},
            CONTRACT_ENTRYPOINTS,
            id="entrypoint-direct",
        ),
    ],
)
def test_a_service_or_entrypoint_reaching_a_wire_model_breaks_a_layer_contract(
    tmp_path, planted, contract
):
    """Row 4: probe of PD-2; the entrypoint, and a service that reaches it through a helper."""
    code, broken = _lint(tmp_path, planted)
    assert code != 0, broken
    assert contract in broken, broken


@pytest.mark.parametrize(
    "dotted",
    [
        "rdf_persistence.domain.iris",
        "rdf_persistence.domain.tenant_move",
        "rdf_persistence.domain.generated.service.rp_service",
        "rdf_persistence.adapters.rp_wire",
        "rdf_persistence.domain.generated.rp_service",
    ],
)
def test_an_old_import_path_is_a_module_not_found_error(dotted):
    """Probe of DEC-9: no shim; a fresh interpreter, so no cached module hides a leftover."""
    code = f"import importlib; importlib.import_module({dotted!r})"
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert done.returncode != 0, f"{dotted} still imports"
    assert "ModuleNotFoundError" in done.stderr, done.stderr[-300:]


def test_a_stale_toolkit_folder_stops_the_service_at_start(monkeypatch):
    """Row 6: the components are read at install, so the old place gives an error, never an empty document."""
    from rdf_persistence.api.entrypoints import openapi
    from tests.toy_service import ToyService

    stale = ROOT / "rdf_persistence" / "domain" / "generated" / "service"
    monkeypatch.setattr(openapi, "served_folders", lambda: (stale,))  # X1
    with pytest.raises(OSError):
        ToyService()


OLD_PATH = re.compile(
    r"domain[./]generated[./]service"
    r"|domain[./]iris\b"
    r"|domain[./]tenant_move"
    r"|\"domain\"\s*,\s*\"generated\"\s*,\s*\"service\""
    r"|\"domain\"\s*/\s*\"generated\"\s*/\s*\"service\""
    r"|(?<!technical/)model/(?:service|adapters)\b"
)
SCANNED_SUFFIXES = {".py", ".adoc", ".toml", ".cfg", ".yaml", ".yml", ".md", ".importlinter", ".mk"}
SCANNED_NAMES = {"Makefile", ".importlinter"}
CHANGELOG = "CHANGELOG.md"  # the release notes name the old paths on purpose (D-10)
SKIPPED_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "temp",
    "openspec",
    "generated",
    "audit",
}


def test_no_live_file_still_names_an_old_path():
    """Found: questions.adoc and data-flows.adoc still named model/service/ (D-8).

    Code, tests, docs and configuration are scanned; the change's own history under openspec/ and the changelog are exempt.
    """
    this = Path(__file__).resolve()
    hits = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or SKIPPED_PARTS & set(path.relative_to(ROOT).parts):
            continue
        if (
            path.resolve() == this
            or path.name == CHANGELOG
            or (path.suffix not in SCANNED_SUFFIXES and path.name not in SCANNED_NAMES)
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{path.relative_to(ROOT)}: {m.group(0)}" for m in OLD_PATH.finditer(text)]
    assert hits == [], "old paths still named:\n" + "\n".join(hits)


# --- stage 4: the testkit's records get their own technical target (PD-11, TC-49..TC-51) -----------

TESTKIT = PACKAGE / "testkit"
GENERATION_DIR = PACKAGE.parent / "rdf_persistence_generation"
GENERATION_SCHEMA = GENERATION_DIR / "model" / "rp_generation.yaml"
TESTKIT_SCHEMA = TECHNICAL / "testkit" / "rp_testkit.yaml"
MOVED_CLASSES = {
    "ClassShape",
    "SlotShape",
    "ContainerMarker",
    "Violation",
    "MachineUser",
    "ZitadelProject",
    "ZitadelServer",
    "ExecResult",
    "FusekiServer",
    "GarageServer",
}
# the slots only the moved classes use; `name`, `required`, `multivalued`, `range`, `class_name`
# and `what` are shared with classes that stay, so they stay.
MOVED_ONLY_SLOTS = {
    "alias",
    "slots",
    "marker",
    "container",
    "help",
    "where",
    "stdout",
    "stderr",
    "url",
    "user",
    "password",
    "endpoint",
    "key_id",
    "secret",
    "region",
    "admin_pat",
    "exit_code",
    "user_id",
    "private_key",
    "server",
    "organisation_id",
    "project_id",
    "machine_users",
}
GENERATION_GENERATED = "rdf_persistence_generation.generated"
KEEPS_THE_GENERATION_MODELS = {
    "freshness.py",
    "conformance.py",
}  # F-1: generator-package moves them


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def test_the_testkit_target_is_technical_and_generates_into_the_testkit():  # PD-11
    schema = yaml.safe_load(TESTKIT_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["classes"]) >= MOVED_CLASSES | {"FieldFlags"}, (
        "the ten records and FieldFlags"
    )
    rows = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "rp-generate"
    ]
    (row,) = [r for r in rows if r["schema"] == TESTKIT_SCHEMA.relative_to(ROOT).as_posix()]
    assert "kind" not in row, "the kind of a target is derived from its modules, never declared"
    assert (row["package"], row["openapi"]) == (TESTKIT_MODELS, False), (
        "the testkit target of PD-11"
    )


def test_no_testkit_module_but_freshness_and_conformance_imports_the_generation_models():  # TC-50
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(TESTKIT.rglob("*.py"))
        if path.name not in KEEPS_THE_GENERATION_MODELS
        and "generated" not in path.relative_to(TESTKIT).parts
        and any(m.startswith(GENERATION_GENERATED) for m in _imported_modules(path))
    ]
    assert offenders == [], f"testkit modules still importing {GENERATION_GENERATED}: {offenders}"


def test_the_moved_records_come_from_the_testkit_package():  # TC-50
    models = import_module(f"{TESTKIT_MODELS}.rp_testkit")
    assert all(hasattr(models, name) for name in MOVED_CLASSES | {"FieldFlags"}), (
        "a moved record is missing from the testkit package"
    )


def test_the_generation_schema_declares_none_of_the_moved_records_nor_their_own_slots():  # TC-51
    schema = yaml.safe_load(GENERATION_SCHEMA.read_text(encoding="utf-8"))
    assert MOVED_CLASSES & set(schema["classes"]) == set(), "a moved class is still declared"
    assert MOVED_ONLY_SLOTS & set(schema["slots"]) == set(), (
        "a slot only they used is still declared"
    )
    assert {"ConstraintCase", "GenerationTarget"} <= set(schema["classes"]), "the stayers"
    assert "ConstraintKind" in schema["enums"], "ConstraintKind stays with ConstraintCase"
    assert "kind" in schema["slots"], "the global slot `kind` stays"


def test_no_testkit_or_generation_module_copies_a_model_with_model_copy_update():  # TC-49
    hits = []
    for folder in (TESTKIT, GENERATION_DIR):
        for path in sorted(folder.rglob("*.py")):
            if "generated" in path.relative_to(folder).parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "model_copy"
                    and any(k.arg == "update" for k in node.keywords)
                ):
                    hits.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert hits == [], f"model_copy(update=...) skips validation; use replaced(): {hits}"


# --- the generator contracts of generator-package (D-19, D-20) -------------------------------------

GENERATOR_PACKAGE = "rdf_persistence_generation"
CONTRACT_NEVER_IMPORTS_GENERATOR = "library-never-imports-the-generator"


def _contract(name: str) -> configparser.SectionProxy:
    config = configparser.ConfigParser()
    config.read(ROOT / ".importlinter", encoding="utf-8")
    section = f"importlinter:contract:{name}"
    assert config.has_section(section), f".importlinter declares the contract {name}"
    return config[section]


def _lines(contract: configparser.SectionProxy, key: str) -> list[str]:
    return [line.strip() for line in contract.get(key, "").splitlines() if line.strip()]


def test_the_library_never_imports_the_generator():
    contract = _contract(CONTRACT_NEVER_IMPORTS_GENERATOR)
    assert contract["type"] == "forbidden"
    assert _lines(contract, "source_modules") == ["rdf_persistence"]
    assert _lines(contract, "forbidden_modules") == [GENERATOR_PACKAGE]
    assert _lines(contract, "ignore_imports") == [], "the contract ignores an edge"


WITHOUT_GENERATE_EXTRA_SOURCES = {
    f"{GENERATOR_PACKAGE}.{m}"
    for m in (
        "cli",
        "config",
        "manifest",
        "pipeline",
        "exceptions",
        "problems",
        "generated",
        "testkit",
        "uml",
    )
} | {
    "rdf_persistence.testkit",
    "rdf_persistence.schema.services.schema",
    "rdf_persistence.schema.services.schema_structure",
}


def test_what_runs_without_the_generate_extra_is_exactly_the_list_of_pd_8():
    """generator-package PD-8, D-27: a module added to or dropped from the list is a decision."""
    contract = _contract("works-without-the-generate-extra")
    sources = _lines(contract, "source_modules")
    assert len(sources) == len(set(sources)), "a source module is listed twice"
    assert set(sources) == WITHOUT_GENERATE_EXTRA_SOURCES
    assert _lines(contract, "forbidden_modules") == ["linkml"]
    assert _lines(contract, "ignore_imports") == [
        f"{GENERATOR_PACKAGE}.cli -> {GENERATOR_PACKAGE}.steps"
    ]


def test_the_runtime_layers_do_not_import_the_generator():
    """generator-package PD-8, D-27: ``runtime-without-extras`` forbids the generator's package."""
    forbidden = _lines(_contract("runtime-without-extras"), "forbidden_modules")
    assert GENERATOR_PACKAGE in forbidden, "runtime-without-extras no longer forbids the generator"
    assert "rdf_persistence.generation" not in forbidden, "the old generation package is gone"


@pytest.mark.parametrize(
    "name", ["event-bus-libraries-in-one-module", "sparql-parser-only-through-the-wrappers"]
)
def test_the_event_bus_and_sparql_contracts_cover_the_generator(name):
    sources = _lines(_contract(name), "source_modules")
    assert {"rdf_persistence", GENERATOR_PACKAGE} <= set(sources), (
        f"{name} no longer lists the generator in source_modules"
    )
