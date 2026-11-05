"""PD-25: every extension module has a row in generation.adoc#extensions, a golden test and goldens."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
EXTENSIONS = ROOT / "rdf_persistence" / "generation" / "extensions"
PAGE = ROOT / "docs" / "modules" / "ROOT" / "pages" / "architecture" / "generation.adoc"
TESTS = Path(__file__).parent
GOLDENS = ROOT / "tests" / "fixtures" / "library" / "golden"
EXTENSIONS_PREFIX = "rdf_persistence/generation/extensions/"

ROW = re.compile(r"^\|`([^`]+)`")
TEMPLATE_DIR = re.compile(r"`(rdf_persistence/generation/templates/[^`]+)`")


def register_rows() -> list[str]:
    """The table rows of section [#extensions], one line each (a row starts with ``|`path```)."""
    section = PAGE.read_text(encoding="utf-8").split("[#extensions]", 1)[1].split("\n[#", 1)[0]
    return [line for line in section.splitlines() if ROW.match(line)]


def first_cells() -> list[str]:
    return [ROW.match(row).group(1) for row in register_rows()]  # type: ignore[union-attr]


def extension_modules() -> list[str]:
    return sorted(p.stem for p in EXTENSIONS.glob("*.py") if p.name != "__init__.py")


def test_the_register_is_parsed() -> None:
    assert first_cells(), "the extensions table has rows starting with a backticked path"


@pytest.mark.parametrize("module", extension_modules())
def test_every_extension_module_has_a_row(module: str) -> None:
    assert f"{EXTENSIONS_PREFIX}{module}.py" in first_cells(), f"{module} has no row in generation.adoc#extensions"


@pytest.mark.parametrize("module", extension_modules())
def test_every_extension_module_has_a_golden_test(module: str) -> None:
    assert (TESTS / f"test_ext_{module}.py").is_file(), f"tests/unit/generation/test_ext_{module}.py is missing"


@pytest.mark.parametrize("module", extension_modules())
def test_every_extension_module_has_a_golden_folder(module: str) -> None:
    folder = GOLDENS / module
    assert folder.is_dir() and any(folder.iterdir()), f"tests/fixtures/library/golden/{module}/ is missing or empty"


@pytest.mark.parametrize("path", [c for c in first_cells() if c.startswith(EXTENSIONS_PREFIX)])
def test_every_extension_row_names_an_existing_module(path: str) -> None:
    assert (ROOT / path).is_file(), f"{path} is listed in the register but does not exist"


@pytest.mark.parametrize("folder", sorted({m for row in register_rows() for m in TEMPLATE_DIR.findall(row)}))
def test_every_template_folder_in_the_register_exists(folder: str) -> None:
    assert (ROOT / folder).is_dir(), f"{folder} is referenced in the register but does not exist"
