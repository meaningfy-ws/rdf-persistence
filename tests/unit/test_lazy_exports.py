"""Importing the domain, or a consumer's generated module, loads no adapter, service or HTTP client (PD-8c)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
HEAVY = ("httpx", "anyio", "rdf_persistence.adapters", "rdf_persistence.services")
PROBE = """
import sys
import {module}
loaded = sorted(
    name for name in sys.modules
    if any(name == heavy or name.startswith(heavy + ".") for heavy in {heavy!r})
)
print(",".join(loaded))
"""


@pytest.mark.parametrize(
    "module",
    ["rdf_persistence.domain", "rdf_persistence", "tests.fixtures.library.generated.books"],
)
def test_importing_the_domain_or_a_generated_module_loads_nothing_heavy(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", PROBE.format(module=module, heavy=HEAVY)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "", f"importing {module} also loaded: {result.stdout.strip()}"


def test_a_lazy_name_is_loaded_on_first_use_and_then_kept() -> None:
    probe = (
        "import sys, rdf_persistence;"
        "assert 'rdf_persistence.services' not in sys.modules;"
        "rdf_persistence.Mapper;"
        "assert 'rdf_persistence.services.mapper' in sys.modules;"
        "assert 'Mapper' in vars(rdf_persistence), 'kept after the first use'"
    )
    subprocess.run([sys.executable, "-c", probe], cwd=ROOT, check=True)


def test_an_unknown_top_level_name_is_an_attribute_error() -> None:
    import rdf_persistence

    with pytest.raises(AttributeError, match="NoSuchName"):
        rdf_persistence.NoSuchName  # noqa: B018
