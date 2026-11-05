"""The pytest marker names of the container tests, and the containers they start (PD-16).

The single source for both ``tests/conftest.py`` and the fixtures plugin. Imports nothing third-party,
so a lane without the extra ``rdf-persistence[testkit]`` can still use it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

STORE, FILES, IDENTITY = "store", "files", "identity"
FUSEKI, GARAGE, ZITADEL = "fuseki", "garage", "zitadel"


@dataclass(frozen=True)
class ContainerMarker:
    """A pytest marker, the container it starts, and its help text."""

    marker: str
    container: str
    help: str


CONTAINER_MARKERS = (
    ContainerMarker(STORE, FUSEKI, "needs the Fuseki container"),
    ContainerMarker(FILES, GARAGE, "needs the Garage container"),
    ContainerMarker(IDENTITY, ZITADEL, "needs the Zitadel container"),
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
