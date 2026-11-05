"""Hypothesis strategies built from a schema's ``SchemaView`` (PD-27 item 4)."""

from hypothesis import strategies as st
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import underscore
from pydantic import BaseModel

from rdf_persistence.services.schema_structure import is_internal, is_owned
from rdf_persistence.testkit.conformance import Conformance

IRI_BASE = "https://example.org/library/"
MAX_DEPTH = 2  # owned parts below the root: Book, Chapter, Note
MAX_ITEMS = 3

IRIS = st.uuids().map(lambda u: f"{IRI_BASE}{u}")
TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zs", "Zl", "Zp")),
    min_size=1,
    max_size=12,
)
# a value strategy per LinkML type, found by walking the type's ancestors
TYPE_VALUES = (
    ("integer", st.integers(0, 10**6)),
    ("boolean", st.booleans()),
    ("datetime", st.datetimes().map(lambda d: d.isoformat())),
    ("date", st.dates().map(lambda d: d.isoformat())),
    ("uriorcurie", IRIS),
    ("uri", IRIS),
    ("string", TEXT),
)


def _scalar(conformance: Conformance, slot: SlotDefinition) -> st.SearchStrategy:
    view = conformance.view
    if slot.identifier:
        return IRIS
    if slot.pattern:
        return st.from_regex(slot.pattern, fullmatch=True)
    if slot.range in view.all_enums():
        return st.sampled_from(sorted(view.get_enum(slot.range).permissible_values))
    if slot.range in view.all_classes():  # a reference to another aggregate: its IRI
        return IRIS
    ancestors = view.type_ancestors(slot.range)
    return next(values for name, values in TYPE_VALUES if name in ancestors)


def _slot_values(conformance: Conformance, slot: SlotDefinition, depth: int) -> st.SearchStrategy:
    owned = is_owned(slot)
    one = _fields(conformance, slot.range, depth - 1) if owned else _scalar(conformance, slot)
    if not slot.multivalued:
        return one
    return st.lists(one, min_size=1, max_size=MAX_ITEMS, unique_by=repr)


def _fields(conformance: Conformance, class_name: str, depth: int) -> st.SearchStrategy[dict]:
    """The JSON of an instance of ``class_name``: required slots always, optional ones by draw."""
    slots = [s for s in conformance.view.class_induced_slots(class_name) if not is_internal(s)]
    in_scope = [s for s in slots if depth >= 0 or s.required or s.identifier]
    values = {
        underscore(s.name): _slot_values(conformance, s, depth)
        for s in in_scope
        if not is_owned(s) or depth > 0 or s.required
    }
    required = {underscore(s.name) for s in in_scope if s.required or s.identifier}
    return st.fixed_dictionaries(
        {n: v for n, v in values.items() if n in required},
        optional={n: v for n, v in values.items() if n not in required},
    )


def aggregate(conformance: Conformance, class_name: str) -> st.SearchStrategy[BaseModel]:
    """Instances of the generated class ``class_name``, owned parts drawn to depth ``MAX_DEPTH``."""
    model = conformance.models[class_name]
    return _fields(conformance, class_name, MAX_DEPTH).map(model.model_validate)
