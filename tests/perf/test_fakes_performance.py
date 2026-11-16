"""The fake store's splitter scans an unterminated long string in linear time (moved from the unit lane, rule 12)."""

import time

import pytest

from rdf_persistence.domain.exceptions import BadQuery
from rdf_persistence.testkit import FakeStore

NAME = "atomic"
BUDGET_SECONDS = 1


@pytest.mark.parametrize("quote", ['"""', "'''"], ids=["double", "single"])
async def test_an_unterminated_long_string_is_refused_without_backtracking_forever(quote):
    store = FakeStore()
    await store.create_dataset(NAME)
    started = time.monotonic()
    with pytest.raises(BadQuery):
        await store.update(NAME, f"INSERT DATA {{ <urn:s> <urn:p> {quote}" + "\\a" * 40)
    seconds = time.monotonic() - started
    assert seconds < BUDGET_SECONDS, f"the splitter took {seconds:.2f} s on a long string"
