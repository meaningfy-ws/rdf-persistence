"""gen-pydantic extended with model validators for the rules the stock generator ignores (PD-24, PD-25).

* ``exactly_one_of`` and ``any_of`` become a validator on the class that declares them; a subclass inherits it,
  as Python inheritance carries pydantic validators. Each alternative is a set of slot conditions that must
  all hold, and a condition is a presence: ``required: true`` or ``value_presence: PRESENT`` or ``ABSENT``.
  Any other form is a generation error, not a rule silently left unenforced.
* ``unique_keys`` becomes a validator on every class with a multivalued slot, valued by objects, whose range
  (or an ancestor of it) declares the key. Two items with equal key tuples are refused; an absent slot is a
  value, so two absent values are equal.

The validators are rendered by the templates ``presence_validator.py.jinja`` and
``unique_keys_validator.py.jinja``.
"""

from dataclasses import dataclass
from typing import ClassVar

from linkml.generators.common.build import ClassResult
from linkml.generators.pydanticgen.template import (
    Import,
    Imports,
    ObjectImport,
    PydanticClass,
    PydanticTemplateModel,
)
from linkml_runtime.linkml_model.meta import (
    AnonymousClassExpression,
    ClassDefinition,
    SlotDefinition,
    UniqueKey,
)
from linkml_runtime.utils.formatutils import underscore
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel

from rdf_persistence.generation.checks.scope import declared_slots

VALIDATOR_IMPORT = Import(module="pydantic", objects=[ObjectImport(name="model_validator")])
PRESENT, ABSENT = "PRESENT", "ABSENT"
SUPPORTED_CONDITION_FIELDS = {"name", "required", "value_presence"}


@dataclass(frozen=True)
class PresenceRule:
    """A class-level rule over alternatives, and when its validator refuses."""

    name: str
    need: str
    refused: str


EXACTLY_ONE_OF = PresenceRule("exactly_one_of", "exactly one", "len(held) != 1")
ANY_OF = PresenceRule("any_of", "at least one", "not held")


class Alternative(BaseModel):
    """One alternative of a rule: its readable label and the Python expression that tells it holds."""

    label: str
    holds: str


class PresenceValidator(PydanticTemplateModel):
    """The validator of an ``exactly_one_of`` or ``any_of`` rule."""

    template: ClassVar[str] = "presence_validator.py.jinja"

    method: str
    class_name: str
    rule: str
    need: str
    refused: str
    alternatives: list[Alternative]
    labels: str


class UniqueKeysValidator(PydanticTemplateModel):
    """The validator of a unique key over the items of a multivalued slot."""

    template: ClassVar[str] = "unique_keys_validator.py.jinja"

    method: str
    class_name: str
    slot: str
    key_name: str
    key_slots: list[str]


class ValidatedClass(PydanticClass):
    """A pydantic class that also renders the model validators of its rules."""

    rule_validators: dict[str, PresenceValidator | UniqueKeysValidator] = {}

    def _validators(self) -> dict[str, PresenceValidator | UniqueKeysValidator] | None:
        return {**(super()._validators() or {}), **self.rule_validators} or None


def _attribute(rule: str, name: str, cls: ClassDefinition, attributes: set[str]) -> str:
    """The Python name of the slot ``name`` of ``cls``; a generation error when ``cls`` has no such slot."""
    python: str = underscore(name)
    if python not in attributes:
        raise ValueError(f"{cls.name}: {rule}: slot {name} is not a slot of the class")
    return python


def _presence(
    rule: str, cls: ClassDefinition, slot: str, condition: SlotDefinition
) -> tuple[str, bool]:
    """``(label, holds)`` of one slot condition: the slot present (True) or absent (False)."""
    where = f"{cls.name}: {rule}: slot condition on {slot}"
    others = {
        k for k, v in vars(condition).items() if v not in (None, [], {})
    } - SUPPORTED_CONDITION_FIELDS
    if others:
        raise ValueError(
            f"{where} uses {sorted(others)}; only required and value_presence are supported"
        )
    if condition.required is False:
        raise ValueError(f"{where} has required: false; use value_presence: ABSENT")
    states = {True} if condition.required else set()
    if condition.value_presence is not None:
        states.add(str(condition.value_presence) == PRESENT)
    if len(states) != 1:
        raise ValueError(f"{where} must state exactly one of required: true and value_presence")
    present = states.pop()
    return f"{slot} {'present' if present else 'absent'}", present


def _alternative(
    rule: str, cls: ClassDefinition, expression: AnonymousClassExpression, attributes: set[str]
) -> Alternative:
    extra = {k for k, v in vars(expression).items() if v not in (None, [], {})} - {
        "slot_conditions"
    }
    if extra or not expression.slot_conditions:
        raise ValueError(
            f"{cls.name}: {rule}: an alternative must hold slot_conditions only, found {sorted(extra) or 'none'}"
        )
    labels, tests = [], []
    for slot, condition in expression.slot_conditions.items():
        python = _attribute(rule, slot, cls, attributes)
        label, present = _presence(rule, cls, slot, condition)
        labels.append(label)
        tests.append(f"self.{python} {'not in' if present else 'in'} (None, [])")
    return Alternative(label=" and ".join(labels), holds=" and ".join(tests))


def _presence_validators(
    cls: ClassDefinition, attributes: set[str]
) -> dict[str, PresenceValidator]:
    found = {}
    for rule, expressions in ((EXACTLY_ONE_OF, cls.exactly_one_of), (ANY_OF, cls.any_of)):
        if not expressions:
            continue
        alternatives = [_alternative(rule.name, cls, e, attributes) for e in expressions]
        method = f"{rule.name}_{cls.name}"
        found[method] = PresenceValidator(
            method=method,
            class_name=cls.name,
            rule=rule.name,
            need=rule.need,
            refused=rule.refused,
            alternatives=alternatives,
            labels=", ".join(a.label for a in alternatives),
        )
    return found


def _holds_objects(view: SchemaView, slot: SlotDefinition) -> bool:
    """True when the values of a slot ranging over a class are objects, not references by identifier."""
    return bool(
        slot.inlined or slot.inlined_as_list or view.get_identifier_slot(slot.range) is None
    )


def _keys_of(view: SchemaView, range_: str) -> dict[str, UniqueKey]:
    """The unique keys of a class and its ancestors by name; the nearest declaration of a name wins."""
    keys: dict[str, UniqueKey] = {}
    for name in view.class_ancestors(range_):
        for key_name, key in (view.get_class(name).unique_keys or {}).items():
            keys.setdefault(key_name, key)
    return keys


def _keyed_slots(view: SchemaView, cls: ClassDefinition) -> list[SlotDefinition]:
    """The slots ``cls`` declares that hold several objects of a class, which the validators check."""
    induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
    slots = (induced[name] for name in sorted(declared_slots(cls) & induced.keys()))
    return [
        slot
        for slot in slots
        if slot.multivalued and slot.range in view.all_classes() and _holds_objects(view, slot)
    ]


def _unique_key_validator(
    view: SchemaView,
    cls: ClassDefinition,
    slot: SlotDefinition,
    key: UniqueKey,
    attributes: set[str],
) -> UniqueKeysValidator:
    item_slots = {s.name for s in view.class_induced_slots(slot.range)}
    missing = [s for s in key.unique_key_slots if s not in item_slots]
    if missing:
        raise ValueError(
            f"{cls.name}: unique key {key.unique_key_name} names {missing}, not slots of {slot.range}"
        )
    return UniqueKeysValidator(
        method=f"unique_keys_{underscore(slot.name)}_{key.unique_key_name}",
        class_name=cls.name,
        slot=_attribute("unique_keys", slot.name, cls, attributes),
        key_name=key.unique_key_name,
        key_slots=[underscore(s) for s in key.unique_key_slots],
    )


def _unique_keys_validators(
    view: SchemaView, cls: ClassDefinition, attributes: set[str]
) -> dict[str, UniqueKeysValidator]:
    validators = (
        _unique_key_validator(view, cls, slot, key, attributes)
        for slot in _keyed_slots(view, cls)
        for key in _keys_of(view, slot.range).values()
    )
    return {validator.method: validator for validator in validators}


def with_validators(result: ClassResult, view: SchemaView) -> ClassResult:
    """``result`` with the model validators of the rules its class declares; unchanged when it has none."""
    cls = result.source
    attributes = set(result.cls.attributes or {})
    validators = {
        **_presence_validators(cls, attributes),
        **_unique_keys_validators(view, cls, attributes),
    }
    if not validators:
        return result
    fields = {name: getattr(result.cls, name) for name in PydanticClass.model_fields}
    result.cls = ValidatedClass(**fields, rule_validators=validators)
    result.imports = (result.imports or Imports()) + Imports(imports=[VALIDATOR_IMPORT])
    return result
