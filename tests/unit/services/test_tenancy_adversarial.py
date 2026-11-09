"""Stage 1 of mwb2-adoption-fixes, attacked: the rename and the root label check (PD-3) at their edges."""

import pytest
from pydantic import ValidationError
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from rdf_persistence.domain.exceptions import Conflict, InvalidBody, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import tenant_resource_name
from rdf_persistence.services import vocabulary
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, SETTINGS, library_slots, toy_mapper

CREATOR = Principal(id=ADA)
BEN = Principal(id=BOB)
OTHER = "https://example.org/other"


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
async def tenancy(store) -> Tenancy:
    made = Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )
    await made.ensure_system_database()
    return made


async def _root_label(store, tenant: str) -> str:
    async with open_session(
        store,
        database=tenant_resource_name(SETTINGS.prefix, tenant),
        tenant_iri=tenant,
        principal=CREATOR,
    ) as session:
        return (await UnitOfWork(session, toy_mapper()).get(Library, tenant)).label


async def _both(tenancy, store, tenant: str) -> tuple[str, str]:
    return (await tenancy.get(tenant))[0].label, await _root_label(store, tenant)


async def test_renaming_an_unknown_tenant_is_not_found_and_writes_nothing(tenancy, store):
    writes = len(store.sent("update"))
    with pytest.raises(NotFound):
        await tenancy.rename(f"{SETTINGS.base}libraries/nope", "B", '"v"', BEN)
    assert len(store.sent("update")) == writes, "nothing was written for an unknown tenant"


async def test_a_root_write_that_conflicts_leaves_the_record_and_the_root_alone(tenancy, store):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    before = await _both(tenancy, store, summary.id)
    store.on("update", Conflict("root moved"), times=1)  # the rename's first update: the root's
    with pytest.raises(Conflict):
        await tenancy.rename(summary.id, "B", version, BEN)
    assert await _both(tenancy, store, summary.id) == before, "neither side changed"
    assert (await tenancy.get(summary.id))[1] == version, "the record's version is unmoved"


async def test_a_rename_to_the_same_label_still_moves_the_record_version(tenancy, store):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    new = await tenancy.rename(summary.id, "A", version, BEN)
    assert await _both(tenancy, store, summary.id) == ("A", "A"), (
        "a same-label rename leaves both sides as they were"
    )
    assert new != version, "a rename is a write of the record: the old version is spent"


async def test_two_renames_in_a_row_each_need_the_version_the_last_answered(tenancy, store):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    second = await tenancy.rename(summary.id, "B", version, BEN)
    await tenancy.rename(summary.id, "C", second, BEN)
    assert await _both(tenancy, store, summary.id) == ("C", "C"), (
        "the last rename won on both sides"
    )
    with pytest.raises(Conflict):
        await tenancy.rename(summary.id, "D", second, BEN)
    assert await _both(tenancy, store, summary.id) == ("C", "C"), "the stale one changed nothing"


@pytest.mark.parametrize("label", ["", "   "])
async def test_an_invalid_label_is_refused_before_the_root_is_written(tenancy, store, label):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    before = await _both(tenancy, store, summary.id)
    with pytest.raises(ValidationError):
        await tenancy.rename(summary.id, label, version, BEN)
    assert await _both(tenancy, store, summary.id) == before, (
        "FAILS today: rename writes the root first and validates the label on the record after, "
        "so a refused label is already stored in the root"
    )


async def test_a_label_with_a_trailing_period_reaches_both_sides_verbatim(tenancy, store):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.rename(summary.id, "Ghent.", version, BEN)
    assert await _both(tenancy, store, summary.id) == ("Ghent.", "Ghent."), (
        "the period is kept on both sides"
    )


# --- vet_root ---------------------------------------------------------------------------------


def _label(predicate_of_label: URIRef, tenant: str, *values: str, subject: str | None = None):
    return [(URIRef(subject or tenant), predicate_of_label, Literal(v)) for v in values]


@pytest.fixture
def label_predicate() -> URIRef:
    return vocabulary.predicate("label")


async def test_vet_root_accepts_exactly_the_records_label(tenancy, label_predicate):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    await tenancy.vet_root(summary.id, _label(label_predicate, summary.id, "A"))


@pytest.mark.parametrize(
    "labels", [(), ("A", "B"), ("B",), ("A", "A2")], ids=["none", "two", "other", "extra"]
)
async def test_vet_root_refuses_none_two_or_other_labels(tenancy, label_predicate, labels):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    with pytest.raises(InvalidBody, match="label route"):
        await tenancy.vet_root(summary.id, _label(label_predicate, summary.id, *labels))


async def test_vet_root_ignores_the_label_of_another_subject(tenancy, label_predicate):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    triples = [
        *_label(label_predicate, summary.id, "A"),
        *_label(label_predicate, summary.id, "Z", subject=OTHER),
    ]
    await tenancy.vet_root(summary.id, triples)


async def test_vet_root_does_not_take_another_subjects_label_for_the_roots(
    tenancy, label_predicate
):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    only_other = _label(label_predicate, summary.id, "A", subject=OTHER)
    with pytest.raises(InvalidBody):
        await tenancy.vet_root(summary.id, only_other)


async def test_vet_root_on_an_unknown_tenant_is_not_found(tenancy, label_predicate):
    with pytest.raises(NotFound):
        await tenancy.vet_root(f"{SETTINGS.base}libraries/nope", [])


async def test_vet_root_compares_the_lexical_form_not_the_datatype(tenancy, label_predicate):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    typed = [(URIRef(summary.id), label_predicate, Literal("A", lang="en"))]
    await tenancy.vet_root(
        summary.id, typed
    )  # documents today's behaviour: the language is ignored


async def test_a_type_triple_does_not_count_as_a_label(tenancy, label_predicate):
    summary = await tenancy.create("A", library_slots(), CREATOR)
    triples = [(URIRef(summary.id), RDF.type, URIRef(OTHER))]
    with pytest.raises(InvalidBody):
        await tenancy.vet_root(summary.id, triples)
