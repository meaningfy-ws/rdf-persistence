"""Parsing for graph loading (PD-6a, PD-8a); ``Session.load_graph`` writes the result."""

import io
import json

import anyio.to_thread
from rdflib import Graph

from rdf_persistence.domain.exceptions import InvalidGraph
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.services.jsonld import (
    ABSOLUTE_IRIS,
    INVALID_IRI,
    OBJECT_OR_ARRAY,
    InvalidIriRefused,
    NamedGraphRefused,
    NotADocumentRefused,
    RelativeIriRefused,
    RemoteContextRefused,
    triples_of,
)
from rdf_persistence.services.vocabulary import media_types

# rdflib takes a media type as the name of its format; the schema declares them (PD-11).
_MEDIA_TYPES = media_types(RdfFormat)

NOT_INLINE = "a JSON-LD context must be inline: remote, file and relative contexts are not followed"
ONE_GRAPH = "a loaded file holds one graph"


def _parse_jsonld(data: bytes) -> Graph:
    """The triples of a JSON-LD file, read by the one JSON-LD path (PD-6); the refusals are its own."""
    try:
        return triples_of(json.loads(data))
    except RemoteContextRefused as error:
        raise InvalidGraph(NOT_INLINE) from error
    except NamedGraphRefused as error:
        raise InvalidGraph(ONE_GRAPH) from error
    except RelativeIriRefused as error:
        raise InvalidGraph(ABSOLUTE_IRIS) from error
    except InvalidIriRefused as error:
        raise InvalidGraph(INVALID_IRI) from error
    except NotADocumentRefused as error:
        raise InvalidGraph(OBJECT_OR_ARRAY) from error
    except Exception as error:  # bad JSON, or what pyld and the N-Quads parser raise
        raise InvalidGraph(str(error) or type(error).__name__) from error


def _parse(data: bytes, rdf_format: RdfFormat) -> Graph:
    if rdf_format == RdfFormat.JSONLD:
        return _parse_jsonld(data)
    rdflib_format = _MEDIA_TYPES[rdf_format]  # an unknown format is a bug, not an invalid graph
    graph = Graph()
    try:
        graph.parse(io.BytesIO(data), format=rdflib_format)
    except Exception as error:
        raise InvalidGraph(str(error) or type(error).__name__) from error
    return graph


async def parse_graph(data: bytes, rdf_format: RdfFormat) -> Graph:
    """Parse ``data`` in a worker thread.

    Raises:
        InvalidGraph: The data does not parse as ``rdf_format``, or a JSON-LD file holds a named
            graph, a relative or invalid IRI, a context that is not inline, or is not an object or
            array (the message gives the reason).
    """
    return await anyio.to_thread.run_sync(_parse, data, rdf_format)
