"""Content negotiation and the version headers (task 5.3, 5.1): Accept, Content-Type, ETag, If-Match."""

import pytest

from rdf_persistence.domain.exceptions import (
    NotAcceptable,
    PreconditionRequired,
    UnsupportedMediaType,
)
from rdf_persistence.entrypoints.negotiation import (
    accepted_media_type,
    etag_of,
    expected_version,
    request_media_type,
)
from rdf_persistence.services.documents import JSON, JSON_LD, TURTLE

# accept header, the representation served (None: nothing the service produces is acceptable)
ACCEPT = [
    (None, JSON),
    ("", JSON),
    ("*/*", JSON),
    ("application/json", JSON),
    ("application/ld+json", JSON_LD),
    ("text/turtle", TURTLE),
    ("TEXT/Turtle", TURTLE),
    ("text/turtle, application/json;q=0.5", TURTLE),
    ("application/json;q=0.5, text/turtle;q=0.9", TURTLE),
    ("application/*", JSON),
    ("text/*", TURTLE),
    ("text/html, */*;q=0.1", JSON),
    ("text/html, text/turtle", TURTLE),
    ("application/ld+json;q=0.3, */*;q=0.1", JSON_LD),
    ("application/json;q=0", None),
    ("text/html", None),
    ("image/png, application/xml", None),
    ("nonsense", None),
    ("*/*;q=0", None),
]


@pytest.mark.parametrize(("header", "served"), ACCEPT, ids=[repr(a) for a, _ in ACCEPT])
def test_accept_picks_the_best_representation_the_service_produces(header, served) -> None:
    if served is None:
        with pytest.raises(NotAcceptable):
            accepted_media_type(header)
    else:
        assert accepted_media_type(header) == served, f"Accept: {header!r}"


def test_a_range_that_names_a_type_overrides_a_wildcard() -> None:
    assert accepted_media_type("*/*;q=0, text/turtle") == TURTLE, "turtle is asked for by name"
    assert accepted_media_type("text/turtle;q=0, */*") == JSON, "turtle is refused by name"


def test_a_client_that_refuses_every_representation_by_name_gets_nothing() -> None:
    header = "text/turtle;q=0, application/json;q=0, application/ld+json;q=0, */*;q=0.1"
    with pytest.raises(NotAcceptable):
        accepted_media_type(header)


CONTENT_TYPES = [
    ("application/json", JSON),
    ("application/json; charset=utf-8", JSON),
    ("Application/JSON", JSON),
    ("application/ld+json", JSON_LD),
    ('application/ld+json; profile="http://www.w3.org/ns/json-ld#compacted"', JSON_LD),
]


@pytest.mark.parametrize(("header", "media"), CONTENT_TYPES)
def test_a_json_or_json_ld_body_is_accepted(header, media) -> None:
    assert request_media_type(header, (JSON, JSON_LD)) == media, header


@pytest.mark.parametrize(
    "header", [None, "", "text/turtle", "text/plain", "application/xml", "json"]
)
def test_any_other_content_type_is_unsupported(header) -> None:
    with pytest.raises(UnsupportedMediaType):
        request_media_type(header, (JSON, JSON_LD))


def test_a_route_that_takes_only_json_refuses_json_ld() -> None:
    with pytest.raises(UnsupportedMediaType):
        request_media_type("application/ld+json", (JSON,))


def test_the_etag_is_the_version_in_quotes() -> None:
    assert etag_of("7f3a") == '"7f3a"', "RFC 9110: an entity tag is a quoted string"


@pytest.mark.parametrize("header", ['"7f3a"', 'W/"7f3a"', "7f3a", ' "7f3a" '])
def test_if_match_names_the_version_it_expects(header) -> None:
    assert expected_version(header) == "7f3a", header


@pytest.mark.parametrize("header", [None, "", "  "])
def test_an_update_without_if_match_is_a_precondition_required(header) -> None:
    with pytest.raises(PreconditionRequired):
        expected_version(header)
