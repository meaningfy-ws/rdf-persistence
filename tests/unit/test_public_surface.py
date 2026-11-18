"""The public surface does not move with the modules (thematic-structure DEC-6, TC-03).

``tests/fixtures/public-surface.json`` maps each name of ``rdf_persistence.__all__`` to the module
that defines it **before the move**. The guard maps that module through the rows of ``LAYOUT`` that
are on to where it must stand now, and checks, for every name, that ``rdf_persistence.<name>`` is the
very object of that module and that the module defines it. ``make refresh-snapshot`` rewrites the file
(it stores old paths, so a stage that turns a row on leaves it as it is).
"""

import json
import os
import sys
from collections.abc import Callable, Iterator
from importlib import import_module
from itertools import count
from pathlib import Path
from types import ModuleType

import pytest

import rdf_persistence
from tests.unit.test_theme_layout import turned_on_classes, turned_on_pairs

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "tests" / "fixtures" / "public-surface.json"
REFRESH = "RP_REFRESH_SNAPSHOT"
NAMES = 149
_MISSING = object()


def home_of(package: ModuleType, name: str) -> str:
    """The module that defines ``name``; a type alias has none of its own, so the lazy map says."""
    module = getattr(getattr(package, name), "__module__", None)
    if isinstance(module, str) and module.split(".")[0] == package.__name__:
        return module
    return getattr(package, "_LAZY_MODULES", {}).get(name, package.__name__)


def _swap(module: str, source: str, target: str) -> str:
    if module == source or module.startswith(f"{source}."):
        return target + module[len(source) :]
    return module


Pairs = tuple[tuple[str, str], ...]
Classes = dict[tuple[str, str], str]  # (old module, class) -> new module: the technical classes


def standing_of(module: str, name: str, pairs: Pairs, classes: Classes) -> str:
    """Where ``name``, recorded at an old module, must stand, given the rows that are on."""
    if (module, name) in classes:
        return classes[module, name]
    for old, new in pairs:
        module = _swap(module, old, new)
    return module


def old_path_of(module: str, name: str, pairs: Pairs, classes: Classes) -> str:
    """The reverse: the old module of a name that may already have moved."""
    for (old, cls), new in classes.items():
        if cls == name and new == module:
            return old
    for old, new in pairs:
        module = _swap(module, new, old)
    return module


def current_snapshot(
    package: ModuleType, pairs: Pairs, classes: Classes | None = None
) -> dict[str, str]:
    return {
        name: old_path_of(home_of(package, name), name, pairs, classes or {})
        for name in sorted(package.__all__)
    }


def surface_problems(
    package: ModuleType, snapshot: dict[str, str], pairs: Pairs, classes: Classes | None = None
) -> list[str]:
    """What differs between the package's public names and the snapshot, as named lines."""
    problems = [
        f"{n} is in __all__ but not in the snapshot"
        for n in sorted(set(package.__all__) - set(snapshot))
    ]
    problems += [
        f"{n} is in the snapshot but not in __all__"
        for n in sorted(set(snapshot) - set(package.__all__))
    ]
    for name in sorted(set(snapshot) & set(package.__all__)):
        expected = standing_of(snapshot[name], name, pairs, classes or {})
        try:
            there = getattr(import_module(expected), name, _MISSING)
        except ImportError:
            problems.append(f"{name}: its module {expected} does not exist")
            continue
        actual = home_of(package, name)
        if there is not getattr(package, name):
            problems.append(f"{name}: {package.__name__}.{name} is not the object of {expected}")
        elif actual != expected:
            problems.append(f"{name}: defined in {actual}, expected {expected}")
    return problems


def _snapshot() -> dict[str, str]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _write(snapshot: dict[str, str]) -> None:
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def refreshed_on_request() -> None:
    """``make refresh-snapshot`` rewrites the file before any test of this module reads it."""
    if os.environ.get(REFRESH):
        _write(current_snapshot(rdf_persistence, turned_on_pairs(), turned_on_classes()))


def test_the_snapshot_holds_the_names_of_the_public_surface():
    """TC-03: 149 names, the very set of ``__all__``."""
    snapshot = _snapshot()

    assert len(snapshot) == NAMES, "the snapshot holds every name of the surface"
    assert set(snapshot) == set(rdf_persistence.__all__), "the snapshot and __all__ differ"
    assert len(rdf_persistence.__all__) == NAMES, "__all__ gained or lost a name"


def test_every_public_name_is_the_object_at_its_layout_home():
    """TC-03: each name resolves, through the lazy map, to the object of its module in ``LAYOUT``."""
    problems = surface_problems(
        rdf_persistence, _snapshot(), turned_on_pairs(), turned_on_classes()
    )

    assert problems == [], "the public surface moved:\n" + "\n".join(problems)


# --- the guard on a planted package ---------------------------------------------------------

Build = Callable[[dict[str, str]], ModuleType]
_PACKAGES = count()


@pytest.fixture
def build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Build]:
    """Write a package of the given module sources under ``tmp_path`` and import it."""
    monkeypatch.syspath_prepend(str(tmp_path))
    created: list[str] = []

    def make(sources: dict[str, str]) -> ModuleType:
        name = f"surface_probe_{next(_PACKAGES)}"
        created.append(name)
        folder = tmp_path / name
        folder.mkdir()
        for module, source in sources.items():
            (folder / f"{module}.py").write_text(source.replace("PKG", name), encoding="utf-8")
        return import_module(name)

    yield make
    for loaded in [m for m in sys.modules if m.split(".")[0] in created]:
        del sys.modules[loaded]


LOWER = "class Thing:\n    pass\n"
INIT_LAZY = (
    "from importlib import import_module\n"
    "_LAZY_MODULES = {'Thing': 'PKG.%s'}\n"
    "def __getattr__(name):\n"
    "    return getattr(import_module(_LAZY_MODULES[name]), name)\n"
    "__all__ = ['Thing']\n"
)


def _pairs(package: ModuleType, *moves: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((f"{package.__name__}.{old}", f"{package.__name__}.{new}") for old, new in moves)


def test_a_package_that_matches_its_snapshot_has_no_problem(build):
    package = build({"__init__": INIT_LAZY % "lower", "lower": LOWER})

    assert surface_problems(package, {"Thing": f"{package.__name__}.lower"}, ()) == []


def test_a_name_missing_from_the_snapshot_or_from_all_is_named(build):
    package = build({"__init__": INIT_LAZY % "lower", "lower": LOWER})

    problems = surface_problems(package, {"Gone": f"{package.__name__}.lower"}, ())

    assert problems == [
        "Thing is in __all__ but not in the snapshot",
        "Gone is in the snapshot but not in __all__",
    ], problems


def test_a_name_still_defined_at_its_old_module_after_its_row_is_on_fails(build):
    """TC-03 planted: the row says ``lower`` -> ``upper``; ``Thing`` is re-exported but defined in ``lower``."""
    package = build(
        {
            "__init__": INIT_LAZY % "lower",
            "lower": LOWER,
            "upper": "from PKG.lower import Thing\n",
        }
    )

    problems = surface_problems(
        package, {"Thing": f"{package.__name__}.lower"}, _pairs(package, ("lower", "upper"))
    )

    assert problems == [
        f"Thing: defined in {package.__name__}.lower, expected {package.__name__}.upper"
    ], problems


def test_a_name_whose_new_module_holds_another_object_fails(build):
    package = build({"__init__": INIT_LAZY % "lower", "lower": LOWER, "upper": LOWER})

    problems = surface_problems(
        package, {"Thing": f"{package.__name__}.lower"}, _pairs(package, ("lower", "upper"))
    )

    assert problems == [
        f"Thing: {package.__name__}.Thing is not the object of {package.__name__}.upper"
    ], problems


def test_a_name_whose_new_module_does_not_exist_fails(build):
    package = build({"__init__": INIT_LAZY % "lower", "lower": LOWER})

    problems = surface_problems(
        package, {"Thing": f"{package.__name__}.lower"}, _pairs(package, ("lower", "upper"))
    )

    assert problems == [f"Thing: its module {package.__name__}.upper does not exist"], problems


def test_a_class_moved_by_a_class_row_is_found_at_its_new_module(build):
    """A technical class leaves its group module for a theme's: its row names the class, not the module."""
    package = build({"__init__": INIT_LAZY % "upper", "lower": LOWER, "upper": LOWER})
    old, new = f"{package.__name__}.lower", f"{package.__name__}.upper"
    classes = {(old, "Thing"): new}
    snapshot = {"Thing": old}

    assert surface_problems(package, snapshot, (), classes) == [], (
        "defined where the class row says"
    )
    assert current_snapshot(package, (), classes) == snapshot, (
        "a refresh writes the old module back"
    )


def test_a_class_row_that_is_on_fails_while_the_class_is_still_in_its_group_module(build):
    package = build(
        {"__init__": INIT_LAZY % "lower", "lower": LOWER, "upper": "from PKG.lower import Thing\n"}
    )
    old, new = f"{package.__name__}.lower", f"{package.__name__}.upper"

    problems = surface_problems(package, {"Thing": old}, (), {(old, "Thing"): new})

    assert problems == [f"Thing: defined in {old}, expected {new}"], problems


def test_a_name_moved_with_its_row_passes_and_the_snapshot_keeps_the_old_path(build):
    package = build({"__init__": INIT_LAZY % "upper", "upper": LOWER})
    pairs = _pairs(package, ("lower", "upper"))
    snapshot = {"Thing": f"{package.__name__}.lower"}

    assert surface_problems(package, snapshot, pairs) == [], "defined where the row says"
    assert current_snapshot(package, pairs) == snapshot, "a refresh writes the old path back"
