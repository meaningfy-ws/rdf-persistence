"""The bus wired end to end: ``bootstrap``, the toolkit's ``Transition`` handler, a handler's unit of work
(message-bus PD-13 to PD-16).

The collaboration and the session are real, over the fake store; the session's ``on_commit`` is the
bus's ``publish``, as the kit wires it.
"""

from types import SimpleNamespace

import pytest
from rdflib import RDF, URIRef
from rdflib.namespace import PROV

from rdf_persistence import bootstrap
from rdf_persistence.collaboration.domain.generated.rp_discussion import (
    Comment,
    PostComment,
    PostReply,
)
from rdf_persistence.collaboration.domain.generated.rp_workflow import Transition
from rdf_persistence.core.domain.exceptions import NotFound
from rdf_persistence.files.domain.generated.rp_files import DeleteFile
from rdf_persistence.messaging.services.messagebus import Work, command
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Add
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.testkit import RecordingObserver
from tests.fixtures.library.domain.generated.books import Book
from tests.toy import ADA, ApproveBook, ShelveBooks, dune, toy_mapper
from tests.unit.activity_helpers import (
    activities,
    framed,
    mapped,
    toy,
    unordered,
    with_class_iris_expanded,
)
from tests.unit.messaging.messagebus_helpers import (
    B1,
    B2,
    B3,
    DRAFT,
    IN_REVIEW,
    PROVENANCE,
    provenance,
    shelving,
    types_of,
    version_of,
    world,
)

APPROVE_BOOK = URIRef("https://example.org/ns/library#ApproveBook")


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
            assert got.started_at_time, f"{name}: the times"
            assert got.ended_at_time, f"{name}: the times"
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


async def test_a_required_parameter_no_dependency_provides_fails_at_bootstrap():  # D-11 d
    async def shelve(cmd: Activity, work: Work, notifer: object) -> None:  # a typo of notifier
        return None

    async def watch(activity: Activity, work: Work, mapper_: object) -> None:
        return None

    with pytest.raises(ValueError, match="notifer"):
        bootstrap(commands={ShelveBooks: shelve})
    with pytest.raises(ValueError, match="mapper_"):
        bootstrap(observers={Activity: [watch]})


async def test_a_parameter_with_a_default_needs_no_dependency():  # D-11 d
    async def shelve(cmd: Activity, work: Work, retries: int = 3) -> int:
        return retries

    bus = bootstrap(commands={ShelveBooks: shelve})

    result = await bus.handle(command(ShelveBooks), SimpleNamespace(session=object()))  # type: ignore[arg-type]
    assert result == 3, "the default stands"


async def test_a_command_handler_of_the_consumer_replaces_the_toolkits():  # TC-78
    async def mine(cmd: Activity, work: Work) -> str:
        return "mine"

    bus = bootstrap(commands={Transition: mine})

    result = await bus.handle(
        command(Transition, used_resource=B1), SimpleNamespace(session=object())
    )  # type: ignore[arg-type]

    assert result == "mine", "the consumer's handler ran, not the toolkit's"


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

        with pytest.raises(RuntimeError, match=f"{shelve.id} has served a commit already"):
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
        assert stored.comment_audience == ["reviewer"], "the comment keeps its audience"
        assert stored.comment_references == [B2], "the comment keeps its references"
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
        assert got.id == reply.id, "the observer gets the reply that was posted"
        assert got.replies_to == first, "the reply answers the first post"
        assert got.used_resource == B1, "the reply names the resource it was posted on"
        assert (got.body_value, got.comment_audience) == (None, None), "the payload is not stored"
        [stored] = [c for c in await w.collaboration.thread(B1) if c.id == iri]
        assert isinstance(stored, Comment), "a reply to the comment"
        assert stored.replies_to == first, "a reply to the comment"


async def test_a_file_deletion_has_no_toolkit_handler():  # TC-95
    async with world() as w:
        with pytest.raises(LookupError, match="DeleteFile"):
            await w.bus.handle(command(DeleteFile, used_resource=B1), w.collaboration)
