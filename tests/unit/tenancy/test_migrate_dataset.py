"""``migrate_dataset``: the pending migrations applied to a parsed dump in memory (schema-migrations PD-15), TC-51 to TC-53.

The dataset holds a stamps graph, a book graph that keeps its ISBN under an old, made-up predicate, and a
registry. Chains are files in ``tmp_path``; the request is the very text the store gets.
"""

import pytest
from pydantic import ValidationError
from rdflib import RDF, XSD, BNode, Dataset, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from rdf_persistence.access.domain.generated.rp_access import Grant
from rdf_persistence.access.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.access.services.access import _access_mapper
from rdf_persistence.core.domain.exceptions import InvalidBody, SparqlError
from rdf_persistence.core.domain.sparql_parsing import prepare_update
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.migrations.services.generated.rp_migrations_services import (
    GrantRoles,
    Migration,
    MigrationStep,
    RoleRename,
)
from rdf_persistence.migrations.services.migrations import Chain, migration_request
from rdf_persistence.migrations.services.migrations import chain_of as chain_of_schema
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel
from rdf_persistence.tenancy.services.migration_runner import migrate_dataset
from tests.migration_helpers import (
    BOOK,
    ISBN,
    LIB,
    LOADED,
    MID_ISBN,
    OLD_ISBN,
    REGISTRY,
    RP,
    STAMP,
    STAMPS,
    TOKEN,
    chain_of,
    dataset,
    migration,
    stamp,
)
from tests.toy import ADA, BOB, DATABASE, SETTINGS, TENANT


def isbns(data: Dataset, graph: URIRef) -> set[str]:
    return {str(o) for _, p, o in data.graph(graph) if p == ISBN}


def stamped(data: Dataset) -> dict[str, str]:
    return {str(s): str(o) for s, _, o in data.graph(STAMPS)}


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


class Inert(Dataset):
    """A dataset whose update does nothing: the request leaves the stamp where it was."""

    def update(self, *_, **__) -> None:
        return None


class Unstamping(Dataset):
    """A dataset whose update empties the stamps graph: the request leaves no stamp."""

    def update(self, *_, **__) -> None:
        self.graph(STAMPS).remove((None, None, None))


def test_a_request_that_leaves_the_stamp_where_it_was_is_refused_as_going_backwards(
    lib_chain, toolkit_chain
):
    """The forward-only rule of the store (PD-23) holds in memory: the stamp read back is not ``to`` or later."""
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"), kind=Inert)
    with pytest.raises(InvalidBody) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (LIB, lib_chain)], STAMPS)
    assert "went backwards" in str(caught.value), "the reason says the stamp did not move forward"
    assert f"1__2 of {LIB}" in str(caught.value), "the reason names the migration"


def test_a_request_that_removes_the_stamp_is_refused_as_leaving_none(lib_chain, toolkit_chain):
    data = dataset(stamp(RP, "1"), stamp(LIB, "1"), kind=Unstamping)
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


def test_a_defect_in_our_own_request_text_escapes_and_is_not_blamed_on_the_dump(toolkit_chain):
    """A schema id SPARQL cannot carry reaches the request builder, which refuses it as a defect of ours."""
    schema = "https://ex.org/a b"
    step = Migration(schema_id=schema, from_version="1", to_version="2")
    hand_built: Chain = (("1", "2"), (step,))
    data = dataset(stamp(RP, "1"), stamp(schema, "1"))
    with pytest.raises(SparqlError) as caught:
        migrate_dataset(data, [(RP, toolkit_chain), (schema, hand_built)], STAMPS)
    assert "migration_request" in {frame.name for frame in caught.traceback}, "the attack ran it"


# -- collection-has-part TC-2 to TC-6: the toolkit's 2 to 3 restates the members of a collection ----------

RP_NS = "https://meaningfy.ws/ns/rdf-persistence#"
MEMBER_CLASS = URIRef(f"{RP_NS}memberClass")
MEMBERSHIP_RULE = URIRef(f"{RP_NS}membershipRule")
RULE_SLOT = URIRef(f"{RP_NS}equalsSlot")
HAD_MEMBER = URIRef("http://www.w3.org/ns/prov#hadMember")
HAS_PART = URIRef("http://purl.org/dc/terms/hasPart")
SHELF_CLASS = URIRef("https://example.org/ns/library#Shelf")
SHELF = URIRef("https://example.org/library/libraries/t/shelves/s1")
B1 = URIRef("https://example.org/library/libraries/t/books/b1")
B2 = URIRef("https://example.org/library/libraries/t/books/b2")
OTHER = URIRef("https://example.org/library/libraries/t/other/x")


@pytest.fixture
def real_toolkit_chain() -> Chain:
    """The toolkit's own chain, as the service loads it."""
    return chain_of_schema(metamodel(), TOOLKIT_MIGRATIONS)[1]


def a_shelf(subject: URIRef = SHELF, *, member_class: str | None = "Book") -> Graph:
    """The graph of a stored collection as the mapper writes it, without its members."""
    graph = Graph(identifier=subject)
    graph.add((subject, RDF.type, SHELF_CLASS))
    graph.add((subject, v.VERSION, TOKEN))
    if member_class is not None:
        graph.add((subject, MEMBER_CLASS, Literal(member_class)))
    return graph


def at_toolkit_version_two(*graphs: Graph, stamp_version: str = "2") -> Dataset:
    """A dump whose stamps graph holds the toolkit's stamp and whose graphs are ``graphs``."""
    data = Dataset()
    data.graph(STAMPS).add(stamp(RP, stamp_version))
    for graph in graphs:
        target = data.graph(graph.identifier)
        for triple in graph:
            target.add(triple)
    return data


def content(data: Dataset, subject: URIRef) -> Graph:
    """What the graph of ``subject`` holds, the version token left out."""
    kept = Graph()
    for triple in data.graph(subject):
        if triple[1] != v.VERSION:
            kept.add(triple)
    return kept


def members_as(members: list[URIRef], predicate: URIRef, *, subject: URIRef = SHELF) -> Graph:
    expected = Graph()
    expected.add((subject, RDF.type, SHELF_CLASS))
    expected.add((subject, MEMBER_CLASS, Literal("Book")))
    for member in members:
        expected.add((subject, predicate, member))
    return expected


def tokens(data: Dataset, subject: URIRef = SHELF) -> set[str]:
    return {str(o) for o in data.graph(subject).objects(subject, v.VERSION)}


@pytest.mark.parametrize("members", [[B1, B2], [B1]], ids=["two members", "one member"])
def test_the_toolkits_migration_restates_the_members_of_a_collection_with_has_part(
    real_toolkit_chain, members
):
    shelf = a_shelf()
    for member in members:
        shelf.add((SHELF, HAD_MEMBER, member))
    data = at_toolkit_version_two(shelf)
    migrate_dataset(data, [(RP, real_toolkit_chain)], STAMPS)
    assert isomorphic(content(data, SHELF), members_as(members, HAS_PART)), (
        "each member is stated with dcterms:hasPart and none with prov:hadMember"
    )
    assert stamped(data) == {RP: "3"}, "the toolkit's stamp is at 3"
    assert tokens(data), "the shelf still has a token"
    assert tokens(data) != {str(TOKEN)}, "the version token was renewed"


def test_a_graph_that_is_not_a_collection_keeps_its_had_member(real_toolkit_chain):
    other = a_shelf(OTHER, member_class=None)  # no rp:memberClass: not a collection
    other.add((OTHER, HAD_MEMBER, B1))
    data = at_toolkit_version_two(other, a_shelf())
    before = content(data, OTHER)
    migrate_dataset(data, [(RP, real_toolkit_chain)], STAMPS)
    assert isomorphic(content(data, OTHER), before), "the triples are as they were"
    assert (OTHER, HAD_MEMBER, B1) in data.graph(OTHER), "prov:hadMember is still stated"
    assert stamped(data) == {RP: "3"}, "the migration did run on the database"


def test_a_collection_with_a_rule_and_no_member_gets_no_has_part_and_keeps_its_rule(
    real_toolkit_chain,
):
    shelf = a_shelf()
    rule = BNode()
    shelf.add((SHELF, MEMBERSHIP_RULE, rule))
    shelf.add((rule, RULE_SLOT, Literal("genre")))
    data = at_toolkit_version_two(shelf)
    migrate_dataset(data, [(RP, real_toolkit_chain)], STAMPS)
    held = content(data, SHELF)
    assert not list(held.triples((None, HAS_PART, None))), "no member was invented"
    assert isomorphic(held, content(at_toolkit_version_two(shelf), SHELF)), (
        "the rule and its blank node part are as they were"
    )
    assert stamped(data) == {RP: "3"}, "the migration did run"


def test_a_collection_of_collections_is_restated_like_any_other(real_toolkit_chain):
    outer = a_shelf(SHELF, member_class="Shelf")
    inner = URIRef("https://example.org/library/libraries/t/shelves/s2")
    outer.add((SHELF, HAD_MEMBER, inner))
    data = at_toolkit_version_two(outer)
    migrate_dataset(data, [(RP, real_toolkit_chain)], STAMPS)
    held = content(data, SHELF)
    assert (SHELF, HAS_PART, inner) in held, "the inner collection is stated with dcterms:hasPart"
    assert (SHELF, HAD_MEMBER, inner) not in held, "and no longer with prov:hadMember"


def test_a_dump_already_at_version_three_is_left_as_it_is_even_with_a_had_member(
    real_toolkit_chain,
):
    shelf = a_shelf()
    shelf.add((SHELF, HAD_MEMBER, B1))  # planted: a version 3 database should not hold it
    data = at_toolkit_version_two(shelf, stamp_version="3")
    before = set(data.quads())
    migrate_dataset(data, [(RP, real_toolkit_chain)], STAMPS)
    assert set(data.quads()) == before, "the stamp guard: nothing changed, not even the token"


def test_the_consumers_drop_of_had_member_after_the_toolkits_step_keeps_the_members(
    tmp_path, real_toolkit_chain
):
    """The drafted step of a consumer (design PD-5) matches nothing once the toolkit's step has run."""
    drop = MigrationStep(
        title="drop prov:hadMember of the shelf",
        where_pattern=f"?s <{HAD_MEMBER}> ?o .",
        delete_pattern=f"?s <{HAD_MEMBER}> ?o .",
    )
    library = chain_of(tmp_path / "lib", LIB, migration(LIB, "1", "2", drop), current="2")
    shelf = a_shelf()
    shelf.add((SHELF, HAD_MEMBER, B1))
    shelf.add((SHELF, HAD_MEMBER, B2))
    data = at_toolkit_version_two(shelf)
    data.graph(STAMPS).add(stamp(LIB, "1"))
    migrate_dataset(data, [(RP, real_toolkit_chain), (LIB, library)], STAMPS)
    assert isomorphic(content(data, SHELF), members_as([B1, B2], HAS_PART)), (
        "the members survive as dcterms:hasPart: the toolkit's chain ran first"
    )
    assert stamped(data) == {RP: "3", LIB: "2"}, "both chains ran"


# -- grant-roles T1 to T7: a migration renames or drops the roles of the stored grants -----------------------

OTHER_TENANT = "https://example.org/libraries/0b2e44d1"
BOOK_GRAPH = f"{TENANT}/books/b1"  # an aggregate's graph: a grant on it is an aggregate-level grant
RECORD = Iris(SETTINGS).access(TENANT)
OTHER_RECORD = Iris(SETTINGS).access(OTHER_TENANT)
ACCESS_TOKEN = Literal("access-token-1")

# (assignee, target, role): a grant as the tests state it
Held = set[tuple[str, str, str | None]]


def the_record(iri: URIRef, tenant: str, held: Held) -> Graph:
    """The access record of ``tenant`` holding ``held`` as grants, as the mapper writes it, with a version token."""
    record = TenantAccess(
        id=str(iri), label="Library", state=TenantState.ACTIVE, database_name=DATABASE,
        grants=[Grant(assignee=a, target=t, role=r) for a, t, r in sorted(held)],
    )  # fmt: skip
    graph = _access_mapper().to_graph(record)
    graph.add((graph_iri(str(iri)), v.VERSION, ACCESS_TOKEN))
    return graph


def system_database(*records: tuple[URIRef, str, Held]) -> Dataset:
    """A dump stamped ``1`` for the consumer's schema, with one access record graph per ``(iri, tenant, grants)``."""
    data = Dataset()
    data.graph(STAMPS).add(stamp(LIB, "1"))
    for iri, tenant, held in records:
        target = data.graph(graph_iri(str(iri)))
        for triple in the_record(iri, tenant, held):
            target.add(triple)
    return data


def sent(data: Dataset, roles: GrantRoles, *, grants: bool = True) -> None:
    """Apply, to ``data``, the request of a migration of the consumer's schema that only has ``roles``."""
    migration = Migration(schema_id=LIB, from_version="1", to_version="2", grant_roles=roles)
    request = migration_request(migration, STAMPS, grants=grants)
    data.update(prepare_update(request, dict(data.namespaces())))


def renames(*pairs: tuple[str, str], drop: list[str] | None = None) -> GrantRoles:
    return GrantRoles(
        rename=[RoleRename(from_role=a, to_role=b) for a, b in pairs] or None, drop=drop
    )


def decoded(data: Dataset, iri: URIRef = RECORD) -> TenantAccess:
    """The access record as the library reads it: a duplicate grant key makes this raise (RISK-1)."""
    graph = data.graph(graph_iri(str(iri)))
    return _access_mapper().from_graph(TenantAccess, str(iri), graph, graph_iri(str(iri)))


def held_by(data: Dataset, iri: URIRef = RECORD) -> Held:
    return {(g.assignee, g.target, g.role) for g in decoded(data, iri).grants or []}


def parts_of(data: Dataset, iri: URIRef = RECORD) -> set:
    return set(data.graph(graph_iri(str(iri))).objects(iri, v.GRANTS))


def tokens_of(data: Dataset, iri: URIRef = RECORD) -> set[str]:
    graph = graph_iri(str(iri))
    return {str(o) for o in data.graph(graph).objects(graph, v.VERSION)}


def test_t1_a_rename_changes_the_role_of_every_grant_that_names_it_and_nothing_else():
    before: Held = {
        (ADA, TENANT, "librarian"),
        (BOB, TENANT, "reader"),
        (ADA, BOOK_GRAPH, "reader"),
    }
    other: Held = {
        (BOB, OTHER_TENANT, "reader"),
        (BOB, OTHER_TENANT, "reader2"),
        (ADA, OTHER_TENANT, "Reader"),
    }
    data = system_database((RECORD, TENANT, before), (OTHER_RECORD, OTHER_TENANT, other))
    parts = parts_of(data)
    sent(data, renames(("reader", "member")))
    assert held_by(data) == {
        (ADA, TENANT, "librarian"),
        (BOB, TENANT, "member"),
        (ADA, BOOK_GRAPH, "member"),
    }, "the grants that named reader name member; the librarian grant is as it was"
    assert held_by(data, OTHER_RECORD) == {
        (BOB, OTHER_TENANT, "member"),
        (BOB, OTHER_TENANT, "reader2"),
        (ADA, OTHER_TENANT, "Reader"),
    }, "every record is renamed; a role that only looks like the name (case, a suffix) is not"
    assert parts_of(data) == parts, "the grant parts are the same nodes: renamed in place"


def test_t2_a_drop_deletes_the_grants_naming_the_role_with_their_parts_and_keeps_the_others():
    before: Held = {
        (ADA, TENANT, "librarian"),
        (BOB, TENANT, "guest"),
        (ADA, BOOK_GRAPH, "guest"),
        (BOB, BOOK_GRAPH, "reader"),
    }
    data = system_database((RECORD, TENANT, before))
    parts = parts_of(data)
    guests = {
        part
        for part in parts
        if (part, v.ROLE, Literal("guest")) in data.graph(graph_iri(str(RECORD)))
    }
    assert len(guests) == 2, "the setup has two grant parts naming guest"
    sent(data, renames(drop=["guest"]))
    assert held_by(data) == {(ADA, TENANT, "librarian"), (BOB, BOOK_GRAPH, "reader")}, (
        "only the guest grants went"
    )
    assert parts_of(data) == parts - guests, "the others keep their parts"
    graph = data.graph(graph_iri(str(RECORD)))
    for part in guests:
        assert not list(graph.triples((part, None, None))), "a dropped part leaves no triple"


@pytest.mark.parametrize(
    ("pairs", "before", "after"),
    [
        (
            [("reader", "member")],
            {(BOB, TENANT, "reader"), (BOB, TENANT, "member")},
            {(BOB, TENANT, "member")},
        ),
        (
            [("reader", "member")],
            {(BOB, TENANT, "reader"), (ADA, TENANT, "member")},
            {(BOB, TENANT, "member"), (ADA, TENANT, "member")},
        ),
        (
            [("reader", "member")],
            {(BOB, TENANT, "reader"), (BOB, BOOK_GRAPH, "member")},
            {(BOB, TENANT, "member"), (BOB, BOOK_GRAPH, "member")},
        ),
    ],
    ids=["the same assignee and target", "another assignee", "another target"],
)
def test_t3_a_rename_onto_a_grant_that_exists_leaves_one_and_only_for_the_same_assignee_and_target(
    pairs, before, after
):
    data = system_database((RECORD, TENANT, before))
    sent(data, renames(*pairs))
    assert held_by(data) == after, (
        "the record decodes (no duplicate key) and holds one grant where there was a pair"
    )


def test_t3b_a_merge_leaves_one_grant_and_the_record_decodes():
    before: Held = {(BOB, TENANT, "reader"), (BOB, TENANT, "viewer"), (ADA, TENANT, "viewer")}
    data = system_database((RECORD, TENANT, before))
    sent(data, renames(("reader", "member"), ("viewer", "member")))
    assert held_by(data) == {(BOB, TENANT, "member"), (ADA, TENANT, "member")}, (
        "one member grant per assignee and target"
    )


def test_t3b_the_operations_in_another_order_would_leave_a_duplicate():
    """The negative control of T3b: the order of ``_operations`` is what the merge relies on (D-4)."""
    data = system_database((RECORD, TENANT, {(BOB, TENANT, "reader"), (BOB, TENANT, "viewer")}))
    migration = Migration(
        schema_id=LIB,
        from_version="1",
        to_version="2",
        grant_roles=renames(("reader", "member"), ("viewer", "member")),
    )
    first_dedup, first_rename, second_dedup, second_rename, *rest = migration_request(
        migration, STAMPS, grants=True
    ).split(";\n")
    reordered = ";\n".join([first_dedup, second_dedup, first_rename, second_rename, *rest])
    data.update(prepare_update(reordered, dict(data.namespaces())))
    with pytest.raises((ValidationError, ValueError)):
        decoded(data)


def test_t3c_a_rename_applies_to_grants_at_every_level():
    before: Held = {(BOB, TENANT, "reader"), (BOB, BOOK_GRAPH, "reader")}
    data = system_database((RECORD, TENANT, before))
    sent(data, renames(("reader", "member")))
    assert held_by(data) == {(BOB, TENANT, "member"), (BOB, BOOK_GRAPH, "member")}, (
        "the tenant-level and the aggregate-level grant are both renamed"
    )


def test_t4_the_same_migration_sent_twice_changes_nothing_the_second_time():
    data = system_database((RECORD, TENANT, {(BOB, TENANT, "reader"), (BOB, TENANT, "guest")}))
    roles = renames(("reader", "member"), drop=["guest"])
    sent(data, roles)
    once = set(data.quads())
    assert stamped(data) == {LIB: "2"}, "the stamp moved"
    sent(data, roles)
    assert set(data.quads()) == once, "the stamp guard matches nothing the second time"


def test_t5_a_migration_that_is_not_for_the_system_database_has_no_effect_on_grants(
    tmp_path, toolkit_chain
):
    """``migrate_dataset`` and a tenant database pass no flag: only the stamp moves (E6)."""
    data = system_database((RECORD, TENANT, {(BOB, TENANT, "reader"), (BOB, TENANT, "guest")}))
    data.graph(STAMPS).add(stamp(RP, "1"))
    migration_with_roles = Migration(
        schema_id=LIB,
        from_version="1",
        to_version="2",
        grant_roles=renames(("reader", "member"), drop=["guest"]),
    )
    chain = chain_of(tmp_path / "grants", LIB, migration_with_roles, current="2")
    before = held_by(data)
    migrate_dataset(data, [(RP, toolkit_chain), (LIB, chain)], STAMPS)
    assert held_by(data) == before, "no grant changed"
    assert stamped(data) == {RP: "1", LIB: "2"}, "the stamp moved"


def test_t7_a_grant_only_migration_changes_the_version_token_of_the_access_record():
    data = system_database(
        (RECORD, TENANT, {(BOB, TENANT, "reader")}),
        (OTHER_RECORD, OTHER_TENANT, {(BOB, OTHER_TENANT, "reader")}),
    )
    sent(data, renames(("reader", "member")))
    for iri in (RECORD, OTHER_RECORD):
        assert len(tokens_of(data, iri)) == 1, "the record has one token"
        assert tokens_of(data, iri) != {str(ACCESS_TOKEN)}, "and it is a new one"


def test_a_migration_with_no_matching_grant_still_moves_the_stamp_and_leaves_the_grants():
    data = system_database((RECORD, TENANT, {(BOB, TENANT, "librarian")}))
    sent(data, renames(("reader", "member"), drop=["guest"]))
    assert held_by(data) == {(BOB, TENANT, "librarian")}, "nothing to rename or drop"
    assert stamped(data) == {LIB: "2"}, "the stamp moved"
