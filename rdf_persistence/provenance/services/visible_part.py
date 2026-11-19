"""What of an activity a caller may see (PD-11; DEC-3, DEC-5)."""

from collections.abc import Callable
from typing import Protocol

from rdf_persistence.provenance.domain.generated.rp_provenance import Activity


class Entity(Protocol):
    """A generation or an invalidation: what both name is the entity."""

    entity: str


def _readable[T: Entity](parts: list[T] | None, may_read: Callable[[str], bool]) -> list[T]:
    """The parts whose entity the caller may read."""
    return [part for part in parts or [] if may_read(part.entity)]


def visible_part(activity: Activity, may_read: Callable[[str], bool]) -> Activity | None:
    """A copy of ``activity`` with only the generations and invalidations whose entity the caller may
    read; ``None`` when the resource it used is hidden or no part is left. ``activity`` is untouched."""
    used = getattr(activity, "used_resource", None)  # only some activity classes use a resource
    if used is not None and not may_read(used):
        return None
    generations = _readable(activity.generations, may_read)
    invalidations = _readable(activity.invalidations, may_read)
    if not generations and not invalidations:
        return None
    return activity.replaced(generations=generations or None, invalidations=invalidations or None)
