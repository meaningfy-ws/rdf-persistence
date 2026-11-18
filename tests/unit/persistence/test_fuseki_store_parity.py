"""FusekiStore after the split says what the pre-split class said (thematic-structure PD-7, TC-43).

The expected errors and texts were read from the Fuseki store of commit 0173b73, before the split:
the very error class and the message of each status, for the data plane and for the administration.
"""

import httpx
import pytest

from rdf_persistence.core.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    StoreUnavailable,
)
from rdf_persistence.persistence.adapters.fuseki import FusekiStore

URL = "http://fuseki.test:3030"


def store_answering(status: int) -> FusekiStore:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=b"body", headers={"content-type": "text/plain"})

    return FusekiStore(URL, "u", "p", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("operation", "status", "error", "message"),
    [
        ("query", 400, BadQuery, "Fuseki refused the SPARQL text as malformed"),
        ("query", 404, DatabaseGone, "Fuseki answered 404 for /d/query"),
        ("update", 405, DatabaseGone, "Fuseki answered 405 for /d/update"),
        ("update", 409, Conflict, "Fuseki answered 409 for /d/update"),
        ("update", 500, StoreUnavailable, "Fuseki answered 500"),
        ("update", 403, StoreUnavailable, "Fuseki answered 403"),
        ("update", 302, StoreUnavailable, "Fuseki answered 302"),
        ("export", 404, DatabaseGone, "Fuseki answered 404 for /d/data"),
        ("import", 409, Conflict, "Fuseki answered 409 for /d/data"),
        ("create", 404, NotFound, "Fuseki answered 404 for /$/datasets"),
        ("create", 405, NotFound, "Fuseki answered 405 for /$/datasets"),
        ("create", 409, Conflict, "Fuseki answered 409 for /$/datasets"),
        ("drop", 404, NotFound, "Fuseki answered 404 for /$/datasets/d"),
        ("list", 404, NotFound, "Fuseki answered 404 for /$/datasets"),
        ("list", 502, StoreUnavailable, "Fuseki answered 502"),
    ],
)
async def test_every_status_maps_to_the_old_error_with_the_old_text(  # TC-43
    operation, status, error, message
):
    store = store_answering(status)
    calls = {
        "query": lambda: store.query("d", "ASK {}"),
        "update": lambda: store.update("d", "X"),
        "export": lambda: store.export_quads("d"),
        "import": lambda: store.import_quads("d", b""),
        "create": lambda: store.create_dataset("d"),
        "drop": lambda: store.drop_dataset("d"),
        "list": lambda: store.list_datasets(),
    }
    with pytest.raises(error) as raised:
        await calls[operation]()
    assert type(raised.value) is error, "the very class, not a subclass of it"
    assert str(raised.value) == message
