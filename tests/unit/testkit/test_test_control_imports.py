"""The test-control modules import only what a consumer's venv has (test-control-testkit PD-13, TC-9)."""

import ast
import sys
from pathlib import Path

import pytest

TESTKIT = Path(__file__).resolve().parents[3] / "rdf_persistence" / "testkit"
GENERATED = "rdf_persistence.testkit.generated.rp_testkit"

# Per module: the non-stdlib modules it may import, and whether each is allowed only inside a function.
# Stage 3 adds `changed_tests` with one row here.
ALLOWED: dict[str, dict[str, bool]] = {
    "run_queue": {},
    "selection_data": {"testmon": True, GENERATED: False},
}


def _imports(source: str) -> list[tuple[int, str, bool]]:
    """Every import as (line, module, inside a function)."""
    tree = ast.parse(source)
    found: list[tuple[int, str, bool]] = []

    def walk(node: ast.AST, in_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            inside = in_function or isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            if isinstance(child, ast.Import):
                found.extend((child.lineno, alias.name, inside) for alias in child.names)
            elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module:
                found.append((child.lineno, child.module, inside))
            walk(child, inside)

    walk(tree, False)
    return found


def violations(module: str, source: str) -> list[str]:
    allowed = ALLOWED[module]
    out = []
    for line, name, in_function in _imports(source):
        top = name.split(".")[0]
        if top in sys.stdlib_module_names:
            continue
        if name in allowed or top in allowed:
            key = name if name in allowed else top
            if allowed[key] and not in_function:
                out.append(f"{module}.py:{line}: {name} may be imported only inside a function")
            continue
        out.append(f"{module}.py:{line}: {name} is not stdlib nor allowed")
    return out


@pytest.mark.parametrize("module", sorted(ALLOWED))
def test_the_module_imports_only_stdlib_and_the_allowed(module: str) -> None:
    source = (TESTKIT / f"{module}.py").read_text(encoding="utf-8")

    assert violations(module, source) == [], f"{module} imports something a consumer may lack"


@pytest.mark.parametrize(
    ("module", "extra", "expected"),
    [
        (
            "run_queue",
            "import rdf_persistence.persistence\n",
            "run_queue.py:{n}: rdf_persistence.persistence",
        ),
        (
            "selection_data",
            "from rdf_persistence.core import x\n",
            "selection_data.py:{n}: rdf_persistence.core",
        ),
        (
            "selection_data",
            "import testmon\n",
            "selection_data.py:{n}: testmon may be imported only inside",
        ),
    ],
    ids=["queue-plants-persistence", "selection-plants-core", "testmon-at-top"],
)
def test_a_planted_import_fails_and_names_the_line(module: str, extra: str, expected: str) -> None:
    source = (TESTKIT / f"{module}.py").read_text(encoding="utf-8") + "\n" + extra
    line = source.count("\n")  # the planted import is the last line

    got = violations(module, source)

    assert got, f"the planted import is caught in {module}"
    assert got[-1].startswith(expected.format(n=line)), f"the line is named: {got}"
