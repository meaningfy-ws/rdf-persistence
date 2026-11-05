"""The Store conformance suite against a real Fuseki; the same cases run on the fake."""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.testkit.store_conformance import CASES, run_case


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_fuseki_conforms(case, store):
    await run_case(case, store)
