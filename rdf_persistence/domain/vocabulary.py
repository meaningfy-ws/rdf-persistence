"""The predicates and kinds the session writes about a graph and in the registry (PD-7, PD-8).

Each constant is the URI of a slot or enum meaning of the metamodel; a test compares them with
the schema.
"""

from collections.abc import Mapping

from rdflib import URIRef
from rdflib.namespace import Namespace

RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
DCTERMS = Namespace("http://purl.org/dc/terms/")

VERSION = RP["version"]
CREATED = DCTERMS["created"]
MODIFIED = DCTERMS["modified"]
CREATOR = DCTERMS["creator"]
CONTRIBUTOR = DCTERMS["contributor"]
# The statements the session makes about a graph IRI; closed shapes ignore them (PD-7).
BOOKKEEPING_PREDICATES = frozenset({VERSION, CREATED, MODIFIED, CREATOR, CONTRIBUTOR})

REGISTRY_GRAPH = RP["graph"]
REGISTRY_KIND = RP["kind"]
REGISTRY_OWNED_BY = RP["ownedBy"]
REGISTRY_KIND_IRIS: Mapping[str, URIRef] = {
    "aggregate": RP["Aggregate"],
    "loaded_graph": RP["LoadedGraph"],
}
