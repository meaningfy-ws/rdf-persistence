"""Content negotiation and the version headers (PD-14, the error matrix).

``Accept`` picks one of the three representations (JSON by default); ``Content-Type`` must name a
body the route takes; the version of an aggregate travels as a quoted ``ETag`` and comes back in
``If-Match``.
"""

from rdf_persistence.domain.exceptions import (
    NotAcceptable,
    PreconditionRequired,
    UnsupportedMediaType,
)
from rdf_persistence.domain.media import JSON, JSON_LD, REPRESENTATIONS

# The headers of the version of an aggregate, and of where a created one is.
IF_MATCH = "If-Match"
ETAG = "ETag"
LOCATION = "Location"
LINK = "Link"
VARY = "Vary"
ANY = "*/*"
# How exactly a range names a media type: the most exact range that matches decides its quality.
_EXACT, _TYPE_WILDCARD, _ANY = 3, 2, 1
WEAK_PREFIX = "W/"


def _quality(parameters: list[str]) -> float:
    for parameter in parameters:
        name, _, value = parameter.partition("=")
        if name.strip().lower() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def _ranges(accept: str) -> list[tuple[str, float]]:
    """The ``(media range, quality)`` pairs of an ``Accept`` header, ranges in lower case."""
    ranges = []
    for part in accept.split(","):
        media, *parameters = part.split(";")
        if media.strip():
            ranges.append((media.strip().lower(), _quality(parameters)))
    return ranges


def _specificity(media_range: str, media_type: str) -> int:
    """How exactly ``media_range`` names ``media_type``; 0 when it does not match."""
    if media_range == media_type:
        return _EXACT
    if media_range == f"{media_type.split('/')[0]}/*":
        return _TYPE_WILDCARD
    return _ANY if media_range == ANY else 0


def _quality_of(ranges: list[tuple[str, float]], media_type: str) -> float:
    """The quality the most exact matching range gives ``media_type``; 0 when none matches."""
    matches = [(_specificity(r, media_type), q) for r, q in ranges]
    best = max(matches, default=(0, 0.0), key=lambda match: match[0])
    return best[1] if best[0] else 0.0


def _negotiate(accept: str | None, offered: tuple[str, ...], refusal: str) -> str:
    """The media type of ``offered`` an ``Accept`` header ranks highest, the first on a tie; none given is any.

    Raises:
        NotAcceptable: Nothing offered is acceptable to the client; ``refusal`` is the message.
    """
    ranges = _ranges(accept) if accept is not None and accept.strip() else [(ANY, 1.0)]
    scored = [(_quality_of(ranges, media_type), media_type) for media_type in offered]
    quality, media_type = max(scored, key=lambda pair: pair[0])  # max keeps the first on a tie
    if quality <= 0:
        raise NotAcceptable(refusal)
    return media_type


def accepted_media_type(accept: str | None) -> str:
    """The representation to serve for an ``Accept`` header: the highest quality, JSON first on a tie.

    Raises:
        NotAcceptable: Nothing the service produces is acceptable to the client.
    """
    return _negotiate(accept, REPRESENTATIONS, f"the service produces {', '.join(REPRESENTATIONS)}")


def accepted_listing_type(accept: str | None) -> str:
    """The representation of a page for an ``Accept`` header: JSON or JSON-LD, JSON first on a tie.

    A page is an envelope of items with their total, which has no Turtle form, so Turtle is never
    chosen, whatever its quality.

    Raises:
        NotAcceptable: Neither JSON nor JSON-LD is acceptable to the client.
    """
    return _negotiate(accept, (JSON, JSON_LD), f"a listing is served as {JSON} or {JSON_LD}")


def request_media_type(content_type: str | None, allowed: tuple[str, ...]) -> str:
    """The media type of a request body, parameters dropped, if the route takes it.

    Raises:
        UnsupportedMediaType: The body has no ``Content-Type``, or one that is not in ``allowed``.
    """
    media_type = (content_type or "").split(";")[0].strip().lower()
    if media_type not in allowed:
        raise UnsupportedMediaType(f"the body must be {', '.join(allowed)}")
    return media_type


def etag_of(version: str) -> str:
    """The ``ETag`` header value of a version token: the token in quotes."""
    return f'"{version}"'


def expected_version(if_match: str | None) -> str:
    """The version an update or a delete expects, from its ``If-Match`` header.

    Raises:
        PreconditionRequired: The header is missing or empty.
    """
    value = (if_match or "").strip()
    if not value:
        raise PreconditionRequired("an update or a delete needs an If-Match header")
    return value.removeprefix(WEAK_PREFIX).strip('"')
