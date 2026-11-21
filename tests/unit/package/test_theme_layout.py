"""The theme layout table's guard (thematic-structure PD-1, TC-01).

The table itself, ``LAYOUT`` and its companions, is data in ``tests/unit/layout_table.py``: other
tests read it too. A stage turns its themes on (``TURNED_ON``); a row that is on must stand at its
new path and no longer at its old one, and a row that is off must not have moved.
"""

import importlib
from pathlib import Path

import pytest

from tests.unit.layout_table import (
    CORE_GENERATED_MODULES,
    GENERATED_REMOVED,
    GROUP_MODULES,
    LAYERS,
    LAYOUT,
    MOVED_MODULES,
    PACKAGE,
    PLACED,
    ROOT,
    Move,
    MovedModule,
    Placed,
    file_of,
    layout_problems,
    moved_module_problems,
    placed_problems,
    turned_on_classes,
    turned_on_pairs,
)

TURNED_ON_TARGET = "tests.unit.layout_table.TURNED_ON"


def test_the_tree_matches_the_layout_rows():
    problems = layout_problems(LAYOUT, ROOT)

    assert problems == [], "the tree and LAYOUT differ:\n" + "\n".join(problems)


def test_the_layout_names_the_themes_the_changed_mapper_knows():
    from tests.changed import THEMES

    assert {row.theme for row in LAYOUT} == THEMES, "LAYOUT and tests.changed.THEMES differ"


def test_every_row_of_the_layout_is_on():
    """TC-01 at the end of the move: no theme is left on its old path."""
    off = sorted({row.theme for row in LAYOUT if not row.on})

    assert off == [], f"themes still off: {off}"
    assert len({row.theme for row in LAYOUT}) == 13, "PD-1 has thirteen themes"


# --- domain-model-per-theme: the generated domain modules in their themes (TC-01, TC-07) ---------


def test_each_moved_generated_module_stands_in_its_theme_and_not_in_core():
    """TC-01: seven modules, each in ``<theme>/domain/generated``; core keeps only two modules."""
    problems = moved_module_problems(MOVED_MODULES, ROOT)

    assert len(MOVED_MODULES) == 7, "DEC-1 moves seven modules"
    assert problems == [], "the generated modules and MOVED_MODULES differ:\n" + "\n".join(problems)


def test_core_generated_holds_only_the_shared_modules_and_the_combined_artefacts():
    generated = ROOT / PACKAGE / "core" / "domain" / "generated"

    modules = {p.stem for p in generated.glob("*.py")}
    artefacts = {p.name for p in generated.iterdir() if p.suffix != ".py"} - {"__pycache__"}

    assert modules == CORE_GENERATED_MODULES | {"__init__"}, f"modules in core: {sorted(modules)}"
    assert {"shapes.ttl", "context.jsonld"} <= artefacts, "the combined set stays in core (DEC-2)"


@pytest.mark.parametrize("theme", ["access", "provenance", "collaboration"])
def test_a_theme_that_gains_a_domain_has_its_generated_package_as_a_created_row(theme):
    rows = [r for r in LAYOUT if (r.theme, r.layer, r.module) == (theme, "domain", "generated")]

    assert [r.created for r in rows] == [True], f"{theme} needs one created domain/generated row"
    assert (ROOT / PACKAGE / theme / "domain" / "__init__.py").is_file(), "the hand-written package"


def test_the_pairs_of_the_guards_include_each_moved_module():
    pairs = dict(turned_on_pairs())

    assert all(pairs[row.old] == row.new for row in MOVED_MODULES)


def test_a_moved_module_left_in_core_or_missing_from_its_theme_is_named(tmp_path):
    row = MovedModule("access", "rp_access")

    left = moved_module_problems((row,), _tree(tmp_path / "a", row.old))
    missing = moved_module_problems((row,), _tree(tmp_path / "b", "rdf_persistence.core.x"))

    assert any(row.old in p and row.new in p for p in left), left
    assert any(row.new in p and "missing" in p for p in missing), missing


def test_a_module_core_does_not_keep_is_named(tmp_path):
    root = _tree(tmp_path, "rdf_persistence.core.domain.generated.rp")

    problems = moved_module_problems((), root)

    assert problems == [f"{GENERATED_REMOVED} is not a module core keeps"], problems


@pytest.mark.parametrize(
    "old",
    [*(row.old for row in MOVED_MODULES), GENERATED_REMOVED],
    ids=lambda old: old.rsplit(".", 1)[1],
)
def test_the_old_deep_path_of_a_moved_module_cannot_be_imported(old):
    """TC-07: no shim at the old path (DEC-8); the module is gone, so the import fails by name."""
    with pytest.raises(ModuleNotFoundError, match=old.rsplit(".", 1)[1]):
        importlib.import_module(old)


# TC-70: what stands at the top of the package once the move is done (PD-1).
TOP_LEVEL_FILES = frozenset({"__init__.py", "py.typed"})


def test_the_top_level_of_the_package_holds_the_themes_and_nothing_else():
    """TC-70: exactly the 13 themes, `model`, `testkit`, two files; no `domain` and no `adapters`."""
    entries = {p.name for p in (ROOT / PACKAGE).iterdir() if p.name != "__pycache__"}
    themes = {row.theme for row in LAYOUT}

    assert entries == themes | {"model", "testkit"} | TOP_LEVEL_FILES, (
        f"unexpected or missing at the top level: {sorted(entries)}"
    )


def test_no_two_rows_share_an_old_or_a_new_path():
    olds = [row.old for row in LAYOUT if row.old]
    news = [row.new for row in LAYOUT]

    assert len(olds) == len(set(olds)), "an old path occurs twice"
    assert len(news) == len(set(news)), "a new path occurs twice"


def test_the_generated_classes_are_all_placed_and_the_tree_agrees():
    problems = placed_problems(PLACED, ROOT)

    assert problems == [], "the generated modules and PLACED differ:\n" + "\n".join(problems)


def test_a_class_is_placed_once_and_in_a_known_theme_and_layer():
    from tests.changed import THEMES

    names = [(p.group, c) for p in PLACED for c in p.classes]

    assert len(names) == len(set(names)), "a class is placed twice"
    assert {p.theme for p in PLACED} <= THEMES, "a placement names an unknown theme"
    assert {p.layer for p in PLACED} <= set(LAYERS), "a placement names an unknown layer"
    assert {p.group for p in PLACED} <= set(GROUP_MODULES), "a placement names an unknown group"


# --- the guard on a planted tree ------------------------------------------------------------

SERVICE_OLD = "rdf_persistence.services.generated.service.rp_service"
# The planted rows use `api`; every theme is on once the move is done, so a test that needs the row off turns
# the themes off itself (`nothing_on`).
SERVICE_NEW = "rdf_persistence.api.entrypoints.generated.rp_api_entrypoints"
ONE_CLASS = (Placed("api", "entrypoints", "service", ("Problem",)),)


def _module(root: Path, module: str, *classes: str) -> None:
    path = file_of(module, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"class {c}:\n    pass\n\n" for c in classes), encoding="utf-8")


def test_a_class_row_off_holds_while_the_class_is_in_its_group_module(tmp_path, nothing_on):
    _module(tmp_path, SERVICE_OLD, "Problem")

    assert placed_problems(ONE_CLASS, tmp_path) == [], "the class stands where the row says"


def test_a_class_row_turned_on_whose_class_is_still_in_the_old_module_fails_naming_both(
    tmp_path, monkeypatch
):
    """TC-01 for a class: the old and the new module are named."""
    monkeypatch.setattr(TURNED_ON_TARGET, frozenset({"api"}))
    _module(tmp_path, SERVICE_OLD, "Problem")

    problems = placed_problems(ONE_CLASS, tmp_path)

    assert any("Problem" in p and SERVICE_OLD in p and SERVICE_NEW in p for p in problems), problems


def test_a_class_row_turned_on_holds_when_the_class_stands_in_the_new_module(tmp_path, monkeypatch):
    monkeypatch.setattr(TURNED_ON_TARGET, frozenset({"api"}))
    _module(tmp_path, SERVICE_NEW, "Problem")

    assert placed_problems(ONE_CLASS, tmp_path) == [], "the moved class satisfies its row"
    assert turned_on_classes(ONE_CLASS) == {(SERVICE_OLD, "Problem"): SERVICE_NEW}


def test_a_class_without_a_row_fails_by_name(tmp_path, nothing_on):
    _module(tmp_path, SERVICE_OLD, "Problem", "Newcomer")

    problems = placed_problems(ONE_CLASS, tmp_path)

    assert problems == [f"Newcomer in {SERVICE_OLD} has no row in PLACED"], problems


def _tree(root: Path, *modules: str) -> Path:
    for module in modules:
        path = file_of(module, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
        for folder in path.relative_to(root).parents:
            if folder != Path("."):
                (root / folder / "__init__.py").touch()
    return root


@pytest.fixture
def core_on(monkeypatch):
    monkeypatch.setattr(TURNED_ON_TARGET, frozenset({"core"}))


@pytest.fixture
def nothing_on(monkeypatch):
    monkeypatch.setattr(TURNED_ON_TARGET, frozenset())


BASE_ROW = (Move("core", "domain", "base"),)


def test_a_module_at_the_old_path_beside_the_moved_one_is_a_leftover(tmp_path, core_on):
    """8.1: no old path stands any more, a copy of the moved module included."""
    root = _tree(tmp_path, "rdf_persistence.core.domain.base", "rdf_persistence.domain.base")

    problems = layout_problems(BASE_ROW, root)

    assert any("still at its old path" in p for p in problems), problems


def test_a_row_turned_on_whose_module_is_still_at_its_old_path_fails_naming_both(tmp_path, core_on):
    """TC-01: the failure names the old path and the new path."""
    root = _tree(tmp_path, "rdf_persistence.domain.base")

    problems = layout_problems(BASE_ROW, root)

    assert any(
        "rdf_persistence.domain.base" in p and "rdf_persistence.core.domain.base" in p
        for p in problems
    ), f"old and new path named: {problems}"


def test_a_row_turned_on_holds_when_the_module_stands_at_its_new_path(tmp_path, core_on):
    root = _tree(tmp_path, "rdf_persistence.core.domain.base")

    assert layout_problems(BASE_ROW, root) == [], "the moved module satisfies its row"


def test_a_row_turned_off_fails_when_the_module_has_moved_early(tmp_path, nothing_on):
    root = _tree(tmp_path, "rdf_persistence.core.domain.base")

    problems = layout_problems(BASE_ROW, root)

    assert any("rdf_persistence.domain.base is missing" in p for p in problems), problems
    assert any("rdf_persistence.core.domain.base has no row" in p for p in problems), problems


def test_a_module_without_a_row_fails_by_name(tmp_path, nothing_on):
    root = _tree(tmp_path, "rdf_persistence.domain.base", "rdf_persistence.services.newcomer")

    problems = layout_problems(BASE_ROW, root)

    assert problems == ["rdf_persistence.services.newcomer has no row in LAYOUT"], problems


def test_a_created_row_is_required_once_its_theme_is_on(tmp_path, core_on):
    rows = (Move("core", "adapters", "fresh", created=True),)

    missing = layout_problems(rows, _tree(tmp_path / "a", "rdf_persistence.domain.__init__"))
    present = layout_problems(rows, _tree(tmp_path / "b", "rdf_persistence.core.adapters.fresh"))

    assert [p.split(" (")[0] for p in missing] == ["rdf_persistence.core.adapters.fresh is missing"]
    assert present == [], "the created module satisfies its row"
