"""service_view: kits built from one schema file share one parse (test-memory-followups PD-2, DEC-2)."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.schema.services import schema as schema_module
from rdf_persistence.schema.services.schema import (
    SERVICE_VIEWS,
    clear_service_views,
    load_schema,
    service_view,
)
from rdf_persistence.schema.services.schema_structure import generation_view
from tests.toy import TOY_SCHEMA
from tests.toy_service import ToyService

PARTIAL = Path(__file__).parents[2] / "fixtures" / "library" / "partial.yaml"


@pytest.fixture(autouse=True)
def _empty_store() -> None:
    """Every case starts and ends with no cached view."""
    clear_service_views()
    yield
    clear_service_views()


@dataclass(frozen=True)
class Outcome:
    """What a case observed: two things that are or are not the same object, and what it expects."""

    first: object
    second: object
    same: bool
    message: str


def written(directory: Path, name: str, comment: str = "") -> Path:
    """A copy of the partial schema under ``name``; ``comment`` makes its bytes differ."""
    path = directory / name
    path.write_text(PARTIAL.read_text() + f"\n# {comment}\n")
    return path


def two_toy_services(_: Path) -> Outcome:
    a, b = ToyService(), ToyService()
    return Outcome(a.kit.view, b.kit.view, True, "two kits of one file share their view")


def new_path_new_entry(directory: Path) -> Outcome:
    one = service_view(written(directory, "one.yaml"))
    other = service_view(written(directory, "other.yaml"))
    return Outcome(one, other, False, "a new path is a new entry")


def rewritten_with_other_content(directory: Path) -> Outcome:
    path = written(directory, "s.yaml", "one")
    before = service_view(path)
    written(directory, "s.yaml", "two")
    return Outcome(before, service_view(path), False, "other bytes at once give a new view")


def rewritten_with_same_bytes(directory: Path) -> Outcome:
    path = written(directory, "s.yaml", "one")
    before = service_view(path)
    written(directory, "s.yaml", "one")
    return Outcome(before, service_view(path), True, "the same bytes give the same view")


def ninth_file_evicts_the_first(directory: Path) -> Outcome:
    loads: list[Path] = []

    def counting(path: str | Path) -> SchemaView:
        loads.append(Path(path))
        return load_schema(path)

    paths = [written(directory, f"s{n}.yaml", str(n)) for n in range(SERVICE_VIEWS + 1)]
    first = service_view(paths[0], load=counting)
    for path in paths[1:]:
        service_view(path, load=counting)
    assert len(schema_module._SERVICE_STORE) == SERVICE_VIEWS, "the store holds eight"
    again = service_view(paths[0], load=counting)
    assert loads.count(paths[0]) == 2, "the evicted file is loaded again on use"
    return Outcome(first, again, False, "the first file's view was evicted and reloaded")


def cleared_store_loads_again(directory: Path) -> Outcome:
    path = written(directory, "s.yaml")
    before = service_view(path)
    clear_service_views()
    return Outcome(before, service_view(path), False, "a cleared store loads again")


def missing_file_raises_as_load_schema(directory: Path) -> Outcome:
    missing = directory / "absent.yaml"
    with pytest.raises(Exception) as expected:  # the type is what is compared
        load_schema(missing)
    with pytest.raises(type(expected.value)) as got:
        service_view(missing)
    assert str(got.value) == str(expected.value), "the same message as load_schema's"
    assert not schema_module._SERVICE_STORE, "a failed load stores nothing"
    return Outcome(1, 1, True, "the same error")


def generation_view_is_apart(_: Path) -> Outcome:
    return Outcome(
        generation_view(TOY_SCHEMA),
        service_view(TOY_SCHEMA),
        False,
        "the generation view is never the shared one",
    )


CASES: dict[str, Callable[[Path], Outcome]] = {
    "two toy services": two_toy_services,
    "a new path": new_path_new_entry,
    "same path, other content": rewritten_with_other_content,
    "same path, same bytes": rewritten_with_same_bytes,
    "nine files": ninth_file_evicts_the_first,
    "cleared store": cleared_store_loads_again,
    "missing file": missing_file_raises_as_load_schema,
    "generation view": generation_view_is_apart,
}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_a_service_view_is_shared_exactly_while_the_file_content_is_the_same(
    case: Callable[[Path], Outcome], tmp_path: Path
) -> None:
    outcome = case(tmp_path)
    assert (outcome.first is outcome.second) is outcome.same, outcome.message


def test_two_threads_started_together_on_one_file_load_it_once(tmp_path: Path) -> None:
    path = written(tmp_path, "s.yaml")
    calls: list[Path] = []
    start = threading.Barrier(2)
    views: list[SchemaView] = []

    def counting(file: str | Path) -> SchemaView:
        calls.append(Path(file))
        return load_schema(file)

    def run() -> None:
        start.wait()
        views.append(service_view(path, load=counting))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(calls) == 1, "the lock lets one thread load"
    assert views[0] is views[1], "both threads get the same view"
