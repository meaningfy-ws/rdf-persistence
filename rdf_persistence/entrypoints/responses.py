"""The answers of the routes: headers, and bodies built from the generated models or from the documents."""

from fastapi import Response
from linkml_runtime.linkml_model.meta import ClassDefinition
from pydantic import BaseModel
from rdflib import URIRef
from rdflib.graph import Graph

from rdf_persistence.domain.generated.service.rp_service import Page
from rdf_persistence.entrypoints.negotiation import etag_of
from rdf_persistence.services.documents import JSON, Documents

ETAG = "ETag"
LINK = "Link"
LOCATION = "Location"
VARY = "Vary"
ACCEPT = "Accept"
CONTEXT_REL = "http://www.w3.org/ns/json-ld#context"


def _context_link(context_url: str) -> str:
    return f'<{context_url}>; rel="{CONTEXT_REL}"'


def model_response(
    model: BaseModel, *, status: int = 200, version: str | None = None, location: str | None = None
) -> Response:
    """``model`` as a JSON answer, with the ``ETag`` of ``version`` and the ``Location`` it has, if given."""
    headers = {}
    if version is not None:
        headers[ETAG] = etag_of(version)
    if location is not None:
        headers[LOCATION] = location
    return Response(
        model.model_dump_json(exclude_none=True),
        status_code=status,
        media_type=JSON,
        headers=headers,
    )


async def document_response(
    context_url: str,
    documents: Documents,
    stored: Graph,
    graph: URIRef,
    cls: ClassDefinition,
    media_type: str,
    version: str,
    *,
    status: int = 200,
    location: str | None = None,
) -> Response:
    """An aggregate read from the store as ``media_type``, with its ``ETag``.

    Plain JSON points at the generated context by a ``Link`` header to ``context_url``, so it is also
    JSON-LD.
    """
    headers = {ETAG: etag_of(version), VARY: ACCEPT}
    if media_type == JSON:
        headers[LINK] = _context_link(context_url)
    if location is not None:
        headers[LOCATION] = location
    body = await documents.render(stored, graph, cls, media_type)
    return Response(body, status_code=status, media_type=media_type, headers=headers)


def page_response(context_url: str, page: Page, media_type: str) -> Response:
    """A page of aggregates as ``media_type``; plain JSON points at the generated context by a ``Link`` header."""
    headers = {VARY: ACCEPT}
    if media_type == JSON:
        headers[LINK] = _context_link(context_url)
    return Response(page.model_dump_json(exclude_none=True), media_type=media_type, headers=headers)
