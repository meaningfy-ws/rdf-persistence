"""Data the collaboration tests, and the route tests built on them, share: the review workflow's states and the annotation vocabulary."""

import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from rdflib import RDF, Namespace, URIRef

from rdf_persistence import AccessRules, Action, generated_models, load_role_definitions
from rdf_persistence.collaboration.domain.generated.rp_collections import (
    MembershipRule,
    SlotEquality,
)
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.discussion import dependents as discussion_dependents
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.iris.services.iris import DEFAULT_IRIS
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books import Genre
from tests.toy import (
    ADA,
    BOB,
    MODULES,
    REVIEW_WORKFLOW,
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
    shelf,
    shelf_iri,
    toy_mapper,
)

OA = Namespace("http://www.w3.org/ns/oa#")
RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
SECRET = "SECRET-9f3a-do-not-show"

REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW, ACCEPTED = (state_iri(REVIEW, s) for s in ("draft", "in_review", "accepted"))
RETIRED = state_iri(REVIEW, "retired")  # a state the file does not list


async def stored(session: Session, *iris: str) -> list[str]:
    """The IRIs, among ``iris``, whose graph the session finds."""
    return [str(h.head_iri) for h in await session.heads(list(iris))]


def annotation(iri: str, *pairs: tuple[URIRef, object], types=(v.ANNOTATION,)) -> list:
    """The triples of a root typed as a web annotation, written as the test says (raw, maybe invalid)."""
    node = URIRef(iri)
    return [*((node, RDF.type, t) for t in types), *((node, p, o) for p, o in pairs)]


ENTRY = "ASK { GRAPH $registry { $graph ?p ?o } }"


async def has_entry(store: FakeStore, iri: str) -> bool:
    text = fill(
        ENTRY, registry=term(DEFAULT_IRIS.registry(TENANT)), graph=term(URIRef(graph_of(iri)))
    )
    return bool((await store.query(FAKE_DATABASE, text)).askAnswer)


MARKER_LEFT = "ASK { GRAPH $registry { ?m a $marker } }"


def everything_said(error: BaseException) -> str:
    """Every text an error carries: its message, repr, arguments and the ``iris`` of a conflict."""
    return " ".join([str(error), repr(error), *map(str, error.args), *getattr(error, "iris", ())])


async def marker_left(session) -> bool:
    return await session._ask(
        MARKER_LEFT, registry=term(DEFAULT_IRIS.registry(TENANT)), marker=term(v.COMMIT_MARKER)
    )


# -- the cascade's and the collections' tests ----------------------------------------------------

HEADS = "VALUES ?m"  # the text of the query that reads the heads of the members


def cascade_poetry() -> MembershipRule:
    return MembershipRule(
        rule_equalities=[SlotEquality(equals_slot="genre", equals_value="poetry")]
    )


def a_shelf(iri: str, **slots):
    return shelf(iri).model_copy(update=slots)


async def cascade_put(session, model) -> str:
    return await session.add_graph(model.id, toy_mapper().to_triples(model))


async def put_book(session, iri: str, genre: Genre = Genre.FICTION) -> None:
    await cascade_put(session, dune(iri, chapters=1).model_copy(update={"genre": genre.value}))


async def cascade_stored(session, iri: str) -> bool:
    return bool(await session.heads([iri]))


async def version(session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


async def regenre(store: FakeStore, iri: str, genre: Genre) -> None:
    """Another writer replaces the book ``iri`` with one of ``genre``."""
    async with fake_session(store, tenant_iri=TENANT) as other:
        model = dune(iri, chapters=1).model_copy(update={"genre": genre.value})
        await other.replace_graph(iri, toy_mapper().to_triples(model), await version(other, iri))


async def gone(store: FakeStore, iri: str) -> None:
    """Another writer removes the aggregate ``iri``."""
    async with fake_session(store, tenant_iri=TENANT) as other:
        await other.remove(iri, await version(other, iri))


def as_ada(collaboration, session):
    return collaboration(caller(principal=ADA), held(role("librarian")), session)


def as_bob_without(collaboration, session, *hidden: str):
    bans = [ban(Action.READ, graph_of(h), BOB) for h in hidden]
    return collaboration(caller(principal=BOB), held(role("reader", who=BOB), bans=bans), session)


async def collections_put(session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


def before(store: FakeStore, operation: str, action, when: str = "") -> None:
    """Await ``action()`` once, just before the first call of ``operation`` whose text holds ``when``."""
    original = getattr(store, operation)
    done = False

    async def wrapped(dataset, text):
        nonlocal done
        if not done and when in text:
            done = True
            await action()
        return await original(dataset, text)

    setattr(store, operation, wrapped)


# -- the workflow's tests, and what the tests built on them share ---------------------------------

B1, B2 = book_iri(1), book_iri(2)
S1 = shelf_iri(1)
PROVENANCE = URIRef(DEFAULT_IRIS.provenance(TENANT))
VIEW = load_schema(TOY_SCHEMA)
T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)


def combined(view=VIEW):
    """What a remove drops with its aggregate: the comments (a transition's activity stays, PD-11)."""
    return discussion_dependents(view)


@asynccontextmanager
async def opened(
    store: FakeStore, now: dict[str, datetime], who: str, rules: AccessRules, *, guarded=True
) -> AsyncIterator[Session]:
    """A session the way the kit opens one: write guards with the workflows, the records dropped with their aggregate."""
    listings = Listings(VIEW)
    guards = WriteGuards(
        toy_mapper(), generated_models(*MODULES), listings, Workflows([REVIEW], VIEW, rules)
    )
    async with fake_session(
        store,
        tenant_iri=TENANT,
        principal=Principal(id=who),
        clock=lambda: now["t"],
        listings=listings,
        guards=guards if guarded else None,
        dependents=combined() if guarded else (),
    ) as session:
        yield session


def collab(rules: AccessRules, session: Session, who: str, *grants, bans=None, view=VIEW):
    return Collaboration(
        session,
        view=view,
        rules=rules,
        iris=DEFAULT_IRIS,
        mapper=toy_mapper(),
        models=generated_models(*MODULES),
        listings=Listings(view),
        workflows=Workflows([REVIEW], view, rules),
        caller=caller(principal=who),
        access=held(*grants, bans=bans),
    )


async def put(session: Session, model) -> None:
    await session.add_graph(model.id, toy_mapper().to_triples(model))


async def status_of(session: Session, iri: str) -> list[str]:
    return sorted(
        map(str, (await session.root_values(iri, [v.WORKFLOW_STATUS]))[v.WORKFLOW_STATUS])
    )


async def records_of(session: Session, iri: str) -> list[str]:
    """The IRIs of the transition activities that used ``iri``, as the provenance graph holds them."""
    return sorted(await session.activities(v.TRANSITION, v.USED, URIRef(iri)))


async def comments_on(session: Session, iri: str) -> list[str]:
    return sorted(await session.graphs_with(v.HAS_TARGET, URIRef(iri)))


async def go(who: Collaboration, session: Session, to: str, iri: str = B1, **more) -> str:
    return await who.transition(iri, to, if_version=await version(session, iri), **more)


# -- the tests of the schema's rules: a copy of the toy schema to change ----------------------------


def copy_schema(tmp_path: Path) -> Path:
    folder = tmp_path / "library"
    shutil.copytree(
        TOY_SCHEMA.parent, folder, ignore=shutil.ignore_patterns("__pycache__", "generated")
    )
    return folder


def edit(folder: Path, module: str, old: str, new: str) -> None:
    text = (folder / module).read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {module}"
    (folder / module).write_text(text.replace(old, new, 1), encoding="utf-8")


# -- the write guards' tests ---------------------------------------------------------------------


def guards(*, workflows: bool = False) -> WriteGuards:
    view = load_schema(TOY_SCHEMA)
    kept = (
        Workflows([REVIEW], view, AccessRules(load_role_definitions(ROLES))) if workflows else None
    )
    return WriteGuards(toy_mapper(), generated_models(*MODULES), Listings(view), kept)


async def save(session, *objects) -> None:
    work = UnitOfWork(session, toy_mapper())
    for obj in objects:
        work.add(obj)
    await work.commit()


async def version_of(session, iri: str) -> str:
    return (await session.get_graph(iri))[2]


# -- the nested collections' tests ---------------------------------------------------------------


def nesting(iri: str, *members: str):
    """A shelf that nests the given shelves."""
    return shelf(iri, nests=True).model_copy(update={"has_part": list(members) or None})


async def replace_in(session, t, *shelves) -> None:
    """Collect, in the transaction ``t``, the replacement of each stored shelf by ``shelves``."""
    for each in shelves:
        triples = toy_mapper().to_triples(each)
        await t.replace_graph(str(each.id), triples, await version_of(session, str(each.id)))


async def replace(session, *shelves) -> None:
    async with session.transaction() as t:
        await replace_in(session, t, *shelves)


async def chain(session, length: int) -> None:
    """Store ``length`` nesting shelves, each one naming the one stored before it."""
    for n in range(1, length + 1):
        await save(session, nesting(shelf_iri(n), *([shelf_iri(n - 1)] if n > 1 else [])))
