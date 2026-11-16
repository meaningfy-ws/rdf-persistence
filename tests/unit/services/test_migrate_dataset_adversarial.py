"""Adversarial tests of ``migrate_dataset``: a client's dump is the input (schema-migrations PD-15, PD-5, PD-23)."""
# ruff: noqa: F811  (fixtures imported from the tests they extend are named again as test arguments)

import pytest
from rdflib import XSD, Dataset, Literal, URIRef

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.service.rp_service import MigrationStep
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migration_runner import migrate_dataset
from rdf_persistence.services.migrations import Chain
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
from tests.unit.services.test_migrate_dataset import (  # noqa: F401  (fixtures)
    BOOK,
    LOADED,
    REGISTRY,
    STAMP,
    STAMPS,
    dataset,
    lib_chain,
    stamp,
    three,
    toolkit_chain,
)

MARK = URIRef("https://example.org/ns/library#marked")


def chains_of(toolkit: Chain, library: Chain):
    return [(RP, toolkit), (LIB, library)]


# -- the three filters hold in memory as they do in the store (PD-5) --------------------------------------


def test_a_step_that_matches_every_triple_marks_only_the_data_graphs(
    lib_chain, tmp_path, toolkit_chain
):
    every = MigrationStep(
        title="mark everything",
        where_pattern="?s ?p ?o .",
        insert_pattern=f"?s <{MARK}> ?o .",
    )
    chain = chain_of(tmp_path / "all", LIB, migration(LIB, "1", "2", every), current="2")
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    migrate_dataset(data, chains_of(toolkit_chain, chain), STAMPS)
    assert any(data.graph(BOOK).triples((None, MARK, None))), "the data graph was matched"
    assert not list(data.graph(STAMPS).triples((None, MARK, None))), (
        "the stamps graph is not matched"
    )
    assert not list(data.graph(LOADED).triples((None, MARK, None))), "a loaded graph is not matched"
    assert not list(data.graph(REGISTRY).triples((None, MARK, None))), (
        "a registry graph is not matched"
    )
    assert len(data.graph(STAMPS)) == 2, "the stamps graph holds its two stamps and nothing else"


def test_a_data_graph_that_looks_like_a_registry_is_left_alone_as_the_store_leaves_it(
    tmp_path, toolkit_chain
):
    """A graph holding any rp:registryKind statement is a registry graph, whatever else it holds (PD-21 item 6)."""
    chain = chain_of(
        tmp_path / "lib", LIB, migration(LIB, "1", "2", rename(OLD_ISBN, ISBN)), current="2"
    )
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    pretender = URIRef("https://example.org/library/libraries/t/books/pretender")
    data.graph(pretender).add((pretender, v.REGISTRY_KIND, Literal("anything")))
    data.graph(pretender).add((pretender, OLD_ISBN, Literal("kept")))
    migrate_dataset(data, chains_of(toolkit_chain, chain), STAMPS)
    assert data.graph(pretender).value(pretender, OLD_ISBN) == Literal("kept"), (
        "treated as a registry"
    )


# -- the stamp is authoritative and is a plain literal -----------------------------------------------------


@pytest.mark.parametrize(
    "held",
    [
        Literal("1", datatype=XSD.integer),
        Literal("1", lang="en"),
        URIRef("1"),
    ],
    ids=["a typed literal", "a language-tagged literal", "an IRI"],
)
def test_a_stamp_that_is_not_a_plain_literal_at_a_pending_version_is_refused(
    lib_chain, toolkit_chain, held
):
    data = dataset(stamp(RP, "1"), (URIRef(LIB), STAMP, held))
    with pytest.raises(InvalidBody):
        migrate_dataset(data, chains_of(toolkit_chain, lib_chain), STAMPS)


@pytest.mark.parametrize(
    "held",
    [Literal("2", datatype=XSD.integer), Literal("2", lang="en")],
    ids=["a typed literal", "a language-tagged literal"],
)
def test_a_stamp_at_the_last_version_that_the_next_migration_could_never_match_is_refused(
    lib_chain, toolkit_chain, held
):
    """The restored tenant would be stamped with a value no later ``DELETE {stamp \"2\"}`` matches: set aside at the next upgrade."""
    data = dataset(stamp(RP, "1"), (URIRef(LIB), STAMP, held), isbn=ISBN)
    with pytest.raises(InvalidBody):
        migrate_dataset(data, chains_of(toolkit_chain, lib_chain), STAMPS)


# equivalence class: a stamp that is not the exact text of a version of the chain; the empty one
# and a padded " 1" (which only an exact-text comparison tells from "1") stand for it
@pytest.mark.parametrize("version", ["", " 1"])
def test_a_version_that_only_looks_like_one_of_the_chain_is_refused(
    lib_chain, toolkit_chain, version
):
    data = dataset(stamp(RP, "1"), stamp(LIB, version))
    with pytest.raises(InvalidBody):
        migrate_dataset(data, chains_of(toolkit_chain, lib_chain), STAMPS)


def test_a_blank_node_or_a_tenant_as_the_subject_of_a_stamp_is_refused(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    data.graph(STAMPS).add((URIRef(str(BOOK)), STAMP, Literal("1")))
    with pytest.raises(InvalidBody, match="does not run"):
        migrate_dataset(data, chains_of(toolkit_chain, lib_chain), STAMPS)


def test_a_stamp_the_toolkit_chain_has_not_reached_is_refused_before_the_library_chain_runs(
    lib_chain, toolkit_chain
):
    data = dataset(stamp(RP, "2"), stamp(LIB, "1"))
    before = set(data.quads())
    with pytest.raises(InvalidBody):
        migrate_dataset(data, chains_of(toolkit_chain, lib_chain), STAMPS)
    assert set(data.quads()) == before, "nothing was migrated before the refusal"


def test_the_same_dataset_migrated_twice_is_migrated_once(three, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    migrate_dataset(data, chains_of(toolkit_chain, three), STAMPS)
    once = set(data.quads())
    migrate_dataset(data, chains_of(toolkit_chain, three), STAMPS)
    assert set(data.quads()) == once, "at the last version a second run applies no update"


# -- a middle failure of a chain ----------------------------------------------------------------------------


def test_a_second_migration_that_fails_is_refused_naming_it_not_the_first(tmp_path, toolkit_chain):
    failing = MigrationStep(
        title="a pattern rdflib cannot run",
        where_pattern=f'?s <{MID_ISBN}> ?o . FILTER(REGEX(?o, "["))',
        delete_pattern=f"?s <{MID_ISBN}> ?o .",
        insert_pattern=f"?s <{ISBN}> ?o .",
    )
    steps = (
        migration(LIB, "1", "2", rename(OLD_ISBN, MID_ISBN)),
        migration(LIB, "2", "3", failing),
    )
    chain = chain_of(tmp_path / "two", LIB, *steps, current="3")
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, chains_of(toolkit_chain, chain), STAMPS)
    assert f"2__3 of {LIB}" in str(caught.value), "the reason names the migration that failed"


# -- resource: the in-memory migration stays near linear in the graphs -----------------------------------------


def many_graphs(count: int) -> Dataset:
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"))
    for i in range(count):
        graph = URIRef(f"https://example.org/library/libraries/t/books/b{i}")
        data.graph(graph).add((graph, v.VERSION, Literal(f"token-{i}")))
        for j in range(3):
            data.graph(graph).add((graph, OLD_ISBN, Literal(f"isbn-{j}")))
    return data


def full_scans_to_migrate(count: int, chains: list[tuple[str, Chain]], monkeypatch) -> int:
    """How many times the migration walks every named graph of the dataset (``Dataset.contexts``)."""
    scans = []
    walk_all_graphs = Dataset.contexts

    def counted(self, *args, **kwargs):
        scans.append(1)
        return walk_all_graphs(self, *args, **kwargs)

    data = many_graphs(count)
    with monkeypatch.context() as patch:
        patch.setattr(Dataset, "contexts", counted)
        migrate_dataset(data, chains, STAMPS)
    return len(scans)


def test_a_plain_rename_walks_the_graphs_a_number_of_times_that_does_not_grow_with_them(
    lib_chain, toolkit_chain, monkeypatch
):
    """PD-26: the loaded-graph exclusion walked every graph once per solution row (3N+6 walks), so a client's
    dump of a few thousand aggregates held the process for hours. A count, not a time: the machine's load
    does not change it."""
    chains = chains_of(toolkit_chain, lib_chain)
    small = full_scans_to_migrate(20, chains, monkeypatch)
    large = full_scans_to_migrate(80, chains, monkeypatch)
    assert large == small, f"20 graphs took {small} full walks, 80 graphs took {large}"
