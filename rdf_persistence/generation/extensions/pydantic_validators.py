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

from typing import ClassVar

from linkml.generators.common.build import ClassResult
from linkml.generators.pydanticgen.template import (
    Import,
    Imports,
    ObjectImport,
    PydanticClass,
    PydanticTemplateModel,
)
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition, UniqueKey
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.exceptions import (
    SchemaGenerationError,
    refusing_unsupported_rules,
)
from rdf_persistence.generation.generated.rp_generation import PresenceRule, RuleAlternative
from rdf_persistence.services.schema_structure import (
    ABSENT,
    ANY_OF,
    EXACTLY_ONE_OF,
    declared_slots,
    keyed_slots,
    presence_alternatives,
)
from rdf_persistence.services.schema_structure import (
    Alternative as Presences,
)

VALIDATOR_IMPORT = Import(module="pydantic", objects=[ObjectImport(name="model_validator")])


RULES = (
    PresenceRule(name=EXACTLY_ONE_OF, need="exactly one", refused="len(held) != 1"),
    PresenceRule(name=ANY_OF, need="at least one", refused="not held"),
)


class PresenceValidator(PydanticTemplateModel):
    """The validator of an ``exactly_one_of`` or ``any_of`` rule."""

    template: ClassVar[str] = "presence_validator.py.jinja"

    method: str
    class_name: str
    rule: str
    need: str
    refused: str
    alternatives: list[RuleAlternative]
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
        raise SchemaGenerationError(f"{cls.name}: {rule}: slot {name} is not a slot of the class")
    return python


def _alternative(
    rule: str, presences: Presences, attributes: set[str], cls: ClassDefinition
) -> RuleAlternative:
    labels, tests = [], []
    for slot, state in presences:
        present = state != ABSENT
        labels.append(f"{slot} {'present' if present else 'absent'}")
        tests.append(
            f"self.{_attribute(rule, slot, cls, attributes)} {'not in' if present else 'in'} (None, [])"
        )
    return RuleAlternative(label=" and ".join(labels), holds=" and ".join(tests))


def _presence_validators(
    view: SchemaView, cls: ClassDefinition, attributes: set[str]
) -> dict[str, PresenceValidator]:
    found = {}
    for rule in RULES:
        with refusing_unsupported_rules():
            declared = presence_alternatives(view, cls, rule.name)
        if not declared:
            continue
        alternatives = [_alternative(rule.name, p, attributes, cls) for p in declared]
        method = f"{rule.name}_{camelcase(cls.name)}"
        found[method] = PresenceValidator(
            method=method,
            class_name=camelcase(cls.name),
            rule=rule.name,
            need=rule.need,
            refused=rule.refused,
            alternatives=alternatives,
            labels=", ".join(a.label for a in alternatives),
        )
    return found


def _unique_key_validator(
    view: SchemaView,
    cls: ClassDefinition,
    slot: SlotDefinition,
    key: UniqueKey,
    attributes: set[str],
) -> UniqueKeysValidator:
    if not (key.unique_key_name.isidentifier() and key.unique_key_name.isascii()):
        raise SchemaGenerationError(
            f"{cls.name}: unique key {key.unique_key_name!r} is not an identifier"
        )
    item_slots = {s.name for s in view.class_induced_slots(slot.range)}
    missing = [s for s in key.unique_key_slots if s not in item_slots]
    if missing:
        raise SchemaGenerationError(
            f"{cls.name}: unique key {key.unique_key_name} names {missing}, not slots of {slot.range}"
        )
    return UniqueKeysValidator(
        method=f"unique_keys_{underscore(slot.name)}_{key.unique_key_name}",
        class_name=camelcase(cls.name),
        slot=_attribute("unique_keys", slot.name, cls, attributes),
        key_name=key.unique_key_name,
        key_slots=[underscore(s) for s in key.unique_key_slots],
    )


def _unique_keys_validators(
    view: SchemaView, cls: ClassDefinition, attributes: set[str]
) -> dict[str, UniqueKeysValidator]:
    declared = declared_slots(cls)
    validators = (
        _unique_key_validator(view, cls, slot, key, attributes)
        for slot, key in keyed_slots(view, cls)
        if slot.name in declared
    )
    return {validator.method: validator for validator in validators}


def with_validators(result: ClassResult, view: SchemaView) -> ClassResult:
    """``result`` with the model validators of the rules its class declares; unchanged when it has none."""
    cls = result.source
    attributes = set(result.cls.attributes or {})
    validators = {
        **_presence_validators(view, cls, attributes),
        **_unique_keys_validators(view, cls, attributes),
    }
    if not validators:
        return result
    fields = {name: getattr(result.cls, name) for name in PydanticClass.model_fields}
    result.cls = ValidatedClass(**fields, rule_validators=validators)
    result.imports = (result.imports or Imports()) + Imports(imports=[VALIDATOR_IMPORT])
    return result
