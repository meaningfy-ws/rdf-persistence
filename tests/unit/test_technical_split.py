"""The technical schemas live under ``model/technical/`` and generate outside the domain (technical-models stage 1).

TC-06..TC-10 and TC-53: the folder holds only technical modules, the domain folder none, the
generated service models sit in ``services``, and the import contracts refuse the domain's reach
into them (PD-1, PD-2).
"""

import configparser
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "rdf_persistence"
MODEL = PACKAGE / "model"
TECHNICAL = MODEL / "technical"
KIND_KEY, TECHNICAL_KIND = "module_kind", "technical"
SERVICE_SCHEMA_PACKAGE = "rdf_persistence.services.generated.service"
CONTRACT_DOMAIN = "domain-never-imports-technical-models"
CONTRACT_LAYERS = "layers"
DOMAIN_CONTRACT_NAME = "the domain never imports a technical model"  # the `name` of that contract


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
    domain_generated = import_module("rdf_persistence.domain.generated")
    assert not (Path(domain_generated.__path__[0]) / "service").exists(), (
        "no service subpackage is left under domain.generated"
    )
    service = import_module(f"{SERVICE_SCHEMA_PACKAGE}.rp_service")
    wire = import_module("rdf_persistence.adapters.generated.rp_wire")
    assert hasattr(service, "ServiceSettings"), "services.generated.service defines ServiceSettings"
    assert hasattr(wire, "JwtClaims"), "adapters.generated.rp_wire defines JwtClaims"


# --- the import contracts, run on a scratch copy of the layout (TC-09, TC-10, TC-53) ---------------

LAYOUT = {
    "__init__.py": "",
    "domain/__init__.py": "",
    "domain/generated/__init__.py": "",
    "domain/generated/rp_core.py": "",
    "domain/layout.py": "",
    "services/__init__.py": "",
    "services/session.py": "",
    "services/generated/__init__.py": "",
    "services/generated/service/__init__.py": "",
    "services/generated/service/rp_service.py": "",
    "adapters/__init__.py": "",
    "adapters/generated/__init__.py": "",
    "adapters/generated/rp_wire.py": "",
}
KEPT_CONTRACTS = (CONTRACT_LAYERS, CONTRACT_DOMAIN)


def _scratch_config(real: Path) -> str:
    """The repository's own contracts ``KEPT_CONTRACTS``, re-rooted on the scratch package."""
    source = configparser.ConfigParser()
    source.read(real, encoding="utf-8")
    scratch = configparser.ConfigParser()
    scratch["importlinter"] = {"root_packages": "\nrdf_persistence"}
    for name in KEPT_CONTRACTS:
        section = f"importlinter:contract:{name}"
        assert source.has_section(section), f"{real.name} declares the contract {name}"
        scratch[section] = dict(source[section])
    path = real.parent / "scratch.importlinter"
    with path.open("w", encoding="utf-8") as handle:
        scratch.write(handle)
    return path.name


def _lint(tmp_path: Path, planted: dict[str, str]) -> subprocess.CompletedProcess[str]:
    for rel, text in {**LAYOUT, **planted}.items():
        path = tmp_path / "rdf_persistence" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    config = _scratch_config_in(tmp_path)
    return subprocess.run(
        [str(Path(sys.executable).parent / "lint-imports"), "--config", config],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _scratch_config_in(tmp_path: Path) -> str:
    source = ROOT / ".importlinter"
    scratch = tmp_path / "source.importlinter"
    scratch.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return _scratch_config(scratch)


def _broken_contracts(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.endswith("BROKEN")]


def test_the_scratch_layout_itself_keeps_every_contract(tmp_path):
    result = _lint(tmp_path, {})
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_domain_module_importing_the_service_models_breaks_the_domain_contract(tmp_path):  # TC-09
    result = _lint(
        tmp_path,
        {"domain/generated/rp_core.py": f"import {SERVICE_SCHEMA_PACKAGE}\n"},
    )
    assert result.returncode != 0, result.stdout
    assert any(DOMAIN_CONTRACT_NAME in line for line in _broken_contracts(result)), result.stdout


def test_a_service_module_importing_the_wire_models_breaks_layers(tmp_path):  # TC-10
    result = _lint(
        tmp_path,
        {"services/session.py": "import rdf_persistence.adapters.generated.rp_wire\n"},
    )
    assert result.returncode != 0, result.stdout
    assert any(line.startswith("Layers") for line in _broken_contracts(result)), result.stdout


def test_the_policy_free_layout_importing_the_service_models_breaks_the_domain_contract(
    tmp_path,
):  # TC-53
    result = _lint(
        tmp_path,
        {"domain/layout.py": f"import {SERVICE_SCHEMA_PACKAGE}\n"},
    )
    assert result.returncode != 0, result.stdout
    assert any(DOMAIN_CONTRACT_NAME in line for line in _broken_contracts(result)), result.stdout
