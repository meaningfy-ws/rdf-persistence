"""The fixtures that tests of more than one theme share: the toy library's documents and a toy session.

They sit at the root of the unit tests because the tests that use them are spread over the themes
(thematic-structure PD-11: a helper used by two themes goes to ``tests/unit/``).
"""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence.api.services.documents import Documents
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import fake_session
from tests.toy import GENERATED, TENANT, TOY_SCHEMA


@pytest.fixture(scope="module")
def documents() -> Documents:
    return Documents(load_schema(TOY_SCHEMA), GENERATED)


@pytest.fixture(scope="module")
def book_class(documents: Documents):
    return documents.aggregates["books"]


@pytest.fixture(scope="module")
def scan_class(documents: Documents):
    return documents.aggregates["scans"]


@pytest.fixture
async def toy_session() -> AsyncIterator[Session]:
    """A session on the toy tenant's database, over the fake store."""
    async with fake_session(
        tenant_iri=TENANT, listings=Listings(load_schema(TOY_SCHEMA))
    ) as session:
        yield session
