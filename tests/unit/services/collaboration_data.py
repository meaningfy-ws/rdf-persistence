"""Data the collaboration tests, and the route tests built on them, share: the review workflow's states and the annotation vocabulary."""

from rdflib import RDF, Namespace, URIRef

from rdf_persistence.persistence.services.session import Session
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.services.workflows import load_workflow, state_iri
from tests.toy import REVIEW_WORKFLOW

OA = Namespace("http://www.w3.org/ns/oa#")
RP = Namespace("https://meaningfy.ws/ns/rdf-persistence#")
SECRET = "SECRET-9f3a-do-not-show"

REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT, IN_REVIEW, ACCEPTED = (state_iri(REVIEW, s) for s in ("draft", "in_review", "accepted"))
RETIRED = state_iri(REVIEW, "retired")  # a state the file does not list


async def stored(session: Session, *iris: str) -> list[str]:
    """The IRIs, among ``iris``, whose graph the session finds."""
    return [str(h.head_iri) for h in await session.heads(list(iris))]


def annotation(iri: str, *pairs: tuple[URIRef, object], types=(v.ANNOTATION,)) -> list:
    """The triples of a root typed as a web annotation, written as the test says (raw, maybe invalid)."""
    node = URIRef(iri)
    return [*((node, RDF.type, t) for t in types), *((node, p, o) for p, o in pairs)]
