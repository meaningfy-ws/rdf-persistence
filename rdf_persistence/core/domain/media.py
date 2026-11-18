"""The media types the toolkit speaks, in one place for the adapters, the services and the routes."""

JSON = "application/json"
JSON_LD = "application/ld+json"
TURTLE = "text/turtle"
N_TRIPLES = "application/n-triples"
N_QUADS = "application/n-quads"
TRIG = "application/trig"
RDF_XML = "application/rdf+xml"
PROBLEM_JSON = "application/problem+json"
# The RDF serialisations that hold named graphs: the aggregate is shown in the graph it lives in.
DATASET_REPRESENTATIONS = (N_QUADS, TRIG)
# The representations of an aggregate, in the order a tie in ``Accept`` is settled.
REPRESENTATIONS = (JSON, JSON_LD, TURTLE, N_TRIPLES, N_QUADS, TRIG, RDF_XML)
# The headers that name a body's media type, and the one that sizes it.
ACCEPT = "Accept"
CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
