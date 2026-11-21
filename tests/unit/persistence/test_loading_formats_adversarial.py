"""A loaded JSON-LD file that breaks the one path is refused and writes nothing (PD-6)."""

import json
from collections.abc import AsyncIterator

import pytest

from rdf_persistence import InvalidGraph
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.files.domain.generated.rp_files import RdfFormat
from rdf_persistence.persistence.services.jsonld import ABSOLUTE_IRIS
from rdf_persistence.persistence.services.loading import NOT_INLINE, ONE_GRAPH
from rdf_persistence.testkit import FakeStore, fake_session, no_network  # noqa: F401  (fixture)
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.unit.persistence.loading_helpers import AGGREGATE, TENANT

EX = "https://ex.org/"
P = "http://ex.org/p"


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator:
    async with fake_session(
        store, tenant_iri=TENANT, principal=Principal(id="https://example.org/people/ada")
    ) as opened:
        yield opened


def assert_store_untouched(store: FakeStore) -> None:
    for kind in ("put_graph", "update", "query"):
        assert store.sent(kind) == [], f"a refused file reached the store ({kind})"


REFUSED = {
    "remote context": ({"@context": "http://x.invalid/c", "@id": EX + "a"}, NOT_INLINE),
    "file context": ({"@context": "file:///etc/hostname", "@id": EX + "a"}, NOT_INLINE),
    "relative context": ({"@context": "c.jsonld", "@id": EX + "a"}, NOT_INLINE),
    "@import": ({"@context": {"@import": "http://x.invalid/c"}, "@id": EX + "a"}, NOT_INLINE),
    "context array": ({"@context": [{"p": P}, "http://x.invalid/c"], "@id": EX + "a"}, NOT_INLINE),
    "nested context": (
        {"@id": EX + "a", P: {"@context": "http://x.invalid/c", "@id": EX + "b"}},
        NOT_INLINE,
    ),
    "named graph": ({"@id": "urn:g", "@graph": [{"@id": EX + "a", P: "x"}]}, ONE_GRAPH),
    "blank-named graph": ({"@id": "_:g", "@graph": [{"@id": EX + "a", P: "x"}]}, ONE_GRAPH),
    "nested graph": ({"@id": EX + "a", P: {"@graph": [{"@id": EX + "b", P: "x"}]}}, ONE_GRAPH),
    "relative subject": ({"@id": "book1", P: "x"}, ABSOLUTE_IRIS),
    "relative object": ({"@id": EX + "a", P: {"@id": "b"}}, ABSOLUTE_IRIS),
}


@pytest.mark.usefixtures("no_network")
@pytest.mark.parametrize("name", REFUSED, ids=list(REFUSED))
async def test_a_refused_jsonld_file_reaches_neither_the_network_nor_the_store(
    store, session, name: str
) -> None:
    """Probe of PD-6 (error matrix rows 1, 3 and 4): refusal text, no fetch, no marker, no graph."""
    document, message = REFUSED[name]
    with pytest.raises(InvalidGraph) as raised:
        await session.load_graph(
            AGGREGATE, json.dumps(document).encode(), rdf_format=RdfFormat.JSONLD
        )
    assert str(raised.value) == message, f"{name}: the toolkit's own refusal"
    assert_store_untouched(store)


async def test_a_null_base_file_does_not_load_as_an_empty_graph(store, session) -> None:
    """found T-1: a file with ``"@base": null`` and a relative ``@id`` creates an empty graph.

    Expected InvalidGraph (ABSOLUTE_IRIS) and no write; actual a graph holding no statement.
    """
    data = json.dumps({"@context": {"@base": None}, "@id": "a", P: "x"}).encode()
    with pytest.raises(InvalidGraph):
        await session.load_graph(AGGREGATE, data, rdf_format=RdfFormat.JSONLD)
    assert_store_untouched(store)


async def test_a_scalar_json_file_does_not_load_as_an_empty_graph(store, session) -> None:
    """found T-6: a file holding ``123`` or ``true`` is JSON, not JSON-LD, and loads as an empty graph."""
    for data in (b"123", b"true"):
        with pytest.raises(InvalidGraph):
            await session.load_graph(AGGREGATE, data, rdf_format=RdfFormat.JSONLD)
        assert_store_untouched(store)
