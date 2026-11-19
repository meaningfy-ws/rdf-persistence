"""The getting-started example of the docs runs: generate its model, then store and read a note."""

import asyncio
import importlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

EXAMPLE = Path(__file__).parents[3] / "docs" / "modules" / "ROOT" / "examples" / "getting-started"
PROJECT_MODULES = ("notes_app", "generated")


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


def test_the_example_stores_a_note_and_reads_it_back(example: Path) -> None:
    app = importlib.import_module("notes_app")

    stored, read_back = asyncio.run(app.main())

    # the store adds the tracking slots (creator, created, ...): compare what the application set
    set_by_us = stored.model_dump(exclude_unset=True)
    assert read_back.model_dump(include=set(set_by_us)) == set_by_us
    assert (read_back.label, read_back.text) == ("Buy milk", "Two litres.")
