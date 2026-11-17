"""Scenario 'the same book three ways' (rp-service-api), against Fuseki."""

import httpx
from pyld import jsonld
from rdflib import Graph

from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import graph_iri
from rdf_persistence.testkit import assert_isomorphic
from tests.integration.api.conftest import make_book
from tests.toy_service import ToyService, assert_problem, principal_of


def triples_of(toy: ToyService, response: httpx.Response, media_type: str) -> Graph:
    """The RDF a response describes: Turtle is parsed, JSON gets the generated context, JSON-LD is read as served, with its own."""
    if media_type == TURTLE:
        return Graph().parse(data=response.text, format="turtle")
    document = response.json()
    if media_type == JSON:  # plain JSON is JSON-LD with the context its Link header names
        document = {"@context": toy.kit.documents.context, **document}
    return Graph().parse(
        data=jsonld.to_rdf(document, {"format": "application/n-quads"}), format="nt"
    )


async def test_the_same_book_is_described_by_the_same_triples_in_json_json_ld_and_turtle(
    toy, client
) -> None:
    book = (await make_book(toy, client)).headers["location"]
    graphs = {}
    for media_type in (JSON, JSON_LD, TURTLE):
        response = await client.get(book, headers={**toy.bearer("ada"), "Accept": media_type})
        assert response.status_code == 200, f"{media_type}: {response.text}"
        assert response.headers["content-type"].split(";")[0] == media_type, (
            "the media type asked for"
        )
        graphs[media_type] = triples_of(toy, response, media_type)
    for media_type in (JSON_LD, TURTLE):
        assert_isomorphic(graphs[JSON], graphs[media_type])


async def test_the_triples_served_are_the_triples_stored(toy, client) -> None:
    created = await make_book(toy, client)
    iri = created.json()["id"]
    tenant = iri.rsplit("/", 2)[0]
    async with toy.kit.session(tenant, principal_of("ada")) as session:
        stored, graph, _ = await session.get_graph(iri)
    content = Graph()
    for s, p, o in stored:
        if s != graph_iri(iri) and p not in v.BOOKKEEPING_PREDICATES:
            content.add((s, p, o))
    served = await client.get(
        created.headers["location"], headers={**toy.bearer("ada"), "Accept": TURTLE}
    )
    assert_isomorphic(content, Graph().parse(data=served.text, format="turtle"))


async def test_an_accept_the_service_cannot_meet_is_a_406_problem(toy, client) -> None:
    book = (await make_book(toy, client)).headers["location"]
    response = await client.get(book, headers={**toy.bearer("ada"), "Accept": "application/xml"})
    problem = assert_problem(response, 406, "not-acceptable")
    assert problem.title == "Not acceptable", "the fixed title"


async def test_a_body_the_service_cannot_read_is_a_415_problem(toy, client) -> None:
    tenant = (await make_book(toy, client)).headers["location"].rsplit("/", 2)[0]
    response = await client.post(
        f"{tenant}/books",
        content="<book/>",
        headers={**toy.bearer("ada"), "Content-Type": "application/xml"},
    )
    assert_problem(response, 415, "unsupported-media-type")
