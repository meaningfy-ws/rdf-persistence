"""The built wheel ships the PEP 561 marker, so a consumer's type checker reads our annotations.

Refs: mwb2-adoption-fixes DEC-4 (#42), T-1.
"""

import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_wheel_ships_the_py_typed_marker(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--no-build-isolation", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("*.whl")
    assert "rdf_persistence/py.typed" in zipfile.ZipFile(wheel).namelist(), (
        "the wheel lists the marker"
    )


@pytest.mark.slow
def test_a_consumers_type_checker_reads_our_annotations(tmp_path: Path) -> None:  # T-1b
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "import rdf_persistence\n"
        "from rdf_persistence import GrantSet\n"
        "from rdf_persistence.testkit import FakeStore\n"
        "\n"
        "GrantSet(grants=5)\n"
    )
    done = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", consumer.name],
        cwd=tmp_path,  # outside the repo: none of its mypy configuration applies
        capture_output=True,
        text=True,
        check=False,
    )
    assert "import-untyped" not in done.stdout, f"the package is typed: {done.stdout}"
    assert "[arg-type]" in done.stdout, f"the wrong argument type is reported: {done.stdout}"


SDK_FREE_IMPORTS = (
    "import sys\n"
    "import rdf_persistence\n"
    "import rdf_persistence.entrypoints.kit\n"
    "import rdf_persistence.adapters.fuseki\n"
    "print([name for name in sys.modules if name.startswith('opentelemetry.sdk')])\n"
)


def test_importing_the_package_loads_no_opentelemetry_sdk_module() -> None:  # TC-17
    done = subprocess.run(
        [sys.executable, "-I", "-c", SDK_FREE_IMPORTS],
        capture_output=True,
        text=True,
        check=True,
    )

    assert done.stdout.strip() == "[]", f"the SDK is the application's, not ours: {done.stdout}"


SHORT_FORMAT = re.compile(r'format="(nt|turtle|xml|json|json-ld|nquads)"')
RETIRED_NAMES = re.compile(r"RDFLIB_|EVENT_STREAM")


def test_no_rdflib_short_format_name_and_no_retired_constant_is_left_in_the_package() -> (
    None
):  # TC-44
    found = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in sorted((ROOT / "rdf_persistence").rglob("*.py"))
        if "generated" not in path.parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if SHORT_FORMAT.search(line) or RETIRED_NAMES.search(line)
    ]
    assert not found, "rdflib takes media types, and the constants are gone (PD-10): " + "; ".join(
        found
    )


def test_tc43_the_settings_extra_pins_pydantic_settings() -> None:  # PD-12
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["optional-dependencies"]["settings"] == ["pydantic-settings==2.16.2"]
    assert not any("pydantic-settings" in name for name in project["dependencies"]), (
        "the library stays out of the base dependencies"
    )
