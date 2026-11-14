"""Adversarial tests of stage 3, discussion (rp-discussion, PD-3 step 4, PD-9 to PD-15, PD-25, PD-26, D-7, D-8).

The new operation on every delete first (a remove drops the comments on the removed aggregate, and
only those), the presence guard under concurrent writers, then who sees what, then foreign and
malformed annotations and hostile input. Each test names the spec line, design item or decision it
holds the code to; "pinned" marks behaviour no document decides. B1 to B3 are books of the toy tenant
and S1 a shelf; ``ada`` is a librarian and a reviewer, ``bob`` a reader and a reviewer. "Another
writer" is a second session on the same fake store, made to act at a stated moment (``before``,
``after``).
"""

import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from rdflib import RDF, Literal, Namespace, URIRef

from rdf_persistence import Action, generated_models
from rdf_persistence.domain.exceptions import (
    Conflict,
    Forbidden,
    InvalidIri,
    NotFound,
    PersistenceError,
    UnknownRole,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_discussion import Comment, Motivation
from rdf_persistence.domain.iris import DEFAULT_IRIS, skolem_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.problems import format_problem
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
    library,
    role,
    shelf,
    shelf_iri,
    toy_mapper,
)
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService
from tests.unit.services.test_collaboration_cascade import before
from tests.unit.services.test_collaboration_collections_adversarial import (
    everything_said,
    marker_left,
)
from tests.unit.services.test_collaboration_discussion import has_entry

B1, B2, B3 = (book_iri(n) for n in (1, 2, 3))
S1 = shelf_iri(1)
VIEW = load_schema(TOY_SCHEMA)
OA = Namespace("http://www.w3.org/ns/oa#")
RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
LIB = Namespace("https://example.org/ns/library#")
SECRET = "SECRET-9f3a-do-not-show"
EVIL = 'x" } . ?s ?p ?o } ; DROP ALL ; # \n\r\t\\ <a> {'
OTHER_TENANT = "https://example.org/libraries/00000000"
COUNT = "SELECT (COUNT(DISTINCT ?g) AS ?n) WHERE { GRAPH $registry { ?g $p_kind ?k } }"
ANY_TRIPLE = "ASK { GRAPH $graph { ?s ?p ?o } }"
EXTRA_ROLES = (
    "- {role: reviewer, level: tenant, actions: [read, annotate]}\n"
    "- {role: editor, level: aggregate, actions: [read, annotate]}\n"
)


# -- fixtures and builders ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def rules(tmp_path_factory: pytest.TempPathFactory) -> AccessRules:
    path = tmp_path_factory.mktemp("roles") / "roles.yaml"
    path.write_text(ROLES.read_text() + EXTRA_ROLES)
    return AccessRules(load_role_definitions(path))


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


def guards() -> WriteGuards:
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(VIEW))


@asynccontextmanager
async def writer(store: FakeStore, *, drops: bool = True) -> AsyncIterator[Session]:
    """A guarded session on the store, as the kit opens one; ``drops=False`` opens one with no dependents."""
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=BOB),
        listings=Listings(VIEW),
        guards=guards(),
        dependents=dependents(VIEW) if drops else (),
    ) as opened:
        yield opened


@pytest.fixture
async def session(store: FakeStore) -> AsyncIterator[Session]:
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=Listings(VIEW),
        guards=guards(),
        dependents=dependents(VIEW),
    ) as opened:
        yield opened


@pytest.fixture
async def bare(store: FakeStore) -> AsyncIterator[Session]:
    """A session with no dependents: its remove drops only the aggregate."""
    async with writer(store, drops=False) as opened:
        yield opened


def acts(rules: AccessRules, session: Session, principal: str, *grants, bans=None, roles=()):
    return Collaboration(
        session,
        view=VIEW,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(VIEW),
        caller=caller(*roles, principal=principal),
        access=held(*grants, bans=bans),
    )


@pytest.fixture
def ada(rules, session) -> Collaboration:
    return acts(rules, session, ADA, role("librarian"), role("reviewer"))


@pytest.fixture
def bob(rules, session) -> Collaboration:
    return acts(rules, session, BOB, role("reader", who=BOB), role("reviewer", who=BOB))


async def put(session: Session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


@pytest.fixture
async def books(session: Session) -> None:
    for iri in (B1, B2, B3):
        await put(session, dune(iri, chapters=1))


async def version(session: Session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


def comment_iri(n: int) -> str:
    return f"{TENANT}/rp-comments/{UUID(int=1000 + n)}"


def a_comment(n: int, target: str, text: str = "remark", **slots) -> Comment:
    """A valid comment with a chosen IRI, for a test that stores it without the service."""
    slots.setdefault("motivated_by", Motivation.COMMENTING)
    return Comment(id=comment_iri(n), has_target=target, body_value=text, **slots)


async def stored(session: Session, *iris: str) -> list[str]:
    return [str(h.head_iri) for h in await session.heads(list(iris))]


async def roots_targeting(session: Session, iri: str) -> list[str]:
    return sorted(await session.graphs_with(v.HAS_TARGET, URIRef(iri)))


async def aggregates(store: FakeStore) -> int:
    text = fill(COUNT, registry=term(DEFAULT_IRIS.registry(TENANT)), p_kind=term(v.REGISTRY_KIND))
    return int(next(iter(await store.query(FAKE_DATABASE, text))).n)


async def has_triples(store: FakeStore, iri: str) -> bool:
    text = fill(ANY_TRIPLE, graph=term(URIRef(graph_of(iri))))
    return bool((await store.query(FAKE_DATABASE, text)).askAnswer)


def annotation(iri: str, *pairs: tuple[URIRef, object], types=(v.ANNOTATION,)) -> list:
    """The triples of a root typed as a web annotation, written as the test says (raw, maybe invalid)."""
    node = URIRef(iri)
    return [*((node, RDF.type, t) for t in types), *((node, p, o) for p, o in pairs)]


def another(store: FakeStore, rules: AccessRules, action: Callable) -> Callable[[], Awaitable]:
    """``action(collaboration)`` as another writer, a librarian and reviewer on a session of its own."""

    async def run() -> None:
        async with writer(store) as other:
            await action(
                acts(rules, other, BOB, role("librarian", who=BOB), role("reviewer", who=BOB))
            )

    return run


async def removed_by_another(store: FakeStore, iri: str) -> None:
    async with writer(store) as other:
        await other.remove(iri, await version(other, iri))


def after(store: FakeStore, operation: str, action: Callable[[], Awaitable]) -> None:
    """Await ``action()`` once, just after the next call of ``operation``."""
    original = getattr(store, operation)
    done = False

    async def wrapped(dataset, text):
        nonlocal done
        result = await original(dataset, text)
        if not done:
            done = True
            await action()
        return result

    setattr(store, operation, wrapped)


# -- 1. a delete drops the comments on the removed aggregate, and only those --------------------


@dataclass
class World:
    """What B1's removal must take (``dropped``) and what it must leave (``kept``)."""

    dropped: dict[str, str]
    kept: dict[str, str]
    part: str  # a part typed as an annotation in B2's graph, which targets B1


async def build_world(session: Session, ada: Collaboration) -> World:
    for iri in (B1, B2):
        await put(session, dune(iri, chapters=1))
    await put(session, dune(B3, chapters=1).model_copy(update={"sequel_of": B1}))
    await session.add_graph(TENANT, toy_mapper().to_triples(library()))
    on_target = await ada.comment(B1, "on b1", references=[B2])
    reply = await ada.comment(B1, "a reply", reply_to=on_target)
    own = shelf_iri(71)  # a consumer's own aggregate typed as an annotation (RISK-3)
    own_triples = toy_mapper().to_triples(shelf(own))
    own_triples += annotation(own, (v.HAS_TARGET, URIRef(B1)), types=(v.ANNOTATION,))
    await session.add_graph(own, own_triples)
    plain = shelf_iri(72)  # an aggregate of another class that uses the same predicate
    await session.add_graph(
        plain,
        [*toy_mapper().to_triples(shelf(plain)), (URIRef(plain), v.HAS_TARGET, URIRef(B1))],
    )
    on_other = await ada.comment(B2, "on b2")
    references = await ada.comment(B2, "mentions b1", references=[B1])
    part = str(skolem_iri(graph_of(B2)))
    await session.replace_graph(
        B2,
        [
            *toy_mapper().to_triples(dune(B2, chapters=1)),
            *annotation(part, (v.HAS_TARGET, URIRef(B1)), (OA.bodyValue, Literal("a part"))),
        ],
        await version(session, B2),
    )
    return World(
        dropped={"comment": on_target, "reply": reply, "consumer annotation": own},
        kept={
            "comment on another aggregate": on_other,
            "comment that only references": references,
            "referrer": B3,
            "other class with the predicate": plain,
            "the aggregate holding the part": B2,
            "tenant root": TENANT,
        },
        part=part,
    )


async def by_session(session: Session, iri: str) -> None:
    await session.remove(iri, await version(session, iri))


async def by_transaction(session: Session, iri: str) -> None:
    old = await version(session, iri)
    async with session.transaction() as transaction:
        await transaction.remove(iri, old)


async def by_unit_of_work(session: Session, iri: str) -> None:
    work = UnitOfWork(session, toy_mapper())
    work.remove(await work.get(Book, iri))
    await work.commit()


PATHS = {
    "Session.remove": by_session,
    "Session.transaction": by_transaction,
    "UnitOfWork.commit": by_unit_of_work,
}


@pytest.fixture(params=list(PATHS))
async def after_removal(request, session, ada) -> World:
    world = await build_world(session, ada)
    await PATHS[request.param](session, B1)
    return world


async def test_no_comment_graph_of_the_removed_aggregate_is_left(session, store, after_removal):
    left = [i for i in after_removal.dropped.values() if await has_triples(store, i)]
    assert left == [], "the graphs of the dropped records are empty"
    assert await stored(session, *after_removal.dropped.values()) == [], "and unregistered"


async def test_no_registry_entry_of_a_dropped_record_is_left(store, after_removal):
    left = [i for i in after_removal.dropped.values() if await has_entry(store, i)]
    assert left == [], "each dropped record's registry entry went with it"


async def test_no_commit_marker_is_left_after_a_remove_that_dropped_comments(
    session, after_removal
):
    assert not await marker_left(session), "the marker is released"


async def test_what_is_not_a_comment_on_the_removed_aggregate_is_kept(
    session, store, after_removal
):
    kept = after_removal.kept
    assert sorted(await stored(session, B2, B3, *kept.values())) == sorted(
        {B2, B3, *(i for i in kept.values() if i != TENANT)}
    ), "every kept aggregate is still stored"
    assert (await session.get_graph(TENANT))[2], "the tenant root is still in the meta graph"
    for name, iri in kept.items():
        assert await has_triples(store, iri) or iri == TENANT, f"{name} keeps its triples"


async def test_a_part_typed_as_an_annotation_in_another_graph_is_not_dropped(
    session, after_removal
):  # the dependents operation matches roots, which the registry owns
    graph, _, _ = await session.get_graph(B2)
    assert (URIRef(after_removal.part), v.HAS_TARGET, URIRef(B1)) in graph, "the part is kept"


async def test_a_consumers_own_annotation_aggregate_targeting_the_removed_one_is_dropped(
    session, after_removal
):  # RISK-3, accepted
    assert await stored(session, after_removal.dropped["consumer annotation"]) == [], (
        "the annotation went with its target"
    )


async def test_the_aggregates_that_only_use_the_predicate_still_target_the_removed_one(
    session, after_removal
):
    assert await roots_targeting(session, B1) == [shelf_iri(72)], "only the other class remains"


async def test_the_removed_aggregates_referrers_still_refer_to_it(session, ada, after_removal):
    found = await ada.referrers(B1)
    kept = after_removal.kept
    assert {r.referrer for r in found.referrers or []} == {
        B3,
        B2,
        kept["comment that only references"],
        kept["other class with the predicate"],
    }, "the sequel, the comment that references b1, the shelf and the book holding the part"


async def test_a_cascade_drops_the_comments_on_the_collection_and_on_its_members(
    session, ada, books, store
):
    await put(session, shelf(S1).model_copy(update={"had_member": [B1, B2]}))
    on = {n: await ada.comment(i, n) for n, i in (("s1", S1), ("b1", B1), ("b2", B2), ("b3", B3))}
    await ada.delete_cascade(S1, await version(session, S1))
    assert await stored(session, *on.values()) == [on["b3"]], (
        "only the comment on the book that stays"
    )
    assert not await marker_left(session), "no commit marker"


@pytest.mark.parametrize(
    "refusal",
    ["stale version", "a stale remove of another aggregate", "an add of an existing graph"],
)
async def test_a_refused_remove_drops_no_comment(refusal, session, ada, books, store):
    on_target = await ada.comment(B1, "stays")
    before_all = await aggregates(store)
    with pytest.raises(Conflict):
        async with session.transaction() as transaction:
            fresh = await version(session, B1)
            await transaction.remove(B1, "stale" if refusal == "stale version" else fresh)
            if refusal == "a stale remove of another aggregate":
                await transaction.remove(B2, "stale")
            if refusal == "an add of an existing graph":
                await transaction.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))
    assert await stored(session, on_target) == [on_target], "the comment is kept"
    assert await aggregates(store) == before_all, "nothing at all changed"
    assert not await marker_left(session), "no commit marker"


async def test_a_replace_of_the_target_drops_no_comment(session, ada, books):
    c = await ada.comment(B1, "stays")
    await session.replace_graph(
        B1, toy_mapper().to_triples(dune(B1, chapters=2)), await version(session, B1)
    )
    assert [x.id for x in await ada.thread(B1)] == [c], "the comment reads on the new version"


async def test_a_comment_that_references_a_removed_aggregate_stays_and_reads(session, ada, books):
    c = await ada.comment(B1, "see b2", references=[B2])
    await session.remove(B2, await version(session, B2))
    [seen] = await ada.thread(B1)
    assert (seen.id, seen.comment_references) == (c, [B2]), "the reference stays as it was written"


async def test_a_comment_of_a_removed_target_is_not_a_referrer_of_what_it_referenced(
    session, ada, books
):  # an orphan reference cannot exist: the comment went with its target
    await ada.comment(B1, "see b2", references=[B2])
    await session.remove(B1, await version(session, B1))
    found = await ada.referrers(B2)
    assert (found.referrers, found.hidden_count) == (None, 0), "no comment refers to b2 any more"


async def test_a_session_without_dependents_orphans_the_comments(session, bare, ada, books, store):
    c = await ada.comment(B1, "orphan")
    await bare.remove(B1, await version(bare, B1))
    assert await stored(bare, c) == [c], "pinned: a session opened without dependents drops nothing"
    assert await roots_targeting(bare, B1) == [c], "and it still targets the removed aggregate"


async def test_the_thread_of_a_removed_aggregate_lists_its_orphans(session, bare, ada, books):
    c = await ada.comment(B1, "orphan")
    await bare.remove(B1, await version(bare, B1))
    assert [x.id for x in await ada.thread(B1)] == [c], (
        "pinned: thread does not check the target is stored"
    )


async def test_an_orphan_cannot_be_commented_on_but_comes_back_with_its_target(
    session, bare, ada, books
):
    c = await ada.comment(B1, "orphan")
    await bare.remove(B1, await version(bare, B1))
    with pytest.raises(NotFound):
        await ada.comment(B1, "too late")
    await put(session, dune(B1, chapters=1))
    assert [x.id for x in await ada.thread(B1)] == [c], (
        "pinned: a new aggregate at the IRI inherits it"
    )


async def test_the_comments_a_remove_without_dependents_left_are_not_referrers_of_the_target(
    session, bare, ada, books
):
    await ada.comment(B1, "orphan")
    await bare.remove(B1, await version(bare, B1))
    found = await ada.referrers(B1)
    assert (found.referrers, found.hidden_count) == (None, 0), (
        "pinned: the target link is no reference"
    )


async def test_the_kit_remove_with_files_drops_the_comments():
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as client:
        headers = toy.bearer("ada")
        path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers[
            "location"
        ]
        tenant = toy.kit.tenant_iri(path.rsplit("/", 1)[1])
        first = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        second = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        on_first, on_second = (
            str(toy.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments")) for _ in range(2)
        )
        async with toy.kit.session(tenant, "ada") as session:
            for comment, target in ((on_first, first), (on_second, second)):
                await session.add_graph(
                    comment, annotation(comment, (v.HAS_TARGET, URIRef(target)))
                )
            old = (await session.get_graph(first))[2]
        await toy.kit.remove_with_files(tenant, "ada", first, old)
        async with toy.kit.session(tenant, "ada") as session:
            assert await stored(session, on_first, on_second) == [on_second], (
                "the comment on the removed aggregate is gone, the other stays"
            )


# -- 2. races: the presence guard under concurrent writers --------------------------------------


async def test_a_comment_posted_while_its_target_is_removed_is_refused_and_nothing_is_left(
    rules, store, session, ada, books
):  # Error matrix; the remove lands first
    old = await ada.comment(B1, "already there")
    before(store, "update", lambda: removed_by_another(store, B1))
    with pytest.raises(Conflict) as refused:
        await ada.comment(B1, "too late")
    assert refused.value.iris == (B1,), "the target is named"
    assert await roots_targeting(session, B1) == [], "no comment, new or old, targets it"
    assert await stored(session, old) == [], "the comment that was there went with the target"


async def test_a_remove_landing_between_a_comments_request_and_its_confirmation_leaves_no_orphan(
    rules, store, session, ada, books
):  # the comment's request applied, then the remove dropped it: the confirmation cannot find it
    after(store, "update", lambda: removed_by_another(store, B1))
    with pytest.raises(Conflict) as refused:
        await ada.comment(B1, "just in time")
    assert refused.value.iris == (B1,), "pinned: the poster is told the target went"
    assert await roots_targeting(session, B1) == [], "and no comment is left on it"
    assert not await marker_left(session), "no commit marker"


async def test_a_comment_added_between_a_removes_read_and_its_send_is_dropped_with_the_target(
    rules, store, session, ada, books
):
    posted: list[str] = []

    async def post(other: Collaboration) -> None:
        posted.append(await other.comment(B1, "in between"))

    before(store, "update", another(store, rules, post))
    await by_session(session, B1)
    assert await stored(session, *posted) == [], "the request that removed b1 dropped it too"
    assert await roots_targeting(session, B1) == [], "nothing is left targeting b1"


async def test_two_comments_racing_both_land_with_distinct_iris(rules, store, session, ada, books):
    posted: list[str] = []

    async def post(other: Collaboration) -> None:
        posted.append(await other.comment(B1, "from bob"))

    before(store, "update", another(store, rules, post))
    posted.append(await ada.comment(B1, "from ada"))
    assert len(set(posted)) == 2, "two IRIs"
    assert sorted(c.id for c in await ada.thread(B1)) == sorted(posted), "both are in the thread"


async def test_a_reply_posted_while_its_parents_target_is_removed_is_refused(
    rules, store, session, ada, books
):
    parent = await ada.comment(B1, "parent")
    before(store, "update", lambda: removed_by_another(store, B1))
    with pytest.raises(Conflict) as refused:
        await ada.comment(B1, "reply", reply_to=parent)
    assert refused.value.iris == (B1,), "the target is named, not the parent"
    assert await roots_targeting(session, B1) == [], "neither parent nor reply is left"


async def test_a_comment_racing_a_replace_of_its_target_succeeds_and_the_new_version_is_intact(
    rules, store, session, ada, books
):
    async def replace() -> None:
        async with writer(store) as other:
            new = toy_mapper().to_triples(dune(B1, chapters=3))
            await other.replace_graph(B1, new, await version(other, B1))

    before(store, "update", replace)
    c = await ada.comment(B1, "during the edit")
    assert [x.id for x in await ada.thread(B1)] == [c], "the comment is stored"
    graph, graph_name, _ = await session.get_graph(B1)
    book = toy_mapper().from_graph(Book, B1, graph, graph_name)
    assert len(book.chapters or []) == 3, "the replace is intact"


async def test_a_comment_racing_the_removal_and_return_of_its_target_lands_on_the_new_one(
    rules, store, session, ada, books
):  # pinned: the guard asks only that the graph has a version, not which
    async def again() -> None:
        await removed_by_another(store, B1)
        async with writer(store) as other:
            await put(other, dune(B1, chapters=2))

    before(store, "update", again)
    c = await ada.comment(B1, "meant for the old one")
    assert [x.id for x in await ada.thread(B1)] == [c], (
        "pinned: it is on the aggregate now at that IRI"
    )


@pytest.mark.parametrize(
    "as_member", [True, False], ids=["the target is a member", "the target is the collection"]
)
async def test_a_comment_racing_a_cascade_that_removes_its_target_is_refused(
    as_member, rules, store, session, ada, books
):
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    target = B1 if as_member else S1
    ver = await version(session, S1)
    before(
        store,
        "update",
        another(store, rules, lambda other: other.delete_cascade(S1, ver)),
    )
    with pytest.raises(Conflict) as refused:
        await ada.comment(target, "too late")
    assert refused.value.iris == (target,), "the removed target is named"
    assert await roots_targeting(session, target) == [], "no comment is left on it"


async def test_a_remove_of_a_target_that_a_racing_cascade_removed_first_leaves_no_orphan(
    rules, store, session, ada, books
):
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    on_b1, on_s1 = await ada.comment(B1, "on b1"), await ada.comment(S1, "on s1")
    ver = await version(session, S1)
    old = await version(session, B1)
    before(store, "update", another(store, rules, lambda other: other.delete_cascade(S1, ver)))
    await session.remove(B1, old)  # pinned: no Conflict, the confirmation of a remove is "absent"
    assert await stored(session, on_b1, on_s1, B1, S1) == [], "the cascade took all four"
    assert not await marker_left(session), "no commit marker"


async def test_a_cascade_racing_a_remove_of_one_member_is_a_conflict_and_keeps_the_collections_comments(
    rules, store, session, ada, books
):
    await put(session, shelf(S1).model_copy(update={"had_member": [B1]}))
    on_b1, on_s1 = await ada.comment(B1, "on b1"), await ada.comment(S1, "on s1")
    ver = await version(session, S1)
    before(store, "update", lambda: removed_by_another(store, B1))
    with pytest.raises(Conflict) as refused:
        await ada.delete_cascade(S1, ver)
    assert refused.value.iris == (B1,), "the removed member is named"
    assert await stored(session, on_b1, on_s1) == [on_s1], (
        "b1's comment went with b1; the shelf's stays"
    )


# -- 3. who sees what ---------------------------------------------------------------------------

READER = role("reader", who=BOB)
AUDIENCES = [
    (
        "one of several roles",
        ["librarian", "reviewer"],
        [READER, role("reviewer", who=BOB)],
        (),
        True,
    ),
    ("none of several roles", ["librarian", "reviewer"], [READER], (), False),
    (
        "a role held on the target only",
        ["editor"],
        [READER, role("editor", graph_of(B1), BOB)],
        (),
        True,
    ),
    (
        "a role held on another aggregate only",
        ["editor"],
        [READER, role("editor", graph_of(B2), BOB)],
        (),
        False,
    ),
    ("a global role defined at system level", ["admin"], [READER], ("admin",), True),
    ("a token role defined at tenant level only", ["librarian"], [READER], ("librarian",), False),
    ("a global role not held", ["admin"], [READER], (), False),
    ("a direct grant has no role", ["reader"], [direct(Action.READ, TENANT, BOB)], (), False),
    ("the role of the caller", ["reader"], [READER], (), True),
]


@pytest.mark.parametrize(
    ("audience", "grants", "roles", "sees"),
    [row[1:] for row in AUDIENCES],
    ids=[row[0] for row in AUDIENCES],
)
async def test_a_comment_is_seen_by_the_roles_of_its_audience_where_they_are_held(
    audience, grants, roles, sees, rules, session, ada, books
):
    c = await ada.comment(B1, "for some", audience=audience)
    seen = [x.id for x in await acts(rules, session, BOB, *grants, roles=roles).thread(B1)]
    assert (c in seen) is sees, f"audience {audience} for roles held {grants} and {roles}"


@pytest.mark.parametrize(
    ("viewer_roles", "sees"),
    [((), False), (("ghost",), False)],
    ids=["a caller without the role", "a token that carries the name"],
)
async def test_an_audience_role_the_roles_file_does_not_define_is_matched_by_no_one(
    viewer_roles, sees, rules, session, books
):  # pinned: written without the service, so the service never checked the name; PD-30 item 3
    await put(session, a_comment(1, B1, comment_audience=["ghost"]))
    who = acts(rules, session, ADA, role("librarian"), roles=viewer_roles)
    assert bool(await who.thread(B1)) is sees, f"a token carrying {viewer_roles} sees the comment"


async def test_the_author_outside_its_own_audience_cannot_reply_to_its_comment(bob, books):
    c = await bob.comment(B1, "for librarians", audience=["librarian"])
    with pytest.raises(NotFound):
        await bob.comment(B1, "my own reply", reply_to=c)  # Q-1: the author does not see it


async def test_a_caller_who_may_annotate_but_holds_a_read_ban_may_neither_comment_nor_read(
    rules, session, books
):  # PD-9: a ban of read forbids every action, annotate included
    who = acts(
        rules, session, BOB, role("reviewer", who=BOB), bans=[ban(Action.READ, graph_of(B1), BOB)]
    )
    with pytest.raises(Forbidden):
        await who.comment(B1, "no")
    with pytest.raises(Forbidden):
        await who.thread(B1)
    assert await roots_targeting(session, B1) == [], "nothing was stored"


async def test_a_ban_of_read_on_one_aggregate_leaves_comments_on_the_others(rules, session, books):
    who = acts(
        rules, session, BOB, role("reviewer", who=BOB), bans=[ban(Action.READ, graph_of(B1), BOB)]
    )
    c = await who.comment(B2, "fine here")
    assert [x.id for x in await who.thread(B2)] == [c], "the ban on b1 does not reach b2's thread"


async def test_a_tenant_ban_of_annotate_refuses_comments_and_keeps_the_thread_readable(
    rules, session, ada, books
):
    c = await ada.comment(B1, "earlier")
    who = acts(
        rules, session, BOB, role("reviewer", who=BOB), bans=[ban(Action.ANNOTATE, TENANT, BOB)]
    )
    with pytest.raises(Forbidden):
        await who.comment(B1, "no")
    assert [x.id for x in await who.thread(B1)] == [c], "annotate is not read"
    assert await roots_targeting(session, B1) == [c], "nothing was stored"


async def test_a_visible_reply_under_a_hidden_parent_a_hidden_reply_and_its_replies_are_hidden(
    ada, bob, books, now_ticks
):
    first = await ada.comment(B1, "open")
    now_ticks()
    middle = await ada.comment(B1, "librarians", audience=["librarian"], reply_to=first)
    now_ticks()
    last = await ada.comment(B1, "open again", reply_to=middle)
    now_ticks()
    other = await ada.comment(B1, "another open", reply_to=first)
    assert [x.id for x in await bob.thread(B1)] == [first, other], (
        "the hidden one hides its replies"
    )
    assert [x.id for x in await ada.thread(B1)] == [first, middle, last, other], "ada sees all four"


@pytest.fixture
def now_ticks(session):
    """Moves the session's clock on a minute each call, so the posts of a test have distinct times."""
    clock = {"t": datetime(2026, 11, 14, 9, tzinfo=UTC)}
    session._clock = lambda: clock["t"]

    def tick() -> None:
        clock["t"] += timedelta(minutes=1)

    return tick


async def test_a_reply_whose_parent_is_on_another_aggregate_is_hidden_and_nothing_raises(
    session, ada, books
):
    elsewhere = await ada.comment(B2, "on b2")
    reply = a_comment(5, B1, "a stray", motivated_by=Motivation.REPLYING, replies_to=elsewhere)
    await put(session, reply)
    assert await ada.thread(B1) == [], (
        "pinned: the parent is not in this thread, so the reply is hidden"
    )
    assert [x.id for x in await ada.thread(B2)] == [elsewhere], "and b2's thread is unchanged"


@pytest.mark.parametrize("shape", ["a pair", "itself", "a missing parent"])
async def test_a_reply_cycle_or_a_reply_to_nothing_ends_and_is_hidden(shape, session, ada, books):
    first, second = comment_iri(1), comment_iri(2)
    parent = {"a pair": second, "itself": first, "a missing parent": comment_iri(99)}[shape]
    await put(session, a_comment(1, B1, motivated_by=Motivation.REPLYING, replies_to=parent))
    if shape == "a pair":
        await put(session, a_comment(2, B1, motivated_by=Motivation.REPLYING, replies_to=first))
    assert await ada.thread(B1) == [], "every reply of the shape is hidden, and thread returns"


async def test_a_hidden_comment_leaves_nothing_in_what_a_caller_without_the_audience_gets(
    rules, session, ada, bob, books
):
    hidden = await ada.comment(B1, SECRET, audience=["librarian"], references=[B3])
    await ada.comment(B1, SECRET + " reply", reply_to=hidden)
    outcomes = [repr(await bob.thread(B1)), (await bob.referrers(B3)).model_dump_json()]
    for outcome in outcomes:
        for secret in (hidden.rsplit("/", 1)[1], SECRET, "librarian", ADA):
            assert secret not in outcome, f"{secret!r} leaked in {outcome}"


async def test_a_reply_to_a_hidden_comment_and_to_a_missing_one_raise_the_same_error(
    ada, bob, books
):  # no oracle for "exists but hidden"
    hidden = await ada.comment(B1, SECRET, audience=["librarian"], references=[B3])
    missing = comment_iri(77)
    texts = {}
    for name, target in (("hidden", hidden), ("missing", missing)):
        with pytest.raises(NotFound) as refused:
            await bob.comment(B1, "reply", reply_to=target)
        texts[name] = everything_said(refused.value).replace(target, "<iri>")
    assert texts["hidden"] == texts["missing"], "one error shape"
    for secret in (SECRET, "librarian", ADA):
        assert secret not in texts["hidden"], f"{secret!r} leaked in the error"


@pytest.mark.parametrize(
    ("class_name", "slot"),
    [
        (None, None),
        ("Comment", None),
        ("Book", None),
        (None, "comment_references"),
        (None, "sequel_of"),
        ("Comment", "comment_references"),
        ("Book", "sequel_of"),
    ],
)
async def test_the_hidden_count_of_comment_referrers_ignores_the_narrowing(
    class_name, slot, session, ada, bob, books
):  # PD-26: each hidden comment once, and the count never follows class_name or slot
    hidden = await ada.comment(B1, SECRET, audience=["librarian"], references=[B3])
    reply = await ada.comment(B2, "hidden too", audience=["librarian"], references=[B3, B3])
    found = await bob.referrers(B3, class_name=class_name, slot=slot)
    assert found.referrers is None, f"{hidden} and {reply} are named nowhere"
    assert found.hidden_count == 2, "two comments, each counted once"


async def test_a_comment_that_references_its_own_target_is_one_referrer_counted_once(
    session, ada, bob, books
):
    c = await ada.comment(B1, "about myself", references=[B1])
    [item] = (await ada.referrers(B1)).referrers or []
    assert (item.referrer, item.referrer_slot) == (c, "comment_references"), (
        "listed once, by its reference"
    )
    hidden = await ada.comment(B1, "librarians", audience=["librarian"], references=[B1])
    found = await bob.referrers(B1)
    assert (len(found.referrers or []), found.hidden_count) == (1, 1), f"{hidden} is counted once"


async def test_a_reply_under_a_hidden_parent_is_a_hidden_referrer_too(session, ada, bob, books):
    parent = await ada.comment(B1, "librarians", audience=["librarian"])
    await ada.comment(B1, "open reply", reply_to=parent, references=[B3])
    found = await bob.referrers(B3)
    assert (found.referrers, found.hidden_count) == (None, 1), "the reply is hidden with its parent"


# -- 4. foreign and malformed annotations -------------------------------------------------------

BODY = (OA.bodyValue, Literal("text"))
MOTIVE = (OA.motivatedBy, OA.commenting)
TARGET_B1 = (v.HAS_TARGET, URIRef(B1))
MALFORMED = {
    "no body": [TARGET_B1, MOTIVE],
    "no motivation": [TARGET_B1, BODY],
    "a blank body": [TARGET_B1, MOTIVE, (OA.bodyValue, Literal(""))],
    "an unknown motivation": [TARGET_B1, BODY, (OA.motivatedBy, URIRef("urn:x:other"))],
    "an unknown slot": [TARGET_B1, BODY, MOTIVE, (URIRef("urn:x:extra"), Literal("more"))],
    "a body that is an IRI": [TARGET_B1, MOTIVE, (OA.bodyValue, URIRef("urn:x:body"))],
    "two bodies": [TARGET_B1, MOTIVE, BODY, (OA.bodyValue, Literal("other"))],
    "two targets": [TARGET_B1, (v.HAS_TARGET, URIRef(B2)), BODY, MOTIVE],
    "a reference that is a literal": [
        TARGET_B1,
        BODY,
        MOTIVE,
        (v.COMMENT_REFERENCES, Literal("x")),
    ],
    "a reply to a literal": [TARGET_B1, BODY, MOTIVE, (RP.repliesTo, Literal("x"))],
}


@pytest.mark.parametrize("shape", list(MALFORMED))
async def test_thread_returns_for_a_foreign_annotation_on_the_target(shape, session, ada, books):
    await session.add_graph(comment_iri(1), annotation(comment_iri(1), *MALFORMED[shape]))
    shown = await ada.thread(B1)
    assert isinstance(shown, list), f"{shape}: thread must return, or raise a documented error"


@pytest.mark.parametrize("shape", list(MALFORMED))
async def test_referrers_returns_for_a_foreign_annotation_that_references_the_aggregate(
    shape, session, ada, books
):
    pairs = [(v.COMMENT_REFERENCES, URIRef(B3)), *MALFORMED[shape]]
    await session.add_graph(comment_iri(1), annotation(comment_iri(1), *pairs))
    found = await ada.referrers(B3)
    listed = [r.referrer for r in found.referrers or []]
    # listed when it is no comment or a comment ada sees; counted when it is a comment she does not
    # (a reply whose parent is not in the thread)
    assert len(listed) + found.hidden_count == 1, f"{shape}: the one referrer is listed or counted"
    assert set(listed) <= {comment_iri(1)}, f"{shape}: and nothing else is listed"


async def test_an_annotation_that_is_no_comment_is_a_referrer_like_any_other(
    rules, session, ada, books
):
    """PD-29: listed to who may read it, counted for who may not; no thread rule applies."""
    foreign = comment_iri(1)
    await session.add_graph(
        foreign, annotation(foreign, (v.COMMENT_REFERENCES, URIRef(B3)), MOTIVE)
    )
    seen = await ada.referrers(B3)
    assert [r.referrer for r in seen.referrers or []] == [foreign], "ada may read it: listed"
    banned = acts(
        rules,
        session,
        BOB,
        role("reader", who=BOB),
        bans=[ban(Action.READ, graph_of(foreign), BOB)],
    )
    unseen = await banned.referrers(B3)
    assert not unseen.referrers, "bob may not read it: not listed"
    assert unseen.hidden_count == 1, "and counted once"


async def test_an_annotation_without_a_text_is_not_in_the_thread(session, ada, books):
    """PD-29: what does not decode as a comment is not a comment."""
    await session.add_graph(comment_iri(1), annotation(comment_iri(1), MOTIVE))
    assert await ada.thread(B1) == [], "another's annotation on b1, with no text, is left out"


async def test_a_foreign_annotation_with_no_target_that_references_an_aggregate_is_a_referrer_call_that_returns(
    session, ada, books
):
    await session.add_graph(
        comment_iri(1), annotation(comment_iri(1), (v.COMMENT_REFERENCES, URIRef(B3)), BODY, MOTIVE)
    )
    found = await ada.referrers(B3)
    listed = found.referrers or []
    assert len(listed) + found.hidden_count == 1, (
        "the annotation is one referrer, listed or counted"
    )


async def test_a_comment_with_two_targets_is_shown_on_both_threads_naming_one(session, ada, books):
    await session.add_graph(
        comment_iri(1),
        annotation(comment_iri(1), TARGET_B1, (v.HAS_TARGET, URIRef(B2)), BODY, MOTIVE),
    )
    on_b1, on_b2 = await ada.thread(B1), await ada.thread(B2)
    assert [(c.id, c.has_target) for c in on_b1 + on_b2] == [(comment_iri(1), B1)] * 2, (
        "pinned: a comment of two targets is in both threads and names the first"
    )


async def test_a_comment_whose_target_is_a_literal_is_in_no_thread(session, ada, books):
    await session.add_graph(
        comment_iri(1), annotation(comment_iri(1), (v.HAS_TARGET, Literal(B1)), BODY, MOTIVE)
    )
    assert await ada.thread(B1) == [], "pinned: a literal is not the IRI"


async def test_a_comment_without_a_creation_time_is_shown_first(session, store, ada, books):
    c = await ada.comment(B1, "will lose its time")
    await ada.comment(B1, "stays timed")
    clock = fill(
        "DELETE WHERE { GRAPH $graph { $graph $p_created ?o } }",
        graph=term(URIRef(graph_of(c))),
        p_created=term(v.CREATED),
    )
    await store.update(FAKE_DATABASE, clock)
    assert (await ada.thread(B1))[0].id == c, "pinned: a missing time sorts before every other"


async def test_a_comment_outside_the_comments_path_is_still_shown_in_the_thread(
    session, ada, books
):
    stray = f"{TENANT}/shelves/{UUID(int=500)}"
    await session.add_graph(stray, annotation(stray, TARGET_B1, BODY, MOTIVE))
    assert [c.id for c in await ada.thread(B1)] == [stray], "pinned: the type decides, not the path"


async def test_a_consumer_can_write_a_comment_through_add_graph_and_it_reads(session, ada, books):
    await put(session, a_comment(3, B1, "written by a consumer", comment_audience=["librarian"]))
    [seen] = await ada.thread(B1)
    assert (seen.id, seen.body_value) == (comment_iri(3), "written by a consumer"), (
        "pinned: nothing stops a session write of the toolkit class (rp_writes: toolkit is a generic-API rule)"
    )


async def test_a_consumer_can_write_a_comment_whose_audience_names_an_undefined_role(
    session, ada, books
):
    await put(session, a_comment(3, B1, comment_audience=["ghost"]))
    assert await roots_targeting(session, B1) == [comment_iri(3)], (
        "pinned: the write path does not check roles"
    )


# -- 5. hostile input to comment ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        EVIL,
        "x" * 200_000,
        "line\nbreak\r\nand\ttab",
        "  padded  ",
        "é中\U0001f600",
        "a' OR '1'='1",
        "\u0000nul",
    ],
    ids=["sparql fragments", "very long", "newlines", "padded", "unicode", "quote", "nul"],
)
async def test_a_hostile_text_is_stored_as_text_or_refused_with_a_documented_error(
    text, store, session, ada, books
):
    count = await aggregates(store)
    try:
        c = await ada.comment(B1, text)
    except PersistenceError:
        assert await aggregates(store) == count, "a refusal stores nothing"
        return
    assert [x.body_value for x in await ada.thread(B1)] == [text], "the text comes back as written"
    assert await aggregates(store) == count + 1, f"one aggregate, {c}, and nothing else changed"
    assert await stored(session, B1, B2, B3) == [B1, B2, B3], "no book was touched"


REFUSED_REFERENCES = {
    "sparql fragments": EVIL,
    "an aggregate IRI with a hostile tail": f"{B1}> }} ; DROP ALL ; <",
    "a graph iri": graph_of(B1),
    "a skolem iri": str(skolem_iri(graph_of(B1))),
    "an aggregate of another tenant": f"{OTHER_TENANT}/books/{UUID(int=1)}",
    "a loaded graph": str(DEFAULT_IRIS.mint_loaded_graph(TENANT, B1)),
    "an empty string": "",
    "a relative path": "books/1",
}


@pytest.mark.parametrize(
    "reference", list(REFUSED_REFERENCES.values()), ids=list(REFUSED_REFERENCES)
)
async def test_a_reference_that_is_not_an_aggregate_of_the_tenant_is_refused_and_nothing_is_stored(
    reference, store, session, ada, books
):
    count = await aggregates(store)
    with pytest.raises(InvalidIri):
        await ada.comment(B1, "fine", references=[B2, reference])
    assert await aggregates(store) == count, "nothing was stored"


async def test_hundreds_of_references_are_stored_and_read_back(session, ada, books):
    many = [book_iri(n) for n in range(1, 401)]
    await ada.comment(B1, "many", references=many)
    [seen] = await ada.thread(B1)
    assert sorted(seen.comment_references or []) == sorted(many), "all four hundred, as a set"


async def test_duplicate_references_and_roles_are_stored_once(session, ada, books):
    await ada.comment(B1, "dups", references=[B2, B2], audience=["librarian", "librarian"])
    [seen] = await ada.thread(B1)
    assert seen.comment_references == [B2], "the reference once"
    assert seen.comment_audience == ["librarian"], "and the role once"


@pytest.mark.parametrize(
    "reference",
    [B1, comment_iri(1), TENANT, f"{TENANT}/access"],
    ids=["the target itself", "a comment", "the tenant root", "the access record"],
)
async def test_a_reference_to_the_target_a_comment_the_root_or_the_record_is_stored(
    reference, session, ada, books
):  # pinned: is_aggregate accepts each (the policy calls the root and the record aggregates)
    await ada.comment(B1, "first")
    await ada.comment(B1, "second", references=[reference])
    assert len(await ada.thread(B1)) == 2, f"a reference to {reference} is accepted"


@pytest.mark.parametrize("role_name", ["", " ", "librarian ", "Librarian", "libr\narian", EVIL])
async def test_an_audience_entry_that_is_not_exactly_a_defined_role_is_refused(
    role_name, store, ada, books
):
    count = await aggregates(store)
    with pytest.raises(UnknownRole):
        await ada.comment(B1, "x", audience=["librarian", role_name])
    assert await aggregates(store) == count, "nothing was stored"


@pytest.mark.parametrize(
    "reply_to",
    [EVIL, "", TENANT, B1, "urn:uuid:" + "0" * 36],
    ids=["fragments", "empty", "tenant", "target", "urn"],
)
async def test_a_hostile_reply_to_is_not_found_and_nothing_is_stored(reply_to, store, ada, books):
    count = await aggregates(store)
    with pytest.raises(NotFound):
        await ada.comment(B1, "x", reply_to=reply_to)
    assert await aggregates(store) == count, "nothing was stored"


BAD_TARGETS = {
    "a graph iri": graph_of(B1),
    "a skolem iri": str(skolem_iri(graph_of(B1))),
    "a loaded graph": str(DEFAULT_IRIS.mint_loaded_graph(TENANT, B1)),
    "an aggregate of another tenant": f"{OTHER_TENANT}/books/{UUID(int=1)}",
    "the access record": f"{TENANT}/access",
    "a missing aggregate": book_iri(99),
    "sparql fragments": EVIL,
    "an aggregate IRI with a hostile tail": f"{B1}> }} ; DROP ALL ; <",
    "an empty string": "",
}


@pytest.mark.parametrize("target", list(BAD_TARGETS.values()), ids=list(BAD_TARGETS))
async def test_a_comment_on_something_that_is_no_aggregate_of_the_tenant_is_refused_with_nothing_stored(
    target, store, session, ada, books
):
    count = await aggregates(store)
    with pytest.raises((NotFound, InvalidIri)):
        await ada.comment(target, "x")
    assert await aggregates(store) == count, "nothing was stored"
    assert await stored(session, B1, B2, B3) == [B1, B2, B3], "no injected statement ran"


# -- 6. the model and the access side -----------------------------------------------------------


async def test_the_generic_router_has_no_route_for_comments_whatever_the_method():
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as client:
        headers = toy.bearer("ada")
        path = (await client.post("/libraries", json=TENANT_BODY, headers=headers)).headers[
            "location"
        ]
        tenant = toy.kit.tenant_iri(path.rsplit("/", 1)[1])
        book = (await client.post(f"{path}/books", json=DUNE_BODY, headers=headers)).json()["id"]
        comment = str(toy.kit.iris.mint_aggregate(tenant, "rp-comment", "rp-comments"))
        async with toy.kit.session(tenant, "ada") as session:
            await session.add_graph(
                comment,
                annotation(
                    comment,
                    (v.HAS_TARGET, URIRef(book)),
                    (OA.bodyValue, Literal(SECRET)),
                    (RP.audience, Literal("librarian")),
                ),
            )
        paths = [route.path for route in toy.app.routes if hasattr(route, "path")]
        assert not [p for p in paths if "rp-comments" in p], "no route names the comments path"
        uuid = comment.rsplit("/", 1)[1]
        seen = {}
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            for url in (f"{path}/rp-comments", f"{path}/rp-comments/{uuid}"):
                response = await client.request(method, url, headers=headers, json={})
                seen[(method, url)] = response
        wrong = {k: r.status_code for k, r in seen.items() if r.status_code not in (404, 405)}
        assert wrong == {}, "no method on a comment path answers other than not found"
        assert not [k for k, r in seen.items() if SECRET in r.text], "the text is not served"


@pytest.mark.parametrize(
    ("members", "rule"), [("class", "Comment"), ("iri", "Book")], ids=["named class", "named IRI"]
)
async def test_a_comment_is_no_member_of_a_collection(members, rule, session, ada, books, store):
    c = await ada.comment(B1, "a remark")
    named = shelf(S1).model_copy(
        update={"member_class": rule, "had_member": [c] if members == "iri" else None}
    )
    with pytest.raises(PersistenceError):
        await put(session, named)
    assert await stored(session, S1) == [], "the collection was refused and nothing was stored"


async def test_a_cascade_of_a_stored_collection_that_names_a_comment_deletes_nothing(
    session, ada, books, store
):  # the stored data is not trusted (PD-28 item 2)
    c = await ada.comment(B1, "a remark")
    async with fake_session(store, tenant_iri=TENANT) as unguarded:
        await put(unguarded, shelf(S1).model_copy(update={"had_member": [c]}))
    with pytest.raises(PersistenceError):
        await ada.delete_cascade(S1, await version(session, S1))
    assert sorted(await stored(session, S1, c, B1)) == sorted([S1, c, B1]), (
        "the refusal deletes nothing"
    )


async def test_find_and_listings_never_return_comments(session, ada, books):
    await ada.comment(B1, "a remark")
    assert await session.find(Book) == [B1, B2, B3], "only the books"
    with pytest.raises(ValueError, match="path"):
        await session.find(Comment)


@pytest.mark.parametrize(
    ("what", "grants", "bans", "roles"),
    [
        ("a grant of another assignee", [role("editor", graph_of(B1), BOB)], None, set()),
        (
            "a grant on another tenant's aggregate",
            [role("editor", f"{OTHER_TENANT}/books/{UUID(int=1)}/graph", ADA)],
            None,
            set(),
        ),
        (
            "a ban does not remove a role",
            [role("reader")],
            [ban(Action.READ, graph_of(B1))],
            {"reader"},
        ),
        ("the aggregate's own role", [role("editor", graph_of(B1))], None, {"editor"}),
    ],
)
def test_the_roles_of_a_caller_are_its_own_grants_in_scope(what, grants, bans, roles, rules):
    assert rules.roles(caller(), held(*grants, bans=bans), B1) == roles, what


@pytest.mark.parametrize(
    ("name", "defined"),
    [
        ("reader", True),
        ("editor", True),
        ("admin", True),
        ("Reader", False),
        ("reader ", False),
        ("rea der", False),
        ("", False),
        ("reader\n", False),
        ("rеader", False),
        ("*", False),
    ],
)
def test_a_role_is_defined_only_by_its_exact_name(name, defined, rules):
    assert rules.defines(name) is defined, repr(name)


async def test_annotate_in_an_aggregate_level_role_lets_its_holder_comment_on_that_aggregate_only(
    rules, session, books
):
    who = acts(rules, session, BOB, role("editor", graph_of(B1), BOB))
    c = await who.comment(B1, "as an editor")
    assert [x.id for x in await who.thread(B1)] == [c], (
        "annotate at aggregate level, and read through it"
    )
    with pytest.raises(NotFound):
        await who.comment(B2, "no grant here")
    assert await roots_targeting(session, B2) == [], "nothing was stored on b2"


RESERVED = [
    ("rp_path", "rp-notes", True),
    ("rp_path", "RP-notes", False),
    ("rp_path", "rp_notes", False),
    ("rp_path", "rp", False),
    ("rp_path", "rpnotes", False),
    ("rp_iri_type", "rp-book", True),
    ("rp_iri_type", "rp_book", False),
    ("rp_iri_type", "rp", False),
]


def reserved_problems(tmp_path: Path, module: str, old: str, new: str) -> list[str]:
    folder = tmp_path / "library"
    shutil.copytree(
        TOY_SCHEMA.parent, folder, ignore=shutil.ignore_patterns("__pycache__", "generated")
    )
    text = (folder / module).read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {module}"
    (folder / module).write_text(text.replace(old, new, 1), encoding="utf-8")
    problems = hard_problems(load_schema(folder / "library.yaml"), folder)
    return [p for p in map(format_problem, problems) if "[reserved_segment]" in p]


@pytest.mark.parametrize(("tag", "value", "reserved"), RESERVED)
def test_only_the_rp_dash_prefix_is_a_reserved_segment(tag, value, reserved, tmp_path):
    new = f"rp_path: books\n      {tag}: {value}" if tag == "rp_iri_type" else f"rp_path: {value}"
    found = reserved_problems(tmp_path, "books.yaml", "rp_path: books", new)
    assert bool(found) is reserved, f"{tag}: {value!r} -> {found}"


def test_a_reserved_type_on_a_class_that_is_not_a_root_is_refused(tmp_path):  # D-8 item 3
    old = "      rp_unlabelled: true\n  Note:"
    new = "      rp_unlabelled: true\n      rp_iri_type: rp-chapter\n  Note:"
    found = reserved_problems(tmp_path, "books.yaml", old, new)
    assert any("Chapter" in p for p in found), f"a part's type is reserved too: {found}"
