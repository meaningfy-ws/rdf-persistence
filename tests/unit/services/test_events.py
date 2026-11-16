"""The event port's helper: the context link of an envelope (TC-06, D-16)."""

import pytest

from rdf_persistence.services.events import context_link


@pytest.mark.parametrize(
    ("public_url", "prefix", "link"),
    [
        ("https://lib.example", "", "https://lib.example/context.jsonld"),
        (None, "", "/context.jsonld"),
        ("https://lib.example", "/api", "https://lib.example/api/context.jsonld"),
        (None, "/api", "/api/context.jsonld"),
        (None, "api/", "/api/context.jsonld"),
        (None, "/", "/context.jsonld"),
    ],
)
def test_context_link_carries_the_mount_prefix_and_is_absolute_only_under_a_public_url(
    public_url, prefix, link
):
    assert context_link(public_url, prefix) == link
