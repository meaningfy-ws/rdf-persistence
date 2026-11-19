"""The getting-started example of the docs runs, and stays a cut of the toy library it is taken from."""

import asyncio
import importlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdf_persistence_generation.cli import main

EXAMPLE = Path(__file__).parents[3] / "docs" / "modules" / "ROOT" / "examples" / "getting-started"
TOY = Path(__file__).parents[2] / "fixtures" / "library"
TOY_MODULES = ("library_tenant.yaml", "books.yaml", "library_access.yaml")
PROJECT_MODULES = ("library_app", "generated")
KEPT_ELEMENT_KEYS = ("title", "description", "class_uri", "slot_uri", "range", "multivalued")


@pytest.fixture
def example(tmp_path: Path) -> Iterator[Path]:
    """The example copied, generated and importable; undone afterwards."""
    folder = tmp_path / "getting-started"
    shutil.copytree(EXAMPLE, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the example must generate"
    sys.path.insert(0, str(folder))
    yield folder
    sys.path.remove(str(folder))
    for name in [n for n in sys.modules if n.split(".")[0] in PROJECT_MODULES]:
        del sys.modules[name]
    importlib.invalidate_caches()


def _elements(files: list[Path], section: str) -> dict[str, dict[str, Any]]:
    """The ``classes`` or ``slots`` of the given schema files, by name."""
    found: dict[str, dict[str, Any]] = {}
    for file in files:
        found.update(yaml.safe_load(file.read_text()).get(section) or {})
    return found


def test_the_example_stores_a_book_and_reads_it_back(example: Path) -> None:
    app = importlib.import_module("library_app")

    stored, read_back = asyncio.run(app.main())

    # the store adds the tracking slots (creator, created, ...): compare what the application set
    set_by_us = stored.model_dump(exclude_unset=True)
    assert read_back.model_dump(include=set(set_by_us)) == set_by_us
    assert (read_back.label, read_back.authors) == ("Dune", ["Frank Herbert"])


@pytest.mark.parametrize("section", ["classes", "slots"])
def test_every_element_of_the_example_is_defined_identically_in_the_toy(section: str) -> None:
    ours = _elements([EXAMPLE / "models" / "library.yaml"], section)
    toys = _elements([TOY / name for name in TOY_MODULES], section)

    assert ours, f"the example defines {section}"
    for name, element in ours.items():
        assert name in toys, f"{name} is not in the toy library"
        for key in KEPT_ELEMENT_KEYS:
            assert element.get(key) == toys[name].get(key), f"{name}: {key} differs from the toy"
        for key in ("mixins", "slots", "is_a"):  # the toy may add more, never differ
            assert set(_as_list(element.get(key))) <= set(_as_list(toys[name].get(key))), (
                f"{name}: {key} is not in the toy's"
            )
        assert element.get("annotations") == _kept(toys[name].get("annotations"), element), (
            f"{name}: annotations differ from the toy"
        )


def _as_list(value: Any) -> list[str]:
    return [] if value is None else [value] if isinstance(value, str) else list(value)


def _kept(annotations: dict[str, Any] | None, element: dict[str, Any]) -> dict[str, Any] | None:
    """The toy's annotations restricted to the keys the example's element has (the toy may carry more)."""
    ours = element.get("annotations")
    if ours is None or annotations is None:
        return annotations if ours is not None else None
    return {key: annotations.get(key) for key in ours}
