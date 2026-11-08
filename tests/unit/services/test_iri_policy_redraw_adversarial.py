"""Re-drawing a clashing tenant id at its boundary: 4, 5 and 6 clashes (iri-policy PD-5)."""

from uuid import UUID

import pytest

from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.services.tenancy import MAX_TENANT_DRAWS
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.toy import library_slots
from tests.unit.services.test_tenancy import CREATOR, PREFIX, _tenancy_drawing


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


TAKEN = str(UUID(int=1))
FREE = str(UUID(int=2))


async def made(store, files, *ids: str):
    tenancy = _tenancy_drawing(store, files, *ids)
    await tenancy.ensure_system_database()
    await store.create_dataset(PREFIX + TAKEN.replace("-", ""))  # an orphan database holds TAKEN
    return tenancy


async def test_the_last_permitted_draw_may_be_the_free_one(store, files):
    tenancy = await made(store, files, *[TAKEN] * (MAX_TENANT_DRAWS - 1), FREE)
    created = await tenancy.create("Ghent", library_slots(), CREATOR)
    assert created.id.endswith(FREE)


async def test_five_clashes_fail_without_a_sixth_draw(store, files):
    tenancy = await made(
        store, files, *[TAKEN] * MAX_TENANT_DRAWS
    )  # a sixth draw would raise StopIteration
    with pytest.raises(PersistenceError, match="no free tenant id"):
        await tenancy.create("Ghent", library_slots(), CREATOR)


async def test_reserved_words_do_not_use_up_the_draws_of_the_clash_budget(store, files):
    tenancy = await made(store, files, "meta", *[TAKEN] * (MAX_TENANT_DRAWS - 1), "access", FREE)
    created = await tenancy.create("Ghent", library_slots(), CREATOR)
    assert created.id.endswith(FREE)


async def test_a_clash_with_a_live_tenants_access_record_alone_is_drawn_again(store, files):
    tenancy = await made(store, files, FREE, FREE, str(UUID(int=3)))
    first = await tenancy.create("Ghent", library_slots(), CREATOR)
    second = await tenancy.create("Bruges", library_slots(), CREATOR)
    assert first.id != second.id
