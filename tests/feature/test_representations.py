"""Steps of ``representations.feature``: a book read in each RDF serialisation, on the toy service with the fakes (rp-service-api)."""

import asyncio

import httpx
import pytest
from pyld import jsonld
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import Dataset, Graph

from rdf_persistence.domain.layout import graph_iri
from rdf_persistence.domain.media import (
    JSON,
    JSON_LD,
    N_QUADS,
    N_TRIPLES,
    RDF_XML,
    TRIG,
    TURTLE,
)
from rdf_persistence.testkit import assert_isomorphic
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, assert_problem

scenarios("representations.feature")

MEDIA_TYPES = {
    "plain JSON": JSON,
    "JSON-LD": JSON_LD,
    "Turtle": TURTLE,
    "N-Triples": N_TRIPLES,
    "N-Quads": N_QUADS,
    "TriG": TRIG,
    "RDF/XML": RDF_XML,
}


class Run:
    """One service and what the scenario has seen of it so far."""

    def __init__(self) -> None:
        self.toy = ToyService()
        asyncio.run(self.toy.kit.tenancy.ensure_system_database())
        self.headers = self.toy.bearer("ada")
        self.tenant_path = ""
        self.book_path = ""
        self.book_iri = ""
        self.answer: httpx.Response | None = None

    def get(self, path: str, media_type: str) -> httpx.Response:
        async def send() -> httpx.Response:
            async with self.toy.client() as http:
                return await http.get(path, headers={**self.headers, "Accept": media_type})

        return asyncio.run(send())

    def triples_of(self, response: httpx.Response, media_type: str) -> Graph:
        """The RDF a response describes: plain JSON gets the generated context, JSON-LD is read as served."""
        if media_type in (JSON, JSON_LD):
            document = response.json()
            if media_type == JSON:  # plain JSON is JSON-LD with the context its Link header names
                document = {"@context": self.toy.kit.documents.context, **document}
            return Graph().parse(data=jsonld.to_rdf(document, {"format": N_QUADS}), format="nt")
        triples = Graph()
        for quad in Dataset().parse(data=response.text, format=media_type).quads():
            triples.add(quad[:3])
        return triples


@pytest.fixture
def run() -> Run:
    return Run()


@given("Ada's library holds a book")
def _library_with_book(run: Run) -> None:
    async def create() -> tuple[httpx.Response, httpx.Response]:
        async with run.toy.client() as http:
            tenant = await http.post("/libraries", json=TENANT_BODY, headers=run.headers)
            book = await http.post(
                f"{tenant.headers['location']}/books", json=DUNE_BODY, headers=run.headers
            )
            return tenant, book

    tenant, book = asyncio.run(create())
    assert tenant.status_code == 201, tenant.text
    assert book.status_code == 201, book.text
    run.tenant_path = tenant.headers["location"]
    run.book_path = book.headers["location"]
    run.book_iri = book.json()["id"]


@when(parsers.parse("Ada reads the book as {representation}"))
def _read_book(run: Run, representation: str) -> None:
    run.answer = run.get(run.book_path, MEDIA_TYPES[representation])


@when(parsers.parse("Ada lists the books as {representation}"))
def _list_books(run: Run, representation: str) -> None:
    run.answer = run.get(f"{run.tenant_path}/books", MEDIA_TYPES[representation])


@then(parsers.parse("the book is served as {representation}"))
def _served_as(run: Run, representation: str) -> None:
    assert run.answer is not None, "the book was read"
    assert run.answer.status_code == 200, run.answer.text
    assert run.answer.headers["content-type"].split(";")[0] == MEDIA_TYPES[representation], (
        "the answer is in the representation asked for"
    )


@then("it describes the same triples as the book read as plain JSON")
def _same_triples(run: Run) -> None:
    assert run.answer is not None, "the book was read"
    media_type = run.answer.headers["content-type"].split(";")[0]
    plain = run.get(run.book_path, JSON)
    assert plain.status_code == 200, plain.text
    assert_isomorphic(run.triples_of(plain, JSON), run.triples_of(run.answer, media_type))


def _quads(run: Run) -> list[tuple]:
    assert run.answer is not None, "the book was read"
    media_type = run.answer.headers["content-type"].split(";")[0]
    quads = list(Dataset().parse(data=run.answer.text, format=media_type).quads())
    assert quads, "the book is shown"
    return quads


@then("every statement is in the book's graph")
def _in_the_graph(run: Run) -> None:
    assert {str(q[3]) for q in _quads(run)} == {str(graph_iri(run.book_iri))}, (
        "the book's statements are in the graph it was read from"
    )


@then("none of them is about that graph")
def _none_about_the_graph(run: Run) -> None:
    assert all(str(q[0]) != str(graph_iri(run.book_iri)) for q in _quads(run)), (
        "the graph is not described in its own answer"
    )


@then("the answer is 406 with a problem response")
def _not_acceptable(run: Run) -> None:
    assert run.answer is not None, "the books were listed"
    assert_problem(run.answer, 406, "not-acceptable")
