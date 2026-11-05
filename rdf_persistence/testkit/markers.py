"""The pytest marker names of the container tests, and the containers they start (PD-16).

The single source for both ``tests/conftest.py`` and the fixtures plugin. Needs no extra, so a lane
without ``rdf-persistence[testkit]`` can still use it.
"""

from collections.abc import Iterable
from typing import Protocol

from rdf_persistence.generation.generated.rp_generation import ContainerMarker

STORE, FILES, IDENTITY = "store", "files", "identity"
FUSEKI, GARAGE, ZITADEL = "fuseki", "garage", "zitadel"


CONTAINER_MARKERS = (
    ContainerMarker(marker=STORE, container=FUSEKI, help="needs the Fuseki container"),
    ContainerMarker(marker=FILES, container=GARAGE, help="needs the Garage container"),
    ContainerMarker(marker=IDENTITY, container=ZITADEL, help="needs the Zitadel container"),
)


def containers_for(markers: Iterable[str]) -> list[str]:
    """Return the containers the given markers need, in a stable order."""
    names = set(markers)
    return [row.container for row in CONTAINER_MARKERS if row.marker in names]


class _IniConfig(Protocol):
    def addinivalue_line(self, name: str, line: str) -> None: ...


def register_markers(config: _IniConfig) -> None:
    """Register the container markers on a pytest config (needs no extra)."""
    for row in CONTAINER_MARKERS:
        config.addinivalue_line("markers", f"{row.marker}: {row.help}")
