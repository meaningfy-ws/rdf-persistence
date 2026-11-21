"""The schema's names for the rows of a reverse-reference read (PD-8).

The session returns referrers as IRIs; the schema names their class and slot. These functions take
the schema view they read from, so ``Collaboration`` and the removal guard name rows alike.
"""

from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.persistence.services.session import ReferrerRow


def classes_by_iri(view: SchemaView) -> dict[str, str]:
    """The name of each class of the schema, by its expanded IRI."""
    return {view.get_uri(c, expand=True): name for name, c in view.all_classes().items()}


def named(view: SchemaView, rows: list[ReferrerRow]) -> set[tuple[str, str, str]]:
    """``(referrer, class name, slot name)`` of each row; an IRI the schema does not know stays as it is.

    A referrer with a type the schema knows is not also listed under the types it does not.
    """
    classes = classes_by_iri(view)
    typed = {referrer for referrer, cls, _, _ in rows if cls in classes}
    return {
        (
            referrer,
            classes.get(cls, cls),
            slot_name(view, classes.get(subject or cls), predicate),
        )
        for referrer, cls, subject, predicate in rows
        if cls in classes or referrer not in typed
    }


def slot_name(view: SchemaView, class_name: str | None, predicate: str) -> str:
    """The slot of ``class_name`` whose ``slot_uri`` is ``predicate``, or ``predicate`` itself."""
    slots = view.class_induced_slots(class_name) if class_name else []
    return next((s.name for s in slots if view.get_uri(s, expand=True) == predicate), predicate)
