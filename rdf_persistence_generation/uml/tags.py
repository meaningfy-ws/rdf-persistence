"""Class tagged values and unique keys (R-20, R-21; PD-20, PD-21; F-1, F-2, F-6; DEC-2, DEC-3).

A tag named like a class annotation of the toolkit's metamodel becomes that annotation; its value is checked
with the hard check's own tables, so a new annotation needs no change here (A-1). The ``unique_key`` tag
becomes a ``unique_keys`` entry. ``apply_tags`` is the one call ``classes.build_class`` makes.
"""

import re
from typing import Final

from linkml_runtime.linkml_model import Annotation
from linkml_runtime.linkml_model.meta import ClassDefinition, UniqueKey

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation, UniqueScope
from rdf_persistence_generation.checks.hard import (
    ALLOWED_ANNOTATIONS,
    PATTERNED_ANNOTATIONS,
    segment_pattern,
)
from rdf_persistence_generation.generated.rp_generation import ReportKind, UmlElement, UmlRule
from rdf_persistence_generation.uml.context import Context

RP_MIXINS: Final = "rp_mixins"  # a tag of the mixin rules (R-25..R-28), not read here
UNIQUE_KEY: Final = "unique_key"
GRAPH: Final = "graph"  # a tenant root's is set by its stereotype (R-18), so its tag is read there
NULLS_EQUAL: Final = "nulls=equal"
KEY_FORM: Final = "<name>: <attribute>, <attribute> [; nulls=equal]"
_KEY = re.compile(r"([^:;]*):([^;]*)(?:;(.*))?", re.DOTALL)
_OWN_TAGS: Final = (RP_MIXINS, UNIQUE_KEY)
_ANNOTATION_NAMES: Final = frozenset(each.value for each in RpAnnotation)


def apply_tags(
    ctx: Context,
    element: UmlElement,
    definition: ClassDefinition,
    derived: dict[str, Annotation],
) -> None:
    """Write the annotations and the unique keys the class's tagged values stand for; report the others.

    ``derived`` are the annotations the converter gives the class itself (a root's path); a tag overrides one.
    """
    annotations = dict(derived)
    tags = ctx.tags.get(element.uml_class.object_id, {})
    for name in sorted(tags):
        if name not in _OWN_TAGS and not (name == GRAPH and element.is_tenant_root):
            written = _annotation_of(ctx, element, name, tags[name])
            if written is not None:
                annotations[name] = written
    if annotations:
        definition.annotations = annotations
    keys = _unique_keys(ctx, element)
    if keys:
        definition.unique_keys = keys


def _annotation_of(ctx: Context, element: UmlElement, name: str, text: str) -> Annotation | None:
    if name in ctx.toolkit.class_annotations:
        why = _value_problem(RpAnnotation(name), text)
        if why is None:
            return Annotation(tag=name, value=text)
        ctx.findings.problem(UmlRule.CLASS_ANNOTATION, element.label, why)
    elif name in _ANNOTATION_NAMES:
        message = f"{name}: tagged value is not a class annotation"
        ctx.findings.problem(UmlRule.CLASS_ANNOTATION, element.label, message)
    else:
        ctx.findings.note(ReportKind.IGNORED_TAG, element.label, f"tagged value {name} is not used")
    return None


def package_kind(ctx: Context, package: str, written: str) -> str | None:
    """A package's ``module_kind`` tagged value, checked like a class annotation's; None, a problem, when wrong (#245)."""
    why = _value_problem(RpAnnotation.MODULE_KIND, written)
    if why is None:
        return written.lower()
    ctx.findings.problem(UmlRule.PACKAGE_MODULE, package, why)
    return None


def _value_problem(tag: RpAnnotation, text: str) -> str | None:
    """What is wrong with the value, by the hard check's rule (read case-blind, as it does); None when nothing."""
    allowed = ALLOWED_ANNOTATIONS.get(tag)
    if allowed is not None and text.lower() not in allowed:
        return f"{tag.value}: {text.lower()!r} is not one of {allowed}"
    pattern = segment_pattern()
    if tag in PATTERNED_ANNOTATIONS and not re.fullmatch(pattern, text):
        return f"{tag.value}: {text!r} does not match {pattern}"
    return None


def _takes_tenant_scope(element: UmlElement) -> bool:
    """True when a key of the class holds across the tenant's aggregates: a root or an abstract root (PD-21)."""
    return bool(element.is_root or element.is_abstract_root)


def _unique_keys(ctx: Context, element: UmlElement) -> dict[str, UniqueKey]:
    keys: dict[str, UniqueKey] = {}
    for written in ctx.tag_values.get(element.uml_class.object_id, {}).get(UNIQUE_KEY, []):
        key = _unique_key(ctx, element, written)
        if key is None:
            continue
        if str(key.unique_key_name) in keys:
            _key_problem(ctx, element, written, "a key of this name is declared twice")
        else:
            keys[str(key.unique_key_name)] = key
    return dict(sorted(keys.items()))


def _key_problem(ctx: Context, element: UmlElement, written: str, why: str) -> None:
    ctx.findings.problem(UmlRule.UNIQUE_KEY, element.label, f"{UNIQUE_KEY} {written!r}: {why}")


def _unique_key(ctx: Context, element: UmlElement, written: str) -> UniqueKey | None:
    parsed = _parse_key(ctx, element, written)
    if isinstance(parsed, str):
        _key_problem(ctx, element, written, parsed)
        return None
    return _build_key(element, *parsed)


def _parse_key(
    ctx: Context, element: UmlElement, written: str
) -> tuple[str, list[str], str | None] | str:
    """The name, the slots and the nulls clause of a key; what is wrong with the tag when it is not one."""
    match = _KEY.fullmatch(written.strip())
    if match is None:
        return f"expected {KEY_FORM}"
    name, slots, clause = match.groups()
    clause = None if clause is None else clause.strip()
    why = _grammar_problem(name.strip(), slots, clause)
    if why is not None:
        return why
    listed = _slots_of(ctx, element, slots)
    why = _unknown_problem(element, listed)
    if why is not None:
        return why
    return name.strip(), [str(found) for _, found in listed], clause


def _unknown_problem(element: UmlElement, listed: list[tuple[str, str | None]]) -> str | None:
    unknown = [each for each, found in listed if found is None]
    if not unknown:
        return None
    return f"no attribute or role {', '.join(repr(each) for each in unknown)} on {element.label}"


def _grammar_problem(name: str, slots: str, clause: str | None) -> str | None:
    if not (name.isidentifier() and name.isascii()):
        return f"the name {name!r} is not an identifier"
    if not all(each.strip() for each in slots.split(",")):
        return f"expected {KEY_FORM}: an attribute is missing"
    if clause is not None and clause != NULLS_EQUAL:
        return f"expected {KEY_FORM}: {clause!r} is not {NULLS_EQUAL}"
    return None


def _slots_of(ctx: Context, element: UmlElement, listed: str) -> list[tuple[str, str | None]]:
    """Each listed name with the slot it stands for: a slot name or a UML name of an attribute or a role.

    An attribute that reuses a toolkit slot stands for the toolkit's slot; None when the name is unknown.
    """
    named = ctx.slot_aliases.get(element.uml_class.object_id, {})
    return [(each.strip(), named.get(each.strip())) for each in listed.split(",")]


def _build_key(element: UmlElement, name: str, slots: list[str], clause: str | None) -> UniqueKey:
    key = UniqueKey(unique_key_name=name, unique_key_slots=slots)
    if clause == NULLS_EQUAL:
        key.consider_nulls_inequal = False
    if _takes_tenant_scope(element):
        scope = RpAnnotation.RP_UNIQUE_SCOPE.value
        key.annotations = {scope: Annotation(tag=scope, value=UniqueScope.TENANT.value)}
    return key
