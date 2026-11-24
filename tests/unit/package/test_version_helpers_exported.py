"""The If-Match helpers are importable from the top-level package (DEC-8, TC-7)."""

import pytest

import rdf_persistence as r
from rdf_persistence.api.entrypoints import negotiation

STRONG = '"v1"'


@pytest.mark.parametrize(
    ("header", "outcome"),
    [
        (STRONG, "v1"),
        (None, r.PreconditionRequired),
        ("", r.PreconditionRequired),
        ('"a", "b"', r.PreconditionRequired),
        ("*", r.PreconditionRequired),
        ('W/"v1"', r.Conflict),
    ],
    ids=["strong", "missing", "empty", "list", "star", "weak"],
)
def test_expected_version_from_the_top_level_package(
    header: str | None, outcome: str | type[Exception]
) -> None:
    if isinstance(outcome, str):
        assert r.expected_version(header) == outcome, f"{header!r} names the version {outcome!r}"
        return
    with pytest.raises(outcome):
        r.expected_version(header)


def test_the_top_level_names_are_the_negotiation_functions() -> None:
    assert r.expected_version is negotiation.expected_version, "expected_version is the same object"
    assert r.matched_version is negotiation.matched_version, "matched_version is the same object"


def test_the_names_are_listed_in_all() -> None:
    missing = {"expected_version", "matched_version"} - set(r.__all__)
    assert not missing, f"not in __all__: {sorted(missing)}"
