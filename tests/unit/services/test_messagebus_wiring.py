"""The bus wired end to end: ``bootstrap``, the toolkit's ``Transition`` handler, a handler's unit of work
(message-bus PD-13 to PD-16, task 3.3).

The collaboration and the session are real, over the fake store; the session's ``on_commit`` is the
bus's ``publish``, as the kit wires it.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import PROV

from rdf_persistence import bootstrap, generated_models
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.generated.rp_access import Action, RoleDefinition, RoleLevel
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_discussion import Comment, PostComment, PostReply
from rdf_persistence.domain.generated.rp_files import DeleteFile
from rdf_persistence.domain.generated.rp_provenance import Activity, Add
from rdf_persistence.domain.generated.rp_workflow import Transition
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.messagebus import MessageBus, Work, command
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.services.write_guards import WriteGuards
from rdf_persistence.testkit import FakeStore, RecordingObserver, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Book
from tests.toy import (
    ADA,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    ApproveBook,
    ShelveBooks,
    book_iri,
    caller,
    dune,
    held,
    role,
    toy_mapper,
)
from tests.unit.services.test_activity_shape import (
    framed,
    mapped,
    toy,
    unordered,
    with_class_iris_expanded,
)
from tests.unit.services.test_session_activity import activities, stored_graph

B1, B2, B3 = book_iri(1), book_iri(2), book_iri(3)
VIEW = load_schema(TOY_SCHEMA)
REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW = (state_iri(REVIEW, s) for s in ("draft", "in_review"))
PROVENANCE = URIRef(DEFAULT_IRIS.provenance(TENANT))
APPROVE_BOOK = URIRef("https://example.org/ns/library#ApproveBook")


@dataclass
class World:
    """One caller's session on a fake store, with a collaboration and a bus wired to publish."""

    store: FakeStore
    session: object
    collaboration: Collaboration
    bus: MessageBus


@asynccontextmanager
async def world(
    *,
    commands=None,
    observers: dict[type[Activity], Sequence] | None = None,
    mapper=True,
    **dependencies,
) -> AsyncIterator[World]:
    rules = AccessRules(
        [
            *load_role_definitions(ROLES),
            RoleDefinition(role="reviewer", level=RoleLevel.TENANT, actions=[Action.ANNOTATE]),
        ]
    )
    bus = bootstrap(
        commands=commands,
        observers=observers,
        mapper=toy_mapper() if mapper else None,
        **dependencies,
    )
    store = FakeStore()
    listings = Listings(VIEW)
    guards = WriteGuards(
        toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], VIEW, rules)
    )
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=listings,
        guards=guards,
        on_commit=bus.publish,
    ) as session:
        collaboration = Collaboration(
            session,
            view=VIEW,
            rules=rules,
            iris=DEFAULT_IRIS,
            mapper=toy_mapper(),
            models=generated_models(*MODULES),
            listings=listings,
            workflows=Workflows([REVIEW], VIEW, rules),
            caller=caller(principal=ADA),
            access=held(role("librarian"), role("reviewer")),
        )
        for iri in (B1, B2):
            await session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))
        yield World(store, session, collaboration, bus)


async def version_of(world: World, iri: str = B1) -> str:
    return (await world.session.get_graph(iri))[2]


async def provenance(world: World) -> Graph:
    return await stored_graph(world.store, PROVENANCE, FAKE_DATABASE)


def types_of(graph: Graph, iri: str) -> set[URIRef]:
    return {t for t in graph.objects(URIRef(iri), RDF.type) if isinstance(t, URIRef)}


async def test_the_toolkit_handler_moves_a_book_and_records_a_transition():  # TC-73
    async with world() as w:
        first = await version_of(w)
        move = command(Transition, used_resource=B1, to_state="in_review", expected_version=first)

        new = await w.bus.handle(move, w.collaboration)

        status = (await w.session.root_values(B1, [v.WORKFLOW_STATUS]))[v.WORKFLOW_STATUS]
        assert [str(s) for s in status] == [IN_REVIEW], "b1 is in review"
        assert new == await version_of(w), "handle returns the new version"
        assert new != first, "which is a new one"
        graph = await provenance(w)
        assert [str(s) for s in graph.subjects(RDF.type, v.TRANSITION)] == [move.id], (
            "one rp:Transition, whose IRI is the command's id"
        )


async def test_an_extension_without_its_own_handler_is_stored_as_itself():  # TC-104
    async with world() as w:
        move = command(
            ApproveBook,
            used_resource=B1,
            to_state="in_review",
            expected_version=await version_of(w),
        )

        await w.bus.handle(move, w.collaboration)

        assert types_of(await provenance(w), move.id) == {
            APPROVE_BOOK,
            v.TRANSITION,
            PROV.Activity,
        }, "the toy's class, rp:Transition and prov:Activity"


async def test_the_observers_get_the_command_as_it_was_stored():  # TC-75
    on_transition, on_activity = RecordingObserver(), RecordingObserver()
    async with world(observers={Transition: [on_transition], Activity: [on_activity]}) as w:
        move = command(
            ApproveBook,
            used_resource=B1,
            to_state="in_review",
            expected_version=await version_of(w),
        )

        await w.bus.handle(move, w.collaboration)

        for name, seen in (("Transition", on_transition), ("Activity", on_activity)):
            [got] = seen.of(ApproveBook)
            assert got.id == move.id, f"the {name} observer got the command's activity"
            assert (got.to_state, got.expected_version) == (None, None), (
                f"{name}: the payload is not stored"
            )
            assert (got.from_state_iri, got.to_state_iri) == (DRAFT, IN_REVIEW), (
                f"{name}: the states"
            )
            assert got.started_at_time and got.ended_at_time, f"{name}: the times"
            assert got.was_associated_with == [ADA], f"{name}: the principal"
            assert [g.entity for g in got.generations or []] == [B1], f"{name}: the generation"
            assert [i.entity for i in got.invalidations or []] == [B1], f"{name}: the invalidation"


async def test_a_stored_consumer_activity_round_trips_through_json_ld():  # TC-105
    async with world() as w:
        move = command(
            ApproveBook,
            used_resource=B1,
            to_state="in_review",
            expected_version=await version_of(w),
        )
        await w.bus.handle(move, w.collaboration)
        model = toy_mapper().from_graph(ApproveBook, move.id, await provenance(w), PROVENANCE)

        assert toy().graph_of(model, "ApproveBook").isomorphic(mapped(model)), (
            "the JSON of the model expands to the mapped graph (TC-12)"
        )
        back = ApproveBook.model_validate(with_class_iris_expanded(framed(model)))
        assert unordered(back) == unordered(model), (
            "the framed graph reads back as the model (TC-13)"
        )


async def test_a_handler_gets_the_dependency_its_signature_names():  # TC-76
    fake, seen = object(), []

    async def shelve(cmd: Activity, work: Work, notifier: object) -> str:
        seen.append(notifier)
        return "done"

    bus = bootstrap(commands={ShelveBooks: shelve}, notifier=fake)

    result = await bus.handle(command(ShelveBooks), SimpleNamespace(session=object()))  # type: ignore[arg-type]

    assert (result, seen) == ("done", [fake]), "the handler received the notifier"


async def test_an_observer_gets_the_dependency_its_signature_names():
    fake, seen = object(), []

    async def watch(activity: Activity, work: Work, notifier: object) -> None:
        seen.append(notifier)

    await bootstrap(observers={Activity: [watch]}, notifier=fake).publish(
        command(ShelveBooks),
        object(),  # type: ignore[arg-type]
    )

    assert seen == [fake], "the observer received the notifier"


async def test_a_dependency_no_handler_or_observer_names_is_a_value_error():  # TC-77
    with pytest.raises(ValueError, match="notifier"):
        bootstrap(notifier=object())


async def test_a_command_handler_of_the_consumer_replaces_the_toolkits():  # TC-78
    async def mine(cmd: Activity, work: Work) -> str:
        return "mine"

    bus = bootstrap(commands={Transition: mine})

    result = await bus.handle(
        command(Transition, used_resource=B1), SimpleNamespace(session=object())
    )  # type: ignore[arg-type]

    assert result == "mine", "the consumer's handler ran, not the toolkit's"


def shelving(*, twice: bool = False, new_book: str | None = None):
    """A ``ShelveBooks`` handler that relabels two books through ``work.unit_of_work()``."""

    async def shelve(cmd: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        for iri in (B1, B2):
            book = await unit.get(Book, iri)
            unit.add(book.model_copy(update={"label": "Shelved"}))
        await unit.commit()
        if twice:
            again = work.unit_of_work()
            book = await again.get(Book, B1)
            again.add(book.model_copy(update={"label": "Again"}))
            await again.commit()

    return shelve


async def test_a_handlers_unit_of_work_commits_one_activity_of_the_command():  # TC-106
    seen = RecordingObserver()
    async with world(commands={ShelveBooks: shelving()}, observers={ShelveBooks: [seen]}) as w:
        shelve = command(ShelveBooks, shelf_note="top shelf")

        await w.bus.handle(shelve, w.collaboration)

        [stored] = [a for a in await activities(w.store, PROVENANCE) if a.id == shelve.id]
        graph = await provenance(w)
        assert types_of(graph, shelve.id) >= {
            URIRef("https://example.org/ns/library#ShelveBooks"),
            PROV.Activity,
        }, "the activity is a ShelveBooks"
        assert (
            graph.value(URIRef(shelve.id), URIRef("https://example.org/ns/library#shelfNote"))
            is not None
        ), "the note is stored"
        assert sorted(g.entity for g in stored.generations or []) == [B1, B2], "two generations"
        assert sorted(i.entity for i in stored.invalidations or []) == [B1, B2], "two invalidations"
        [got] = seen.of(ShelveBooks)
        assert got.shelf_note == "top shelf", "the observer got the activity once, with its note"


async def test_a_second_commit_with_the_same_command_is_refused_and_the_first_stands():  # TC-79
    async with world(commands={ShelveBooks: shelving(twice=True)}) as w:
        shelve = command(ShelveBooks)

        with pytest.raises(RuntimeError):
            await w.bus.handle(shelve, w.collaboration)

        book = toy_mapper().from_graph(Book, B1, (await w.session.get_graph(B1))[0], None)
        assert book.label == "Shelved", "the first commit stands, the second wrote nothing"
        assert [a.id for a in await activities(w.store, PROVENANCE) if a.id == shelve.id] == [
            shelve.id
        ], "the one activity of the command is stored"


async def test_an_observer_of_a_command_commits_what_it_adds_as_its_own_activity():  # TC-79a
    async def add_a_book(activity: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        unit.add(dune(B3, chapters=1))
        await unit.commit()

    async with world(
        commands={ShelveBooks: shelving()}, observers={ShelveBooks: [add_a_book]}
    ) as w:
        await w.bus.handle(command(ShelveBooks), w.collaboration)

        adds = [
            a
            for a in await activities(w.store, PROVENANCE)
            if isinstance(a, Add) and [g.entity for g in a.generations or []] == [B3]
        ]
        assert len(adds) == 1, "the observer's commit is one rp:Add of the new book"


async def test_a_unit_of_work_with_a_command_refuses_batches_and_writes_nothing():  # TC-80
    async with world() as w:
        served = toy_mapper().served(command(ShelveBooks))
        unit = UnitOfWork(w.session, toy_mapper(), served=served)
        unit.add(dune(B3, chapters=1))

        with pytest.raises(ValueError, match="batches"):
            await unit.commit(batches=True)

        with pytest.raises(NotFound):
            await w.session.get_graph(B3)


async def test_the_toolkit_handler_posts_a_comment_and_returns_its_iri():  # TC-92
    async with world() as w:
        post = command(
            PostComment,
            used_resource=B1,
            body_value="hi",
            comment_audience=["reviewer"],
            comment_references=[B2],
        )

        iri = await w.bus.handle(post, w.collaboration)

        [stored] = await w.collaboration.thread(B1)
        assert (stored.id, stored.body_value) == (iri, "hi"), (
            "the comment is stored, its IRI returned"
        )
        assert (stored.comment_audience, stored.comment_references) == (["reviewer"], [B2])
        assert [str(s) for s in (await provenance(w)).subjects(RDF.type, v.POST_COMMENT)] == [
            post.id
        ], "the activity's IRI is the command's id"


async def test_an_observer_of_posts_gets_the_reply_that_was_posted():  # TC-93
    seen = RecordingObserver()
    async with world(observers={PostComment: [seen]}) as w:
        first = await w.bus.handle(
            command(PostComment, used_resource=B1, body_value="hi"), w.collaboration
        )
        reply = command(PostReply, used_resource=B1, body_value="re", replies_to=first)

        iri = await w.bus.handle(reply, w.collaboration)

        [got] = seen.of(PostReply)
        assert (got.id, got.replies_to, got.used_resource) == (reply.id, first, B1)
        assert (got.body_value, got.comment_audience) == (None, None), "the payload is not stored"
        [stored] = [c for c in await w.collaboration.thread(B1) if c.id == iri]
        assert isinstance(stored, Comment) and stored.replies_to == first, "a reply to the comment"


async def test_a_file_deletion_has_no_toolkit_handler():  # TC-95
    async with world() as w:
        with pytest.raises(LookupError, match="DeleteFile"):
            await w.bus.handle(command(DeleteFile, used_resource=B1), w.collaboration)
