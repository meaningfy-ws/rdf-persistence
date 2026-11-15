"""The event port's helper: the context link of an envelope (TC-06)."""

import pytest

from rdf_persistence.services.events import context_link


@pytest.mark.parametrize(
    ("public_url", "link"),
    [("https://lib.example", "https://lib.example/context.jsonld"), (None, "/context.jsonld")],
)
def test_context_link_is_absolute_with_a_public_url_and_relative_without(public_url, link):
    assert context_link(public_url) == link
