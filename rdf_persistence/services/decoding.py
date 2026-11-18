"""Decoding a stored activity into its most specific generated class (aggregate-events PD-16).

Apart from ``provenance`` because it needs the mapper, which imports the session; ``provenance`` may not.
"""

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError
from rdflib import RDF, Graph, URIRef

from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.provenance.services.provenance import activity_class_of
from rdf_persistence.services.mapper import GeneratedModels, Mapper


def decode_activity(
    view: SchemaView, models: GeneratedModels, mapper: Mapper, iri: str, graph: Graph
) -> Activity:
    """The activity at ``iri`` in ``graph``, in the most specific class among its types.

    Raises:
        LookupError: No class of the schema is one of its types.
        ValueError: The class refuses the triples.
    """
    cls = activity_class_of(view, models, graph.objects(URIRef(iri), RDF.type))
    return mapper.from_graph(cls, iri, graph, None)


def error_text(error: Exception) -> str:
    """``error`` for a log: a validation error names each field at fault and the fault, never the value."""
    if isinstance(error, ValidationError):
        faults = error.errors(include_url=False, include_input=False, include_context=False)
        return "; ".join(f"{'.'.join(map(str, f['loc']))}: {f['msg']}" for f in faults)
    return str(error)
