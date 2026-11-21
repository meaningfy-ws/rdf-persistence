"""Every parse of SPARQL text goes through a wrapper that holds the parser lock while rdflib parses.

The lock is swapped for one that counts how deep it is held; each rdflib parser function is swapped for a
spy that notes the depth at the moment it runs, then parses for real.
"""

from collections.abc import Callable
from typing import Any

import pytest

from rdf_persistence.core.domain import sparql_parsing
from tests.unit.builders import RecordingLock

QUERY = "SELECT ?s WHERE { ?s ?p ?o }"
UPDATE = "INSERT DATA { <urn:a> <urn:b> <urn:c> }"


@pytest.fixture
def lock(monkeypatch: pytest.MonkeyPatch) -> RecordingLock:
    recording = RecordingLock()
    monkeypatch.setattr(sparql_parsing, "SPARQL_PARSER_LOCK", recording)  # X2
    return recording


def spy(monkeypatch: pytest.MonkeyPatch, name: str, lock: RecordingLock) -> list[int]:
    """Replace ``sparql_parsing.<name>`` by a function that records the lock depth, then calls the original."""
    depths: list[int] = []
    original: Callable[..., Any] = getattr(sparql_parsing, name)

    def recording(*args: Any, **kwargs: Any) -> Any:
        depths.append(lock.depth)
        return original(*args, **kwargs)

    monkeypatch.setattr(sparql_parsing, name, recording)  # X2
    return depths


@pytest.mark.parametrize(
    ("wrapper", "parser", "text"),
    [
        ("parse_query", "parseQuery", QUERY),
        ("parse_update", "parseUpdate", UPDATE),
        ("prepare_query", "prepareQuery", QUERY),
        ("prepare_update", "prepareUpdate", UPDATE),
    ],
)
def test_each_wrapper_holds_the_lock_while_rdflib_parses(monkeypatch, lock, wrapper, parser, text):
    depths = spy(monkeypatch, parser, lock)
    result = getattr(sparql_parsing, wrapper)(text)
    assert result is not None
    assert depths == [1], "rdflib parsed once, with the lock held"
    assert lock.depth == 0, "and the lock was let go before the caller got the result"


def test_prepare_update_applies_the_prefixes_it_is_given(lock):
    update = sparql_parsing.prepare_update("INSERT DATA { ex:a ex:b ex:c }", {"ex": "urn:example:"})
    assert update is not None
    assert lock.taken == 1
