"""The schema's names for the rows of a reverse-reference read (PD-8).

The session returns referrers as IRIs; the schema names their class and slot. These functions take
the schema view they read from, so ``Collaboration`` and the removal guard name rows alike.
"""

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.collaboration.services.generated.rp_collaboration_services import Referrer
from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.generated.rows.rp_persistence_rows import ReferrerRow
from rdf_persistence.schema.services.schema_structure import annotation_text, served_roots


def classes_by_iri(view: SchemaView) -> dict[str, str]:
    """The name of each class of the schema, by its expanded IRI."""
    return {view.get_uri(c, expand=True): name for name, c in view.all_classes().items()}


def located(view: SchemaView, iris: Iris, class_name: str, iri: str) -> tuple[str, str] | None:
    """``(rp_path, id)``, the address a referrer is served at, or ``None`` when it has none.

    The path is the ``rp_path`` of ``class_name`` when it is a served root (the test the generic router
    uses); the id is the one ``iri`` ends in as an aggregate IRI. When either is missing, there is no
    address, so neither is given.
    """
    path = next(
        (
            annotation_text(root, RpAnnotation.RP_PATH)
            for root in served_roots(view)
            if root.name == class_name
        ),
        None,
    )
    found = iris.aggregate_id_of(iri)
    return None if path is None or found is None else (path, found)


def referrer_item(
    iri: str, class_name: str, slot: str, address: tuple[str, str] | None
) -> Referrer:
    """The ``Referrer`` of one row; ``address`` (from ``located``) sets both of its location fields, or neither."""
    path, found = address or (None, None)
    return Referrer(
        referrer=iri,
        referrer_class=class_name,
        referrer_slot=slot,
        referrer_rp_path=path,
        referrer_id=found,
    )


def named(view: SchemaView, rows: list[ReferrerRow]) -> set[tuple[str, str, str]]:
    """``(referrer, class name, slot name)`` of each row; an IRI the schema does not know stays as it is.

    A referrer with a type the schema knows is not also listed under the types it does not.
    """
    classes = classes_by_iri(view)
    typed = {row.referrer for row in rows if row.referrer_class in classes}
    return {
        (
            row.referrer,
            classes.get(row.referrer_class, row.referrer_class),
            slot_name(view, classes.get(row.subject_class or row.referrer_class), row.predicate),
        )
        for row in rows
        if row.referrer_class in classes or row.referrer not in typed
    }


def slot_name(view: SchemaView, class_name: str | None, predicate: str) -> str:
    """The slot of ``class_name`` whose ``slot_uri`` is ``predicate``, or ``predicate`` itself.

    The identifier slot is the node's IRI, never a statement, so it never names one (#277).
    """
    slots = view.class_induced_slots(class_name) if class_name else []
    return next(
        (s.name for s in slots if not s.identifier and view.get_uri(s, expand=True) == predicate),
        predicate,
    )
