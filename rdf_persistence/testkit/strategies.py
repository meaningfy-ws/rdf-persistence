"""Hypothesis strategies built from a schema's ``SchemaView`` (PD-27 item 4).

Needs ``hypothesis``, which is not a dependency of the toolkit: add it to the test dependencies of
the project that imports this module. Nothing else of the testkit imports it.
"""

try:
    from hypothesis import strategies as st
except ImportError as error:  # pragma: no cover - exercised by a test through a blocked import
    raise ImportError(
        "rdf_persistence.testkit.strategies needs hypothesis: add `hypothesis` to your test dependencies"
    ) from error

from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import underscore
from pydantic import BaseModel

from rdf_persistence.services.schema_structure import (
    ABSENT,
    ANY_OF,
    EXACTLY_ONE_OF,
    Alternative,
    is_owned,
    presence_alternatives,
)
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


def _presence_choices(
    conformance: Conformance, class_name: str
) -> list[tuple[str, list[Alternative]]]:
    """The ``exactly_one_of`` and ``any_of`` rules of the class and its ancestors, with their alternatives."""
    view = conformance.view
    return [
        (rule, found)
        for ancestor in view.class_ancestors(class_name)
        for rule in (EXACTLY_ONE_OF, ANY_OF)
        if (found := presence_alternatives(view, view.get_class(ancestor), rule))
    ]


def _present_slots(alternative: Alternative) -> set[str]:
    return {slot for slot, state in alternative if state != ABSENT}


def _held(rule: str, alternatives: list[Alternative], pick: int) -> tuple[set[str], set[str]]:
    """The slots the picked alternative makes present, and those it makes absent."""
    chosen = alternatives[pick]
    absent = {slot for slot, state in chosen if state == ABSENT}
    if rule == EXACTLY_ONE_OF:  # the other alternatives must not hold
        absent |= {
            s for i, alt in enumerate(alternatives) if i != pick for s in _present_slots(alt)
        }
    return _present_slots(chosen), absent


def _forced(
    choices: list[tuple[str, list[Alternative]]], picks: tuple[int, ...]
) -> tuple[set[str], set[str]]:
    """The slots the picked alternatives of every rule make present, and the ones they make absent."""
    held = [_held(rule, alts, pick) for (rule, alts), pick in zip(choices, picks, strict=True)]
    present = set().union(*(slots for slots, _ in held))
    return present, set().union(*(slots for _, slots in held)) - present


def _fields(conformance: Conformance, class_name: str, depth: int) -> st.SearchStrategy[dict]:
    """The JSON of an instance of ``class_name``: required slots always, optional ones by draw.

    A class that declares ``exactly_one_of`` or ``any_of`` draws one alternative and makes it hold.
    Internal slots are drawn too: they belong to the object, though they never cross the context.
    """
    choices = _presence_choices(conformance, class_name)
    picks = st.tuples(*(st.integers(0, len(found) - 1) for _, found in choices))
    return picks.flatmap(
        lambda drawn: _fields_for(conformance, class_name, depth, _forced(choices, drawn))
    )


def _must(slot: SlotDefinition, present: set[str]) -> bool:
    return bool(slot.required or slot.identifier or slot.name in present)


def _drawn(slot: SlotDefinition, depth: int, must: bool) -> bool:
    """Whether the slot is drawn at this depth: beyond the last level only what is required, and
    an optional owned part only above it."""
    deep_enough = depth >= 0 or must
    return deep_enough and (not is_owned(slot) or depth > 0 or bool(slot.required))


def _fields_for(
    conformance: Conformance, class_name: str, depth: int, forced: tuple[set[str], set[str]]
) -> st.SearchStrategy[dict]:
    present, absent = forced
    slots = [s for s in conformance.view.class_induced_slots(class_name) if s.name not in absent]
    required = {underscore(s.name) for s in slots if _must(s, present)}
    values = _drawn_values(conformance, slots, depth, required)
    return st.fixed_dictionaries(
        {n: v for n, v in values.items() if n in required},
        optional={n: v for n, v in values.items() if n not in required},
    )


def _drawn_values(
    conformance: Conformance, slots: list[SlotDefinition], depth: int, required: set[str]
) -> dict[str, st.SearchStrategy]:
    """A strategy for each slot drawn at this depth, by the name it has in JSON."""
    return {
        underscore(s.name): _slot_values(conformance, s, depth)
        for s in slots
        if _drawn(s, depth, underscore(s.name) in required)
    }


def aggregate(conformance: Conformance, class_name: str) -> st.SearchStrategy[BaseModel]:
    """Instances of the generated class ``class_name``, owned parts drawn to depth ``MAX_DEPTH``."""
    model = conformance.models[class_name]
    return _fields(conformance, class_name, MAX_DEPTH).map(model.model_validate)
