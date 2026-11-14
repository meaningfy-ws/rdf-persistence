"""Collaboration.comment and .thread: remarks on an aggregate, who sees them, what a delete takes (PD-12 to PD-15, #81).

The toy library has the roles ``librarian`` and ``reader``; this file adds ``reviewer`` (read and
annotate). Ada is a librarian and a reviewer, bob a reader and a reviewer, unless a test says otherwise.
"Another writer" is a second session on the same fake store, made to act at a stated moment by
wrapping one operation of the store (``before``).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import Action, generated_models
from rdf_persistence.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidBody,
    InvalidIri,
    NotFound,
    UnknownRole,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_discussion import Comment, Motivation
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.discussion import dependents
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Book
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
    direct,
    dune,
    graph_of,
    held,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)

B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
S1 = shelf_iri(1)
VIEW = load_schema(TOY_SCHEMA)
T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)
ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(
        ROLES.read_text() + "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"
    )
    return AccessRules(load_role_definitions(path))


@pytest.fixture
def now() -> dict[str, datetime]:
    """The time the session's clock tells; a test moves it."""
    return {"t": T0}


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store: FakeStore, now: dict[str, datetime]) -> AsyncIterator[Session]:
    """A session the way the kit opens one: write guards, and a remove that drops the comments."""
    listings = Listings(VIEW)
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        clock=lambda: now["t"],
        listings=listings,
        guards=WriteGuards(toy_mapper(), generated_models(*MODULES), listings),
        dependents=dependents(VIEW),
    ) as opened:
        yield opened


def collab(rules: AccessRules, session: Session, who: str, **access) -> Collaboration:
    return Collaboration(
        session,
        view=VIEW,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(VIEW),
        caller=caller(principal=who),
        access=held(*access.get("grants", ()), bans=access.get("bans")),
    )


@pytest.fixture
def ada(rules, session) -> Collaboration:
    return collab(rules, session, ADA, grants=[role("librarian"), role("reviewer")])


@pytest.fixture
def bob(rules, session) -> Collaboration:
    return collab(rules, session, BOB, grants=[role("reader", who=BOB), role("reviewer", who=BOB)])


async def put(session: Session, model: Book) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


@pytest.fixture
async def books(session: Session) -> None:
    for iri in (B1, B2, B3):
        await put(session, dune(iri, chapters=1))


async def version(session: Session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def comments_on(session: Session, iri: str) -> list[str]:
    return sorted(await session.graphs_with(v.HAS_TARGET, URIRef(iri)))


async def has_entry(store: FakeStore, iri: str) -> bool:
    text = fill(
        ENTRY, registry=term(DEFAULT_IRIS.registry(TENANT)), graph=term(URIRef(graph_of(iri)))
    )
    return bool((await store.query(FAKE_DATABASE, text)).askAnswer)


def before(store: FakeStore, operation: str, action, when: str = "") -> None:
    """Await ``action()`` once, just before the next call of ``operation`` whose text holds ``when``."""
    original = getattr(store, operation)
    done = False

    async def wrapped(dataset, text):
        nonlocal done
        if not done and when in text:
            done = True
            await action()
        return await original(dataset, text)

    setattr(store, operation, wrapped)


async def test_a_reviewer_comments_but_may_not_modify(rules, session, books):  # TC-49
    who = collab(rules, session, BOB, grants=[role("reviewer", who=BOB)])
    stored = await who.comment(B1, "see chapter 3")
    assert stored in await comments_on(session, B1), "the comment is stored"
    with pytest.raises(Forbidden):
        rules.require(caller(principal=BOB), held(role("reviewer", who=BOB)), B1, Action.MODIFY)


async def test_a_comment_leaves_the_target_untouched_and_is_tracked(
    session, ada, books, now
):  # TC-50
    before_version = await version(session, B1)
    now["t"] = T0 + timedelta(minutes=5)
    c = await ada.comment(B1, "nice", references=[B2])
    assert await version(session, B1) == before_version, "b1 is not written"
    [stored] = await ada.thread(B1)
    assert stored.id == c, "the thread holds the comment that was posted"
    assert stored.body_value == "nice", "with its text"
    assert stored.has_target == B1, "on the aggregate it was posted on"
    assert stored.motivated_by == Motivation.COMMENTING, "a first comment is a comment, not a reply"
    assert stored.comment_references == [B2], "with its references"
    assert stored.creator == ADA, "the session's principal is the author"
    assert stored.created == now["t"], "and the session's clock the time"


async def test_a_reader_may_not_comment_and_nothing_is_stored(rules, session, books):  # TC-51
    reader = collab(rules, session, BOB, grants=[role("reader", who=BOB)])
    with pytest.raises(Forbidden):
        await reader.comment(B1, "hello")
    assert await comments_on(session, B1) == [], "no comment graph was written"


async def test_a_comment_with_an_audience_is_seen_by_those_in_it_only(ada, bob, books):  # TC-52
    c = await ada.comment(B1, "for librarians", audience=["librarian"])
    assert await bob.thread(B1) == [], "a reader is not in the audience"
    assert [x.id for x in await ada.thread(B1)] == [c], "a librarian is"


async def test_a_reply_names_its_parent_and_is_a_reply(ada, bob, books, now):  # TC-53
    c2 = await bob.comment(B1, "nice")
    now["t"] += timedelta(minutes=1)
    c3 = await ada.comment(B1, "thanks", reply_to=c2)
    parent, reply = await bob.thread(B1)
    assert parent.id == c2, "the older comment comes first"
    assert reply.id == c3, "its reply after it"
    assert reply.replies_to == c2, "the reply names its parent"
    assert reply.motivated_by == Motivation.REPLYING, "and says it replies"
    assert reply.has_target == B1, "a reply targets the aggregate, not the comment"
    assert parent.replies_to is None, "the parent names none"


async def test_a_reply_under_a_hidden_parent_is_hidden_too(ada, bob, books, now):  # TC-54
    hidden = await ada.comment(B1, "librarians only", audience=["librarian"])
    now["t"] += timedelta(minutes=1)
    open_reply = await ada.comment(B1, "and a reply", reply_to=hidden)
    assert await bob.thread(B1) == [], "the reply is hidden with its parent, audience or not"
    assert [c.id for c in await ada.thread(B1)] == [hidden, open_reply], "a librarian sees both"


@pytest.mark.parametrize("reply_to", ["another aggregate", "missing", "hidden"])
async def test_a_reply_to_a_comment_not_in_the_thread_is_not_found(
    reply_to, ada, bob, books
):  # TC-55
    elsewhere = await ada.comment(B2, "on b2")
    hidden = await ada.comment(B1, "librarians only", audience=["librarian"])
    target = {
        "another aggregate": elsewhere,
        "missing": f"{TENANT}/rp-comments/{UUID(int=99)}",
        "hidden": hidden,
    }[reply_to]
    with pytest.raises(NotFound):
        await bob.comment(B1, "reply", reply_to=target)


@pytest.mark.parametrize(
    ("what", "error"),
    [
        ({"text": "  \n"}, InvalidBody),
        ({"audience": ["nobody"]}, UnknownRole),
        ({"references": ["https://elsewhere.org/x"]}, InvalidIri),
    ],
    ids=["blank text", "undefined audience role", "reference outside the tenant"],
)
async def test_a_comment_that_is_not_valid_is_refused_and_nothing_is_stored(
    what, error, session, ada, books
):  # TC-56
    with pytest.raises(error):
        await ada.comment(B1, **{"text": "fine", **what})
    assert await comments_on(session, B1) == [], "nothing was stored"


async def test_there_is_no_comment_on_a_comment_or_on_the_tenant(ada, books):  # TC-57
    c2 = await ada.comment(B1, "a comment")
    for target in (c2, TENANT):
        with pytest.raises(InvalidIri):
            await ada.comment(target, "no")


async def test_a_reference_is_checked_for_its_shape_and_not_for_existence(ada, books):
    """Pinned (PD-30 item 10): an IRI the policy mints, of an aggregate never stored, is accepted and kept."""
    never_stored = book_iri(99)
    await ada.comment(B1, "see a book not written yet", references=[never_stored])
    [found] = await ada.thread(B1)
    assert found.comment_references == [never_stored], "the reference is stored as given"


async def test_removing_a_comment_keeps_its_replies_stored_and_hidden(session, ada, books):
    """Pinned (PD-30 item 10): a remove through a session takes the comments on its target, not the replies."""
    parent = await ada.comment(B1, "the parent")
    reply = await ada.comment(B1, "the reply", reply_to=parent)
    await session.remove(parent, await version(session, parent))
    assert [str(h.head_iri) for h in await session.heads([reply])] == [reply], "the reply is stored"
    assert await ada.thread(B1) == [], "but its parent is gone, so no thread shows it"


async def test_an_annotation_the_application_wrote_takes_a_comment_but_a_comment_does_not(
    session, ada, books
):
    """PD-30 item 7: only what decodes as a toolkit comment refuses one; stage 4 adds the records."""
    theirs = (
        f"{TENANT}/rp-comments/{UUID(int=7)}"  # typed oa:Annotation, with no text and no motivation
    )
    await session.add_graph(theirs, [(URIRef(theirs), RDF.type, v.ANNOTATION)])
    c = await ada.comment(theirs, "a remark on an annotation")
    assert [x.id for x in await ada.thread(theirs)] == [c], (
        "the application's annotation has a thread"
    )
    with pytest.raises(InvalidIri, match="comment"):
        await ada.comment(c, "a remark on a comment")


async def test_a_comment_on_a_missing_aggregate_is_not_found(ada, books):
    with pytest.raises(NotFound):
        await ada.comment(book_iri(9), "no one there")


async def test_a_comment_that_references_an_aggregate_is_one_of_its_referrers(ada, books):  # TC-58
    c = await ada.comment(B1, "see b2", references=[B2])
    [found] = (await ada.referrers(B2)).referrers or []
    assert found.referrer == c, "the referrer is the comment"
    assert found.referrer_class == "Comment", "of the class Comment"
    assert found.referrer_slot == "comment_references", "by the slot of its references"


async def test_a_comment_outside_the_audience_is_counted_and_not_named(ada, bob, books):  # TC-59
    await ada.comment(B1, "see b2", audience=["librarian"], references=[B2])
    found = await bob.referrers(B2)
    assert found.referrers is None, "a reader is not in the audience, so nothing is named"
    assert found.hidden_count == 1, "but the comment is counted"


async def test_a_comment_on_an_aggregate_the_caller_may_not_read_is_counted_and_not_named(
    rules, session, ada, books
):  # TC-59a
    c = await ada.comment(B2, "see b1", references=[B1])
    bob = collab(
        rules,
        session,
        BOB,
        grants=[role("reader", who=BOB)],
        bans=[ban(Action.READ, graph_of(B2), BOB)],
    )
    found = await bob.referrers(B1)
    assert found.referrers is None, f"{c} is not listed"
    assert found.hidden_count == 1, "but it is counted"


async def test_the_replies_to_a_hidden_comment_are_counted_and_not_named(ada, bob, books):
    """PD-30 item 2: a reply refers to its parent by ``replies_to``, and is judged as a comment too."""
    hidden = await ada.comment(B1, "for librarians", audience=["librarian"])
    await ada.comment(B1, "a reply with no audience of its own", reply_to=hidden)
    found = await bob.referrers(hidden)
    assert found.referrers is None, "the reply is under a parent that bob does not see"
    assert found.hidden_count == 1, "and it is counted"


async def test_a_comment_the_caller_sees_in_the_thread_is_listed_without_the_right_to_read_it(
    rules, session, ada, books
):
    """PD-30 item 2: the thread's rule alone decides for a comment, not the read right on its own IRI."""
    c = await ada.comment(B1, "see b2", references=[B2])
    limited = collab(
        rules,
        session,
        BOB,
        grants=[direct(Action.READ, graph_of(B1), BOB), direct(Action.READ, graph_of(B2), BOB)],
    )
    assert [x.id for x in await limited.thread(B1)] == [c], "the caller sees c in b1's thread"
    assert not rules.may(
        caller(principal=BOB), held(direct(Action.READ, graph_of(B1), BOB)), c, Action.READ
    ), "yet it holds no right on the comment's own IRI"
    found = await limited.referrers(B2)
    assert [r.referrer for r in found.referrers or []] == [c], "so c is a listed referrer of b2"
    assert found.hidden_count == 0, "and not a hidden one"


async def test_a_comment_removed_between_the_rows_and_the_comments_breaks_no_read(
    store, session, ada, books
):
    gone = await ada.comment(B1, "see b2", references=[B2])
    kept = await ada.comment(B3, "see b2 too", references=[B2])

    async def remove() -> None:
        await session.remove(gone, await version(session, gone))

    before(store, "query", remove, when="SELECT DISTINCT ?root")  # the read of the comments
    found = await ada.referrers(B2)
    assert kept in [r.referrer for r in found.referrers or []], "the comment that stayed is listed"


async def test_the_comments_on_an_aggregate_are_not_its_referrers(session, ada, books):  # TC-60
    await ada.comment(B1, "one")
    await ada.comment(B1, "two", references=[B3])
    await put(session, dune(book_iri(4), chapters=1).model_copy(update={"sequel_of": B1}))
    found = await ada.referrers(B1)
    assert [r.referrer for r in found.referrers or []] == [book_iri(4)], "only the sequel"
    assert found.hidden_count == 0, "and no comment is a hidden referrer"


async def test_removing_an_aggregate_removes_the_comments_on_it_and_keeps_the_others(
    store, session, ada, books
):  # TC-61
    on_b1 = await ada.comment(B1, "see b2", references=[B2])
    on_b2 = await ada.comment(B2, "about b2")
    await session.remove(B2, await version(session, B2))
    assert await session.heads([on_b2]) == [], "the comment on b2 is gone"
    assert not await has_entry(store, on_b2), "with its registry entry"
    assert [h.head_iri for h in await session.heads([on_b1])] == [on_b1], "the other stays"


async def test_a_cascade_removes_the_comments_on_its_members(session, ada, books):  # D-7 item 4
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    on_member = await ada.comment(B1, "on a member")
    on_other = await ada.comment(B2, "on a book that stays")
    await ada.delete_cascade(S1, await version(session, S1))
    assert await session.heads([on_member]) == [], "the member's comment went with it"
    kept = [h.head_iri for h in await session.heads([on_other])]
    assert kept == [on_other], "the comment on the book that stays is untouched"


async def test_a_reference_to_a_removed_aggregate_stays(session, ada, books):
    c = await ada.comment(B1, "see b2", references=[B2])
    await session.remove(B2, await version(session, B2))
    assert [x.id for x in await ada.thread(B1)] == [c], "the comment keeps its dangling reference"


async def test_a_comment_races_the_removal_of_its_target_and_loses(
    store, session, ada, books
):  # TC-62
    async def gone() -> None:
        async with fake_session(store, tenant_iri=TENANT) as other:
            await other.remove(B1, await version(other, B1))

    before(store, "update", gone)
    with pytest.raises(Conflict) as refused:
        await ada.comment(B1, "too late")
    assert refused.value.iris == (B1,), "the removed target is named"
    assert await comments_on(session, B1) == [], "the comment was not stored"


@pytest.mark.slow  # 600 commits on the fake store
async def test_a_target_with_many_comments_is_removed_with_them_in_one_request(
    store, session, ada, books
):  # TC-63
    ids = []
    for batch in range(12):  # 12 requests of 50 to set up: ``comment`` 600 times takes a minute
        async with session.transaction() as t:
            for n in range(50):
                minted = str(DEFAULT_IRIS.mint_aggregate(TENANT, "rp-comment", "rp-comments"))
                model = Comment(
                    id=minted,
                    has_target=B1,
                    body_value=f"remark {batch * 50 + n}",
                    motivated_by=Motivation.COMMENTING,
                )
                await t.add_graph(minted, toy_mapper().to_triples(model))
                ids.append(minted)
    assert len(await session.heads(ids)) == 600, "the comments are stored"
    work = UnitOfWork(session, toy_mapper())
    work.remove(await work.get(Book, B1))
    sent = len(store.sent("update"))
    await work.commit()  # a commit of more than the root limit would raise CommitTooLarge
    assert len(store.sent("update")) == sent + 1, "one update request"
    assert await session.heads(ids) == [], "no comment graph is left"
    assert await session.graphs_with(v.HAS_TARGET) == {}, "no stored root targets anything"


async def test_a_thread_is_oldest_first_and_ties_go_by_iri(ada, books, now):  # TC-64
    ids = []
    for minutes in (2, 1, 1):
        now["t"] = T0 + timedelta(minutes=minutes)
        ids.append(await ada.comment(B1, f"at {minutes}"))
    late, early_a, early_b = ids
    assert [c.id for c in await ada.thread(B1)] == [*sorted([early_a, early_b]), late], (
        "the two at minute 1 by IRI, then the one at minute 2"
    )


async def test_the_author_does_not_see_its_comment_outside_its_audience(bob, books):  # Q-1
    await bob.comment(B1, "for librarians", audience=["librarian"])
    assert await bob.thread(B1) == [], "the audience is a role bob does not hold"


async def test_a_thread_needs_read_on_the_aggregate(rules, session, books):
    outsider = collab(
        rules,
        session,
        BOB,
        grants=[role("reader", who=BOB)],
        bans=[ban(Action.READ, graph_of(B2), BOB)],
    )
    with pytest.raises(Forbidden):
        await outsider.thread(B2)


async def test_comments_on_a_schema_without_the_module_are_a_lookup_error(
    rules: AccessRules, session: Session, books: None
):
    view = load_schema(Path(TOY_SCHEMA).parent / "partial.yaml")
    build = Collaboration(
        session,
        view=view,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        caller=caller(principal=ADA),
        access=held(role("librarian"), role("reviewer")),
    )
    with pytest.raises(LookupError, match="rp_discussion"):
        await build.comment(B1, "x")
    with pytest.raises(LookupError, match="rp_discussion"):
        await build.thread(B1)
