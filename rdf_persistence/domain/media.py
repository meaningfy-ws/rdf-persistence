"""The media types the toolkit speaks, in one place for the adapters, the services and the routes."""

JSON = "application/json"
JSON_LD = "application/ld+json"
TURTLE = "text/turtle"
PROBLEM_JSON = "application/problem+json"
# The representations of an aggregate, in the order a tie in ``Accept`` is settled.
REPRESENTATIONS = (JSON, JSON_LD, TURTLE)
# The headers that name a body's media type, and the one that sizes it.
ACCEPT = "Accept"
CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"
