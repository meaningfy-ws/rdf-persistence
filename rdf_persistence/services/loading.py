"""Graph loading (PD-6a, PD-8a): parse a file of RDF and put it in its own named graph.

The loaded graph is written to ``{aggregate_iri}/content/{uuid4}``. It becomes the aggregate's
only when the caller's commit passes the returned IRI as ``loaded_graphs``.
"""

import io

import anyio.to_thread
from rdflib import Graph, URIRef

from rdf_persistence.domain.errors import InvalidGraph
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import loaded_graph_iri
from rdf_persistence.services.store import Store

_RDFLIB_FORMATS = {
    RdfFormat.TURTLE: "turtle",
    RdfFormat.RDFXML: "xml",
    RdfFormat.NTRIPLES: "nt",
    RdfFormat.JSONLD: "json-ld",
}


def _parse(data: bytes, format: RdfFormat) -> Graph:
    graph = Graph()
    try:
        graph.parse(io.BytesIO(data), format=_RDFLIB_FORMATS[format])
    except Exception as error:
        raise InvalidGraph(str(error) or type(error).__name__) from error
    return graph


async def load_graph(
    store: Store, database: str, aggregate_iri: str, data: bytes, *, format: RdfFormat
) -> URIRef:
    """Parse ``data`` and write it to a new named graph of the aggregate; returns its IRI.

    The caller registers the graph by passing the IRI as ``loaded_graphs`` in its commit.

    Raises:
        InvalidGraph: The data does not parse as ``format``; nothing is written.
        DatabaseGone: The tenant database does not exist.
    """
    graph = await anyio.to_thread.run_sync(_parse, data, format)
    iri = loaded_graph_iri(aggregate_iri)
    await store.put_graph(database, iri, graph)
    return iri
