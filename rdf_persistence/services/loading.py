"""Parsing for graph loading (PD-6a, PD-8a); ``Session.load_graph`` writes the result."""

import io
import json
from typing import Any

import anyio.to_thread
from rdflib import Graph

from rdf_persistence.domain.exceptions import InvalidGraph
from rdf_persistence.domain.generated.rp_files import RdfFormat

_RDFLIB_FORMATS = {
    RdfFormat.TURTLE: "turtle",
    RdfFormat.RDFXML: "xml",
    RdfFormat.NTRIPLES: "nt",
    RdfFormat.JSONLD: "json-ld",
}


NOT_INLINE = "a JSON-LD context must be inline: remote, file and relative contexts are not followed"


def _refers_outside(node: Any) -> bool:
    """True if a ``@context`` anywhere in ``node`` is not an inline object (or array of them)."""
    if isinstance(node, list):
        return any(_refers_outside(item) for item in node)
    if not isinstance(node, dict):
        return False
    for key, value in node.items():
        if key == "@import" or (key == "@context" and not _inline(value)):
            return True
        if _refers_outside(value):
            return True
    return False


def _inline(context: Any) -> bool:
    items = context if isinstance(context, list) else [context]
    return all(item is None or isinstance(item, dict) for item in items)


def _refuse_outside_contexts(data: bytes) -> None:
    """Refuse JSON-LD whose contexts rdflib would fetch or read (PD-8c); bad JSON is the parser's to report."""
    try:
        document = json.loads(data)
    except ValueError:
        return
    if _refers_outside(document):
        raise InvalidGraph(NOT_INLINE)


def _parse(data: bytes, rdf_format: RdfFormat) -> Graph:
    rdflib_format = _RDFLIB_FORMATS[rdf_format]  # an unknown format is a bug, not an invalid graph
    if rdf_format == RdfFormat.JSONLD:
        _refuse_outside_contexts(data)
    graph = Graph()
    try:
        graph.parse(io.BytesIO(data), format=rdflib_format)
    except Exception as error:
        raise InvalidGraph(str(error) or type(error).__name__) from error
    return graph


async def parse_graph(data: bytes, rdf_format: RdfFormat) -> Graph:
    """Parse ``data`` in a worker thread.

    Raises:
        InvalidGraph: The data does not parse as ``rdf_format``.
    """
    return await anyio.to_thread.run_sync(_parse, data, rdf_format)
