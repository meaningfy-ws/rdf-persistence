"""What of an activity a caller may see (PD-11; DEC-3, DEC-5)."""

from collections.abc import Callable

from rdf_persistence.domain.generated.rp_provenance import Activity


def visible_part(activity: Activity, may_read: Callable[[str], bool]) -> Activity | None:
    """A copy of ``activity`` with only the generations and invalidations whose entity the caller may
    read; ``None`` when the resource it used is hidden or no part is left. ``activity`` is untouched."""
    used = getattr(activity, "used_resource", None)  # only some activity classes use a resource
    if used is not None and not may_read(used):
        return None
    generations = [g for g in activity.generations or [] if may_read(g.entity)]
    invalidations = [i for i in activity.invalidations or [] if may_read(i.entity)]
    if not generations and not invalidations:
        return None
    return activity.model_copy(
        update={"generations": generations or None, "invalidations": invalidations or None}
    )
