"""The lock, the diff and the draft (task 1.2, PD-3, PD-5; TC-01 to TC-05a)."""

from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema_structure import generation_view
from rdf_persistence_generation.generated.rp_generation import (
    LockChange,
    LockedClass,
    LockedSlot,
    LockRule,
    SchemaLock,
)
from rdf_persistence_generation.lock import changes, described, draft, summarise

from .conftest import ROOT_SCHEMA, Breaker

BOOK = "http://purl.org/ontology/bibo/Book"
SHELF = "https://example.org/ns/library#Shelf"
SHELF_SLOT = "https://example.org/ns/library#shelf"
ISBN = "http://purl.org/ontology/bibo/isbn"
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"

# (module, old, new) edits, each applied to the first match.
Edits = tuple[tuple[str, str, str], ...]

BOOK_SLOTS = "slots: [isbn, authors, published, genre, chapters, shelf, sequel_of]"
SUBTITLE_SLOT = "slots:\n  subtitle:\n    slot_uri: lib:subtitle\n    range: string\n  isbn:"
ISBN_DEF = "    slot_uri: bibo:isbn\n    range: string\n"
AUTHORS_MULTI = "    slot_uri: schema:author\n    range: string\n    multivalued: true\n"
NEW_ROOT = (
    "slots:\n  isbn:",
    "  Rack:\n    class_uri: lib:Rack\n    mixins: [AggregateRoot, Described, Tracked]\n"
    "    annotations:\n      rp_path: racks\n      database: tenant\n\nslots:\n  isbn:",
)


def lock_of(root: Path) -> SchemaLock:
    return summarise(generation_view(root), root.parent)


def locks_after(toy: Path, break_toy: Breaker, edits: Edits) -> tuple[SchemaLock, SchemaLock]:
    """The toy's lock before and after ``edits``."""
    before = lock_of(toy / ROOT_SCHEMA)
    for edit in edits:
        break_toy(*edit)
    return before, lock_of(toy / ROOT_SCHEMA)


def classes_of(lock: SchemaLock) -> dict[str, LockedClass]:
    return {c.class_uri: c for c in lock.locked_classes or []}


def slots_of(lock: SchemaLock, class_uri: str) -> dict[str, LockedSlot]:
    return {s.slot_uri: s for s in classes_of(lock)[class_uri].locked_slots or []}


# ---- TC-01 -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def toy_lock() -> SchemaLock:
    return lock_of(Path(__file__).parents[2] / "fixtures" / "library" / ROOT_SCHEMA)


def test_the_lock_names_the_schema(toy_lock: SchemaLock) -> None:
    assert toy_lock.schema_id == "https://example.org/ns/library", "the lock names the schema"
    assert toy_lock.schema_version == "1", "the lock names the version"


def test_a_root_is_locked_with_its_iri_type_path_and_slots(toy_lock: SchemaLock) -> None:
    book = classes_of(toy_lock)[BOOK]
    assert book.iri_type == "book", "a root records its type"
    assert book.root_path == "books", "a root records its path"
    isbn = slots_of(toy_lock, BOOK)[ISBN]
    assert isbn.range == XSD_STRING, "a string slot records the datatype IRI"
    assert not isbn.required, "isbn is optional"
    assert not isbn.multivalued, "isbn is single"
    assert not isbn.inlined, "isbn is a value"


def test_a_slot_to_a_class_records_the_class_iri_and_an_owned_slot_is_inlined(
    toy_lock: SchemaLock,
) -> None:
    slots = slots_of(toy_lock, BOOK)
    chapters = slots["https://example.org/ns/library#chapter"]
    assert chapters.range == "http://purl.org/ontology/bibo/Chapter", "range is the class IRI"
    assert chapters.multivalued, "chapters are many"
    assert chapters.inlined, "chapters are owned"
    assert slots[SHELF_SLOT].range == SHELF, "a reference to a root keeps the root's IRI"
    assert slots[SHELF_SLOT].inlined is False, "a reference is not owned"


def test_an_enum_range_is_the_enum_name_and_its_values_are_meaning_iris(
    toy_lock: SchemaLock,
) -> None:
    genre = slots_of(toy_lock, BOOK)["http://schema.org/genre"]
    assert genre.range == "Genre", "an enum range is the enum's name"
    enums = {e.name: e.enum_values for e in toy_lock.locked_enums or []}
    assert enums["Genre"] == [
        "http://schema.org/Fiction",
        "http://schema.org/NonFiction",
        "http://schema.org/Poetry",
    ], "values are meaning IRIs, sorted"


def test_the_tenant_root_and_the_owned_parts_are_locked(toy_lock: SchemaLock) -> None:
    classes = classes_of(toy_lock)
    assert "http://schema.org/Library" in classes, "the tenant root is stored"
    assert "http://purl.org/ontology/bibo/Chapter" in classes, "an owned part is stored"
    assert "https://example.org/ns/library#Note" in classes, "a part of a part is stored"
    assert classes["http://purl.org/ontology/bibo/Chapter"].iri_type is None, (
        "only roots have a type"
    )


def test_the_lock_holds_no_mixin_or_toolkit_class_that_no_root_reaches(
    toy_lock: SchemaLock,
) -> None:
    """The toy has no abstract class; an abstract root is the case of `test_lock_adversarial.py`."""
    uris = set(classes_of(toy_lock))
    toolkit = {u.rsplit("#", 1)[-1] for u in uris if "meaningfy.ws" in u}
    assert toolkit == {"MembershipRule", "SlotEquality"}, f"toolkit classes in the lock: {toolkit}"
    assert not any(u.endswith(("#Comment", "#TenantAccess")) for u in uris), "unreachable class"
    mixins = ("#Described", "#Tracked", "#AggregateRoot")
    assert not any(u.endswith(mixins) for u in uris), "a mixin is not stored"


def test_the_lock_is_sorted_and_repeatable(toy_lock: SchemaLock) -> None:
    uris = [c.class_uri for c in toy_lock.locked_classes or []]
    assert uris == sorted(uris), "classes sorted by IRI"
    for cls in toy_lock.locked_classes or []:
        slot_uris = [s.slot_uri for s in cls.locked_slots or []]
        assert slot_uris == sorted(slot_uris), f"slots of {cls.class_uri} sorted"
    names = [e.name for e in toy_lock.locked_enums or []]
    assert names == sorted(names), "enums sorted by name"
    again = lock_of(Path(__file__).parents[2] / "fixtures" / "library" / ROOT_SCHEMA)
    assert again == toy_lock, "the same schema gives the same lock"


# ---- TC-02, TC-03, TC-04: classification, both directions --------------------------------------

ADD_SUBTITLE: Edits = (
    ("books.yaml", BOOK_SLOTS, BOOK_SLOTS.replace("sequel_of]", "sequel_of, subtitle]")),
    ("books.yaml", "slots:\n  isbn:", SUBTITLE_SLOT),
)
ADD_SUBTITLE_REQUIRED: Edits = (
    *ADD_SUBTITLE,
    ("books.yaml", "range: string\n  isbn:", "range: string\n    required: true\n  isbn:"),
)
ISBN_REQUIRED: Edits = (("books.yaml", ISBN_DEF, ISBN_DEF + "    required: true\n"),)
AUTHORS_SINGLE: Edits = (
    ("books.yaml", AUTHORS_MULTI, AUTHORS_MULTI.replace("    multivalued: true\n", "")),
)
RANGE_CHANGED: Edits = (("books.yaml", "    range: date\n", "    range: string\n"),)
ENUM_VALUE: Edits = (
    (
        "books.yaml",
        "      poetry:\n",
        "      drama:\n        meaning: schema:Drama\n      poetry:\n",
    ),
)
ADD_ROOT: Edits = (("books.yaml", *NEW_ROOT),)

# (edits, rule going old -> edited, rule going edited -> old, words the change names)
TABLE = [
    pytest.param(ADD_ROOT, LockRule.SAFE, LockRule.NEEDS_STEP, "Rack", id="class"),
    pytest.param(ADD_SUBTITLE, LockRule.SAFE, LockRule.DESTRUCTIVE, "subtitle", id="optional-slot"),
    pytest.param(ISBN_REQUIRED, LockRule.NEEDS_STEP, LockRule.SAFE, "isbn", id="required"),
    pytest.param(AUTHORS_SINGLE, LockRule.NEEDS_STEP, LockRule.SAFE, "author", id="multivalued"),
    pytest.param(ENUM_VALUE, LockRule.SAFE, LockRule.NEEDS_STEP, "Drama", id="enum-value"),
    pytest.param(RANGE_CHANGED, LockRule.NEEDS_STEP, LockRule.NEEDS_STEP, "issued", id="range"),
    pytest.param(
        ADD_SUBTITLE_REQUIRED, LockRule.NEEDS_STEP, LockRule.DESTRUCTIVE, "subtitle", id="req-slot"
    ),
]


@pytest.mark.parametrize(("edits", "forward", "backward", "mention"), TABLE)
def test_a_change_is_classified_in_both_directions(
    toy_copy: Path,
    break_toy: Breaker,
    edits: Edits,
    forward: LockRule,
    backward: LockRule,
    mention: str,
) -> None:
    before, after = locks_after(toy_copy, break_toy, edits)
    for old, new, rule in ((before, after, forward), (after, before, backward)):
        found = changes(old, new)
        assert [c.rule for c in found] == [rule], f"changes: {[described(c) for c in found]}"
        assert mention in described(found[0]), f"{mention!r} not named in {found[0]}"


def test_a_slot_change_names_its_class_and_slot(toy_copy: Path, break_toy: Breaker) -> None:
    before, after = locks_after(toy_copy, break_toy, ISBN_REQUIRED)
    (change,) = changes(before, after)
    assert change.class_uri == BOOK, "the class is named"
    assert change.slot_uri == ISBN, "the slot is named"


def test_an_enum_change_names_enum_and_value(toy_copy: Path, break_toy: Breaker) -> None:
    before, after = locks_after(toy_copy, break_toy, ENUM_VALUE)
    (change,) = changes(after, before)
    assert change.enum_name == "Genre", "the enum is named"
    assert change.enum_value == "http://schema.org/Drama", "the value is named"


def test_no_change_gives_no_differences(toy_copy: Path) -> None:
    lock = lock_of(toy_copy / ROOT_SCHEMA)
    assert changes(lock, lock) == [], "no change, no difference"
    assert draft(lock, lock).steps == [], "no change, no step"


# ---- TC-03: the drop draft ---------------------------------------------------------------------

DROP_SHELF: Edits = (("books.yaml", "slot_uri: lib:shelf\n", "slot_uri: lib:shelfMark\n"),)


def test_a_removed_slot_iri_is_destructive_and_drafts_a_drop(
    toy_copy: Path, break_toy: Breaker
) -> None:
    before, after = locks_after(toy_copy, break_toy, DROP_SHELF)
    found = changes(before, after)
    destructive = [c for c in found if c.rule == LockRule.DESTRUCTIVE]
    assert [(c.class_uri, c.slot_uri) for c in destructive] == [(BOOK, SHELF_SLOT)], "one drop"
    others = [c.rule for c in found if c.rule != LockRule.DESTRUCTIVE]
    assert others == [LockRule.SAFE], "the new slot IRI is safe"

    migration = draft(before, after)
    assert migration.schema_id == "https://example.org/ns/library", "the schema comes from the lock"
    assert migration.from_version == "1", "from comes from the old lock"
    assert migration.to_version == "1", "to comes from the new lock"
    (step,) = migration.steps or []
    assert step.title == f"DROP <{SHELF_SLOT}> of <{BOOK}> (deletes data)", "the title"
    assert step.where_pattern == f"?s a <{BOOK}> ; <{SHELF_SLOT}> ?o", "the where pattern"
    assert step.delete_pattern == f"?s <{SHELF_SLOT}> ?o", "the delete pattern"
    assert step.insert_pattern is None, "a drop inserts nothing"
    assert step.unresolved is None, "a drop is resolved"


def test_the_draft_takes_its_versions_from_the_locks(toy_copy: Path, break_toy: Breaker) -> None:
    before, after = locks_after(toy_copy, break_toy, DROP_SHELF)
    newer = after.model_copy(update={"schema_version": "2"})
    migration = draft(before, newer)
    assert migration.from_version == "1", "from is the old lock's version"
    assert migration.to_version == "2", "to is the new lock's version"


# ---- TC-04: unresolved steps -------------------------------------------------------------------


def test_a_needs_a_step_change_drafts_one_unresolved_step_naming_it(
    toy_copy: Path, break_toy: Breaker
) -> None:
    before, after = locks_after(toy_copy, break_toy, ISBN_REQUIRED)
    (step,) = draft(before, after).steps or []
    assert step.unresolved, "an unresolved step says what is missing"
    assert ISBN in step.title, "the title names the slot"
    assert BOOK in step.title, "the title names the class"
    assert step.where_pattern is None, "an unresolved step has no where pattern"
    assert step.delete_pattern is None, "an unresolved step has no delete pattern"
    assert step.insert_pattern is None, "an unresolved step has no insert pattern"


def test_a_safe_change_drafts_no_step(toy_copy: Path, break_toy: Breaker) -> None:
    before, after = locks_after(toy_copy, break_toy, ADD_SUBTITLE)
    assert draft(before, after).steps == [], "a safe change needs no step"


def test_each_change_gets_its_own_step_in_a_stable_order(
    toy_copy: Path, break_toy: Breaker
) -> None:
    before, after = locks_after(toy_copy, break_toy, (*ISBN_REQUIRED, *AUTHORS_SINGLE, *DROP_SHELF))
    steps = draft(before, after).steps or []
    assert len(steps) == 3, [s.title for s in steps]
    assert sum(1 for s in steps if s.unresolved) == 2, "two of the three need the developer"
    assert draft(before, after) == draft(before, after), "the same locks give the same draft"


# ---- TC-05: renames that change nothing stored ---------------------------------------------------

RENAME_SLOT: Edits = (
    ("books.yaml", "slots: [isbn, authors", "slots: [isbn_code, authors"),
    ("books.yaml", "slots:\n  isbn:\n", "slots:\n  isbn_code:\n"),
    ("books.yaml", "unique_key_slots: [isbn]", "unique_key_slots: [isbn_code]"),
)
RENAME_PART: Edits = (
    ("books.yaml", "  Note:\n    title: Note", "  Remark:\n    title: Note"),
    ("books.yaml", "range: Note", "range: Remark"),
)


@pytest.mark.parametrize("edits", [RENAME_SLOT, RENAME_PART], ids=["slot", "non-root-class"])
def test_a_linkml_rename_that_keeps_the_iris_changes_nothing(
    toy_copy: Path, break_toy: Breaker, edits: Edits
) -> None:
    before, after = locks_after(toy_copy, break_toy, edits)
    assert changes(before, after) == [], "a rename that keeps the IRIs stores the same"


# ---- TC-05a: not migratable --------------------------------------------------------------------

RENAME_ROOT: Edits = (
    ("books.yaml", "  Shelf:\n    title: Shelf", "  Rack:\n    title: Shelf"),
    ("books.yaml", "range: Shelf", "range: Rack"),
)
NEW_PATH: Edits = (("books.yaml", "rp_path: books", "rp_path: volumes"),)
NEW_TYPE: Edits = (("books.yaml", "rp_path: books", "rp_path: books\n      rp_iri_type: tome"),)
NOT_OWNED: Edits = (
    (
        "books.yaml",
        "    annotations:\n      owned: true\n",
        "",
    ),
)


@pytest.mark.parametrize(
    ("edits", "mention"),
    [
        pytest.param(RENAME_ROOT, "Shelf", id="renamed-root"),
        pytest.param(NEW_PATH, "books", id="path"),
        pytest.param(NEW_TYPE, "tome", id="iri-type"),
        pytest.param(NOT_OWNED, "chapter", id="inlined"),
    ],
)
def test_a_change_of_stored_iris_or_graphs_is_not_migratable(
    toy_copy: Path, break_toy: Breaker, edits: Edits, mention: str
) -> None:
    before, after = locks_after(toy_copy, break_toy, edits)
    blocked = [c for c in changes(before, after) if c.rule == LockRule.NOT_MIGRATABLE]
    assert blocked, (
        f"expected a not-migratable change in {[described(c) for c in changes(before, after)]}"
    )
    assert any(mention in described(c) for c in blocked), f"{mention!r} not named in {blocked}"


def test_a_change_is_described_by_its_target() -> None:
    slot = LockChange(rule=LockRule.SAFE, what="slot added", class_uri=BOOK, slot_uri=ISBN)
    enum = LockChange(
        rule=LockRule.SAFE, what="enum value added", enum_name="Genre", enum_value="x"
    )
    assert described(slot) == f"slot added: <{ISBN}> of <{BOOK}>", "a slot of its class"
    assert described(enum) == "enum value added: Genre x", "an enum and its value"
