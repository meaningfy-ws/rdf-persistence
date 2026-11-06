"""Fixtures of the tenancy tests: Fuseki, a file store from a parametrised fixture, and a prefix per test.

The file store is the fake or Garage, and the tests run against both unchanged. Each test gets its own prefix, so the system database and the tenant databases
of one test never meet another's, and everything it made is dropped afterwards.
"""

import uuid
from collections.abc import AsyncIterator

import pytest

from rdf_persistence.adapters.s3 import S3FileStore
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.domain.iris import system_database_name, tenant_name_prefix
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import SETTINGS, toy_mapper

FILE_STORES = ["fake", "garage"]


@pytest.fixture(params=FILE_STORES)
def files(request: pytest.FixtureRequest) -> FileStore:
    if request.param == "garage":
        server = request.getfixturevalue("garage")
        return S3FileStore(server.endpoint, server.key_id, server.secret, server.region)
    return FakeFileStore()


@pytest.fixture
def settings() -> ServiceSettings:
    return SETTINGS.model_copy(update={"prefix": f"t{uuid.uuid4().hex[:12]}"})


@pytest.fixture
async def tenancy(store, files, settings) -> AsyncIterator[Tenancy]:
    made = Tenancy(store, files, settings, mapper=toy_mapper(), access_class=LibraryAccess)
    await made.ensure_system_database()
    yield made
    mine = (system_database_name(settings.prefix), tenant_name_prefix(settings.prefix))
    for name in await store.list_datasets():
        if name.startswith(mine[1]) or name == mine[0]:
            await store.drop_dataset(name)
    for bucket in await files.list_buckets(mine[1]):
        await files.delete_bucket(bucket)
