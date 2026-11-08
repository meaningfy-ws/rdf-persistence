"""What the schema says about its aggregates and rules, read once (PD-22): annotations, defaults, rules."""

from pathlib import Path

import pytest
from linkml_runtime.linkml_model.annotations import Annotation
from linkml_runtime.linkml_model.meta import ClassDefinition, PresenceEnum, SlotDefinition

from rdf_persistence.domain.generated.rp_core import (
    DatabaseKind,
    GraphKind,
    ModuleKind,
    RpAnnotation,
)
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import (
    ABSENT,
    ANY_OF,
    EXACTLY_ONE_OF,
    PRESENT,
    UnsupportedRuleError,
    annotation,
    apply_defaults,
    flag,
    generation_view,
    holds_iri,
    holds_owned_part,
    iri_type_of,
    iri_types,
    is_bookkeeping,
    is_internal,
    is_owned,
    is_tenant_root,
    json_name,
    keyed_slots,
    presence_alternatives,
)

ROOT = Path(__file__).parents[3]
TOY = ROOT / "tests" / "fixtures" / "library" / "library.yaml"
METAMODEL = ROOT / "rdf_persistence" / "model" / "rp.yaml"

HEAD = """
id: https://example.org/ns/rules
name: rules
title: Rules
description: Classes that declare the rules the resolver reads.
prefixes: {r: "https://example.org/ns/r#", linkml: "https://w3id.org/linkml/"}
default_prefix: r
default_range: string
imports: [linkml:types]
"""

PRESENCE = (
    HEAD
    + """
classes:
  Contact:
    title: Contact
    description: A contact reachable by exactly one of mail and phone.
    slots: [mail, phone]
    exactly_one_of:
      - slot_conditions: {mail: {name: mail, required: true}}
      - slot_conditions: {phone: {name: phone, value_presence: ABSENT}}
  Reach:
    title: Reach
    description: A way to reach somebody.
    slots: [mail, phone]
    any_of:
      - slot_conditions: {mail: {name: mail, value_presence: PRESENT}}
      - slot_conditions: {phone: {name: phone, value_presence: PRESENT}}
  Customer:
    title: Customer
    description: A contact that is also a customer.
    is_a: Contact
slots:
  mail: {title: Mail, description: The mail address., range: string}
  phone: {title: Phone, description: The phone number., range: string}
"""
)

KEYS = (
    HEAD
    + """
classes:
  Entry:
    title: Entry
    description: An entry, one per name and tag.
    slots: [name, tag]
    unique_keys:
      entry_key: {unique_key_slots: [name, tag]}
      other_key: {unique_key_slots: [tag]}
  Dated:
    title: Dated
    description: An entry with a day, one per name.
    is_a: Entry
    unique_keys:
      entry_key: {unique_key_slots: [name]}
  Account:
    title: Account
    description: An account, referred to by identifier.
    slots: [acct, name]
    unique_keys:
      account_key: {unique_key_slots: [name]}
  Ledger:
    title: Ledger
    description: Entries and accounts.
    slots: [entries, dated, accounts, watchers]
slots:
  name: {title: Name, description: The name., range: string}
  tag: {title: Tag, description: The tag., range: string}
  acct: {title: Account id, description: The identifier., range: string, identifier: true}
  entries: {title: Entries, description: The entries., range: Entry, multivalued: true, inlined_as_list: true}
  dated: {title: Dated, description: The dated entries., range: Dated, multivalued: true, inlined_as_list: true}
  accounts: {title: Accounts, description: The accounts by identifier., range: Account, multivalued: true}
  watchers: {title: Watchers, description: The watchers., range: string, multivalued: true}
"""
)


def view_of(tmp_path: Path, schema: str):
    path = tmp_path / "rules.yaml"
    path.write_text(schema, encoding="utf-8")
    return load_schema(path)


def names(alternatives):
    return [[(slot, str(state)) for slot, state in alternative] for alternative in alternatives]


@pytest.mark.parametrize(
    ("slot", "check", "expected"),
    [
        ("grants", is_owned, True),
        ("grants", is_internal, False),
        ("database_name", is_internal, True),
        ("version", is_bookkeeping, True),
        ("created", is_bookkeeping, True),
        ("modified", is_bookkeeping, True),
        ("creator", is_bookkeeping, True),
        ("contributor", is_bookkeeping, True),
        ("label", is_bookkeeping, False),
    ],
)
def test_a_predicate_reads_its_annotation_from_the_metamodel(slot, check, expected) -> None:
    view = load_schema(METAMODEL)
    assert check(view.get_slot(slot)) is expected, f"{check.__name__}({slot}) != {expected}"


def test_a_tag_that_is_not_there_gives_none_and_a_false_flag() -> None:
    view = load_schema(METAMODEL)
    slot = view.get_slot("label")
    assert annotation(slot, RpAnnotation.OWNED) is None, "an absent annotation reads as None"
    assert not flag(slot, RpAnnotation.OWNED), "an absent annotation is not a true flag"


def test_the_tenant_root_is_the_class_in_the_meta_graph() -> None:
    view = load_schema(TOY)
    assert is_tenant_root(view.get_class("Library")), "Library lives in the meta graph"
    assert not is_tenant_root(view.get_class("Book")), "Book has a graph of its own"
    assert annotation(view.get_class("Library"), RpAnnotation.GRAPH) == GraphKind.META.value


def test_every_value_set_of_the_vocabulary_has_members() -> None:
    sets = {ModuleKind: 3, DatabaseKind: 2, GraphKind: 1}
    assert {k: len(k) for k in sets} == sets, "a value set of the annotation vocabulary changed"


def required(view, cls: str, slot: str) -> bool:
    return bool(view.induced_slot(slot, cls).required)


@pytest.mark.parametrize(
    ("cls", "slot", "expected"),
    [
        ("Chapter", "label", False),  # rp_unlabelled
        ("Note", "label", True),  # labelled, unchanged
        ("Book", "description", True),  # a root
        ("Scan", "description", True),  # a root
        ("LibraryAccess", "description", True),  # a root through TenantAccess
        ("Chapter", "description", False),  # owned, not a root
        ("Library", "description", False),  # the tenant root is not an AggregateRoot
    ],
)
def test_the_generation_view_has_the_defaults_applied(cls: str, slot: str, expected: bool) -> None:
    assert required(generation_view(TOY), cls, slot) is expected, f"{cls}.{slot} != {expected}"


def test_the_metamodel_is_left_untouched() -> None:
    view = load_schema(METAMODEL)
    apply_defaults(view, METAMODEL.parent)
    assert not required(view, "TenantAccess", "description"), "PD-23 exempts the metamodel"


def test_presence_alternatives_list_each_slot_present_or_absent(tmp_path: Path) -> None:
    view = view_of(tmp_path, PRESENCE)
    found = presence_alternatives(view, view.get_class("Contact"), EXACTLY_ONE_OF)
    assert names(found) == [[("mail", "PRESENT")], [("phone", "ABSENT")]], (
        "required means present; value_presence is read as written"
    )
    assert all(isinstance(s, PresenceEnum) for a in found for _, s in a), "LinkML's PresenceEnum"
    assert found[0][0][1] == PRESENT and found[1][0][1] == ABSENT, "comparable to the constants"


def test_a_rule_is_read_from_the_class_that_declares_it(tmp_path: Path) -> None:
    view = view_of(tmp_path, PRESENCE)
    assert presence_alternatives(view, view.get_class("Reach"), ANY_OF), "Reach declares any_of"
    assert presence_alternatives(view, view.get_class("Reach"), EXACTLY_ONE_OF) == [], "not this"
    assert presence_alternatives(view, view.get_class("Customer"), EXACTLY_ONE_OF) == [], (
        "a subclass declares nothing itself; the caller walks the ancestry"
    )


REFUSED = [
    ("{mail: {name: mail, required: true, value_presence: ABSENT}}", "exactly one of required"),
    ("{mail: {name: mail}}", "exactly one of required"),
    ("{mail: {name: mail, required: false}}", "required: false"),
    ("{mail: {name: mail, pattern: x}}", "pattern"),
    ("{nowhere: {name: nowhere, required: true}}", "nowhere"),
]


@pytest.mark.parametrize(("conditions", "message"), REFUSED)
def test_a_condition_other_than_a_clear_presence_is_refused(
    tmp_path: Path, conditions: str, message: str
) -> None:
    schema = PRESENCE.replace("{mail: {name: mail, required: true}}", conditions)
    view = view_of(tmp_path, schema)
    with pytest.raises(UnsupportedRuleError, match=message):
        presence_alternatives(view, view.get_class("Contact"), EXACTLY_ONE_OF)


def keyed(view, cls: str) -> list[tuple[str, str, list[str]]]:
    return [
        (str(slot.name), str(key.unique_key_name), [str(s) for s in key.unique_key_slots])
        for slot, key in keyed_slots(view, view.get_class(cls))
    ]


def test_a_slot_of_objects_is_keyed_by_the_keys_of_its_range(tmp_path: Path) -> None:
    found = keyed(view_of(tmp_path, KEYS), "Ledger")
    assert ("entries", "entry_key", ["name", "tag"]) in found, "Entry's key governs entries"
    assert ("entries", "other_key", ["tag"]) in found, "every key of the range governs it"


def test_a_slot_that_refers_by_identifier_is_not_keyed(tmp_path: Path) -> None:
    slots = {slot for slot, _, _ in keyed(view_of(tmp_path, KEYS), "Ledger")}
    assert "accounts" not in slots, "a reference holds no objects to compare"
    assert "watchers" not in slots, "a slot of strings is not keyed"


def test_the_nearest_declaration_of_a_key_name_wins(tmp_path: Path) -> None:
    found = [f for f in keyed(view_of(tmp_path, KEYS), "Ledger") if f[0] == "dated"]
    assert sorted(found) == [
        ("dated", "entry_key", ["name"]),
        ("dated", "other_key", ["tag"]),
    ], "Dated redeclares entry_key; the key of Entry it replaces must not appear as well"


def test_a_subclass_has_the_keyed_slots_it_inherits(tmp_path: Path) -> None:
    schema = KEYS.replace(
        "slots:\n  name:",
        "  Archive:\n    title: Archive\n    description: A kept ledger.\n    is_a: Ledger\nslots:\n  name:",
    )
    view = view_of(tmp_path, schema)
    assert keyed(view, "Archive") == keyed(view, "Ledger"), "inherited slots are keyed too"


def test_the_grants_of_an_access_record_are_keyed_in_the_metamodel() -> None:
    view = load_schema(METAMODEL)
    found = [
        (s.name, k.unique_key_name) for s, k in keyed_slots(view, view.get_class("TenantAccess"))
    ]
    assert found == [("grants", "grant_key")], "only the grants of an access record are keyed"


@pytest.mark.parametrize(
    ("cls", "slot", "owned_part", "iri"),
    [
        ("Book", "chapters", True, False),  # owned objects
        ("Scan", "scan_of", False, True),  # a reference to another aggregate
        ("Book", "id", False, True),  # a uri-typed slot
        ("Book", "authors", False, False),  # plain text
    ],
)
def test_a_slot_holds_owned_parts_or_iris_or_neither(cls, slot, owned_part, iri) -> None:
    view = load_schema(TOY)
    induced = view.induced_slot(slot, cls)
    assert holds_owned_part(view, induced) is owned_part, f"{cls}.{slot} owned part"
    assert holds_iri(view, induced) is iri, f"{cls}.{slot} IRI"


@pytest.mark.parametrize(
    ("name", "alias", "expected"),
    [
        ("file_key", None, "file_key"),
        ("file key", None, "file_key"),
        ("problem_slug", "slug", "slug"),
    ],
)
def test_the_json_name_of_a_slot_is_its_alias_or_its_name_in_snake_case(
    name, alias, expected
) -> None:
    assert json_name(SlotDefinition(name=name, alias=alias)) == expected


def test_the_iri_types_of_the_toy_library_are_its_roots_and_its_owned_classes() -> None:
    roots, owned = iri_types(load_schema(TOY))
    assert "book" in roots, "Book is a concrete aggregate root"
    assert {"chapter", "note"} <= owned, "the classes reached through owned slots"
    assert not roots & owned, "a type is a root's or a part's, not both"


@pytest.mark.parametrize(
    ("name", "annotated", "expected"),
    [
        ("OntologyFile", None, "ontology-file"),
        ("RDFFile", None, "rdf-file"),
        ("Term", None, "term"),
        ("OntologyFile", "ofile", "ofile"),
    ],
)
def test_the_iri_type_is_the_annotation_else_the_kebab_case_name(name, annotated, expected) -> None:
    cls = ClassDefinition(name=name)
    if annotated:
        cls.annotations[RpAnnotation.RP_IRI_TYPE.value] = Annotation(
            tag=RpAnnotation.RP_IRI_TYPE.value, value=annotated
        )
    assert iri_type_of(cls) == expected, f"{name} annotated {annotated}"
