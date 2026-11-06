"""The router's unit tests run against fakes and in-process requests: any socket connection is a failure."""

import pytest

from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _offline(no_network: None) -> None:  # noqa: F811
    """Block the network for every test of this folder."""
