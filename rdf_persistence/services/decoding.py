"""Decoding a stored activity into its most specific generated class (aggregate-events PD-16).

Apart from ``provenance`` because it needs the mapper, which imports the session; ``provenance`` may not.
"""

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import RDF, Graph, URIRef

from rdf_persistence.domain.generated.rp_provenance import Activity
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.provenance import activity_class_of


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
