"""Attacks on the gate of a hand-written migration step (PD-5, PD-6, D-4), and on the guarded request.

A step must stay inside ``?rp_graph``, never touch the stamps graph or a loaded graph, never mint a
blank node, never run more operations than the template has, and do nothing once the stamp moved.
Each test below plants one hostile file or database and asserts what the design promises.
"""

from pathlib import Path

import pytest
import yaml
from rdflib import Literal, URIRef
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.domain.exceptions import InvalidMigration, SparqlError
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import Migration
from rdf_persistence.domain.sparql import term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migrations import load_migration, migration_request
from rdf_persistence.testkit import FakeStore
from tests.unit.services.test_migration_files import (
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

BS = chr(92)


def esc(word: str) -> str:
    """``word`` written with SPARQL ``u`` escapes, which a SPARQL parser reads back as the word."""
    return "".join(f"{BS}u{ord(c):04x}" for c in word)


def load(tmp_path: Path, **fields: str | None) -> Migration:
    return load_migration(write(tmp_path, migration(step(**fields))))


def refused(tmp_path: Path, **fields: str | None) -> str:
    with pytest.raises(InvalidMigration) as error:
        load(tmp_path, **fields)
    return str(error.value)


WHERE = f"?s {SHELF} ?o ."
DELETE = f"?s {SHELF} ?o ."
INSERT = f"?s {PLACE} ?o ."


def fields_with(clause: str, text: str) -> dict[str, str | None]:
    """The fields of a valid step, with the clause ``clause`` replaced by ``text``."""
    fields: dict[str, str | None] = {
        "where_pattern": WHERE,
        "delete_pattern": DELETE,
        "insert_pattern": INSERT,
    }
    fields[clause] = text
    return fields


CLAUSES = ["where_pattern", "delete_pattern", "insert_pattern"]
OTHER = "<urn:other>"

# -- attacks the gate stops ------------------------------------------------------------------------

STOPPED_IN_ANY_CLAUSE = {
    "mixed case": f"Graph {OTHER} {{ ?s {SHELF} ?o }}",
    "odd case": f"gRaPh {OTHER} {{ ?s {SHELF} ?o }}",
    "glued to a variable": "GRAPH?x { ?s ?p ?o }",
    "after a brace": f"{{GRAPH {OTHER} {{ ?s ?p ?o }}}}",
    "after a dot": f"?s {SHELF} ?o .GRAPH {OTHER} {{ ?s ?p ?o }}",
    "after a newline": f"?s {SHELF} ?o .\nGRAPH\n{OTHER} {{ ?s ?p ?o }}",
    "after a tab": f"?s {SHELF} ?o .\tGRAPH\t{OTHER} {{ ?s ?p ?o }}",
    "service": "SERVICE <http://localhost:1/sparql> { ?s ?p ?o }",
    "service silent": "SERVICE SILENT <http://localhost:1/sparql> { ?s ?p ?o }",
    "lower service": "service <http://localhost:1/sparql> { ?s ?p ?o }",
    "after a string with an escaped quote": f'?s {SHELF} "a{BS}"b" . GRAPH {OTHER} {{ ?s ?p ?o }}',
    "a comparison that looks like an iri": f"?s {SHELF} ?o FILTER(?o < 3 && ?o > 1) GRAPH {OTHER} {{ ?s ?p ?o }}",
    "a prefixed name": f"?s rdf:type ?o . ?s {SHELF} ?o",
    "an empty prefix": "?s :shelf ?o",
}


@pytest.mark.parametrize("clause", ["where_pattern"])
@pytest.mark.parametrize("attack", STOPPED_IN_ANY_CLAUSE.values(), ids=STOPPED_IN_ANY_CLAUSE)
def test_a_graph_service_or_prefix_in_the_where_is_refused(tmp_path, clause, attack):
    refused(tmp_path, **fields_with(clause, attack))


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
@pytest.mark.parametrize("attack", STOPPED_IN_ANY_CLAUSE.values(), ids=STOPPED_IN_ANY_CLAUSE)
def test_a_graph_service_or_prefix_in_a_template_is_refused(tmp_path, clause, attack):
    refused(tmp_path, **fields_with(clause, attack))


RESERVED = {
    "dollar form": "$rp_registry",
    "the old token": "?rp_old",
    "the new token": "?rp_new",
    "a bare prefix": "?rp_",
    "a lookalike of the graph variable": "?rp_graph2",
    "the graph variable's suffix": "?rp_graphx",
}


@pytest.mark.parametrize("clause", CLAUSES)
@pytest.mark.parametrize("variable", RESERVED.values(), ids=RESERVED)
def test_a_reserved_variable_is_refused_in_every_clause(tmp_path, clause, variable):
    refused(tmp_path, **fields_with(clause, f"{variable} {SHELF} ?o ."))


@pytest.mark.parametrize("clause", CLAUSES)
@pytest.mark.parametrize("variable", ["?rp_graph", "$rp_graph"])
def test_the_graph_variable_alone_is_open_to_a_step(tmp_path, clause, variable):
    loaded = load(tmp_path, **fields_with(clause, f"{variable} {SHELF} ?o ."))
    assert loaded.steps


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
@pytest.mark.parametrize(
    "blank",
    ["[]", "[ ]", "_:b", "( )", "(1)", "[ a <urn:T> ]", f"[ {PLACE} ( 1 2 ) ]"],
    ids=["empty", "spaced", "labelled", "nil", "list", "typed", "nested"],
)
def test_every_form_of_blank_node_in_a_template_is_refused(tmp_path, clause, blank):
    refused(tmp_path, **fields_with(clause, f"?s {PLACE} {blank} ."))


def test_a_trailing_comment_that_would_swallow_the_template_is_refused(tmp_path):
    for clause in CLAUSES:
        refused(tmp_path, **fields_with(clause, f"?s {SHELF} ?o . # and the rest"))


def test_a_trailing_comment_with_a_newline_loads_and_the_request_keeps_its_shape(tmp_path):
    loaded = load(tmp_path, where_pattern=f"?s {SHELF} ?o . # note\n", insert_pattern=INSERT)
    assert len(parseUpdate(migration_request(loaded, STAMPS)).request) == 3


@pytest.mark.parametrize("clause", CLAUSES)
def test_closing_braces_and_a_second_operation_are_refused(tmp_path, clause):
    refused(tmp_path, **fields_with(clause, "?s ?p ?o } } ; DROP ALL ; INSERT { ?s ?p ?o"))


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
def test_a_template_that_closes_the_clause_and_opens_a_graph_is_refused(tmp_path, clause):
    refused(
        tmp_path,
        **fields_with(clause, f"?s ?p ?o }} }} INSERT {{ GRAPH {OTHER} {{ ?s ?p ?o"),
    )


# -- attacks that get through the gate: the check reads text, the parser reads another text --------


def _hidden_in_what_looks_like_an_iri(payload: str) -> str:
    """A filter whose ``<`` and ``>`` enclose ``payload`` with no space: the scan reads an IRI."""
    return f"?s {SHELF} ?o FILTER(?o<3){payload}FILTER(?o>1)"


EVADING_WHERE = {
    "an escaped GRAPH": f"{esc('GRAPH')} {OTHER} {{ ?x {SHELF} ?o }}",
    "an escaped lower graph": f"{esc('graph')} {OTHER} {{ ?x {SHELF} ?o }}",
    "an escaped first letter of GRAPH": f"{BS}u0047RAPH {OTHER} {{ ?x {SHELF} ?o }}",
    "an eight digit escape of GRAPH": f"{BS}U00000047RAPH {OTHER} {{ ?x {SHELF} ?o }}",
    "an escaped SERVICE": f"{esc('SERVICE')} <http://localhost:1/sparql> {{ ?x ?p ?o }}",
    "an escaped reserved variable": f"?s {SHELF} ?o . BIND({OTHER} AS ?{esc('rp_registry')})",
    "an escaped dollar reserved variable": f"?s {SHELF} ?o . BIND({OTHER} AS ${esc('rp_registry')})",
    "an escaped reserved prefix only": f"?s {SHELF} ?o . BIND(1 AS ?{BS}u0072p_old)",
    "a newline escape that ends a comment": f"?s {SHELF} ?o . # {BS}u000A GRAPH {OTHER} {{ ?x {SHELF} ?o }}",
    "GRAPH between two comparison signs": _hidden_in_what_looks_like_an_iri("GRAPH?x{?a?b?c}"),
    "a reserved variable between two comparison signs": _hidden_in_what_looks_like_an_iri(
        'BIND("n"AS?rp_registry)'
    ),
}


@pytest.mark.parametrize("attack", EVADING_WHERE.values(), ids=EVADING_WHERE)
def test_a_graph_or_reserved_variable_written_so_the_scan_misses_it_is_refused(tmp_path, attack):
    """PD-6: no pattern may contain GRAPH, SERVICE or a ``?rp_`` variable other than ``?rp_graph``.

    SPARQL reads ``u`` escapes before it tokenises, and ``?o<3)...(?o>`` is a comparison, not an
    IRI; a scan of the raw text sees neither.
    """
    refused(tmp_path, **fields_with("where_pattern", attack))


@pytest.mark.parametrize("clause", ["delete_pattern", "insert_pattern"])
@pytest.mark.parametrize(
    "blank",
    [
        f"{BS}u005b{BS}u005d",
        f"{BS}u005b {BS}u005d",
        f"{BS}u0028 1 2 {BS}u0029",
        f"{BS}u0028{BS}u0029",
    ],
    ids=["escaped-brackets", "escaped-spaced-brackets", "escaped-list", "escaped-nil"],
)
def test_a_blank_node_written_with_escapes_is_refused(tmp_path, clause, blank):
    refused(tmp_path, **fields_with(clause, f"?s {PLACE} {blank} ."))


# -- what the evasions would do to a database -------------------------------------------------------

DATABASE = "lib-t-0001"
A = URIRef("https://example.org/t/a")
B = URIRef("https://example.org/t/b")
C = URIRef("https://example.org/t/c")  # a graph with no version token
LOADED = URIRef("https://example.org/t/content/0000000000001")
REGISTRY = URIRef("https://example.org/t/registry")
SHELF_IRI = URIRef("https://example.org/ns/library#shelf")
PLACE_IRI = URIRef("https://example.org/ns/library#place")
KIND_LOADED = v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]
SEED = f"""INSERT DATA {{
  GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }}
  GRAPH <{A}> {{ <{A}> <{SHELF_IRI}> "a" ; <{v.VERSION}> "token-a" }}
  GRAPH <{B}> {{ <{B}> <{SHELF_IRI}> "b" ; <{v.VERSION}> "token-b" }}
  GRAPH <{C}> {{ <{C}> <{SHELF_IRI}> "c" }}
  GRAPH <{LOADED}> {{ <{B}> <{SHELF_IRI}> "loaded" }}
  GRAPH <{REGISTRY}> {{ <{LOADED}> <{v.REGISTRY_KIND}> <{KIND_LOADED}> }}
}}"""


@pytest.fixture
async def store():
    fake = FakeStore()
    for name in (DATABASE, "other"):
        await fake.create_dataset(name)
        await fake.update(name, SEED)
    return fake


async def quads(store: FakeStore, database: str = DATABASE) -> set[tuple]:
    rows = await store.query(database, "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }")
    return {(r.g, r.s, r.p, r.o) for r in rows}  # type: ignore[union-attr]


def graph_of(found: set[tuple], graph: URIRef) -> set[tuple]:
    return {(s, p, o) for g, s, p, o in found if g == graph}


def without_tokens(triples: set[tuple]) -> set[tuple]:
    return {t for t in triples if t[1] != v.VERSION}


async def applied_or_refused(tmp_path: Path, store: FakeStore, **fields: str | None) -> bool:
    """Load the step and send its request; False when the gate refuses the file."""
    try:
        loaded = load(tmp_path, **fields)
    except InvalidMigration:
        return False
    await store.update(DATABASE, migration_request(loaded, STAMPS))
    return True


async def test_a_step_cannot_reach_the_loaded_graph_by_rebinding_the_registry_variable(
    tmp_path, store
):
    """The template's FILTER NOT EXISTS reads ``?rp_registry``; a step that binds it blinds the guard."""
    before = await quads(store)
    for attack in (
        f"?s <{SHELF_IRI}> ?o . BIND(<urn:none> AS ?{esc('rp_registry')})",
        _hidden_in_what_looks_like_an_iri('BIND("n"AS?rp_registry)').replace(
            "?s " + SHELF, f"?s <{SHELF_IRI}>"
        ),
    ):
        fresh = FakeStore()
        await fresh.create_dataset(DATABASE)
        await fresh.update(DATABASE, SEED)
        if await applied_or_refused(
            tmp_path, fresh, where_pattern=attack, delete_pattern=f"?s <{SHELF_IRI}> ?o ."
        ):
            assert graph_of(await quads(fresh), LOADED) == graph_of(before, LOADED), attack
            assert graph_of(await quads(fresh), REGISTRY) == graph_of(before, REGISTRY), attack


async def test_a_where_that_reads_another_graph_cannot_write_into_graphs_it_did_not_match(
    tmp_path, store
):
    """An escaped GRAPH makes the where match on graph B whatever ``?rp_graph`` is, so every graph,
    the registry among them, gets the insert; a step must never move data between graphs."""
    before = await quads(store)
    gate = {
        "where_pattern": f"{esc('GRAPH')} <{B}> {{ ?x <{SHELF_IRI}> ?o }}",
        "insert_pattern": f"<{A}> <{PLACE_IRI}> ?o .",
    }
    if await applied_or_refused(tmp_path, store, **gate):
        after = await quads(store)
        assert without_tokens(graph_of(after, REGISTRY)) == without_tokens(
            graph_of(before, REGISTRY)
        ), "the registry graph gained data from graph B"
        assert not any(p == PLACE_IRI for _, p, _ in graph_of(after, B)), "B was written from B"
        assert not any(p == PLACE_IRI for _, p, _ in graph_of(after, A)), "A was written from B"


# -- (a) every operation is inert once the stamp is not from_version ---------------------------------

OTHER_SCHEMA = URIRef("https://example.org/ns/other")
NOT_FROM = {
    "the target": [Literal("2")],
    "an older one": [Literal("0")],
    "empty": [Literal("")],
    "a trailing space": [Literal("1 ")],
    "a leading zero": [Literal("01")],
    "a newline after": [Literal("1" + chr(10))],
    "an integer": [Literal(1)],
    "a string typed literal": [
        Literal("1", datatype=URIRef("http://www.w3.org/2001/XMLSchema#token"))
    ],
    "a language tagged one": [Literal("1", lang="en")],
    "an IRI": [URIRef("1")],
}


async def with_stamps(store: FakeStore, stamps: list) -> None:
    await store.update(
        DATABASE,
        f"DELETE WHERE {{ GRAPH <{STAMPS}> {{ ?s <{v.DATA_SCHEMA_VERSION}> ?o }} }}",
    )
    for stamp in stamps:
        await store.update(
            DATABASE,
            f"INSERT DATA {{ GRAPH <{STAMPS}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> {term(stamp)} }} }}",
        )


@pytest.mark.parametrize("stamps", NOT_FROM.values(), ids=NOT_FROM)
async def test_every_operation_is_inert_when_the_stamp_is_not_the_from_version(store, stamps):
    await with_stamps(store, stamps)
    before = await quads(store)
    await store.update(DATABASE, migration_request(migration(rename(), rename()), STAMPS))
    assert await quads(store) == before


async def test_no_stamp_at_all_leaves_the_data_alone(store):
    await with_stamps(store, [])
    before = await quads(store)
    await store.update(DATABASE, migration_request(migration(rename()), STAMPS))
    assert await quads(store) == before


async def test_the_stamp_of_another_schema_or_another_graph_does_not_arm_the_request(store):
    await with_stamps(store, [])
    await store.update(
        DATABASE,
        f"""INSERT DATA {{
          GRAPH <{STAMPS}> {{ <{OTHER_SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }}
          GRAPH <{A}> {{ <{SCHEMA}> <{v.DATA_SCHEMA_VERSION}> "1" }} }}""",
    )
    before = await quads(store)
    await store.update(DATABASE, migration_request(migration(rename()), STAMPS))
    assert await quads(store) == before


async def test_two_requests_in_a_row_move_the_data_once(store):
    request = migration_request(migration(rename()), STAMPS)
    await store.update(DATABASE, request)
    once = await quads(store)
    await store.update(DATABASE, request)
    assert await quads(store) == once


# -- (b) a step cannot change the stamps graph, a loaded graph, or another database ----------------


async def test_a_step_that_matches_everything_leaves_stamps_and_loaded_graphs_alone(store):
    before = await quads(store)
    everything = step(where_pattern="?s ?p ?o .", delete_pattern="?s ?p ?o .")
    await store.update(DATABASE, migration_request(migration(everything), STAMPS))
    after = await quads(store)
    assert graph_of(after, LOADED) == graph_of(before, LOADED)
    assert graph_of(after, STAMPS) == {(URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal("2"))}
    assert await quads(store, "other") == before, "another database is another dataset"


@pytest.mark.parametrize(
    "guard", [f"<{STAMPS}>", f"<{LOADED}>"], ids=["the stamps graph", "a loaded graph"]
)
async def test_a_where_that_names_a_protected_graph_as_the_graph_variable_changes_nothing_there(
    store, guard
):
    before = await quads(store)
    named = step(
        where_pattern=f"VALUES ?rp_graph {{ {guard} }} ?s ?p ?o .",
        delete_pattern="?s ?p ?o .",
        insert_pattern=f"?s <{PLACE_IRI}> ?o .",
    )
    await store.update(DATABASE, migration_request(migration(named), STAMPS))
    after = await quads(store)
    assert graph_of(after, LOADED) == graph_of(before, LOADED)
    assert graph_of(after, STAMPS) == {(URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal("2"))}


async def test_a_step_can_write_the_graph_variable_to_the_graphs_data_only_there(store):
    using = step(
        where_pattern=f"?rp_graph <{SHELF_IRI}> ?o .",
        delete_pattern=f"?rp_graph <{SHELF_IRI}> ?o .",
        insert_pattern=f"?rp_graph <{PLACE_IRI}> ?o .",
    )
    await store.update(DATABASE, migration_request(migration(using), STAMPS))
    after = await quads(store)
    for graph, value in ((A, "a"), (B, "b"), (C, "c")):
        assert (graph, PLACE_IRI, Literal(value)) in graph_of(after, graph)
        assert not any(p == PLACE_IRI for _, p, _ in graph_of(after, LOADED))


# -- (d) a where that binds ?rp_graph to a constant IRI stays inside that graph ---------------------

CONSTANT_BINDINGS = {
    "bind": f"BIND(<{B}> AS ?rp_graph) ?s <{SHELF_IRI}> ?o .",
    "values": f"VALUES ?rp_graph {{ <{B}> }} ?s <{SHELF_IRI}> ?o .",
    "sub-select": f"{{ SELECT ?rp_graph WHERE {{ VALUES ?rp_graph {{ <{B}> }} }} }} ?s <{SHELF_IRI}> ?o .",
}


@pytest.mark.parametrize("pattern", CONSTANT_BINDINGS.values(), ids=CONSTANT_BINDINGS)
async def test_a_where_that_pins_the_graph_variable_changes_that_graph_only(store, pattern):
    before = await quads(store)
    pinned = step(where_pattern=pattern, delete_pattern=f"?s <{SHELF_IRI}> ?o .")
    await store.update(DATABASE, migration_request(migration(pinned), STAMPS))
    after = await quads(store)
    assert without_tokens(graph_of(after, B)) == set(), "B lost its shelf"
    for untouched in (A, C, LOADED, REGISTRY):
        assert without_tokens(graph_of(after, untouched)) == without_tokens(
            graph_of(before, untouched)
        ), untouched


@pytest.mark.parametrize(
    "construct",
    [
        f"?s <{SHELF_IRI}> ?o MINUS {{ ?s <{PLACE_IRI}> ?o }}",
        f"?s <{SHELF_IRI}>/<{PLACE_IRI}>* ?o",
        f"?s <{SHELF_IRI}> ?o VALUES ?o {{ 'a' 'c' }}",
        f"{{ SELECT ?s ?o WHERE {{ ?s <{SHELF_IRI}> ?o }} }}",
        f"?s <{SHELF_IRI}> ?o FILTER NOT EXISTS {{ ?s <{PLACE_IRI}> ?o }}",
    ],
    ids=["minus", "path", "values", "sub-select", "not-exists"],
)
async def test_the_richer_constructs_a_step_may_use_keep_to_the_graphs_the_template_allows(
    tmp_path, store, construct
):
    before = await quads(store)
    loaded = load(tmp_path, where_pattern=construct, delete_pattern=f"?s <{SHELF_IRI}> ?o .")
    await store.update(DATABASE, migration_request(loaded, STAMPS))
    after = await quads(store)
    assert graph_of(after, LOADED) == graph_of(before, LOADED)
    assert graph_of(after, REGISTRY) == graph_of(before, REGISTRY)
    assert graph_of(after, STAMPS) == {(URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal("2"))}


# -- (c) the token rotation -------------------------------------------------------------------------


def tokens_of(found: set[tuple]) -> dict[URIRef, Literal]:
    return {s: o for g, s, p, o in found if p == v.VERSION and g == s}  # type: ignore[misc]


async def test_each_graph_gets_its_own_new_token_and_a_graph_without_one_gets_none(store):
    for index in range(30):  # many graphs in the one operation
        graph = URIRef(f"https://example.org/t/many/{index}")
        await store.update(
            DATABASE,
            f'INSERT DATA {{ GRAPH <{graph}> {{ <{graph}> <{v.VERSION}> "old-{index}" }} }}',
        )
    before = tokens_of(await quads(store))
    await store.update(DATABASE, migration_request(migration(rename()), STAMPS))
    after = tokens_of(await quads(store))
    assert set(after) == set(before), "no graph gained or lost a token"
    assert C not in after, "a graph with no token stays without"
    assert all(after[g] != before[g] for g in before), "every token changed"
    assert len(set(after.values())) == len(after), "no two graphs share a new token"
    assert all(str(t) for t in after.values())


async def test_a_step_that_matches_nothing_still_rotates_the_tokens_and_moves_the_stamp(store):
    miss = step(where_pattern="?s <urn:absent> ?o .", delete_pattern="?s <urn:absent> ?o .")
    before = await quads(store)
    await store.update(DATABASE, migration_request(migration(miss), STAMPS))
    after = await quads(store)
    assert tokens_of(after)[A] != tokens_of(before)[A]
    assert graph_of(after, STAMPS) == {(URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal("2"))}
    assert without_tokens(graph_of(after, A)) == without_tokens(graph_of(before, A))


async def test_a_graph_holding_a_foreign_subject_with_a_version_keeps_that_triple(store):
    """Only ``<graph> rp:version`` is a token; the same predicate on another subject is data."""
    await store.update(
        DATABASE,
        f'INSERT DATA {{ GRAPH <{A}> {{ <urn:thing> <{v.VERSION}> "mine" }} }}',
    )
    await store.update(DATABASE, migration_request(migration(rename()), STAMPS))
    assert (URIRef("urn:thing"), v.VERSION, Literal("mine")) in graph_of(await quads(store), A)


# -- (e) injection through the file's own fields ----------------------------------------------------

HOSTILE_VERSIONS = {
    "quote and braces": '1" } } ; DROP ALL ; #',
    "closing the literal": '1" . } ; CLEAR ALL ; INSERT DATA { <urn:x> <urn:y> "',
    "backslashes": "a" + BS + BS + "b" + BS,
    "backslash quote": BS + '"',
    "a newline": "1" + chr(10) + "DROP ALL",
    "a carriage return": "1" + chr(13) + chr(10) + "DROP ALL ;",
    "a tab": "1" + chr(9) + "2",
    "unicode": chr(0xE9) + chr(0x4E2D) + chr(0x1F600),
    "a unicode escape text": BS + "u0022 } ; DROP ALL ; #",
    "triple quotes": '"""',
    "single quotes": "'''",
    "an angle bracket": "1>",
    "a comment": "1 # x",
    "a null": "1" + chr(0) + "2",
    "a control": chr(1) + chr(127),
    "a semicolon": "1;2",
    "a long one": "v" * 5000,
}


def hostile(version: str, steps=None) -> Migration:
    return Migration(
        schema_id=SCHEMA, from_version=version, to_version=version + "-next", steps=steps
    )


@pytest.mark.parametrize("version", HOSTILE_VERSIONS.values(), ids=HOSTILE_VERSIONS)
@pytest.mark.parametrize("with_step", [False, True], ids=["no-step", "a-step"])
async def test_a_version_cannot_break_out_of_its_literal(store, version, with_step):
    steps = [rename()] if with_step else None
    request = migration_request(hostile(version, steps), STAMPS)
    assert len(parseUpdate(request).request) == (3 if with_step else 1)
    await with_stamps(store, [Literal(version)])
    before = await quads(store)
    await store.update(DATABASE, request)
    after = await quads(store)
    assert graph_of(after, STAMPS) == {
        (URIRef(SCHEMA), v.DATA_SCHEMA_VERSION, Literal(version + "-next"))
    }, "the stamp is exactly the to_version, as typed"
    assert {g for g, *_ in after} == {g for g, *_ in before}, "no graph was added or dropped"
    for untouched in (LOADED, REGISTRY):
        assert graph_of(after, untouched) == graph_of(before, untouched)


@pytest.mark.parametrize("version", HOSTILE_VERSIONS.values(), ids=HOSTILE_VERSIONS)
def test_a_hostile_version_in_a_file_loads_and_builds_the_expected_operations(tmp_path, version):
    path = write(tmp_path, hostile(version, [rename()]))
    loaded = load_migration(path)
    assert (loaded.from_version, loaded.to_version) == (version, version + "-next")
    assert len(parseUpdate(migration_request(loaded, STAMPS)).request) == 3


# equivalence classes: a character IRIREF forbids (two stand for them), the empty id
@pytest.mark.parametrize("schema_id", ["https://example.org/a>b", "https://example.org/a b", ""])
def test_a_schema_id_that_cannot_be_an_iri_is_refused_by_the_loader_and_the_builder(
    tmp_path, schema_id
):
    broken = Migration(schema_id=schema_id, from_version="1", to_version="2")
    with pytest.raises(SparqlError):
        migration_request(broken, STAMPS)
    path = tmp_path / FILE
    path.write_text(yaml.safe_dump(broken.model_dump(exclude_none=True)), encoding="utf-8")
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(path)


@pytest.mark.parametrize(
    "schema_id",
    ["urn:example:library", "https://example.org/ns/a(b)", "https://example.org/ns/" + chr(0xE9)],
)
def test_a_schema_id_with_odd_but_legal_characters_is_carried_as_one_iri(schema_id):
    request = migration_request(
        Migration(schema_id=schema_id, from_version="1", to_version="2"), STAMPS
    )
    assert f"<{schema_id}>" in request
    assert len(parseUpdate(request).request) == 1


# -- the file itself -------------------------------------------------------------------------------


def raw(tmp_path: Path, text: str | bytes) -> Path:
    path = tmp_path / FILE
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


HEADER = f"schema_id: {SCHEMA}\nfrom_version: '1'\nto_version: '2'\n"


@pytest.mark.parametrize(
    "text",
    [
        HEADER + "---\n" + HEADER,
        HEADER + "...\n---\nfoo: bar\n",
        "",
        "---\n",
        "null\n",
        "[]\n",
        "42\n",
        "a: &x [*x]\n",
        "{" * 5000,
        "[" * 100000,
        HEADER + "steps: " + "[" * 50000,
    ],
    ids=[
        "two-documents",
        "a-second-document",
        "empty",
        "marker-only",
        "null",
        "list",
        "scalar",
        "self-alias",
        "deep-braces",
        "deep-flow",
        "deep-steps",
    ],
)
def test_a_file_that_is_not_one_mapping_is_refused_not_crashed(tmp_path, text):
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(raw(tmp_path, text))


@pytest.mark.parametrize(
    "content",
    [b"\xff\xfe\x00bad", b"schema_id: \xc3\x28\n", chr(0).encode() + b"x: 1"],
    ids=["utf16-noise", "bad-utf8", "nul"],
)
def test_bytes_that_are_not_text_are_refused_naming_the_file(tmp_path, content):
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(raw(tmp_path, content))


def test_a_file_that_starts_with_a_byte_order_mark_loads(tmp_path):
    """Chosen outcome: the YAML reader skips the mark, as editors on some systems write one."""
    loaded = load_migration(raw(tmp_path, chr(0xFEFF) + HEADER))
    assert (loaded.from_version, loaded.to_version) == ("1", "2"), "the fields are read"


@pytest.mark.parametrize(
    "field",
    ["where_pattern: 5", "where_pattern: [a, b]", "where_pattern: {a: b}", "title: [x]"],
)
def test_a_step_field_that_is_not_text_is_refused_naming_the_file(tmp_path, field):
    text = HEADER + "steps:\n  - title: t\n    insert_pattern: '?s ?p ?o'\n    " + field + "\n"
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(raw(tmp_path, text))


# equivalence classes, one per YAML type: float, int (0x10 is the same), bool, null (~ is the same)
@pytest.mark.parametrize("version", ["1.10", "1.0", "010", "true", "null"])
def test_an_unquoted_version_that_yaml_reads_as_another_type_is_refused(tmp_path, version):
    text = f"schema_id: {SCHEMA}\nfrom_version: {version}\nto_version: '9'\n"
    with pytest.raises(InvalidMigration, match="from_version"):
        load_migration(raw(tmp_path, text))


def test_an_unquoted_version_that_yaml_reads_as_text_is_the_text_written(tmp_path):
    text = f"schema_id: {SCHEMA}\nfrom_version: 1e3\nto_version: '9'\n"
    loaded = load_migration(raw(tmp_path, text))
    assert loaded.from_version == "1e3", "the file said one thing, the toolkit read the same"


# equivalence class: a key the format does not know
@pytest.mark.parametrize("extra", ["graph: <urn:x>"])
def test_a_key_the_format_does_not_know_is_refused(tmp_path, extra):
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(raw(tmp_path, HEADER + extra + "\n"))


def test_a_key_given_twice_is_refused_so_a_reviewer_reads_what_runs(tmp_path):
    text = (
        HEADER
        + "steps:\n  - title: one\n    where_pattern: '?s ?p ?o'\n    delete_pattern: '?s ?p ?o'\n"
        + "steps:\n  - title: two\n    where_pattern: '?s ?p ?o'\n    insert_pattern: '?s ?p ?o'\n"
    )
    with pytest.raises(InvalidMigration, match=FILE):
        load_migration(raw(tmp_path, text))


def test_an_anchor_reused_in_two_steps_loads_as_two_checked_steps(tmp_path):
    text = (
        HEADER
        + "steps:\n"
        + f"  - &s\n    title: t\n    where_pattern: '?s {SHELF} ?o'\n    delete_pattern: '?s {SHELF} ?o'\n"
        + "  - *s\n"
    )
    loaded = load_migration(raw(tmp_path, text))
    assert loaded.steps
    assert len(loaded.steps) == 2
    assert len(parseUpdate(migration_request(loaded, STAMPS)).request) == 4


def test_an_alias_cannot_smuggle_a_graph_past_the_check(tmp_path):
    text = (
        HEADER
        + "steps:\n  - title: t\n    where_pattern: &w '?s ?p ?o'\n    delete_pattern: *w\n"
        + "  - title: u\n    where_pattern: '?s ?p ?o'\n    delete_pattern: 'GRAPH <urn:x> { ?s ?p ?o }'\n"
    )
    with pytest.raises(InvalidMigration, match="step 2"):
        load_migration(raw(tmp_path, text))


def test_a_step_too_long_for_the_parser_is_refused_with_its_own_message(tmp_path):
    """PD-21 item 4: rdflib gives up at about a hundred triple patterns; say so, not "does not parse"."""
    triples = " ".join(f"?s <urn:p{i}> ?o{i} ." for i in range(120))
    with pytest.raises(InvalidMigration) as error:
        load(tmp_path, where_pattern=triples, delete_pattern="?s <urn:p0> ?o0 .")
    message = str(error.value)
    assert "too long to check" in message
    assert "split" in message
    assert "does not parse" not in message


@pytest.mark.parametrize("depth", [20, 400, 5000])
def test_deeply_nested_braces_are_loaded_or_refused_never_a_crash(tmp_path, depth):
    nested = "{" * depth + f"?s {SHELF} ?o" + "}" * depth
    try:
        loaded = load(tmp_path, where_pattern=nested, delete_pattern=DELETE)
    except InvalidMigration:
        return  # a refusal is one of the two allowed outcomes
    assert isinstance(loaded, Migration), f"depth {depth}: neither loaded nor refused"


# -- legitimate files that must load -------------------------------------------------------------

LEGIT = {
    "a literal holding GRAPH": ("where_pattern", f'?s {SHELF} ?o FILTER (?o != "GRAPH")'),
    "a literal holding SERVICE": ("where_pattern", f"?s {SHELF} 'SERVICE'"),
    "a long literal holding GRAPH": ("where_pattern", f'?s {SHELF} """GRAPH\n x"""'),
    "a literal with an escaped quote and GRAPH": ("where_pattern", f'?s {SHELF} "a{BS}"GRAPH"'),
    "a literal holding a bracket": ("insert_pattern", f'?s {PLACE} "[x] ( _:b )" .'),
    "a literal holding a prefixed look": ("where_pattern", f'?s {SHELF} "a:b"'),
    "a literal holding a reserved look": ("where_pattern", f'?s {SHELF} "?rp_x $rp_y"'),
    "an IRI holding GRAPH": ("where_pattern", "?s <https://example.org/GRAPH/SERVICE> ?o"),
    "an IRI holding a colon": ("where_pattern", "?s <urn:a:b:c> ?o"),
    "an IRI holding parentheses": ("where_pattern", "?s <urn:a(b)> ?o"),
    "an IRI holding brackets": ("insert_pattern", f"?s {PLACE} <urn:a[1]> ."),
    "an IRI holding a hash": ("where_pattern", "?s <http://x/y#z> ?o"),
    "an IRI holding a question mark": ("where_pattern", "?s <http://x/y?rp_x=1> ?o"),
    "a regex filter": ("where_pattern", f'?s {SHELF} ?o FILTER (regex(?o, "^(a|b)$", "i"))'),
    "numbers": ("where_pattern", f"?s {SHELF} 1.5e3 . ?s {SHELF} -4 . ?s {SHELF} true"),
    "a language tag": ("where_pattern", f'?s {SHELF} "x"@en-GB'),
    "the a keyword": ("where_pattern", "?s a <urn:Book>"),
    "a typed literal": (
        "where_pattern",
        f'?s {SHELF} "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
    ),
    "a typed literal inserted": (
        "insert_pattern",
        f'?s {PLACE} "1"^^<http://www.w3.org/2001/XMLSchema#integer> .',
    ),
    "a variable named graph": ("where_pattern", f"?graph {SHELF} ?service"),
    "a comparison": ("where_pattern", f"?s {SHELF} ?o FILTER (?o < 3 && ?o > 1)"),
    "a hash in a literal": ("where_pattern", f'?s {SHELF} "a#b"'),
    "a hash in an IRI then a comment": ("where_pattern", "?s <http://x/y#z> ?o # GRAPH\n"),
    "a blank node in the where": ("where_pattern", f"?s {SHELF} [ {PLACE} ?o ]"),
    "an empty node in the where": ("where_pattern", f"?s {SHELF} []"),
    "a dollar variable": ("where_pattern", "$s ?p $o"),
}


@pytest.mark.parametrize(("clause", "text"), LEGIT.values(), ids=LEGIT)
def test_a_legitimate_pattern_is_not_refused(tmp_path, clause, text):
    loaded = load(tmp_path, **fields_with(clause, text))
    assert loaded.steps
    assert len(parseUpdate(migration_request(loaded, STAMPS)).request) == 3


# -- PD-21: what the parser understood, escapes, a key twice, a registry graph -----------------------

NESTED_HIDING_PLACES = {
    "a sub-select": f"{{ SELECT ?s WHERE {{ GRAPH {OTHER} {{ ?s ?p ?o }} }} }}",
    "a union": f"{{ ?s {SHELF} ?o }} UNION {{ GRAPH {OTHER} {{ ?s ?p ?o }} }}",
    "an optional": f"?s {SHELF} ?o OPTIONAL {{ SERVICE <http://localhost:1/s> {{ ?s ?p ?o }} }}",
    "a minus": f"?s {SHELF} ?o MINUS {{ GRAPH {OTHER} {{ ?s ?p ?o }} }}",
    "a filter exists": f"?s {SHELF} ?o FILTER EXISTS {{ GRAPH {OTHER} {{ ?s ?p ?o }} }}",
    "a filter not exists": f"?s {SHELF} ?o FILTER NOT EXISTS {{ SERVICE <urn:s> {{ ?s ?p ?o }} }}",
    "a reserved variable in a sub-select": "{ SELECT ?rp_x WHERE { ?s ?p ?rp_x } }",
    "a reserved variable under optional": f"?s {SHELF} ?o OPTIONAL {{ ?s ?p ?rp_old }}",
    "a reserved variable in a path query": f"?s {SHELF}/{PLACE}* ?rp_new",
    "a reserved variable in exists": f"?s {SHELF} ?o FILTER EXISTS {{ ?s ?p ?rp_registry }}",
}


@pytest.mark.parametrize("attack", NESTED_HIDING_PLACES.values(), ids=NESTED_HIDING_PLACES)
def test_the_walk_finds_a_graph_service_or_reserved_variable_in_any_nested_pattern(
    tmp_path, attack
):
    refused(tmp_path, **fields_with("where_pattern", attack))


@pytest.mark.parametrize("clause", CLAUSES)
@pytest.mark.parametrize("text", [f"?s {SHELF} ?o . # {BS}u0047RAPH", f"?s ?p '{BS}u0041'"])
def test_a_codepoint_escape_in_any_pattern_is_refused_outright_even_in_a_literal(
    tmp_path, clause, text
):
    message = refused(tmp_path, **fields_with(clause, text))
    assert clause in message
    assert "codepoint escape" in message


@pytest.mark.parametrize("escape", [BS + "u0041", BS + "U00000041"])
def test_a_codepoint_escape_in_the_schema_id_is_refused_naming_the_field(tmp_path, escape):
    fields = {"schema_id": SCHEMA + escape, "from_version": "1", "to_version": "2"}
    path = tmp_path / FILE
    path.write_text(yaml.safe_dump(fields), encoding="utf-8")
    with pytest.raises(InvalidMigration, match=f"{FILE}.*schema_id has a codepoint escape"):
        load_migration(path)


@pytest.mark.parametrize("field", ["from_version", "to_version"])
@pytest.mark.parametrize("escape", [BS + "u0041", BS + "U00000041"])
def test_a_version_with_codepoint_escape_text_loads_as_typed(tmp_path, field, escape):  # 108
    fields = {"schema_id": SCHEMA, "from_version": "1", "to_version": "2", field: "a" + escape}
    path = tmp_path / FILE
    path.write_text(yaml.safe_dump(fields), encoding="utf-8")
    assert getattr(load_migration(path), field) == "a" + escape


def test_a_key_given_twice_is_refused_naming_the_file_and_the_key(tmp_path):
    with pytest.raises(InvalidMigration, match=rf"{FILE}.*'to_version' twice"):
        load_migration(raw(tmp_path, HEADER + "to_version: '3'\n"))


def test_a_collection_that_is_empty_is_refused_in_a_template(tmp_path):
    message = refused(tmp_path, **fields_with("insert_pattern", f"?s {PLACE} () ."))
    assert "blank node" in message


async def test_a_delete_of_everything_leaves_the_registry_graph_alone(store):
    """PD-21 item 6: a graph holding registry statements is not a step's to change."""
    before = await quads(store)
    everything = step(where_pattern="?s ?p ?o .", delete_pattern="?s ?p ?o .")
    await store.update(DATABASE, migration_request(migration(everything), STAMPS))
    after = await quads(store)
    assert graph_of(after, REGISTRY) == graph_of(before, REGISTRY)
    assert graph_of(after, A) == set(), "an ordinary graph is still the step's"
