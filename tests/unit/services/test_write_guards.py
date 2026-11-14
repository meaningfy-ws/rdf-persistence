"""WriteGuards: the collection rule on the write path (PD-6, TC-15 to TC-20, TC-22)."""

import pytest

from rdf_persistence import InvalidBody, InvalidIri, NotFound, generated_models
from rdf_persistence.domain.generated.rp_collections import MembershipRule, SlotEquality
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.reference_collections import member_class_iris
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from tests.toy import MODULES, TENANT, TOY_SCHEMA, book_iri, dune, shelf, shelf_iri, toy_mapper

ELSEWHERE = "https://elsewhere.org/b"


def guards() -> WriteGuards:
    view = load_schema(TOY_SCHEMA)
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(view))


def rule(slot: str, value: str) -> MembershipRule:
    return MembershipRule(rule_equalities=[SlotEquality(equals_slot=slot, equals_value=value)])


def a_shelf(n: int = 1, **slots):
    return shelf(shelf_iri(n)).model_copy(update=slots)


async def save(session, *objects) -> None:
    work = UnitOfWork(session, toy_mapper())
    for obj in objects:
        work.add(obj)
    await work.commit()


async def version_of(session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def test_a_collection_of_stored_books_is_saved_and_its_members_are_untouched():  # TC-15
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), dune(book_iri(2)))
        before = [await version_of(session, book_iri(n)) for n in (1, 2)]
        await save(session, a_shelf(had_member=[book_iri(1), book_iri(2)]))
        assert await version_of(session, shelf_iri(1)), "the shelf is stored"
        assert before == [await version_of(session, book_iri(n)) for n in (1, 2)], "books untouched"


BAD_BODY = [
    pytest.param({"had_member": [shelf_iri(2)]}, shelf_iri(2), id="TC-16-another-class"),
    pytest.param({"had_member": [book_iri(99)]}, book_iri(99), id="TC-17-never-stored"),
    pytest.param({"member_class": "Chapter"}, "Chapter", id="TC-19-not-a-served-root"),
    pytest.param({"membership_rule": rule("colour", "red")}, "colour", id="TC-20-unknown-slot"),
    pytest.param({"membership_rule": rule("genre", "haiku")}, "haiku", id="TC-20-bad-value"),
]


@pytest.mark.parametrize(("slots", "named"), BAD_BODY)
async def test_a_collection_that_breaks_a_rule_is_refused_naming_it_and_not_stored(slots, named):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(2))  # a shelf, not a book
        with pytest.raises(InvalidBody, match=named):
            await save(session, a_shelf(**slots))
        with pytest.raises(NotFound):
            await session.get_graph(shelf_iri(1))


async def test_every_member_that_is_not_of_the_class_is_named():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), a_shelf(2))
        with pytest.raises(InvalidBody) as refused:
            await save(session, a_shelf(had_member=[book_iri(1), shelf_iri(2), book_iri(99)]))
        assert shelf_iri(2) in str(refused.value), "the shelf is not a book"
        assert book_iri(99) in str(refused.value), "b99 was never stored"
        assert book_iri(1) not in str(refused.value), "b1 is a member of the class"


async def test_a_member_the_tenant_does_not_mint_is_an_invalid_iri():  # TC-18
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        with pytest.raises(InvalidIri, match=ELSEWHERE):
            await save(session, a_shelf(had_member=[ELSEWHERE]))
        with pytest.raises(NotFound):
            await session.get_graph(shelf_iri(1))


@pytest.mark.parametrize(
    "slots",
    [
        {"membership_rule": rule("genre", "poetry")},
        {"membership_rule": MembershipRule()},
        {"member_class": "Shelf", "had_member": [shelf_iri(2)]},
    ],
    ids=["rule", "empty-rule", "collection-of-collections"],
)
async def test_a_valid_rule_or_collection_of_collections_is_saved(slots):
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, a_shelf(2))
        await save(session, a_shelf(**slots))
        assert await version_of(session, shelf_iri(1)), "the shelf is stored"


async def test_a_session_without_guards_checks_nothing():  # TC-22
    async with fake_session(tenant_iri=TENANT) as session:
        await save(session, a_shelf(2))
        await save(session, a_shelf(had_member=[shelf_iri(2)]))
        assert await version_of(session, shelf_iri(1)), "the shelf of shelves is stored"


async def test_a_replace_of_a_collection_is_guarded_like_an_add():
    async with fake_session(tenant_iri=TENANT, guards=guards()) as session:
        await save(session, dune(book_iri(1)), a_shelf(2))
        await save(session, a_shelf(had_member=[book_iri(1)]))
        kept = await version_of(session, shelf_iri(1))
        work = UnitOfWork(session, toy_mapper())
        stored = await work.get(type(a_shelf()), shelf_iri(1))
        work.add(stored.model_copy(update={"had_member": [shelf_iri(2)]}))
        with pytest.raises(InvalidBody, match=shelf_iri(2)):
            await work.commit()
        assert await version_of(session, shelf_iri(1)) == kept, "the shelf is as it was"


async def test_a_book_through_a_guarded_session_costs_no_extra_query():
    queries = []
    for guarded in (None, guards()):
        store = FakeStore()
        async with fake_session(store, tenant_iri=TENANT, guards=guarded) as session:
            await save(session, dune(book_iri(1)))
        queries.append(len(store.sent("query")))
    assert queries[0] == queries[1], "the same number of queries with and without guards"


async def test_the_guard_leaves_a_non_collection_untouched():
    triples = list(toy_mapper().to_triples(dune(book_iri(1))))
    async with fake_session(tenant_iri=TENANT) as session:
        prepared = await guards().prepare(session, book_iri(1), triples, None)
        assert prepared == triples, "the triples of a book are written as they are"


def test_the_classes_of_a_member_class_are_it_and_its_descendants():  # PD-27: no root subclass in the toy
    view = load_schema(TOY_SCHEMA)
    lib = "https://example.org/ns/library#"
    assert member_class_iris(view, "Shelf") == {f"{lib}Shelf"}, "a class with no subclass"
    assert f"{lib}LibraryAccess" in member_class_iris(view, "TenantAccess"), (
        "a subclass is accepted"
    )
