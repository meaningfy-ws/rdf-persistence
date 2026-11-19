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


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> zipfile.ZipFile:
    """The wheel of this checkout, built once."""
    out = tmp_path_factory.mktemp("wheel")
    subprocess.run(
        ["uv", "build", "--wheel", "--no-build-isolation", "--out-dir", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (built,) = out.glob("*.whl")
    return zipfile.ZipFile(built)


def test_the_wheel_ships_the_py_typed_marker(wheel: zipfile.ZipFile) -> None:
    assert "rdf_persistence/py.typed" in wheel.namelist(), "the wheel lists the marker"


def test_the_wheel_ships_the_generator_as_a_sibling_package(wheel: zipfile.ZipFile) -> None:
    """TC-07 (PD-7): the generator, its model, templates and marker; no old folder."""
    names = set(wheel.namelist())
    templates = {
        f"rdf_persistence_generation/templates/{p.relative_to(ROOT / 'rdf_persistence_generation/templates').as_posix()}"
        for p in (ROOT / "rdf_persistence_generation/templates").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    wanted = {
        "rdf_persistence/py.typed",
        "rdf_persistence_generation/py.typed",
        "rdf_persistence_generation/model/rp_generation.yaml",
        "rdf_persistence/model/rp_core.yaml",
        *templates,
    }

    assert templates, "the generator has templates"
    assert not wanted - names, f"missing from the wheel: {sorted(wanted - names)}"
    assert not [n for n in names if n.startswith("rdf_persistence/generation/")], "the old folder"


def test_the_wheel_points_rp_generate_at_the_generator(wheel: zipfile.ZipFile) -> None:
    """TC-08 (PD-7)."""
    (entry_points,) = [n for n in wheel.namelist() if n.endswith(".dist-info/entry_points.txt")]

    lines = wheel.read(entry_points).decode().splitlines()

    assert "rp-generate = rdf_persistence_generation.cli:main" in lines, lines


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
    "import rdf_persistence.api.entrypoints.kit\n"
    "import rdf_persistence.persistence.adapters.fuseki\n"
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


NOT_SHIPPED = re.compile(r"(^|/)(__pycache__/|\.gitignore$|\.DS_Store$)|\.pyc$")


def tracked(package: str) -> list[str]:
    """The files git tracks under ``package``, minus those a wheel leaves out."""
    done = subprocess.run(
        ["git", "ls-files", package], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [f for f in done.stdout.splitlines() if not NOT_SHIPPED.search(f)]


@pytest.mark.slow
@pytest.mark.parametrize("package", ["rdf_persistence", "rdf_persistence_generation"])
def test_every_tracked_file_of_a_package_is_in_the_wheel(
    wheel: zipfile.ZipFile, package: str
) -> None:
    """Error matrix: a wheel missing a generator file (a template, a YAML, a ``.jinja``, a ``.py``)."""
    names = set(wheel.namelist())

    missing = [f for f in tracked(package) if f not in names]

    assert tracked(package), f"git lists nothing for {package}"
    assert missing == [], f"{len(missing)} tracked files are not in the wheel, first: {missing[:5]}"
