"""A JSON-LD file whose context is not inline never reaches a server (needs a local server).

The refusal itself, with its message, is tested in tests/unit/services/test_loading.py.

rdflib fetches a remote context through ``urllib``, which ``httpx.MockTransport`` cannot catch, so
the proof that nothing is fetched needs a real listener on 127.0.0.1. No container is started.
"""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from rdf_persistence import InvalidGraph
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.services.loading import parse_graph


class _Recorder(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append(self.path)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/ld+json")
        self.end_headers()
        self.wfile.write(b'{"@context": {"title": "http://purl.org/dc/terms/title"}}')

    def log_message(self, *args):  # silence
        pass


@pytest.fixture
def context_server() -> Iterator[HTTPServer]:
    """A local server that records every request made to it."""
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    server.requests = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def jsonld(context: object) -> bytes:
    return json.dumps(
        {"@context": context, "@id": "https://example.org/b", "title": "Dune"}
    ).encode()


NON_INLINE = {
    "iri": lambda url: jsonld(url),
    "iri in an array": lambda url: jsonld([{"x": "http://example.org/x"}, url]),
    "file iri": lambda _: jsonld("file:///etc/hostname"),
    "bare path": lambda _: jsonld("/etc/hostname"),
    "relative path": lambda _: jsonld("context.jsonld"),
    "nested in a node": lambda url: json.dumps(
        {
            "@id": "https://example.org/b",
            "http://example.org/p": {"@context": url, "@id": "https://example.org/c"},
        }
    ).encode(),
    "in a graph array": lambda url: json.dumps(
        [{"@context": url, "@id": "https://example.org/b"}]
    ).encode(),
    "scoped in a term": lambda url: jsonld(
        {"title": {"@id": "http://purl.org/dc/terms/title", "@context": url}}
    ),
    "@import": lambda url: jsonld({"@import": url}),
}


@pytest.mark.parametrize("make", NON_INLINE.values(), ids=NON_INLINE.keys())
async def test_a_jsonld_context_that_is_not_inline_never_reaches_the_server(context_server, make):
    """The refusal and its message are proved in the unit lane; here only that the server is not asked."""
    url = f"http://127.0.0.1:{context_server.server_port}/context.jsonld"
    with pytest.raises(InvalidGraph):
        await parse_graph(make(url), RdfFormat.JSONLD)
    assert context_server.requests == [], "the server was never asked"
