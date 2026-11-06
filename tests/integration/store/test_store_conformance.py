"""The Store conformance suite against a real Fuseki; the same cases run on the fake."""

import pytest

from rdf_persistence.testkit.store_conformance import CASES, run_case


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_fuseki_conforms(case, store):
    await run_case(case, store)
