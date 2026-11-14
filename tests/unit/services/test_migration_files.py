"""A migration file is loaded, checked, and turned into the one guarded update request (PD-5 to PD-8).

TC-11 and TC-11a (the file checks), TC-15 (the request text) and the proof that the request, applied
to a store, moves the data once and only once.
"""

from pathlib import Path

import pytest
import yaml
from rdflib import RDF, Literal, URIRef
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.domain.exceptions import InvalidMigration
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.domain.iris import stamps_graph_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migrations import load_migration, migration_request
from rdf_persistence.testkit import FakeStore

BASE = "https://example.org/"
STAMPS = stamps_graph_iri(BASE)
SCHEMA = "https://example.org/ns/library"
SHELF = "<https://example.org/ns/library#shelf>"
PLACE = "<https://example.org/ns/library#place>"
FILE = "1__2.yaml"


def step(title: str = "rename shelf", **fields: str | None) -> MigrationStep:
    return MigrationStep(title=title, **fields)


def rename() -> MigrationStep:
    return step(
        where_pattern=f"?s {SHELF} ?o .",
        delete_pattern=f"?s {SHELF} ?o .",
        insert_pattern=f"?s {PLACE} ?o .",
    )


def migration(*steps: MigrationStep) -> Migration:
    return Migration(schema_id=SCHEMA, from_version="1", to_version="2", steps=list(steps) or None)


def write(folder: Path, content: Migration | str) -> Path:
    path = folder / FILE
    text = (
        content
        if isinstance(content, str)
        else yaml.safe_dump(content.model_dump(exclude_none=True))
    )
    path.write_text(text, encoding="utf-8")
    return path


def refusal(tmp_path: Path, *steps: MigrationStep) -> str:
    with pytest.raises(InvalidMigration) as refused:
        load_migration(write(tmp_path, migration(*steps)))
    return str(refused.value)


# -- TC-11a, a valid file loads ------------------------------------------------------------------


def test_a_valid_file_loads_into_the_generated_model(tmp_path):
    loaded = load_migration(write(tmp_path, migration(rename())))
    assert loaded == migration(rename())


def test_a_step_may_use_the_graph_variable_in_where_and_insert(tmp_path):  # TC-11a
    using = step(
        where_pattern=f"?rp_graph {SHELF} ?o .",
        insert_pattern=f"?rp_graph {PLACE} ?o .",
    )
    assert load_migration(write(tmp_path, migration(using))).steps == [using]


def test_a_where_pattern_may_filter_bind_and_be_optional(tmp_path):  # D-4
    rich = step(
        where_pattern=f'?s {SHELF} ?o . OPTIONAL {{ ?s {PLACE} ?p }} FILTER (?o != "x") BIND (1 AS ?n)',
        insert_pattern=f"?s {PLACE} ?o .",
    )
    assert load_migration(write(tmp_path, migration(rich))).steps == [rich]


def test_a_file_with_no_step_loads(tmp_path):
    assert load_migration(write(tmp_path, migration())).steps is None


# -- TC-11, one test per refusal -----------------------------------------------------------------


def test_an_unresolved_step_is_refused_naming_file_and_step(tmp_path):
    draft = step(
        title="drop shelf", unresolved="what replaces it?", where_pattern=f"?s {SHELF} ?o ."
    )
    message = refusal(tmp_path, rename(), draft)
    assert FILE in message and "step 2" in message and "drop shelf" in message
    assert "what replaces it?" in message


def test_a_step_without_a_where_pattern_is_refused(tmp_path):
    assert "where_pattern" in refusal(tmp_path, step(insert_pattern=f"?s {PLACE} ?o ."))


def test_a_blank_where_pattern_is_refused(tmp_path):
    assert "where_pattern" in refusal(
        tmp_path, step(where_pattern="  ", insert_pattern=f"?s {PLACE} ?o .")
    )


def test_a_step_with_neither_delete_nor_insert_is_refused(tmp_path):
    assert "delete_pattern" in refusal(tmp_path, step(where_pattern=f"?s {SHELF} ?o ."))


@pytest.mark.parametrize(
    "pattern",
    [
        f"?s {PLACE} _:b .",
        f"?s {PLACE} [ {SHELF} 1 ] .",
        f"?s {PLACE} ( 1 2 ) .",
    ],
    ids=["labelled", "bracketed", "collection"],
)
@pytest.mark.parametrize("clause", ["insert_pattern", "delete_pattern"])
def test_a_blank_node_in_delete_or_insert_is_refused(tmp_path, clause, pattern):
    refused = refusal(tmp_path, step(where_pattern=f"?s {SHELF} ?o .", **{clause: pattern}))
    assert "blank node" in refused and "step 1" in refused


def test_a_blank_node_in_where_is_allowed(tmp_path):
    fine = step(where_pattern=f"?s {SHELF} [ {PLACE} ?o ] .", insert_pattern=f"?s {PLACE} ?o .")
    assert load_migration(write(tmp_path, migration(fine))).steps == [fine]


@pytest.mark.parametrize("keyword", ["GRAPH", "graph", "SERVICE"])
@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_graph_and_service_are_refused_in_any_pattern(tmp_path, clause, keyword):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = f"{keyword} <urn:other> {{ ?s {SHELF} ?o }}"
    assert clause in refusal(tmp_path, step(**fields))


@pytest.mark.parametrize("variable", ["?rp_registry", "$rp_registry", "?rp_x"])
def test_a_reserved_variable_is_refused(tmp_path, variable):
    refused = refusal(
        tmp_path,
        step(where_pattern=f"{variable} {SHELF} ?o .", insert_pattern=f"?s {PLACE} ?o ."),
    )
    assert "rp_" in refused


def test_a_keyword_inside_an_iri_string_or_comment_is_not_a_keyword(tmp_path):
    fine = step(
        where_pattern=(
            f'?s {SHELF} ?o . FILTER (?o != "GRAPH") # SERVICE\n'
            "FILTER (?s != <https://example.org/graph/SERVICE/?rp_x>)"
        ),
        insert_pattern=f"?s {PLACE} ?o .",
    )
    assert load_migration(write(tmp_path, migration(fine))).steps == [fine]


@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_a_pattern_that_does_not_parse_is_refused(tmp_path, clause):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ex:shelf ?o ."  # no PREFIX in the request
    refused = refusal(tmp_path, step(**fields))
    assert clause in refused and "step 1" in refused


@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_a_pattern_that_escapes_its_group_is_refused(tmp_path, clause):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ?p ?o } } ; CLEAR ALL ; INSERT DATA { <a> <b> <c>"
    assert clause in refusal(tmp_path, step(**fields))


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
def test_a_pattern_that_parses_alone_but_breaks_the_whole_request_is_refused(tmp_path, clause):
    # alone it is INSERT { ?s ?p ?o } WHERE {} ; CLEAR ALL ; INSERT { ?s ?p ?o } WHERE {}: it parses
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ?p ?o } WHERE {} ; CLEAR ALL ; INSERT { ?s ?p ?o"
    assert "the request does not parse" in refusal(tmp_path, step(**fields))


def test_a_request_with_the_wrong_number_of_operations_is_refused(tmp_path, monkeypatch):
    from rdf_persistence.services import migrations

    smuggled = migrations.migration_request
    monkeypatch.setattr(
        migrations,
        "migration_request",
        lambda m, stamps: smuggled(m, stamps) + ";\nCLEAR ALL",
    )
    with pytest.raises(InvalidMigration, match="parses into 4 operations, not the 3"):
        load_migration(write(tmp_path, migration(rename())))


def test_a_prefixed_name_is_refused_because_the_request_has_no_prefixes(tmp_path):
    prefixed = step(where_pattern="?s rdf:type ?o .", insert_pattern=f"?s {PLACE} ?o .")
    assert "prefixed name" in refusal(tmp_path, prefixed)


def test_an_invalid_file_is_refused_naming_the_file(tmp_path):
    for text in ("{not: [valid", "- a list", "schema_id: x"):
        with pytest.raises(InvalidMigration, match=FILE):
            load_migration(write(tmp_path, text))


def test_a_missing_file_is_refused_naming_the_file(tmp_path):
    with pytest.raises(InvalidMigration, match="missing.yaml"):
        load_migration(tmp_path / "missing.yaml")


def test_a_schema_id_that_is_no_iri_is_refused(tmp_path):
    path = write(tmp_path, migration().model_copy(update={"schema_id": "not an iri"}))
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(path)


# -- TC-15, the request text ---------------------------------------------------------------------


def operations(request: str) -> list[str]:
    return [part.strip() for part in request.split(";\n")]


def test_the_request_is_the_steps_then_the_rotation_then_the_stamp_move():  # TC-15
    second = step(
        title="drop",
        where_pattern=f"?s {PLACE} ?o .",
        delete_pattern=f"?s {PLACE} ?o .",
    )
    ops = operations(migration_request(migration(rename(), second), STAMPS))
    assert len(ops) == 4
    assert f"INSERT {{ GRAPH ?rp_graph {{ ?s {PLACE} ?o . }} }}" in ops[0]
    assert (
        "INSERT" not in ops[1] and f"DELETE {{ GRAPH ?rp_graph {{ ?s {PLACE} ?o . }} }}" in ops[1]
    )
    assert "STRUUID()" in ops[2] and str(v.VERSION) in ops[2]
    assert '"2"' in ops[3] and '"1"' in ops[3]


def test_each_operation_carries_the_from_guard():  # TC-15
    ops = operations(migration_request(migration(rename(), rename()), STAMPS))
    guard = f'GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }}'
    assert all(guard in op for op in ops)


def test_a_step_keeps_to_one_graph_and_leaves_stamps_and_loaded_graphs_alone():
    step_op = operations(migration_request(migration(rename()), STAMPS))[0]
    loaded = v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]
    assert f"FILTER (?rp_graph != <{STAMPS}>)" in step_op
    assert (
        f"FILTER NOT EXISTS {{ GRAPH ?rp_registry {{ ?rp_graph <{v.REGISTRY_KIND}> <{loaded}> }} }}"
        in step_op
    )
    assert (
        f"FILTER NOT EXISTS {{ GRAPH ?rp_graph {{ ?rp_entry <{v.REGISTRY_KIND}> ?rp_kind }} }}"
        in step_op
    )


def test_the_rotation_leaves_the_modified_date_alone():
    rotation = operations(migration_request(migration(rename()), STAMPS))[1]
    assert str(v.MODIFIED) not in rotation


def test_without_steps_the_request_is_the_stamp_move_alone():  # TC-15
    request = migration_request(migration(), STAMPS)
    assert len(operations(request)) == 1
    assert "STRUUID" not in request and '"2"' in request


def test_the_request_parses_into_the_expected_operations():
    assert len(parseUpdate(migration_request(migration(rename(), rename()), STAMPS)).request) == 4


# -- the request, applied -------------------------------------------------------------------------

DATABASE = "lib-t-0001"
BOOK = URIRef("https://example.org/t/book/1")
LOADED = URIRef("https://example.org/t/content/0000000000001")
REGISTRY = URIRef("https://example.org/t/registry")
SHELF_IRI = URIRef("https://example.org/ns/library#shelf")
PLACE_IRI = URIRef("https://example.org/ns/library#place")
OLD_TOKEN = Literal("token-1")


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(DATABASE)
    await fake.update(
        DATABASE,
        f"""INSERT DATA {{
          GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }}
          GRAPH <{BOOK}> {{ <{BOOK}> a <urn:Book> ; <{SHELF_IRI}> "A3" ; <{v.VERSION}> "{OLD_TOKEN}" }}
          GRAPH <{LOADED}> {{ <{BOOK}> <{SHELF_IRI}> "loaded" }}
          GRAPH <{REGISTRY}> {{ <{LOADED}> <{v.REGISTRY_KIND}> <{v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]}> }}
        }}""",
    )
    return fake


async def triples(store: FakeStore, graph: URIRef) -> set[tuple]:
    rows = await store.query(
        DATABASE, f"SELECT ?s ?p ?o WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"
    )
    return {(r.s, r.p, r.o) for r in rows}  # type: ignore[union-attr]


async def stamp(store: FakeStore) -> list[str]:
    rows = await store.query(
        DATABASE,
        f"SELECT ?v WHERE {{ GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> ?v }} }}",
    )
    return [str(r.v) for r in rows]  # type: ignore[union-attr]


async def test_the_request_moves_the_data_rotates_the_token_and_moves_the_stamp(store):
    await store.update(DATABASE, migration_request(migration(rename()), STAMPS))
    book = await triples(store, BOOK)
    assert (BOOK, PLACE_IRI, Literal("A3")) in book
    assert not any(p == SHELF_IRI for _, p, _ in book)
    assert (BOOK, RDF.type, URIRef("urn:Book")) in book
    token = next(o for _, p, o in book if p == v.VERSION)
    assert token != OLD_TOKEN
    assert await triples(store, LOADED) == {(BOOK, SHELF_IRI, Literal("loaded"))}
    assert await stamp(store) == ["2"]


async def test_sending_the_same_request_again_changes_nothing(store):
    request = migration_request(migration(rename()), STAMPS)
    await store.update(DATABASE, request)
    before = {g: await triples(store, g) for g in (BOOK, LOADED, STAMPS)}
    await store.update(DATABASE, request)
    assert {g: await triples(store, g) for g in (BOOK, LOADED, STAMPS)} == before
