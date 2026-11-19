"""Test helper for event-driven code: an observer that keeps what it got (message-bus PD-22).

Register it on the real ``MessageBus`` and assert which activities a command led to; there is no
fake bus.
"""

from rdf_persistence.messaging.services.messagebus import Work
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity


class RecordingObserver:
    """An observer that appends every activity it is called with; it never raises."""

    def __init__(self) -> None:
        self.activities: list[Activity] = []

    async def __call__(self, activity: Activity, work: Work) -> None:
        self.activities.append(activity)

    def of[A: Activity](self, cls: type[A]) -> list[A]:
        """The recorded activities that are instances of ``cls`` (subclasses included), in call order."""
        return [a for a in self.activities if isinstance(a, cls)]

    def __repr__(self) -> str:
        # the bus names an observer in its log by repr when it has no __qualname__
        return f"RecordingObserver({len(self.activities)} activities)"
