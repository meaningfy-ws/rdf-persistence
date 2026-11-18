"""``migrate_dataset``: the pending migrations applied to a parsed dump in memory (schema-migrations PD-15), TC-51 to TC-53.

The dataset holds a stamps graph, a book graph that keeps its ISBN under an old, made-up predicate, and a
registry. Chains are files in ``tmp_path``; the request is the very text the store gets.
"""

from pathlib import Path

import pytest
from rdflib import XSD, Dataset, Literal, URIRef

from rdf_persistence.core.domain.exceptions import InvalidBody, SparqlError
from rdf_persistence.core.domain.generated.rp_core import RegistryKind
from rdf_persistence.iris.domain.layout import stamps_graph_iri
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.services import migration_runner
from rdf_persistence.services.generated.service.rp_service import MigrationStep
from rdf_persistence.services.migration_runner import migrate_dataset
from rdf_persistence.services.migrations import Chain
from tests.toy import SETTINGS
from tests.unit.services.migration_helpers import (
    ISBN,
    LIB,
    MID_ISBN,
    OLD_ISBN,
    RP,
    chain_of,
    migration,
    rename,
)

STAMPS = stamps_graph_iri(SETTINGS.base)
BOOK = URIRef("https://example.org/library/libraries/t/books/b")
LOADED = URIRef("https://example.org/library/libraries/t/loaded/l")
REGISTRY = URIRef("https://example.org/library/libraries/t/registry")
TOKEN = Literal("token-1")
STAMP = URIRef(str(v.DATA_SCHEMA_VERSION))


def stamp(schema: str, version: str) -> tuple[URIRef, URIRef, Literal]:
    return URIRef(schema), STAMP, Literal(version)


def dataset(*stamps: tuple[URIRef, URIRef, Literal], isbn: URIRef = OLD_ISBN) -> Dataset:
    """A dump with the given stamps, a book whose ISBN is under ``isbn``, a loaded graph and its registry."""
    data = Dataset()
    for statement in stamps:
        data.graph(STAMPS).add(statement)
    data.graph(BOOK).add((BOOK, v.VERSION, TOKEN))
    data.graph(BOOK).add((BOOK, isbn, Literal("A3")))
    data.graph(LOADED).add((BOOK, OLD_ISBN, Literal("loaded")))
    data.graph(REGISTRY).add(
        (LOADED, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH])
    )
    data.graph(REGISTRY).add((REGISTRY, OLD_ISBN, Literal("registry")))
    return data


def isbns(data: Dataset, graph: URIRef) -> set[str]:
    return {str(o) for _, p, o in data.graph(graph) if p == ISBN}


def stamped(data: Dataset) -> dict[str, str]:
    return {str(s): str(o) for s, _, o in data.graph(STAMPS)}


@pytest.fixture
def lib_chain(tmp_path: Path) -> Chain:
    """``[1, 2]``: version 2 moves the ISBN from its old predicate to the book's."""
    return chain_of(
        tmp_path / "lib", LIB, migration(LIB, "1", "2", rename(OLD_ISBN, ISBN)), current="2"
    )


@pytest.fixture
def three(tmp_path: Path) -> Chain:
    """``[1, 2, 3]``: the ISBN goes old, then middle, then the book's predicate."""
    steps = (
        migration(LIB, "1", "2", rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", rename(MID_ISBN, ISBN)),
    )
    return chain_of(tmp_path / "three", LIB, *steps, current="3")


@pytest.fixture
def toolkit_chain(tmp_path: Path) -> Chain:
    return chain_of(tmp_path / "rp", RP, current="1")


# -- TC-51: an older dump is migrated in memory ------------------------------------------------------


def test_a_pending_migration_moves_the_data_the_stamp_and_the_tokens(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert isbns(data, BOOK) == {"A3"}, "the ISBN is under the book's predicate"
    assert stamped(data) == {RP: "1", LIB: "2"}, "the consumer's stamp moved, the toolkit's did not"
    tokens = {str(o) for _, _, o in data.graph(BOOK).triples((BOOK, v.VERSION, None))}
    assert len(tokens) == 1, "a migration with steps renews the token"
    assert str(TOKEN) not in tokens, "a migration with steps renews the token"


def test_a_chain_of_two_pending_migrations_applies_both_in_order(three, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, three)], STAMPS)
    assert isbns(data, BOOK) == {"A3"}, "old to middle to the book's predicate"
    assert stamped(data)[LIB] == "3", "the stamp is at the last version"


def test_only_the_migrations_after_the_stamp_are_applied(three, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "2"), isbn=MID_ISBN)
    data.graph(BOOK).add((BOOK, OLD_ISBN, Literal("old")))
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, three)], STAMPS)
    assert isbns(data, BOOK) == {"A3"}, "the second migration ran"
    assert data.graph(BOOK).value(BOOK, OLD_ISBN) == Literal("old"), "the first did not"


def test_a_dump_at_the_running_versions_is_left_as_it_is(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "2"), isbn=ISBN)
    before = set(data.quads())
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert set(data.quads()) == before, "no update was applied: not even the tokens changed"


def test_loaded_graphs_and_registry_graphs_are_left_alone(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert data.graph(LOADED).value(BOOK, OLD_ISBN) == Literal("loaded"), "a loaded graph is kept"
    assert data.graph(REGISTRY).value(REGISTRY, OLD_ISBN) == Literal("registry"), (
        "a registry graph is kept"
    )


# -- TC-52: a dump that cannot be read as a version of the chains is refused ------------------------------


@pytest.mark.parametrize(
    ("statements", "named"),
    [
        ([], ["missing"]),
        ([(RP, "1")], [LIB, "missing"]),
        ([(RP, "1"), (LIB, "9")], ["'9'"]),
        ([(RP, "9"), (LIB, "1")], [RP, "'9'"]),
        ([(RP, "1"), (LIB, "1"), (LIB, "2")], [LIB, "'1'", "'2'"]),
        ([(RP, "1"), (LIB, "1"), ("urn:schema:other", "1")], ["urn:schema:other"]),
    ],
    ids=[
        "no stamps",
        "a stamp missing",
        "a version the chain does not have",
        "a version the toolkit chain does not have",
        "a doubled stamp",
        "a foreign schema",
    ],
)
def test_a_stamps_graph_that_is_not_one_version_per_chain_is_refused(
    lib_chain, toolkit_chain, statements, named
):
    data = dataset(*(stamp(*pair) for pair in statements))
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    for text in named:
        assert text in str(caught.value), f"the reason names {text}"


def test_a_statement_in_the_stamps_graph_that_is_not_a_stamp_is_refused(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    data.graph(STAMPS).add((URIRef(LIB), URIRef("urn:p"), Literal("1")))
    with pytest.raises(InvalidBody, match="not a stamp"):
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)


# -- TC-53: a migration that fails on the dataset ----------------------------------------------------------


def test_a_migration_that_fails_on_the_dataset_is_refused_naming_it(tmp_path, toolkit_chain):
    failing = MigrationStep(
        title="a pattern rdflib cannot run",
        where_pattern=f'?s <{OLD_ISBN}> ?o . FILTER(REGEX(?o, "["))',
        delete_pattern=f"?s <{OLD_ISBN}> ?o .",
        insert_pattern=f"?s <{ISBN}> ?o .",
    )
    chain = chain_of(tmp_path / "bad", LIB, migration(LIB, "1", "2", failing), current="2")
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, chain)], STAMPS)
    assert f"1__2 of {LIB}" in str(caught.value), "the reason names the migration"


# -- PD-25: what a stamp is, how a refusal reads, what escapes ---------------------------------------------


@pytest.mark.parametrize(
    "stamp_literal",
    [Literal("1", lang="en"), Literal("1", datatype=XSD.string), Literal(1)],
    ids=["a language tag", "xsd:string", "another datatype"],
)
def test_a_stamp_that_is_not_a_plain_literal_is_refused(lib_chain, toolkit_chain, stamp_literal):
    """The runner's guard is a plain literal: rdflib reads ``"1"`` and ``"1"^^xsd:string`` as two terms (PD-25.1)."""
    data = dataset(stamp(RP, "1"))
    data.graph(STAMPS).add((URIRef(LIB), STAMP, stamp_literal))
    with pytest.raises(InvalidBody, match="not a stamp"):
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)


def test_a_long_value_from_the_dump_is_cut_in_the_reason(lib_chain, toolkit_chain):
    long = "urn:" + "x" * 500
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    data.graph(STAMPS).add((URIRef(long), URIRef(long), URIRef(long)))
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert "x" * 300 not in str(caught.value), "the subject, predicate and value are cut (PD-25.3)"
    assert "..." in str(caught.value), "and the cut is marked"


NOTHING = "INSERT DATA { GRAPH <urn:g> { <urn:a> <urn:b> <urn:c> } }"
DROP_STAMPS = f"DELETE WHERE {{ GRAPH <{STAMPS}> {{ ?s ?p ?o }} }}"


def test_a_request_that_leaves_the_stamp_where_it_was_is_refused_as_going_backwards(
    lib_chain, toolkit_chain, monkeypatch
):
    """The forward-only rule of the store (PD-23) holds in memory: the stamp read back is not ``to`` or later."""
    monkeypatch.setattr(migration_runner, "migration_request", lambda *_: NOTHING)
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert "went backwards" in str(caught.value), "the reason says the stamp did not move forward"
    assert f"1__2 of {LIB}" in str(caught.value), "the reason names the migration"


def test_a_request_that_removes_the_stamp_is_refused_as_leaving_none(
    lib_chain, toolkit_chain, monkeypatch
):
    monkeypatch.setattr(migration_runner, "migration_request", lambda *_: DROP_STAMPS)
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    with pytest.raises(InvalidBody, match="there is no stamp") as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert "None" not in str(caught.value), "a missing stamp is not the version 'None' (PD-25.8)"


class Failing(Dataset):
    """A dataset whose update fails as the named exception does."""

    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self.error = error

    def update(self, *_, **__) -> None:
        raise self.error


@pytest.mark.parametrize(
    "error", [RecursionError("deep"), MemoryError("full")], ids=["recursion", "memory"]
)
def test_what_is_not_the_requests_fault_escapes_as_it_is(lib_chain, toolkit_chain, error):
    data = Failing(error)
    for statement in (stamp(RP, "1"), stamp(LIB, "1")):
        data.graph(STAMPS).add(statement)
    with pytest.raises(type(error)):
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)


def test_a_defect_in_our_own_request_text_escapes_and_is_not_blamed_on_the_dump(
    lib_chain, toolkit_chain, monkeypatch
):
    def broken(*_):
        raise SparqlError("a template of ours is wrong")

    monkeypatch.setattr(migration_runner, "migration_request", broken)
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    with pytest.raises(SparqlError):
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
