"""Fixtures the persistence unit tests share."""

import pytest

from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE


@pytest.fixture
async def store() -> FakeStore:
    """A fake store holding the one empty dataset the sessions open."""
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake
