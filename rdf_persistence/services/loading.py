"""Parsing for graph loading (PD-6a, PD-8a); ``Session.load_graph`` writes the result."""

import io

import anyio.to_thread
from rdflib import Graph

from rdf_persistence.domain.errors import InvalidGraph
from rdf_persistence.domain.generated.rp_files import RdfFormat

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


async def parse_graph(data: bytes, format: RdfFormat) -> Graph:
    """Parse ``data`` in a worker thread.

    Raises:
        InvalidGraph: The data does not parse as ``format``.
    """
    return await anyio.to_thread.run_sync(_parse, data, format)
