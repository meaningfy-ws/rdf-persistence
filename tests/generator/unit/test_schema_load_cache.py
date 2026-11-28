"""D-15: a generation run parses each imported schema once, however many views it builds."""

import os
import shutil
from pathlib import Path

import pytest
from linkml_runtime.linkml_model.meta import SchemaDefinition
from linkml_runtime.utils import schemaview
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence_generation.cli import main
from rdf_persistence_generation.schema_cache import (
    PROCESS_CACHE,
    SchemaLoadCache,
    cached_schema_loads,
)

from .golden import TOY

ROOT = "id: https://example.org/{n}\nname: {n}\nimports: [{imports}]\n{body}"
LEAF_BODY = "classes:\n  Leaf:\n    description: {text}\n"


class CountingLoader:
    """The parse the cache wraps: the real one, counting the paths it is asked for."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self._real = schemaview.load_schema_wrap

    def __call__(self, path: str, **kwargs: str | None) -> SchemaDefinition:
        self.paths.append(str(path))
        return self._real(path, **kwargs)


def _write(folder: Path, leaf_text: str = "first") -> Path:
    (folder / "leaf.yaml").write_text(
        ROOT.format(n="leaf", imports="", body=LEAF_BODY.format(text=leaf_text)), encoding="utf-8"
    )
    root = folder / "root.yaml"
    root.write_text(ROOT.format(n="root", imports="leaf", body=""), encoding="utf-8")
    return root


def _closure(root: Path) -> SchemaView:
    view = SchemaView(str(root))
    view.imports_closure()
    return view


def test_a_second_view_of_an_unchanged_import_is_served_from_the_cache(tmp_path: Path) -> None:
    root = _write(tmp_path)
    loader = CountingLoader()
    with cached_schema_loads(SchemaLoadCache(), load=loader):
        _closure(root)
        parsed_once = len(loader.paths)
        _closure(root)
    assert len(loader.paths) == parsed_once, "the second view parsed a file again"
    assert parsed_once == 2, f"expected the root and its import to be parsed: {loader.paths}"


def test_a_file_whose_stat_changed_is_parsed_again(tmp_path: Path) -> None:
    root = _write(tmp_path)
    loader = CountingLoader()
    with cached_schema_loads(SchemaLoadCache(), load=loader):
        _closure(root)
        _write(tmp_path, leaf_text="second, and longer")
        view = _closure(root)
    assert [Path(p).name for p in loader.paths].count("leaf.yaml") == 2, (
        "the edited import stayed cached"
    )
    assert view.get_class("Leaf").description == "second, and longer", "the view saw stale content"


def test_two_views_do_not_share_the_schemas_they_hold(tmp_path: Path) -> None:
    root = _write(tmp_path)
    with cached_schema_loads(SchemaLoadCache(), load=CountingLoader()):
        first = _closure(root)
        first.schema_map["leaf"].classes["Leaf"].description = "changed by the first view"
        second = _closure(root)
    assert second.get_class("Leaf").description == "first", "a mutation leaked between views"


def test_an_import_read_with_a_base_folder_is_kept_as_pickled_bytes_and_keeps_its_source_file(
    tmp_path: Path,
) -> None:
    root = _write(tmp_path)
    cache = SchemaLoadCache()
    with cached_schema_loads(cache, load=CountingLoader()):
        first = _closure(root).schema_map["leaf"].source_file
        second = _closure(root).schema_map["leaf"].source_file
    assert {type(frozen) for _, frozen in cache.entries.values()} == {bytes}, (
        "an entry fell back to a deep copy, which costs more than the parse it saves"
    )
    assert str(second) == str(first), "the copy lost the file the import came from"


def test_the_process_cache_lives_for_one_run_so_a_same_size_edit_is_seen_by_the_next(
    tmp_path: Path,
) -> None:  # F-3
    root = _write(tmp_path, leaf_text="first")
    leaf = tmp_path / "leaf.yaml"
    stat = leaf.stat()
    PROCESS_CACHE.clear()
    with cached_schema_loads():
        with cached_schema_loads():  # a nested block does not end the run
            _closure(root)
        assert PROCESS_CACHE.entries, "the inner block ended the run: nothing kept within it"
        _closure(root)
    assert not PROCESS_CACHE.entries, "a parse survived the run that made it"
    _write(tmp_path, leaf_text="second")  # the same size
    os.utime(leaf, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # and the same stat
    with cached_schema_loads():
        view = _closure(root)
    assert view.get_class("Leaf").description == "second", "the next run saw the stale parse"


def test_the_cache_is_off_outside_the_block(tmp_path: Path) -> None:
    root = _write(tmp_path)
    before = schemaview.load_schema_wrap
    with cached_schema_loads(SchemaLoadCache(), load=CountingLoader()):
        assert schemaview.load_schema_wrap is not before, "the block installed nothing"
    assert schemaview.load_schema_wrap is before, "the stock loader was not put back"
    assert _closure(root).get_class("Leaf") is not None, "the stock loader no longer works"


def _generate(folder: Path) -> dict[str, bytes]:
    shutil.copy(TOY / "partial.yaml", folder)
    (folder / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "partial.yaml"\npackage = "partial.domain.generated"\n'
        'python = "domain/generated"\ntypescript = "web"\nmigrations = "migrations"\n'
    )
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the run failed"
    return {
        str(path.relative_to(folder)): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "pyproject.toml"
    }


@pytest.mark.slow
def test_generation_output_is_the_same_with_a_cold_and_a_warm_cache(tmp_path: Path) -> None:
    cold, warm = tmp_path / "cold", tmp_path / "warm"
    cold.mkdir()
    warm.mkdir()
    PROCESS_CACHE.clear()
    uncached = _generate(cold)  # every import is parsed
    cached = _generate(warm)  # a run of its own: the process cache ends with each run (F-3)
    assert cached.keys() == uncached.keys(), "the two runs wrote different files"
    differing = [name for name in cached if cached[name] != uncached[name]]
    assert differing == [], f"files differ between the runs: {differing}"
