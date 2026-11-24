"""A migration file is loaded, checked, and turned into the one guarded update request (PD-5 to PD-8).

TC-11 and TC-11a (the file checks), TC-15 (the request text) and the proof that the request, applied
to a store, moves the data once and only once.
"""

from pathlib import Path

import pytest
from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.core.domain.exceptions import InvalidMigration, SparqlError
from rdf_persistence.core.domain.generated.rp_core import RegistryKind
from rdf_persistence.migrations.services.generated.rp_migrations_services import MigrationStep
from rdf_persistence.migrations.services.migrations import load_migration, migration_request
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import FakeStore
from tests.unit.migrations.migration_steps import (
    FILE,
    PLACE,
    SCHEMA,
    SHELF,
    STAMPS,
    migration,
    rename,
    step,
    write,
)


def refusal(tmp_path: Path, *steps: MigrationStep) -> str:
    with pytest.raises(InvalidMigration) as refused:
        load_migration(write(tmp_path, migration(*steps)))
    return str(refused.value)


# -- TC-11a, a valid file loads ------------------------------------------------------------------


def test_a_valid_file_loads_into_the_generated_model(tmp_path):
    loaded = load_migration(write(tmp_path, migration(rename())))
    assert loaded == migration(rename()), "the file's fields are the model's"


def test_a_step_may_use_the_graph_variable_in_where_and_insert(tmp_path):  # TC-11a
    using = step(
        where_pattern=f"?rp_graph {SHELF} ?o .",
        insert_pattern=f"?rp_graph {PLACE} ?o .",
    )
    steps = load_migration(write(tmp_path, migration(using))).steps
    assert steps == [using], "?rp_graph is open to a step"


def test_a_where_pattern_may_filter_bind_and_be_optional(tmp_path):  # D-4
    rich = step(
        where_pattern=f'?s {SHELF} ?o . OPTIONAL {{ ?s {PLACE} ?p }} FILTER (?o != "x") BIND (1 AS ?n)',
        insert_pattern=f"?s {PLACE} ?o .",
    )
    steps = load_migration(write(tmp_path, migration(rich))).steps
    assert steps == [rich], "filter, bind and optional are allowed in a where"


def test_a_file_with_no_step_loads(tmp_path):
    steps = load_migration(write(tmp_path, migration())).steps
    assert steps is None, "a migration may only move the stamp"


def test_a_where_pattern_may_read_the_toolkits_own_predicates(tmp_path):  # PD-22 item 3
    reading = step(
        where_pattern=f"?s <{v.VERSION}> ?t . ?s <{v.REGISTRY_KIND}> ?k . ?s <{v.DATA_SCHEMA_VERSION}> ?d .",
        insert_pattern=f"?s {PLACE} ?t .",
    )
    steps = load_migration(write(tmp_path, migration(reading))).steps
    assert steps == [reading], "reading is harmless"


# -- TC-11, one test per refusal -----------------------------------------------------------------


def test_an_unresolved_step_is_refused_naming_file_and_step(tmp_path):
    draft = step(
        title="drop shelf", unresolved="what replaces it?", where_pattern=f"?s {SHELF} ?o ."
    )
    message = refusal(tmp_path, rename(), draft)
    assert FILE in message, "the file is named"
    assert "step 2" in message, "the step's number is named"
    assert "drop shelf" in message, "the step's title is named"
    assert "what replaces it?" in message, "the draft's note is shown"


def test_a_long_draft_note_and_title_are_cut_in_the_message(tmp_path):
    draft = step(title="t" * 5000, unresolved="n" * 5000)
    message = refusal(tmp_path, draft)
    assert len(message) < 1000, "what the file says is bounded"


def test_a_step_without_a_where_pattern_is_refused(tmp_path):
    message = refusal(tmp_path, step(insert_pattern=f"?s {PLACE} ?o ."))
    assert "where_pattern" in message, "the missing pattern is named"


def test_a_blank_where_pattern_is_refused(tmp_path):
    message = refusal(tmp_path, step(where_pattern="  ", insert_pattern=f"?s {PLACE} ?o ."))
    assert "where_pattern" in message, "a blank pattern is a missing one"


def test_a_step_with_neither_delete_nor_insert_is_refused(tmp_path):
    message = refusal(tmp_path, step(where_pattern=f"?s {SHELF} ?o ."))
    assert "delete_pattern" in message, "the two patterns it lacks are named"


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
    assert "blank node" in refused, "the reason is given"
    assert "step 1" in refused, "the step is named"


# Class: a predicate of the toolkit's own list; one per clause stands for it
@pytest.mark.parametrize("predicate", [v.VERSION])
@pytest.mark.parametrize("clause", ["insert_pattern", "delete_pattern"])
def test_a_template_naming_a_toolkit_predicate_is_refused(
    tmp_path, clause, predicate
):  # PD-22 item 3
    refused = refusal(
        tmp_path, step(where_pattern=f"?s {SHELF} ?o .", **{clause: f"?s <{predicate}> ?o ."})
    )
    assert clause in refused, "the pattern is named"


def test_a_blank_node_in_where_is_allowed(tmp_path):
    fine = step(where_pattern=f"?s {SHELF} [ {PLACE} ?o ] .", insert_pattern=f"?s {PLACE} ?o .")
    steps = load_migration(write(tmp_path, migration(fine))).steps
    assert steps == [fine], "a where only matches"


@pytest.mark.parametrize("keyword", ["GRAPH", "graph", "SERVICE"])
@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_graph_and_service_are_refused_in_any_pattern(tmp_path, clause, keyword):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = f"{keyword} <urn:other> {{ ?s {SHELF} ?o }}"
    assert clause in refusal(tmp_path, step(**fields)), "the pattern is named"


# Classes: a reserved ?rp_ variable (?rp_x is the same), the dollar form
@pytest.mark.parametrize("variable", ["?rp_registry", "$rp_registry"])
def test_a_reserved_variable_is_refused(tmp_path, variable):
    refused = refusal(
        tmp_path,
        step(where_pattern=f"{variable} {SHELF} ?o .", insert_pattern=f"?s {PLACE} ?o ."),
    )
    assert "rp_" in refused, "the reserved variable is named"


def test_a_keyword_inside_an_iri_string_or_comment_is_not_a_keyword(tmp_path):
    fine = step(
        where_pattern=(
            f'?s {SHELF} ?o . FILTER (?o != "GRAPH") # SERVICE\n'
            "FILTER (?s != <https://example.org/graph/SERVICE/?rp_x>)"
        ),
        insert_pattern=f"?s {PLACE} ?o .",
    )
    steps = load_migration(write(tmp_path, migration(fine))).steps
    assert steps == [fine], "a word inside a string, an IRI or a comment is no keyword"


@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_a_pattern_with_a_prefixed_name_is_refused_naming_the_pattern_and_the_step(
    tmp_path, clause
):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ex:shelf ?o ."  # no PREFIX in the request
    refused = refusal(tmp_path, step(**fields))
    assert clause in refused, "the pattern is named"
    assert "step 1" in refused, "the step is named"


@pytest.mark.parametrize("clause", ["where_pattern", "delete_pattern", "insert_pattern"])
def test_a_pattern_that_escapes_its_group_is_refused(tmp_path, clause):
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ?p ?o } } ; CLEAR ALL ; INSERT DATA { <a> <b> <c>"
    assert clause in refusal(tmp_path, step(**fields)), "the pattern is named"


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
def test_a_pattern_that_parses_alone_but_breaks_the_whole_request_is_refused(tmp_path, clause):
    # alone it is INSERT { ?s ?p ?o } WHERE {} ; CLEAR ALL ; INSERT { ?s ?p ?o } WHERE {}: it parses
    fields = {
        "where_pattern": f"?s {SHELF} ?o .",
        "delete_pattern": f"?s {SHELF} ?o .",
        "insert_pattern": f"?s {PLACE} ?o .",
    }
    fields[clause] = "?s ?p ?o } WHERE {} ; CLEAR ALL ; INSERT { ?s ?p ?o"
    message = refusal(tmp_path, step(**fields))
    assert "the request does not parse" in message, "the whole request is checked"


def test_a_request_with_the_wrong_number_of_operations_is_refused(tmp_path, monkeypatch):
    from rdf_persistence.migrations.services import migrations

    smuggled = migrations.migration_request
    monkeypatch.setattr(  # X3
        migrations,
        "migration_request",
        lambda m, stamps, **flags: smuggled(m, stamps, **flags) + ";\nCLEAR ALL",
    )
    with pytest.raises(InvalidMigration, match="parses into 4 operations, not the 3"):
        load_migration(write(tmp_path, migration(rename())))


def test_a_prefixed_name_is_refused_because_the_request_has_no_prefixes(tmp_path):
    prefixed = step(where_pattern="?s rdf:type ?o .", insert_pattern=f"?s {PLACE} ?o .")
    assert "prefixed name" in refusal(tmp_path, prefixed), "the reason is given"


def test_a_prefixed_name_hidden_in_a_filter_that_looks_like_an_iri_is_refused(
    tmp_path,
):  # PD-22 item 1
    hidden = step(
        where_pattern=f"?s {SHELF} ?o FILTER(?o<rdf:x||?p>1)", insert_pattern=f"?s {PLACE} ?o ."
    )
    assert "prefixed name" in refusal(tmp_path, hidden), "the parse tree has the name"


def test_an_unclosed_iri_is_refused_as_not_parsing(tmp_path):
    unclosed = step(where_pattern="?s <urn:shelf ?o .", insert_pattern=f"?s {PLACE} ?o .")
    assert "does not parse" in refusal(tmp_path, unclosed), "the parser's refusal is the reason"


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
    assert len(ops) == 4, "two steps, the rotation, the stamp move"
    assert f"INSERT {{ GRAPH ?rp_graph {{ ?s {PLACE} ?o . }} }}" in ops[0], "step 1 inserts"
    assert "INSERT" not in ops[1], "step 2 has no insert"
    assert f"DELETE {{ GRAPH ?rp_graph {{ ?s {PLACE} ?o . }} }}" in ops[1], "step 2 deletes"
    assert "STRUUID()" in ops[2], "the rotation mints a token"
    assert str(v.VERSION) in ops[2], "the rotation replaces the version token"
    assert '"2"' in ops[3], "the stamp moves to the new version"
    assert '"1"' in ops[3], "the stamp moves from the old version"


def test_each_operation_carries_the_from_guard():  # TC-15
    ops = operations(migration_request(migration(rename(), rename()), STAMPS))
    guard = f'GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }}'
    unguarded = [op for op in ops if guard not in op]
    assert unguarded == [], "every operation matches only the from stamp"


def test_a_step_leaves_the_stamps_graph_alone():
    step_op = operations(migration_request(migration(rename()), STAMPS))[0]
    assert f"FILTER (?rp_graph != <{STAMPS}>)" in step_op, "the stamps graph is filtered out"


def test_a_step_leaves_loaded_graphs_alone():
    step_op = operations(migration_request(migration(rename()), STAMPS))[0]
    loaded = v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]
    guard = f"MINUS {{ GRAPH ?rp_registry {{ ?rp_graph <{v.REGISTRY_KIND}> <{loaded}> }} }}"
    assert guard in step_op, "a graph the registry calls loaded is excluded by MINUS (PD-26)"


def test_the_loaded_graph_exclusion_gives_the_result_of_the_filter_it_replaced():
    """PD-26: MINUS and the earlier FILTER NOT EXISTS agree on every kind of graph a dump can hold."""
    loaded_kind = v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]
    minus = f"MINUS {{ GRAPH ?rp_registry {{ ?rp_graph <{v.REGISTRY_KIND}> <{loaded_kind}> }} }}"
    old_filter = minus.replace("MINUS", "FILTER NOT EXISTS")
    request = migration_request(migration(rename()), STAMPS)
    assert minus in request, "the request holds the exclusion this test replaces"
    other_registry, from_data_graph, pretender, loaded_two = (
        URIRef(f"https://example.org/t/{name}")
        for name in ("registry-b", "data-graph", "pretender", "loaded-two")
    )

    def holding_every_kind_of_graph() -> Dataset:
        data = Dataset()
        data.graph(URIRef(STAMPS)).add((URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal("1")))
        for graph in (
            BOOK,
            LOADED,
            loaded_two,
            pretender,
            REGISTRY,
            other_registry,
            from_data_graph,
        ):
            data.graph(graph).add((BOOK, SHELF_IRI, Literal(f"on {graph}")))
        data.graph(BOOK).add((BOOK, v.VERSION, OLD_TOKEN))
        data.graph(REGISTRY).add((LOADED, v.REGISTRY_KIND, loaded_kind))
        data.graph(other_registry).add((loaded_two, v.REGISTRY_KIND, loaded_kind))
        data.graph(from_data_graph).add((from_data_graph, v.REGISTRY_KIND, Literal("other")))
        data.graph(pretender).add((pretender, v.REGISTRY_KIND, Literal("anything")))
        return data

    with_minus, with_filter = holding_every_kind_of_graph(), holding_every_kind_of_graph()
    with_minus.update(request)
    with_filter.update(request.replace(minus, old_filter))
    moved = {c for _, p, _, c in with_minus.quads() if p == PLACE_IRI}
    assert moved == {BOOK}, "the step reached the data graph and no other kind of graph"

    def without_tokens(data: Dataset) -> set:  # the rotated version token is random (STRUUID)
        return {q for q in data.quads() if q[1] != v.VERSION}

    assert without_tokens(with_minus) == without_tokens(with_filter), (
        "the same quads after both texts"
    )


def test_a_step_leaves_registry_graphs_alone():
    step_op = operations(migration_request(migration(rename()), STAMPS))[0]
    guard = f"FILTER NOT EXISTS {{ GRAPH ?rp_graph {{ ?rp_entry <{v.REGISTRY_KIND}> ?rp_kind }} }}"
    assert guard in step_op, "a graph that holds registry statements is filtered out"


def test_the_rotation_leaves_the_modified_date_alone():
    rotation = operations(migration_request(migration(rename()), STAMPS))[1]
    assert str(v.MODIFIED) not in rotation, "a migration is not an edit"


def test_without_steps_the_request_is_the_stamp_move_alone():  # TC-15
    request = migration_request(migration(), STAMPS)
    assert len(operations(request)) == 1, "one operation"
    assert "STRUUID" not in request, "no rotation without a step"
    assert '"2"' in request, "the stamp moves to the new version"


def test_the_request_parses_into_the_expected_operations():
    request = migration_request(migration(rename(), rename()), STAMPS)
    assert len(parseUpdate(request).request) == 4, "two steps, the rotation, the stamp move"


def test_the_request_refuses_a_pattern_that_was_not_checked():
    unchecked = step(where_pattern=f"?s {SHELF} ?o .", insert_pattern="?s ex:place ?o .")
    with pytest.raises(SparqlError, match="insert_pattern"):
        migration_request(migration(unchecked), STAMPS)


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
    assert (BOOK, PLACE_IRI, Literal("A3")) in book, "the value is under the new predicate"
    assert not any(p == SHELF_IRI for _, p, _ in book), "the old predicate is gone"
    assert (BOOK, RDF.type, URIRef("urn:Book")) in book, "the rest of the graph is kept"
    token = next(o for _, p, o in book if p == v.VERSION)
    assert token != OLD_TOKEN, "the version token is rotated"
    assert await triples(store, LOADED) == {(BOOK, SHELF_IRI, Literal("loaded"))}, (
        "a loaded graph is not touched"
    )
    assert await stamp(store) == ["2"], "the stamp moved"


async def test_sending_the_same_request_again_changes_nothing(store):
    request = migration_request(migration(rename()), STAMPS)
    await store.update(DATABASE, request)
    before = {g: await triples(store, g) for g in (BOOK, LOADED, STAMPS)}
    await store.update(DATABASE, request)
    after = {g: await triples(store, g) for g in (BOOK, LOADED, STAMPS)}
    assert after == before, "the stamp is the guard: a second send matches nothing"
