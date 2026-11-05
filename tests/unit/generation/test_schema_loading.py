"""load_schema opens a schema whose metamodel imports resolve to the installed package (PD-22)."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.services.schema import load_schema

LIBRARY = Path(__file__).parents[2] / "fixtures" / "library"
MODEL = Path(__file__).parents[3] / "rdf_persistence" / "model"


@dataclass(frozen=True)
class ToySchema:
    """A toy schema file, the classes it defines and the metamodel classes it must bring in."""

    name: str
    toy: frozenset[str]
    imported: frozenset[str]


TOY_SCHEMAS = (
    ToySchema(
        "library",
        frozenset({"Library", "Book", "Chapter", "Note", "Scan", "LibraryAccess"}),
        frozenset({"TenantAccess"}),
    ),
    ToySchema("partial", frozenset({"Shelf"}), frozenset({"AggregateRoot", "Described"})),
    ToySchema("library_tenant", frozenset({"Library"}), frozenset({"AggregateRoot"})),
    ToySchema("books", frozenset({"Book", "Chapter", "Note"}), frozenset({"Tracked", "Described"})),
    ToySchema("scans", frozenset({"Scan", "Book"}), frozenset({"StoredFile"})),
    ToySchema(
        "library_access",
        frozenset({"LibraryAccess"}),
        frozenset({"Grant", "TenantAccess", "Principal"}),
    ),
)


@pytest.mark.parametrize("schema", TOY_SCHEMAS, ids=lambda s: s.name)
def test_toy_schema_loads_with_its_own_and_the_metamodel_classes(schema: ToySchema) -> None:
    classes = set(load_schema(LIBRARY / f"{schema.name}.yaml").all_classes())
    assert schema.toy <= classes, f"{schema.name}: missing toy classes {schema.toy - classes}"
    assert schema.imported <= classes, (
        f"{schema.name}: missing metamodel classes {schema.imported - classes}"
    )


def test_loading_does_not_depend_on_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    classes = load_schema(LIBRARY / "library.yaml").all_classes()
    assert "TenantAccess" in classes, "the metamodel was not found from another directory"


def test_missing_metamodel_module_is_a_clear_error(tmp_path: Path) -> None:
    schema = tmp_path / "broken.yaml"
    schema.write_text(
        "id: https://example.org/broken\nname: broken\ndefault_prefix: x\n"
        "prefixes: {x: 'https://example.org/x#', linkml: 'https://w3id.org/linkml/'}\n"
        "imports: [linkml:types, rdf_persistence/model/rp_nothing]\n"
    )
    with pytest.raises(FileNotFoundError, match="rp_nothing"):
        load_schema(schema).all_classes()


def test_no_two_metamodel_slots_share_a_slot_uri() -> None:
    view = load_schema(MODEL / "rp.yaml")
    uris = Counter(view.get_uri(slot, expand=False) for slot in view.all_slots().values())
    shared = {uri: n for uri, n in uris.items() if n > 1}
    assert not shared, f"slots sharing a predicate: {shared}"
