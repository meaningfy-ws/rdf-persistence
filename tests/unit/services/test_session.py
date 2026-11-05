"""What the session refuses before it reaches the store (no network: a store that must stay unused)."""

import httpx
import pytest

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.services.session import open_session

TENANT = "http://example.org/libraries/6f1c"
ME = Principal(id="http://example.org/people/me")


def unreachable(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"the session reached the store with {request.url}")


@pytest.fixture
async def store():
    async with FusekiStore(
        "http://fuseki.test", "u", "p", transport=httpx.MockTransport(unreachable)
    ) as s:
        yield s


OUTSIDE = "http://example.org/libraries/other-tenant/books/1"


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("get_graph", (OUTSIDE,)),
        ("add_graph", (OUTSIDE, [])),
        ("replace_graph", (OUTSIDE, [], "v")),
        ("remove", (OUTSIDE, "v")),
    ],
)
async def test_an_iri_outside_the_tenant_is_refused_before_any_request(store, method, arguments):
    async with open_session(store, database="db", tenant_iri=TENANT, principal=ME) as session:
        with pytest.raises(ValueError, match="not inside the tenant"):
            await getattr(session, method)(*arguments)
