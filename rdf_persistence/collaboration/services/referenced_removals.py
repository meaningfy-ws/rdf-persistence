"""The schema side of the refusal of a removal that something still refers to (PD-7, PD-10).

``ReferencedRemovals`` is built once from the schema and the limits, like ``WriteGuards``, and shared
by every session. It names the classes that refuse deletion and turns the referrer rows of a refused
root into the ``InUse`` the caller sees: the readable referrers named up to the cap, the others counted.
"""

from collections.abc import Iterable, Sequence

from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef

from rdf_persistence.collaboration.services.referrer_naming import named
from rdf_persistence.core.domain.exceptions import InUse
from rdf_persistence.persistence.services.generated.rows.rp_persistence_rows import ReferrerRow
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.referrers import Readable
from rdf_persistence.schema.services.schema_structure import refusing_classes


class ReferencedRemovals:
    """The classes that refuse deletion while referred to, and the diagnosis of a refusal."""

    def __init__(self, view: SchemaView, limits: LimitSettings) -> None:
        self._view = view
        self._cap = limits.max_named_referrers
        self.refusing: frozenset[URIRef] = refusing_classes(view)

    async def in_use(
        self,
        roots: Iterable[str],
        root: str,
        rows: Sequence[ReferrerRow],
        readable: Readable | None,
    ) -> InUse:
        """The ``InUse`` for the refused ``roots``, naming the referrers in ``rows``, which refer to
        ``root``, one of them.

        ``readable`` says which referrers of ``root`` the caller may read (``None``: all of them),
        judged against ``root`` itself: a comment is judged by the thread of the IRI given. The readable
        referrer aggregates are sorted by IRI; the first ``max_named_referrers`` are named with every
        ``(class, slot)`` item they hold, the rest are ``more_count``, and the unreadable ones are
        ``hidden_count``, each aggregate once.
        """
        refused = sorted(roots)
        items = sorted(named(self._view, list(rows)))
        referrers = {referrer for referrer, _, _ in items}
        allowed = referrers if readable is None else await readable(root, rows)
        shown = sorted(referrers & allowed)[: self._cap]
        return InUse(
            f"{', '.join(refused)} is still referred to",
            iris=tuple(refused),
            referrers=tuple(item for item in items if item[0] in shown),
            more_count=len(referrers & allowed) - len(shown),
            hidden_count=len(referrers - allowed),
            filtered=readable is not None,
        )
