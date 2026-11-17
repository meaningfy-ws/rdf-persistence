"""Content negotiation and the version headers (task 5.3, 5.1): Accept, Content-Type, ETag, If-Match."""

import pytest

from rdf_persistence.domain.exceptions import (
    Conflict,
    NotAcceptable,
    PreconditionRequired,
    UnsupportedMediaType,
)
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.entrypoints.negotiation import (
    accepted_listing_type,
    accepted_media_type,
    etag_of,
    expected_version,
    matched_version,
    request_media_type,
)

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


# One case per class: absent, produced but not accepted, an unknown type, malformed.
@pytest.mark.parametrize("header", [None, "text/turtle", "application/xml", "json"])
def test_any_other_content_type_is_unsupported(header) -> None:
    with pytest.raises(UnsupportedMediaType):
        request_media_type(header, (JSON, JSON_LD))


def test_a_route_that_takes_only_json_refuses_json_ld() -> None:
    with pytest.raises(UnsupportedMediaType):
        request_media_type("application/ld+json", (JSON,))


def test_the_etag_is_the_version_in_quotes() -> None:
    assert etag_of("7f3a") == '"7f3a"', "RFC 9110: an entity tag is a quoted string"


@pytest.mark.parametrize("header", ['"7f3a"', ' "7f3a" '])
def test_if_match_names_the_version_it_expects(header) -> None:
    assert expected_version(header) == "7f3a", header


def test_a_weak_tag_never_matches_in_expected_version() -> (
    None
):  # TC-13 (breaking: it was stripped)
    with pytest.raises(Conflict):
        expected_version('W/"7f3a"')


@pytest.mark.parametrize("header", ["7f3a", "*", '"v1", "v3"'])  # TC-21b
def test_expected_version_refuses_what_it_cannot_read_without_a_read(header) -> None:
    with pytest.raises(PreconditionRequired, match="matched_version"):
        expected_version(header)


class Current:
    """A ``current`` that counts its calls and answers one version."""

    def __init__(self, version: str = "v3") -> None:
        self.version, self.calls = version, 0

    async def __call__(self) -> str:
        self.calls += 1
        return self.version


async def test_a_single_strong_tag_is_the_version_and_nothing_is_read() -> None:  # TC-12
    current = Current()
    assert await matched_version('"v3"', current) == "v3"
    assert current.calls == 0, "a single strong tag costs no read"


async def test_a_weak_tag_names_no_version() -> None:  # TC-13
    with pytest.raises(Conflict):
        await matched_version('W/"v3"', Current())


async def test_a_star_matches_the_current_version() -> None:  # TC-14
    current = Current()
    assert await matched_version("*", current) == "v3"
    assert current.calls == 1


@pytest.mark.parametrize("header", ['"v1", "v3"', '"v1",W/"v2" , "v3"', '"v1", , "v3"'])
async def test_a_list_that_names_the_current_version_gives_it(header) -> None:  # TC-15, TC-21c
    current = Current()
    assert await matched_version(header, current) == "v3", header
    assert current.calls == 1, "a list costs one read"


async def test_a_list_that_does_not_name_the_current_version_is_a_conflict() -> None:  # TC-16
    with pytest.raises(Conflict, match="not one If-Match names"):
        await matched_version('"v1", "v2"', Current())


async def test_a_comma_inside_a_quoted_tag_does_not_split_it() -> None:
    current = Current()
    assert await matched_version('"a,b"', current) == "a,b"
    assert current.calls == 0


@pytest.mark.parametrize("header", [None, "", "  ", "v3", '"v3', '*, "v3"'])
async def test_a_missing_or_malformed_if_match_is_a_precondition_required(header) -> None:  # TC-17
    current = Current()
    with pytest.raises(PreconditionRequired):
        await matched_version(header, current)
    assert current.calls == 0, "refused before any read"


# One class (no usable If-Match); None and blank are the two operands of `(if_match or "").strip()`.
@pytest.mark.parametrize("header", [None, "  "])
def test_an_update_without_if_match_is_a_precondition_required(header) -> None:
    with pytest.raises(PreconditionRequired):
        expected_version(header)


# accept header, the representation a listing is served in: a page has no Turtle form (None: 406)
LISTING_ACCEPT = [
    (None, JSON),
    ("*/*", JSON),
    ("application/json", JSON),
    ("application/ld+json", JSON_LD),
    ("text/turtle, application/json;q=0.1", JSON),
    ("text/turtle;q=0.9, application/ld+json;q=0.2", JSON_LD),
    ("text/*, application/json;q=0.5", JSON),
    ("text/turtle", None),
    ("text/*", None),
    ("text/html", None),
    ("application/json;q=0, text/turtle", None),
]


@pytest.mark.parametrize(
    ("header", "served"), LISTING_ACCEPT, ids=[repr(a) for a, _ in LISTING_ACCEPT]
)
def test_a_listing_is_served_as_json_or_json_ld_and_never_as_turtle(header, served) -> None:
    if served is None:
        with pytest.raises(NotAcceptable):
            accepted_listing_type(header)
    else:
        assert accepted_listing_type(header) == served, f"Accept: {header!r}"
