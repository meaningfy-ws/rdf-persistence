"""The schema lock, its comparison and the migration it drafts (PD-3, PD-5).

``summarise`` reads what a target stores, as RDF sees it: IRIs, not LinkML names, so a rename that keeps
its IRIs changes nothing. ``changes`` classifies each difference between two locks by the table of PD-3;
``draft`` turns them into the steps of a migration for the developer to review.
"""

from collections.abc import Iterable, Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.core.domain.sparql import term
from rdf_persistence.services.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.services.schema_structure import (
    annotation_text,
    database_of,
    holds_owned_part,
    iri_type_of,
    root_classes,
)
from rdf_persistence_generation.generated.rp_generation import (
    LockChange,
    LockedClass,
    LockedEnum,
    LockedSlot,
    LockRule,
    SchemaLock,
)


def described(change: LockChange) -> str:
    """The change as one line: the sentence, then the slot of the class, or the enum and value."""
    where = " of ".join(f"<{p}>" for p in (change.slot_uri, change.class_uri) if p)
    about = where or " ".join(p for p in (change.enum_name, change.enum_value) if p)
    return f"{change.what}: {about}" if about else change.what


# ---- summarise ---------------------------------------------------------------------------------


def _iri(view: SchemaView, element: ClassDefinition | SlotDefinition) -> str:
    return str(view.get_uri(element, expand=True))


def _range_of(view: SchemaView, slot: SlotDefinition) -> str:
    """The range as an IRI; an enum's name for an enum."""
    range_ = str(slot.range)
    if range_ in view.all_classes():
        return _iri(view, view.get_class(range_))
    if range_ in view.all_enums():
        return range_
    return str(view.expand_curie(str(view.get_type(range_).uri)))


def _stored_classes(view: SchemaView, folder: Path) -> list[ClassDefinition]:
    """The own roots and the classes reachable from them through owned parts, concrete ones only."""
    found: dict[str, ClassDefinition] = {}
    pending = [root.name for root in root_classes(view, folder)]
    while pending:
        name = pending.pop()
        cls = view.get_class(name)
        if name in found or cls.mixin or cls.abstract:
            continue
        found[name] = cls
        for slot in view.class_induced_slots(name):
            if holds_owned_part(view, slot):
                pending.extend(view.class_descendants(str(slot.range)))
    return list(found.values())


def _locked_slot(view: SchemaView, slot: SlotDefinition) -> LockedSlot:
    return LockedSlot(
        slot_uri=_iri(view, slot),
        range=_range_of(view, slot),
        required=bool(slot.required),
        multivalued=bool(slot.multivalued),
        inlined=holds_owned_part(view, slot),
    )


def _locked_class(view: SchemaView, cls: ClassDefinition, roots: set[str]) -> LockedClass:
    is_root = cls.name in roots
    slots = sorted(
        (_locked_slot(view, s) for s in view.class_induced_slots(cls.name)), key=_slot_key
    )
    return LockedClass(
        class_uri=_iri(view, cls),
        iri_type=iri_type_of(cls) if is_root else None,
        root_path=annotation_text(cls, RpAnnotation.RP_PATH) if is_root else None,
        root_database=database_of(view, cls).value if is_root else None,
        locked_slots=slots,
    )


def _slot_key(slot: LockedSlot) -> tuple[str, str, bool, bool, bool]:
    """Every field, so slots sharing an IRI keep one order whatever the schema's declaration order."""
    return (
        slot.slot_uri,
        slot.range,
        bool(slot.required),
        bool(slot.multivalued),
        bool(slot.inlined),
    )


def _merged(classes: Iterable[LockedClass]) -> list[LockedClass]:
    """One class per IRI, with the union of the slots: stored data cannot tell classes sharing an IRI apart."""
    by_uri: dict[str, list[LockedClass]] = {}
    for cls in classes:
        by_uri.setdefault(cls.class_uri, []).append(cls)
    return [_merge_group(uri, group) for uri, group in sorted(by_uri.items())]


def _merge_group(uri: str, group: list[LockedClass]) -> LockedClass:
    def first(field: str) -> str | None:
        return next((v for c in group if (v := getattr(c, field))), None)

    slots = {_slot_key(s): s for c in group for s in c.locked_slots or []}
    return LockedClass(
        class_uri=uri,
        iri_type=first("iri_type"),
        root_path=first("root_path"),
        root_database=first("root_database"),
        locked_slots=sorted(slots.values(), key=_slot_key),
    )


def _locked_enum(view: SchemaView, name: str) -> LockedEnum:
    values = [
        str(view.expand_curie(pv.meaning)) if pv.meaning else str(pv.text)
        for pv in view.get_enum(name).permissible_values.values()
    ]
    return LockedEnum(name=name, enum_values=sorted(values))


def summarise(view: SchemaView, folder: Path) -> SchemaLock:
    """The lock of the schema: what the modules kept in ``folder`` store, sorted so it is repeatable."""
    roots = {root.name for root in root_classes(view, folder)}
    stored = _stored_classes(view, folder)
    classes = [_locked_class(view, cls, roots) for cls in stored]
    enums = {
        str(slot.range)
        for cls in stored
        for slot in view.class_induced_slots(cls.name)
        if str(slot.range) in view.all_enums()
    }
    return SchemaLock(
        schema_id=str(view.schema.id),
        schema_version=str(view.schema.version),
        locked_classes=_merged(classes),
        locked_enums=[_locked_enum(view, name) for name in sorted(enums)],
    )


# ---- changes -----------------------------------------------------------------------------------


def _slot_changes(class_uri: str, old: LockedSlot, new: LockedSlot) -> Iterator[LockChange]:
    rows = (
        (
            bool(old.inlined) != bool(new.inlined),
            LockRule.NOT_MIGRATABLE,
            "inlined changed (data would move between graphs)",
        ),
        (
            old.range != new.range,
            LockRule.NEEDS_STEP,
            f"range changed from {old.range} to {new.range}",
        ),
        (bool(new.required) and not old.required, LockRule.NEEDS_STEP, "slot became required"),
        (bool(old.required) and not new.required, LockRule.SAFE, "required dropped"),
        (
            bool(old.multivalued) and not new.multivalued,
            LockRule.NEEDS_STEP,
            "multivalued became single",
        ),
        (bool(new.multivalued) and not old.multivalued, LockRule.SAFE, "single became multivalued"),
    )
    for happened, rule, what in rows:
        if happened:
            yield LockChange(rule=rule, what=what, class_uri=class_uri, slot_uri=new.slot_uri)


def _class_changes(old: LockedClass, new: LockedClass) -> Iterator[LockChange]:
    uri = new.class_uri
    if (old.iri_type, old.root_path) != (new.iri_type, new.root_path):
        yield LockChange(
            rule=LockRule.NOT_MIGRATABLE,
            what=f"IRI type or path changed from {old.iri_type}/{old.root_path} "
            f"to {new.iri_type}/{new.root_path} (a step cannot change an IRI)",
            class_uri=uri,
        )
    if old.root_database != new.root_database:
        yield LockChange(
            rule=LockRule.NOT_MIGRATABLE,
            what=f"database changed from {old.root_database} to {new.root_database} "
            "(the data would be read from another database)",
            class_uri=uri,
        )
    yield from _class_slot_changes(old, new)


def _class_slot_changes(old: LockedClass, new: LockedClass) -> Iterator[LockChange]:
    uri = new.class_uri
    old_slots = {s.slot_uri: s for s in old.locked_slots or []}
    new_slots = {s.slot_uri: s for s in new.locked_slots or []}
    for slot_uri in sorted(old_slots.keys() | new_slots.keys()):
        if slot_uri not in new_slots:
            yield LockChange(
                rule=LockRule.DESTRUCTIVE,
                what="slot removed (deletes data)",
                class_uri=uri,
                slot_uri=slot_uri,
            )
        elif slot_uri not in old_slots:
            rule = LockRule.NEEDS_STEP if new_slots[slot_uri].required else LockRule.SAFE
            yield LockChange(rule=rule, what="slot added", class_uri=uri, slot_uri=slot_uri)
        else:
            yield from _slot_changes(uri, old_slots[slot_uri], new_slots[slot_uri])


def _enum_changes(old: LockedEnum, new: LockedEnum) -> Iterator[LockChange]:
    before, after = set(old.enum_values or []), set(new.enum_values or [])
    for value in sorted(after - before):
        yield LockChange(
            rule=LockRule.SAFE, what="enum value added", enum_name=new.name, enum_value=value
        )
    for value in sorted(before - after):
        yield LockChange(
            rule=LockRule.NEEDS_STEP,
            what="enum value removed",
            enum_name=new.name,
            enum_value=value,
        )


def _all_class_changes(old: SchemaLock, new: SchemaLock) -> Iterator[LockChange]:
    old_classes = {c.class_uri: c for c in _merged(old.locked_classes or [])}
    new_classes = {c.class_uri: c for c in _merged(new.locked_classes or [])}
    for uri in sorted(old_classes.keys() | new_classes.keys()):
        if uri not in new_classes:
            yield LockChange(rule=LockRule.NEEDS_STEP, what="class removed", class_uri=uri)
        elif uri not in old_classes:
            yield LockChange(rule=LockRule.SAFE, what="class added", class_uri=uri)
        else:
            yield from _class_changes(old_classes[uri], new_classes[uri])


def _all_enum_changes(old: SchemaLock, new: SchemaLock) -> Iterator[LockChange]:
    old_enums = {e.name: e for e in old.locked_enums or []}
    new_enums = {e.name: e for e in new.locked_enums or []}
    for name in sorted(old_enums.keys() | new_enums.keys()):
        yield from _enum_changes(
            old_enums.get(name) or LockedEnum(name=name),
            new_enums.get(name) or LockedEnum(name=name),
        )


def changes(old: SchemaLock, new: SchemaLock) -> list[LockChange]:
    """The differences from ``old`` to ``new``, each classified by the PD-3 table; sorted, so stable."""
    return [*_all_class_changes(old, new), *_all_enum_changes(old, new)]


# ---- draft -------------------------------------------------------------------------------------

DRAFT_DESCRIPTION = "Drafted by rp-generate from the schema change. Review every step."


def _drop_step(change: LockChange) -> MigrationStep:
    cls, slot = term(URIRef(str(change.class_uri))), term(URIRef(str(change.slot_uri)))
    return MigrationStep(
        title=f"DROP {slot} of {cls} (deletes data)",
        where_pattern=f"?s a {cls} ; {slot} ?o",
        delete_pattern=f"?s {slot} ?o",
    )


def _unresolved_step(change: LockChange) -> MigrationStep:
    return MigrationStep(
        title=described(change),
        unresolved=f"Write the step for this change, or remove it if no data needs moving: {described(change)}",
    )


def draft(old: SchemaLock, new: SchemaLock) -> Migration:
    """The migration from ``old`` to ``new``: a drop per destructive change, an unresolved step per
    needs-a-step change, nothing for a safe one. A not-migratable change never reaches a draft."""
    steps = [
        _drop_step(c) if c.rule == LockRule.DESTRUCTIVE else _unresolved_step(c)
        for c in changes(old, new)
        if c.rule in (LockRule.DESTRUCTIVE, LockRule.NEEDS_STEP)
    ]
    return Migration(
        schema_id=new.schema_id,
        from_version=old.schema_version,
        to_version=new.schema_version,
        description=DRAFT_DESCRIPTION,
        steps=steps,
    )
