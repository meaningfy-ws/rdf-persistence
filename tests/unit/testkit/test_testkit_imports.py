"""The library's testkit never reaches the generator (generator-package PD-1, PD-3; shims gone, #165)."""

import ast
from importlib import import_module
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parents[3] / "rdf_persistence"
TESTKIT = PACKAGE / "testkit"
GENERATION_SCHEMA = PACKAGE.parent / "rdf_persistence_generation" / "model" / "rp_generation.yaml"
GENERATOR = "rdf_persistence_generation"
TESTKIT_MODELS = "rdf_persistence.testkit.generated"
TECHNICAL_RECORDS = {
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
    "FieldFlags",
}


def library_modules() -> list[Path]:
    """Every testkit module but the generated package."""
    return [
        path
        for path in sorted(TESTKIT.rglob("*.py"))
        if "generated" not in path.relative_to(TESTKIT).parts
    ]


def imports(path: Path) -> list[tuple[str, str]]:
    """The (module, name) pairs a file imports; ``import a.b`` gives ``("a.b", "")``."""
    pairs = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            pairs += [(alias.name, "") for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            pairs += [(node.module, alias.name) for alias in node.names]
    return pairs


def is_under(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def test_no_library_testkit_module_imports_the_generator():
    """TC-01: no testkit module imports rdf_persistence_generation."""
    offenders = [
        f"{path.relative_to(PACKAGE)} imports {module}" + (f" {name}" if name else "")
        for path in library_modules()
        for module, name in imports(path)
        if is_under(module, GENERATOR)
    ]
    assert library_modules(), "the scan found no testkit module"
    assert offenders == [], f"the library testkit imports the generator: {offenders}"


def test_the_records_a_library_testkit_module_imports_live_in_the_testkit_models():
    """TC-02: each record imported from the testkit models is defined there, not in rp_generation."""
    testkit_models = import_module(f"{TESTKIT_MODELS}.rp_testkit")
    imported = {
        name
        for path in library_modules()
        for module, name in imports(path)
        if is_under(module, TESTKIT_MODELS)
    }
    schema = yaml.safe_load(GENERATION_SCHEMA.read_text(encoding="utf-8"))
    declared = set(schema["classes"]) | set(schema["enums"])
    in_generation = imported & declared
    missing = {name for name in imported if not hasattr(testkit_models, name)}
    assert imported, "the library testkit imports no record from its models"
    assert in_generation == set(), f"defined in rp_generation: {sorted(in_generation)}"
    assert missing == set(), f"not defined in {TESTKIT_MODELS}: {sorted(missing)}"


def test_the_generation_schema_declares_the_conformance_cases_and_no_technical_record():
    """TC-03: rp_generation.yaml keeps ConstraintCase and ConstraintKind, none of the PD-11 records."""
    schema = yaml.safe_load(GENERATION_SCHEMA.read_text(encoding="utf-8"))
    declared = set(schema["classes"]) | set(schema["enums"])
    assert {"ConstraintCase", "ConstraintKind"} <= declared, "the conformance suite's records"
    assert declared & TECHNICAL_RECORDS == set(), "a testkit record is declared in rp_generation"


def test_the_generation_schema_description_does_not_mention_the_testkit():
    """TC-03 (PD-1): the description of rp_generation.yaml stops mentioning the testkit."""
    schema = yaml.safe_load(GENERATION_SCHEMA.read_text(encoding="utf-8"))
    assert "testkit" not in schema["description"].lower(), schema["description"]
