"""Collaboration.readable_referrers: which referrers of a resource the caller may read (PD-9, matrix 9).

The same rule ``referrers`` applies: a comment is readable when its thread shows it to the caller, any
other referrer when the caller may read it.
"""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence import Action, generated_models
from rdf_persistence.access.services.access import AccessRules, load_role_definitions
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.discussion import dependents
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ban,
    book_iri,
    caller,
    dune,
    graph_of,
    held,
    role,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
S1 = shelf_iri(1)
VIEW = load_schema(TOY_SCHEMA)


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(
        ROLES.read_text() + "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"
    )
    return AccessRules(load_role_definitions(path))


@pytest.fixture
async def session() -> AsyncIterator[Session]:
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    listings = Listings(VIEW)
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=listings,
        guards=WriteGuards(toy_mapper(), generated_models(*MODULES), listings),
        dependents=dependents(VIEW),
    ) as opened:
        yield opened


def collab(rules: AccessRules, session: Session, who: str, grants, bans=None) -> Collaboration:
    return Collaboration(
        session,
        view=VIEW,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(VIEW),
        caller=caller(principal=who),
        access=held(*grants, bans=bans),
    )


@pytest.fixture
def ada(rules, session) -> Collaboration:
    return collab(rules, session, ADA, [role("librarian"), role("reviewer")])


def bob(rules, session, hidden: str | None = None) -> Collaboration:
    bans = [ban(Action.READ, graph_of(hidden), BOB)] if hidden else None
    grants = [role("reader", who=BOB), role("reviewer", who=BOB)]
    return collab(rules, session, BOB, grants, bans)


async def put_book(session: Session, iri: str, **slots: str) -> None:
    book = dune(iri, chapters=1, **slots)
    await session.add_graph(book.id, toy_mapper().to_triples(book))


async def test_the_readable_referrers_are_those_the_caller_may_read(rules, session, ada):
    await put_book(session, B1, shelf=S1)
    await put_book(session, B2, shelf=S1)
    rows = await session.referrer_rows(S1)
    assert await bob(rules, session, hidden=B2).readable_referrers(S1, rows) == {B1}
    assert await ada.readable_referrers(S1, rows) == {B1, B2}, "ada may read both"


async def test_no_rows_have_no_readable_referrers(ada):
    assert await ada.readable_referrers(S1, []) == set()


async def test_a_comment_seen_in_its_thread_is_readable_and_one_not_seen_is_not(
    rules, session, ada
):  # matrix 9
    await put_book(session, B1)
    await put_book(session, B2)
    seen = await ada.comment(B1, "for all", references=[B2])
    unseen = await ada.comment(B1, "for librarians", audience=["librarian"], references=[B2])
    rows = await session.referrer_rows(B2)
    assert await bob(rules, session).readable_referrers(B2, rows) == {seen}
    assert unseen in await ada.readable_referrers(B2, rows), "the audience sees its own"


async def test_a_comment_is_not_readable_by_a_right_to_read_it_as_an_aggregate(
    rules, session, ada
):  # PD-9: judged by its thread, not by may
    await put_book(session, B1)
    await put_book(session, B2)
    c = await ada.comment(B1, "for librarians", audience=["librarian"], references=[B2])
    rows = await session.referrer_rows(B2)
    access = held(role("reader", who=BOB), role("reviewer", who=BOB))
    assert rules.may(caller(principal=BOB), access, c, Action.READ), "bob may read its graph"
    seen_by_bob = await bob(rules, session).readable_referrers(B2, rows)
    assert seen_by_bob == set(), "yet its thread hides it"
