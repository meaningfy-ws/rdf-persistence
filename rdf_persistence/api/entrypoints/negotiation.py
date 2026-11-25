"""Content negotiation and the version headers (PD-14, the error matrix).

``Accept`` picks one of the three representations (JSON by default); ``Content-Type`` must name a
body the route takes; the version of an aggregate travels as a quoted ``ETag`` and comes back in
``If-Match``.
"""

from collections.abc import Awaitable, Callable, Iterable

import mimeparse

from rdf_persistence.access.domain.generated.rp_access import Action
from rdf_persistence.core.domain.exceptions import (
    Conflict,
    NotAcceptable,
    PreconditionRequired,
    UnsupportedMediaType,
)
from rdf_persistence.core.domain.media import JSON, JSON_LD, REPRESENTATIONS

# The headers of the version of an aggregate, and of where a created one is.
IF_MATCH = "If-Match"
ETAG = "ETag"
RECORD_ETAG = "Record-ETag"  # the access record's version, on the root read (PD-6)
ALLOWED_ACTIONS = "Allowed-Actions"  # what the caller may do, on the reads (PD-10)
HELD_ROLES = "Held-Roles"  # the roles the caller holds on the aggregate, on the reads (DEC-6)
LOCATION = "Location"
LINK = "Link"
LAST_EVENT_ID = "Last-Event-ID"  # where a follower of the events resumes (aggregate-events PD-12)
VARY = "Vary"
ANY = "*/*"
_SLASH, _WILDCARD = "/", "*"  # of a media range
WEAK_PREFIX = "W/"
_SEPARATOR, _QUOTE, ANY_VERSION = ",", '"', "*"  # of an If-Match list; ``*`` matches any version
_QUOTES_ONLY = 2  # the length of ``""``, an entity tag without its version


def allowed_actions_value(actions: Iterable[Action]) -> str:
    """The ``Allowed-Actions`` value: ``actions`` by name, comma separated."""
    return ", ".join(action.value for action in actions)


def held_roles_value(roles: Iterable[str]) -> str:
    """The ``Held-Roles`` value: ``roles`` sorted, comma separated; empty when none is held."""
    return ",".join(sorted(roles))


def _quality(raw: str | None) -> str:
    """The weight of a range from its ``q`` text: unreadable, empty or above 1 reads as 1, negative as 0 (F-3)."""
    try:
        weight = float(raw or "")
    except ValueError:
        return "1"
    return "0" if weight < 0 else str(weight if weight <= 1 else 1)  # nan is neither: it reads as 1


def _media_range(member: str) -> tuple[str, str, dict[str, str]] | None:
    """A member of an ``Accept`` header as ``mimeparse`` reads it, ``q`` set; None when it is no media range.

    Not a range (F-3): no ``/`` (``mimeparse`` would read ``*`` as ``*/*``), an empty type or subtype,
    or ``*`` for the type with a subtype other than ``*``.
    """
    if _SLASH not in member.partition(";")[0]:
        return None
    try:
        type_, subtype, params = mimeparse.parse_mime_type(member)
    except mimeparse.MimeTypeParseException:
        return None
    if not type_ or not subtype or (type_ == _WILDCARD and subtype != _WILDCARD):
        return None
    params["q"] = _quality(params.get("q"))
    return type_, subtype, params


def _negotiate(accept: str | None, offered: tuple[str, ...], refusal: str) -> str:
    """The media type of ``offered`` an ``Accept`` header ranks highest, the first on a tie; none given is any.

    The header is split on commas outside quotes; a member that is no media range is skipped, and
    the others are read by ``mimeparse`` and each offered type is scored with ``quality_parsed``
    (not ``best_match``, which breaks a quality tie by specificity, PD-5).

    Raises:
        NotAcceptable: Nothing offered is acceptable to the client, or no member is a media range;
            ``refusal`` is the message.
    """
    header = accept.lower() if accept is not None and accept.strip() else ANY
    members = (_media_range(entry) for entry in _entries(header))
    ranges = [member for member in members if member is not None]
    scored = [(mimeparse.quality_parsed(media_type, ranges), media_type) for media_type in offered]
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


def _entries(value: str) -> list[str]:
    """The members of an ``If-Match`` list or an ``Accept`` header: split on commas outside quotes, empty members skipped (RFC 9110 5.6.1)."""
    entries, current, quoted = [], "", False
    for char in value:
        if char == _SEPARATOR and not quoted:
            entries.append(current)
            current = ""
            continue
        quoted = quoted != (char == _QUOTE)
        current += char
    entries.append(current)
    return [entry.strip() for entry in entries if entry.strip()]


def _tag(entry: str) -> tuple[bool, str] | None:
    """``(weak, version)`` of an entity tag, ``"v"`` or ``W/"v"``; None when the entry is not one."""
    weak = entry.startswith(WEAK_PREFIX)
    quoted = entry.removeprefix(WEAK_PREFIX)
    if len(quoted) < _QUOTES_ONLY or not (quoted.startswith(_QUOTE) and quoted.endswith(_QUOTE)):
        return None
    version = quoted[1:-1]
    return (weak, version) if _QUOTE not in version else None


def _required_header(if_match: str | None) -> str:
    value = (if_match or "").strip()
    if not value:
        raise PreconditionRequired("an update or a delete needs an If-Match header")
    return value


def expected_version(if_match: str | None) -> str:
    """The version an update or a delete expects, from an ``If-Match`` with one strong entity tag; no read.

    ``*`` and lists need the current version to be matched: use ``matched_version``.

    Raises:
        PreconditionRequired: The header is missing or empty, or is not one entity tag.
        Conflict: The tag is weak, which never matches (RFC 9110 strong comparison).
    """
    entries = _entries(_required_header(if_match))
    tag = _tag(entries[0]) if len(entries) == 1 else None
    if tag is None:
        raise PreconditionRequired(
            "If-Match must be one entity tag here; matched_version takes * or a list"
        )
    weak, version = tag
    if weak:
        raise Conflict("a weak entity tag never matches")
    return version


def _named_versions(value: str) -> tuple[list[str], list[str]]:
    """The members of a list of entity tags, and the versions its strong tags name.

    Raises:
        PreconditionRequired: The list is empty or has a member that is not an entity tag.
    """
    entries = _entries(value)
    tags = [_tag(entry) for entry in entries]
    if not tags or None in tags:
        raise PreconditionRequired("If-Match must be * or entity tags")
    return entries, [tag[1] for tag in tags if tag is not None and not tag[0]]


async def matched_version(if_match: str | None, current: Callable[[], Awaitable[str]]) -> str:
    """The one version a guarded write takes, from its ``If-Match``.

    ``*`` matches any version. Otherwise the header lists entity tags: a strong ``"v"`` names ``v``,
    a weak ``W/"v"`` names nothing. One strong tag is the version, with no read; ``*`` or a longer
    list awaits ``current()`` and gives it when ``*`` or named.

    Raises:
        PreconditionRequired: The header is missing, blank, or neither ``*`` alone nor entity tags.
        Conflict: Only weak tags, or none of them names the current version.
    """
    value = _required_header(if_match)
    if value == ANY_VERSION:
        return await current()
    entries, named = _named_versions(value)
    if len(entries) == 1 and named:
        return named[0]
    if named and (version := await current()) in named:
        return version
    raise Conflict("the version is not one If-Match names")
