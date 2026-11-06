"""Fixtures of the tenancy tests: Fuseki, a file store from a parametrised fixture, and a prefix per test.

The file store is the fake or Garage, and the tests run against both unchanged. Each test gets its own prefix, so the system database and the tenant databases
of one test never meet another's, and everything it made is dropped afterwards.
"""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence.adapters.s3 import S3FileStore
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import SETTINGS, toy_mapper
from tests.toy_service import drop_buckets, drop_databases, unique_prefix

FILE_STORES = ["fake", "garage"]


@pytest.fixture(params=FILE_STORES)
def files(request: pytest.FixtureRequest) -> FileStore:
    if request.param == "garage":
        server = request.getfixturevalue("garage")
        return S3FileStore(server.endpoint, server.key_id, server.secret, server.region)
    return FakeFileStore()


@pytest.fixture
def settings() -> ServiceSettings:
    return SETTINGS.model_copy(update={"prefix": unique_prefix()})


@pytest.fixture
async def tenancy(store, files, settings) -> AsyncIterator[Tenancy]:
    made = Tenancy(
        store, files, settings, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
    await made.ensure_system_database()
    yield made
    await drop_databases(store, settings.prefix)
    await drop_buckets(files, settings.prefix)
