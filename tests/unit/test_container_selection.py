"""A marker starts only the containers it needs (PD-16)."""

import pytest

from rdf_persistence.testkit.markers import containers_for


@pytest.mark.parametrize(
    ("markers", "expected"),
    [
        ([], []),
        (["unit"], []),
        (["integration", "store"], ["fuseki"]),
        (["integration", "identity"], ["zitadel"]),
        (["e2e", "store", "files", "identity"], ["fuseki", "garage", "zitadel"]),
    ],
)
def test_markers_select_containers(markers: list[str], expected: list[str]) -> None:
    assert containers_for(markers) == expected
