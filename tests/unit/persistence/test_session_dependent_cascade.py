"""Removing a whole removes its parts, at commit, transitively (dependent-aggregates PD-5 to PD-9, D-1,
D-3; A-1, A-2, A-6, A-7, A-15, G-1), on the fake store.

The tree: audit A1 is the whole of results R1 and R2, result R1 the whole of finding F1, and R1 has a
loaded graph L1. Every row asserts the exception type and ``iris``; a ``NotFound`` carries none.
"""

import pytest
from rdflib import RDF, URIRef

from rdf_persistence.core.domain.exceptions import CommitTooLarge, Conflict, InUse
from rdf_persistence.core.domain.generated.rp_core import DependenceLink
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.mapper import Mapper, UnitOfWork, generated_models
from rdf_persistence.provenance.domain.generated.rp_provenance import Remove
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated import audits
from tests.fixtures.library.domain.generated.audits import Audit, AuditFinding, AuditResult
from tests.toy import MODULES, TOY_SCHEMA
from tests.unit.activity_helpers import Hook
from tests.unit.persistence.dependent_helpers import (
    A1,
    A2,
    AUDIT,
    LIB,
    LINK,
    R1,
    R2,
    R3,
    RESULT,
    audit,
    iri,
    is_stored,
    new_store,
    opened,
    result,
)
from tests.unit.persistence.referrer_helpers import StubRefusal

FINDING, OF_RESULT, CITES = (
    URIRef(LIB + name) for name in ("Finding", "of_result", "cites_finding")
)
LINK_F = DependenceLink(
    part_classes=[str(FINDING)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
)
LINK_BACK = DependenceLink(  # an audit may point back at a result: a loop of links
    part_classes=[str(AUDIT)], pointer=str(OF_RESULT), whole_classes=[str(RESULT)]
)
LINKS = (LINK, LINK_F)
F1, F3, F9 = iri("findings", 1), iri("findings", 3), iri("findings", 9)
C1 = iri("comments", 1)
LOADED = b"<https://example.org/a> <https://example.org/b> <https://example.org/c> ."


def finding(root: str, *wholes: str) -> list:
    """A finding that points to each of ``wholes`` (one is the legal number)."""
    triples = [(URIRef(root), RDF.type, FINDING)]
    return triples + [(URIRef(root), OF_RESULT, URIRef(w)) for w in wholes]


class Tree:
    """The versions of the stored tree, and its loaded graph."""

    a1 = r1 = r2 = f1 = ""
    loaded: URIRef


async def seeded(session) -> Tree:
    tree = Tree()
    tree.a1 = await session.add_graph(A1, audit(A1))
    tree.loaded = await session.load_graph(R1, LOADED, rdf_format=RdfFormat.TURTLE)
    tree.r1 = await session.add_graph(R1, result(R1, A1), [tree.loaded])
    tree.r2 = await session.add_graph(R2, result(R2, A1))
    tree.f1 = await session.add_graph(F1, finding(F1, R1))
    return tree


@pytest.fixture
async def store():
    return await new_store()


async def test_removing_the_whole_removes_every_part_in_one_request_and_one_activity(store):
    hook = Hook()
    async with opened(store, links=LINKS, on_commit=hook) as session:
        tree = await seeded(session)
        before = len(hook.calls)
        updates = len(store.sent("update"))
        await session.remove(A1, tree.a1)
        stored = [await is_stored(session, root) for root in (A1, R1, R2, F1)]
        assert stored == [False] * 4, "the whole and its three parts are gone"
        held = await store.query(FAKE_DATABASE, f"ASK {{ GRAPH <{tree.loaded}> {{ ?s ?p ?o }} }}")
        assert not held.askAnswer, "the loaded graph of a part went with it"
        assert len(store.sent("update")) == updates + 1, "one request"
        assert len(hook.calls) == before + 1, "one activity"
        activity = hook.calls[-1][0]
        assert isinstance(activity, Remove), "a Remove activity"
        assert sorted(i.entity for i in activity.invalidations or []) == sorted([A1, R1, R2, F1])


@pytest.mark.parametrize(("max_roots", "refused"), [(4, False), (3, True)], ids=["exact", "over"])
async def test_each_root_counts_once_against_max_roots(store, max_roots, refused):
    """A1 and R2 removed by the caller, R1 and F1 found: four roots, R2 not counted twice (A-7)."""
    async with opened(store, links=LINKS, max_roots=max_roots) as session:
        tree = await seeded(session)

        async def delete() -> None:
            async with session.transaction() as transaction:
                await transaction.remove(A1, tree.a1)
                await transaction.remove(R2, tree.r2)

        if refused:
            with pytest.raises(CommitTooLarge, match=str(max_roots)):
                await delete()
            assert await is_stored(session, A1), "nothing was written"
        else:
            await delete()
            stored = [await is_stored(session, root) for root in (A1, R1, R2, F1)]
            assert stored == [False] * 4, "each root removed once, F1 with them"


async def test_a_cascade_of_four_roots_sends_one_no_late_part_guard(store):
    async with opened(store, links=LINKS) as session:
        tree = await seeded(session)
        await session.remove(A1, tree.a1)
        request = store.sent("update")[-1]
        assert request.count("VALUES ?lroot") == 1, "one guard for the four removed roots (D-11)"


async def test_the_cascade_is_a_span_inside_the_commit_that_names_no_part(store, spans):
    async with opened(store, links=LINKS) as session:
        tree = await seeded(session)
        await session.remove(A1, tree.a1)
    *_, cascade = [s for s in spans() if s.name == "rp.session.cascade"]  # the last: the delete
    *_, commit = [s for s in spans() if s.name == "rp.session.commit"]
    assert cascade.attributes["rp.step"] == "cascade", "the step (PD-15)"
    assert cascade.parent.span_id == commit.context.span_id, "inside the commit's span"
    shown = " ".join(str(value) for value in cascade.attributes.values())
    assert not any(part in shown for part in (R1, R2, F1)), "no part's IRI in the span (PD-10)"


def audit_links() -> tuple[DependenceLink, ...]:
    """The links of the library's audits: a result depends on an audit, a finding on a result."""
    return (
        DependenceLink(
            part_classes=[LIB + "AuditResult"],
            pointer=LIB + "ofAudit",
            whole_classes=[LIB + "Audit"],
        ),
        DependenceLink(
            part_classes=[LIB + "AuditFinding"],
            pointer=LIB + "ofResult",
            whole_classes=[LIB + "AuditResult"],
        ),
    )


@pytest.mark.parametrize(("max_roots", "refused"), [(4, False), (3, True)], ids=["exact", "over"])
async def test_each_root_counts_once_against_max_roots_through_the_unit_of_work(
    store, max_roots, refused
):
    """The mapper counts the two roots the caller removed, the session the four of the commit; the
    session's count decides (A-7, PD-6)."""
    ids = {kind: iri(kind, 1) for kind in ("audits", "audit-results", "audit-findings")}
    second = iri("audit-results", 2)
    mapper = Mapper(
        load_schema(TOY_SCHEMA),
        generated_models(*MODULES, audits),
        limits=LimitSettings(max_roots=max_roots),
    )
    async with opened(store, links=audit_links(), max_roots=max_roots) as session:
        seed = UnitOfWork(session, mapper)
        for root in (
            Audit(id=ids["audits"], label="a"),
            AuditResult(id=ids["audit-results"], label="r1", of_audit=ids["audits"]),
            AuditResult(id=second, label="r2", of_audit=ids["audits"]),
            AuditFinding(id=ids["audit-findings"], label="f", of_result=ids["audit-results"]),
        ):
            seed.add(root)
            await seed.commit()
        work = UnitOfWork(session, mapper)
        work.remove(await work.get(Audit, ids["audits"]))
        work.remove(await work.get(AuditResult, second))
        if refused:
            with pytest.raises(CommitTooLarge, match=str(max_roots)):
                await work.commit()
            assert await is_stored(session, ids["audits"]), "nothing was written"
        else:
            await work.commit()
            stored = [await is_stored(session, root) for root in (*ids.values(), second)]
            assert stored == [False] * 4, "each root removed once, the parts found with them"


async def test_a_whole_with_three_parts_over_a_limit_of_three_is_too_large(store):
    async with opened(store, max_roots=3) as session:
        a1 = await session.add_graph(A1, audit(A1))
        for part in (R1, R2, R3):
            await session.add_graph(part, result(part, A1))
        with pytest.raises(CommitTooLarge, match="3"):
            await session.remove(A1, a1)
        assert await is_stored(session, R3), "nothing was written"


async def test_a_loop_of_links_is_read_once_and_ends(store):
    """A1 is a part of R1 and R1 a part of A1: discovery meets A1 again and stops (A-7)."""
    async with opened(store, links=(LINK, LINK_BACK)) as session:
        async with session.transaction() as transaction:
            await transaction.add_graph(A1, [*audit(A1), (URIRef(A1), OF_RESULT, URIRef(R1))])
            await transaction.add_graph(R1, result(R1, A1))
        _, _, version = await session.get_graph(A1)
        await session.remove(A1, version)
        assert not await is_stored(session, R1), "the part of the loop went"
        assert not await is_stored(session, A1), "the whole went, once"


async def test_a_cascade_reads_no_stored_state_per_part(store):
    """A-15: only the explicit root is read with ``_stored``; the parts use discovery's version."""
    async with opened(store, links=LINKS) as session:
        tree = await seeded(session)
        before = len(store.sent("query"))
        await session.remove(A1, tree.a1)
        reads = [q for q in store.sent("query")[before:] if str(v.CREATED) in q]
        assert len(reads) == 1, "one stored read, for the removed root"


# --- the same-transaction check: a part written under a whole the commit removes ---------------
async def add_late_result(transaction, tree):
    await transaction.add_graph(R3, result(R3, A1))


async def replace_held_part(transaction, tree):
    await transaction.replace_graph(R1, result(R1, A1), tree.r1)


async def add_under_cascaded_part(transaction, tree):
    await transaction.add_graph(F9, finding(F9, R1))


@pytest.mark.parametrize(
    ("write", "named"),
    [
        pytest.param(add_late_result, (A1, R3), id="add under the removed whole"),
        pytest.param(replace_held_part, (A1, R1), id="G-1 replace of a cascaded part"),
        pytest.param(add_under_cascaded_part, (F9, R1), id="A-2 add under a cascaded part"),
    ],
)
async def test_a_part_written_under_a_removed_whole_is_a_conflict_unsent(store, write, named):
    async with opened(store, links=LINKS) as session:
        tree = await seeded(session)
        updates = len(store.sent("update"))
        with pytest.raises(
            Conflict
        ) as error:  # not ValueError: the part is held, not collected twice
            async with session.transaction() as transaction:
                await write(transaction, tree)
                await transaction.remove(A1, tree.a1)
        assert error.value.iris == named, "the Conflict names the part and the whole"
        assert len(store.sent("update")) == updates, "nothing was sent"
        assert await is_stored(session, A1), "nothing was removed"


# --- the existing referrer pre-checks see the cascaded removals --------------------------------
async def test_a_referrer_added_in_the_commit_of_a_cascaded_part_is_in_use(store):
    refusal = StubRefusal(refusing=frozenset({FINDING}))
    async with opened(store, links=LINKS, removals=refusal) as session:
        tree = await seeded(session)
        updates = len(store.sent("update"))
        with pytest.raises(InUse) as error:
            async with session.transaction() as transaction:
                await transaction.add_graph(A2, [*audit(A2), (URIRef(A2), CITES, URIRef(F1))])
                await transaction.remove(A1, tree.a1)
        assert error.value.iris == (F1,), "the refused part is named"
        assert len(store.sent("update")) == updates, "nothing was sent"
        assert await is_stored(session, F1), "nothing was removed"


async def test_a_stored_referrer_of_a_cascaded_part_refuses_the_delete(store):
    refusal = StubRefusal(refusing=frozenset({FINDING}))
    async with opened(store, links=LINKS, removals=refusal) as session:
        await session.add_graph(A2, audit(A2))
        tree = await seeded(session)
        _, _, version = await session.get_graph(A2)
        await session.replace_graph(A2, [*audit(A2), (URIRef(A2), CITES, URIRef(F1))], version)
        with pytest.raises(InUse) as error:
            await session.remove(A1, tree.a1)
        assert error.value.iris == (F1,), "the cited part is named"
        assert await is_stored(session, R2), "nothing was removed"


async def test_a_comment_added_on_a_cascaded_part_is_a_conflict_unsent(store):
    pair = ((v.ANNOTATION, v.HAS_TARGET),)
    async with opened(store, links=LINKS, dependents=pair) as session:
        tree = await seeded(session)
        updates = len(store.sent("update"))
        with pytest.raises(Conflict) as error:
            async with session.transaction() as transaction:
                await transaction.add_graph(
                    C1,
                    [(URIRef(C1), RDF.type, v.ANNOTATION), (URIRef(C1), v.HAS_TARGET, URIRef(R1))],
                )
                await transaction.remove(A1, tree.a1)
        assert not isinstance(error.value, InUse), "a dependent comment is no referrer"
        assert error.value.iris == (C1, R1), "the comment and the part are named"
        assert len(store.sent("update")) == updates, "nothing was sent"


# --- parts that change between the discovery and the send (PD-7, PD-11, D-3) -------------------
async def test_a_part_removed_after_discovery_is_a_conflict_naming_the_whole(store):
    async with opened(store, links=LINKS) as session, opened(store, "ben", links=LINKS) as other:
        tree = await seeded(session)

        async def remove_part() -> None:
            await other.remove(R2, tree.r2)

        store.before_update = remove_part
        with pytest.raises(Conflict) as error:
            await session.remove(A1, tree.a1)
        assert error.value.iris == (A1,), "the whole is named, never the part"
        assert await is_stored(session, A1), "nothing was removed"


@pytest.mark.parametrize(
    ("late", "triples"),
    [
        pytest.param(R3, result(R3, A1), id="under the whole"),
        pytest.param(F3, finding(F3, R1), id="under a cascaded part"),
    ],
)
async def test_a_part_added_after_discovery_is_a_conflict_naming_the_whole(store, late, triples):
    async with opened(store, links=LINKS) as session, opened(store, "ben", links=LINKS) as other:
        tree = await seeded(session)

        async def add_part() -> None:
            await other.add_graph(late, triples)

        store.before_update = add_part
        with pytest.raises(Conflict) as error:
            await session.remove(A1, tree.a1)
        assert error.value.iris == (A1,), "the explicitly removed whole is named"
        assert await is_stored(session, R1), "nothing was removed"
