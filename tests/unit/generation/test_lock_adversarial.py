"""Attacks on the lock, its comparison and its draft (PD-3, PD-5, D-3).

Two kinds of test. Schema edits on a copy of the toy library, to see whether a change in what a
schema stores shows in the lock and whether a change that stores nothing new stays out of it. And
locks built by hand, to see every row of the PD-3 table classified and every draft loadable.
"""

import shutil
from pathlib import Path

import pytest
import yaml

from rdf_persistence.domain.exceptions import InvalidMigration, SparqlError
from rdf_persistence.generation.generated.rp_generation import (
    LockChange,
    LockedClass,
    LockedEnum,
    LockedSlot,
    LockRule,
    SchemaLock,
)
from rdf_persistence.generation.lock import changes, described, draft
from rdf_persistence.services.migrations import load_migration

from .conftest import ROOT_SCHEMA, Breaker
from .test_lock import (
    BOOK,
    BOOK_SLOTS,
    ISBN,
    SHELF,
    XSD_STRING,
    Edits,
    lock_of,
    locks_after,
)

SCHEMA = "https://example.org/ns/library"


def rules(found: list[LockChange]) -> list[LockRule]:
    return [c.rule for c in found]


def not_safe(found: list[LockChange]) -> list[LockChange]:
    return [c for c in found if c.rule != LockRule.SAFE]


def seen(found: list[LockChange]) -> str:
    return "; ".join(f"{c.rule}: {described(c)}" for c in found) or "no change"


# -- the lock does not depend on how the schema is written --------------------------------------

BOOK_SLOTS_REVERSED = "slots: [sequel_of, shelf, chapters, genre, published, authors, isbn]"
MOVE_ENUM_VALUE: Edits = (
    (
        "books.yaml",
        "      fiction:\n        title: Fiction\n        description: Invented narrative.\n"
        "        meaning: schema:Fiction\n",
        "",
    ),
    (
        "books.yaml",
        "        meaning: schema:Poetry\n",
        "        meaning: schema:Poetry\n      fiction:\n        title: Fiction\n"
        "        description: Invented narrative.\n        meaning: schema:Fiction\n",
    ),
)
SHELF_BLOCK = (
    "  Shelf:\n    title: Shelf\n    description: A shelf of the library; an aggregate root that books"
    " are placed on, and a collection of the books it names.\n    class_uri: lib:Shelf\n"
    "    mixins: [AggregateRoot, Described, Tracked, ReferenceCollection]\n    annotations:\n"
    "      rp_path: shelves\n      database: tenant\n"
)
SHELF_LAST: Edits = (
    ("books.yaml", SHELF_BLOCK, ""),
    ("books.yaml", "\nslots:\n  isbn:", f"{SHELF_BLOCK}\nslots:\n  isbn:"),
)
IMPORTS_SWAPPED: Edits = (
    ("library.yaml", "  - books\n  - books_activities\n", "  - books_activities\n  - books\n"),
)
VALUE_KEY_RENAMED: Edits = (("books.yaml", "      fiction:\n", "      fictional:\n"),)


@pytest.mark.parametrize(
    "edits",
    [
        (("books.yaml", BOOK_SLOTS, BOOK_SLOTS_REVERSED),),
        MOVE_ENUM_VALUE,
        SHELF_LAST,
        IMPORTS_SWAPPED,
        VALUE_KEY_RENAMED,
    ],
    ids=["slot-order", "enum-value-order", "class-order", "import-order", "enum-value-key"],
)
def test_a_schema_written_in_another_order_or_with_other_names_has_the_same_lock(
    toy_copy: Path, break_toy: Breaker, edits: Edits
) -> None:
    before, after = locks_after(toy_copy, break_toy, edits)
    assert after == before


TWO_SLOTS_ONE_IRI = (
    "slots:\n  isbn_alt:\n    slot_uri: bibo:isbn\n    range: string\n    required: true\n  isbn:"
)
ALT_LAST = BOOK_SLOTS.replace("sequel_of]", "sequel_of, isbn_alt]")
ALT_FIRST = BOOK_SLOTS.replace("[isbn,", "[isbn_alt, isbn,")


def test_two_slots_that_share_an_iri_give_the_same_lock_in_either_order(
    toy_copy: Path, break_toy: Breaker
) -> None:
    """The lock sorts by slot IRI; slots that tie must not keep the order the schema wrote them in."""
    break_toy("books.yaml", "slots:\n  isbn:", TWO_SLOTS_ONE_IRI)
    break_toy("books.yaml", BOOK_SLOTS, ALT_LAST)
    last = lock_of(toy_copy / ROOT_SCHEMA)
    break_toy("books.yaml", ALT_LAST, ALT_FIRST)
    first = lock_of(toy_copy / ROOT_SCHEMA)
    assert first == last
    assert changes(first, last) == [], "and no change shows between the two orders"


def test_the_same_schema_gives_the_same_lock_every_time(toy_copy: Path) -> None:
    runs = [lock_of(toy_copy / ROOT_SCHEMA) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert runs[0].model_dump_json() == runs[2].model_dump_json()


def test_the_lock_of_a_schema_does_not_depend_on_the_folder_it_is_kept_in(
    toy_copy: Path, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere" / "deeper"
    shutil.copytree(toy_copy, elsewhere)
    assert lock_of(elsewhere / ROOT_SCHEMA) == lock_of(toy_copy / ROOT_SCHEMA)


# -- a change in what the schema stores must show in the lock ----------------------------------------

SWAP_CLASS_IRIS: Edits = (
    ("books.yaml", "    class_uri: bibo:Book\n", "    class_uri: lib:Parked\n"),
    ("books.yaml", "    class_uri: lib:Shelf\n", "    class_uri: bibo:Book\n"),
    ("books.yaml", "    class_uri: lib:Parked\n", "    class_uri: lib:Shelf\n"),
)
MOVE_SLOT: Edits = (
    ("books.yaml", BOOK_SLOTS, "slots: [isbn, authors, published, genre, chapters, shelf]"),
    ("books.yaml", "slots: [number, notes]", "slots: [number, notes, sequel_of]"),
)
NARROW_BY_USAGE: Edits = (
    (
        "books.yaml",
        BOOK_SLOTS + "\n",
        BOOK_SLOTS + "\n    slot_usage:\n      authors:\n        required: true\n",
    ),
)
SINGLE_BY_USAGE: Edits = (
    (
        "books.yaml",
        BOOK_SLOTS + "\n",
        BOOK_SLOTS + "\n    slot_usage:\n      authors:\n        multivalued: false\n",
    ),
)
GENRE_TWIN = (
    "enums:\n  Genre2:\n    permissible_values:\n      fiction:\n        meaning: schema:Fiction\n"
    "      nonfiction:\n        meaning: schema:NonFiction\n      poetry:\n"
    "        meaning: schema:Poetry\n  Genre:\n"
)
RANGE_BETWEEN_TWINS: Edits = (
    ("books.yaml", "enums:\n  Genre:\n", GENRE_TWIN),
    (
        "books.yaml",
        BOOK_SLOTS + "\n",
        BOOK_SLOTS + "\n    slot_usage:\n      genre:\n        range: Genre2\n",
    ),
)
REQUIRED_MIXIN_SLOT: Edits = (
    (
        "books.yaml",
        "slots:\n  isbn:",
        "slots:\n  mark:\n    slot_uri: lib:mark\n    range: string\n    required: true\n  isbn:",
    ),
    (
        "books.yaml",
        "\nslots:\n  mark:",
        "  Marked:\n    class_uri: lib:Marked\n    mixin: true\n    slots: [mark]\n\nslots:\n  mark:",
    ),
    (
        "books.yaml",
        "mixins: [AggregateRoot, Described, Tracked, UnderWorkflow]",
        "mixins: [AggregateRoot, Described, Tracked, UnderWorkflow, Marked]",
    ),
)
NOT_A_ROOT: Edits = (
    (
        "books.yaml",
        "mixins: [AggregateRoot, Described, Tracked, ReferenceCollection]",
        "mixins: [Described, Tracked, ReferenceCollection]",
    ),
)
ABSTRACT_ROOT: Edits = (
    ("books.yaml", "    class_uri: lib:Shelf\n", "    class_uri: lib:Shelf\n    abstract: true\n"),
)
PART_BECOMES_ROOT: Edits = (
    (
        "books.yaml",
        "    mixins: [Described]\n    slots: [number, notes]\n    annotations:\n      rp_unlabelled: true\n",
        "    mixins: [AggregateRoot, Described, Tracked]\n    slots: [number, notes]\n"
        "    annotations:\n      rp_unlabelled: true\n      rp_path: chapters\n      database: tenant\n",
    ),
)
PART_TYPE_CHANGED: Edits = (
    (
        "books.yaml",
        "      rp_unlabelled: true\n",
        "      rp_unlabelled: true\n      rp_iri_type: chapter-x\n",
    ),
)
NOTE_TEXT_REQUIRED: Edits = (
    (
        "books.yaml",
        "    slot_uri: schema:text\n    range: string\n",
        "    slot_uri: schema:text\n    range: string\n    required: true\n",
    ),
)
OTHER_DATABASE: Edits = (
    (
        "books.yaml",
        "      rp_path: shelves\n      database: tenant\n",
        "      rp_path: shelves\n      database: application\n",
    ),
)

CHANGES_THAT_MUST_SHOW = [
    pytest.param(SWAP_CLASS_IRIS, {LockRule.NOT_MIGRATABLE}, id="class-iris-swapped"),
    pytest.param(MOVE_SLOT, {LockRule.DESTRUCTIVE}, id="slot-moved-between-classes"),
    pytest.param(NARROW_BY_USAGE, {LockRule.NEEDS_STEP}, id="required-by-slot-usage"),
    pytest.param(SINGLE_BY_USAGE, {LockRule.NEEDS_STEP}, id="single-by-slot-usage"),
    pytest.param(RANGE_BETWEEN_TWINS, {LockRule.NEEDS_STEP}, id="range-to-a-twin-enum"),
    pytest.param(REQUIRED_MIXIN_SLOT, {LockRule.NEEDS_STEP}, id="required-slot-from-a-mixin"),
    pytest.param(NOT_A_ROOT, {LockRule.NEEDS_STEP}, id="root-stops-being-a-root"),
    pytest.param(ABSTRACT_ROOT, {LockRule.NEEDS_STEP}, id="root-becomes-abstract"),
    pytest.param(PART_BECOMES_ROOT, {LockRule.NOT_MIGRATABLE}, id="part-becomes-a-root"),
    pytest.param(NOTE_TEXT_REQUIRED, {LockRule.NEEDS_STEP}, id="slot-of-a-part-required"),
]


@pytest.mark.parametrize(("edits", "expected"), CHANGES_THAT_MUST_SHOW)
def test_a_change_of_what_is_stored_shows_with_a_rule_that_is_not_safe(
    toy_copy: Path, break_toy: Breaker, edits: Edits, expected: set[LockRule]
) -> None:
    before, after = locks_after(toy_copy, break_toy, edits)
    found = changes(before, after)
    assert expected <= set(rules(found)), seen(found)


def test_a_change_of_the_database_of_a_root_is_not_migratable(
    toy_copy: Path, break_toy: Breaker
) -> None:
    """The database says where a root is read from; a step cannot move data between databases."""
    before, after = locks_after(toy_copy, break_toy, OTHER_DATABASE)
    found = changes(before, after)
    assert LockRule.NOT_MIGRATABLE in rules(found), seen(found)


def test_the_database_of_a_subclass_is_the_one_it_inherits(
    toy_copy: Path, break_toy: Breaker
) -> None:
    """Read as the toolkit reads it (``database_of``), so a root without its own annotation is `tenant`."""
    before, after = locks_after(toy_copy, break_toy, OTHER_DATABASE)
    by_uri = {c.class_uri: c.root_database for c in after.locked_classes or []}
    assert by_uri[SHELF] == "application"
    assert {c.class_uri: c.root_database for c in before.locked_classes or []}[SHELF] == "tenant"


def test_a_change_of_the_iri_type_of_a_part_is_not_seen_by_the_lock(
    toy_copy: Path, break_toy: Breaker
) -> None:
    # PD-21 item 5: a part's IRI type matters only under a part template that writes {type}, a runtime setting rp-generate does not know (RISK-8)
    before, after = locks_after(toy_copy, break_toy, PART_TYPE_CHANGED)
    assert before == after


def test_the_slot_a_class_inherits_from_a_mixin_is_named_on_the_class(
    toy_copy: Path, break_toy: Breaker
) -> None:
    before, after = locks_after(toy_copy, break_toy, REQUIRED_MIXIN_SLOT)
    required = [c for c in changes(before, after) if c.rule == LockRule.NEEDS_STEP]
    assert {c.class_uri for c in required} == {BOOK}, seen(required)


def test_a_slot_moved_between_classes_is_destructive_where_it_left(
    toy_copy: Path, break_toy: Breaker
) -> None:
    before, after = locks_after(toy_copy, break_toy, MOVE_SLOT)
    destructive = [c for c in changes(before, after) if c.rule == LockRule.DESTRUCTIVE]
    assert [(c.class_uri, c.slot_uri) for c in destructive] == [
        (BOOK, "https://example.org/ns/library#sequelOf")
    ]


# -- every row of the PD-3 table, from locks built by hand ---------------------------------------


def slot(
    uri: str = ISBN,
    range_: str = XSD_STRING,
    *,
    required: bool = False,
    multivalued: bool = False,
    inlined: bool = False,
) -> LockedSlot:
    return LockedSlot(
        slot_uri=uri, range=range_, required=required, multivalued=multivalued, inlined=inlined
    )


def klass(
    uri: str = BOOK, *slots: LockedSlot, iri_type: str | None = None, path: str | None = None
) -> LockedClass:
    return LockedClass(class_uri=uri, iri_type=iri_type, root_path=path, locked_slots=list(slots))


def lock(
    *classes: LockedClass, enums: list[LockedEnum] | None = None, version: str = "1"
) -> SchemaLock:
    return SchemaLock(
        schema_id=SCHEMA, schema_version=version, locked_classes=list(classes), locked_enums=enums
    )


def enum(name: str = "Genre", *values: str) -> LockedEnum:
    return LockedEnum(name=name, enum_values=list(values))


ROOT = {"iri_type": "book", "path": "books"}
TABLE_ROWS = {
    "class-removed": (lock(klass(BOOK), klass(SHELF)), lock(klass(BOOK)), LockRule.NEEDS_STEP),
    "class-added": (lock(klass(BOOK)), lock(klass(BOOK), klass(SHELF)), LockRule.SAFE),
    "slot-removed": (lock(klass(BOOK, slot())), lock(klass(BOOK)), LockRule.DESTRUCTIVE),
    "slot-added": (lock(klass(BOOK)), lock(klass(BOOK, slot())), LockRule.SAFE),
    "slot-added-required": (
        lock(klass(BOOK)),
        lock(klass(BOOK, slot(required=True))),
        LockRule.NEEDS_STEP,
    ),
    "required-set": (
        lock(klass(BOOK, slot())),
        lock(klass(BOOK, slot(required=True))),
        LockRule.NEEDS_STEP,
    ),
    "required-dropped": (
        lock(klass(BOOK, slot(required=True))),
        lock(klass(BOOK, slot())),
        LockRule.SAFE,
    ),
    "single-to-multi": (
        lock(klass(BOOK, slot())),
        lock(klass(BOOK, slot(multivalued=True))),
        LockRule.SAFE,
    ),
    "multi-to-single": (
        lock(klass(BOOK, slot(multivalued=True))),
        lock(klass(BOOK, slot())),
        LockRule.NEEDS_STEP,
    ),
    "range-changed": (
        lock(klass(BOOK, slot())),
        lock(klass(BOOK, slot(range_="http://www.w3.org/2001/XMLSchema#integer"))),
        LockRule.NEEDS_STEP,
    ),
    "range-to-an-enum": (
        lock(klass(BOOK, slot())),
        lock(klass(BOOK, slot(range_="Genre")), enums=[enum("Genre", "a")]),
        LockRule.NEEDS_STEP,
    ),
    "inlined-set": (
        lock(klass(BOOK, slot())),
        lock(klass(BOOK, slot(inlined=True))),
        LockRule.NOT_MIGRATABLE,
    ),
    "inlined-dropped": (
        lock(klass(BOOK, slot(inlined=True))),
        lock(klass(BOOK, slot())),
        LockRule.NOT_MIGRATABLE,
    ),
    "type-changed": (
        lock(klass(BOOK, **ROOT)),
        lock(klass(BOOK, iri_type="tome", path="books")),
        LockRule.NOT_MIGRATABLE,
    ),
    "path-changed": (
        lock(klass(BOOK, **ROOT)),
        lock(klass(BOOK, iri_type="book", path="volumes")),
        LockRule.NOT_MIGRATABLE,
    ),
    "root-to-part": (lock(klass(BOOK, **ROOT)), lock(klass(BOOK)), LockRule.NOT_MIGRATABLE),
    "part-to-root": (lock(klass(BOOK)), lock(klass(BOOK, **ROOT)), LockRule.NOT_MIGRATABLE),
    "path-set-from-nothing": (
        lock(klass(BOOK, iri_type="book")),
        lock(klass(BOOK, iri_type="book", path="books")),
        LockRule.NOT_MIGRATABLE,
    ),
    "enum-value-gone": (
        lock(enums=[enum("Genre", "a", "b")]),
        lock(enums=[enum("Genre", "a")]),
        LockRule.NEEDS_STEP,
    ),
    "enum-value-added": (
        lock(enums=[enum("Genre", "a")]),
        lock(enums=[enum("Genre", "a", "b")]),
        LockRule.SAFE,
    ),
    "enum-gone": (lock(enums=[enum("Genre", "a")]), lock(), LockRule.NEEDS_STEP),
    "enum-added": (lock(), lock(enums=[enum("Genre", "a")]), LockRule.SAFE),
}


@pytest.mark.parametrize(("old", "new", "rule"), TABLE_ROWS.values(), ids=TABLE_ROWS)
def test_each_row_of_the_table_has_its_classification(
    old: SchemaLock, new: SchemaLock, rule: LockRule
) -> None:
    found = changes(old, new)
    assert rule in rules(found), seen(found)
    worst = {LockRule.NOT_MIGRATABLE, LockRule.DESTRUCTIVE, LockRule.NEEDS_STEP}
    if rule in worst:
        assert not_safe(found), "a row that is not safe must show as not safe"
    else:
        assert not not_safe(found), seen(found)


def test_a_change_made_of_several_rows_reports_each_of_them() -> None:
    old = lock(klass(BOOK, slot(), **ROOT))
    new = lock(
        klass(
            BOOK,
            slot(range_="http://www.w3.org/2001/XMLSchema#integer", required=True, inlined=True),
            iri_type="tome",
            path="volumes",
        )
    )
    found = changes(old, new)
    assert set(rules(found)) == {LockRule.NOT_MIGRATABLE, LockRule.NEEDS_STEP}
    assert len(found) == 4, seen(found)


def test_an_absent_value_and_a_false_one_are_the_same_lock() -> None:
    bare = LockedSlot(slot_uri=ISBN, range=XSD_STRING)
    explicit = slot()
    assert changes(lock(klass(BOOK, bare)), lock(klass(BOOK, explicit))) == []
    no_slots = SchemaLock(
        schema_id=SCHEMA, schema_version="1", locked_classes=[LockedClass(class_uri=BOOK)]
    )
    assert changes(no_slots, lock(klass(BOOK))) == []


def test_the_order_of_the_lists_in_a_lock_does_not_change_what_is_found() -> None:
    a, b = klass(BOOK, slot(ISBN), slot("urn:b", required=True)), klass(SHELF, slot("urn:c"))
    old = lock(a, b, enums=[enum("A", "x", "y"), enum("B", "z")])
    flipped = lock(
        klass(SHELF, slot("urn:c")),
        klass(BOOK, slot("urn:b", required=True), slot(ISBN)),
        enums=[enum("B", "z"), enum("A", "y", "x")],
    )
    assert changes(old, flipped) == []
    assert changes(flipped, old) == []


def test_two_classes_with_one_iri_are_not_lost_by_the_comparison() -> None:
    """LinkML lets a subclass keep its parent's ``class_uri``; a change to either must show."""
    old = lock(klass(BOOK, slot(ISBN)), klass(BOOK, slot("urn:b")))
    new = lock(klass(BOOK, slot(ISBN, required=True)), klass(BOOK, slot("urn:b")))
    assert not_safe(changes(old, new)), "the change to the first class is hidden by the second"


def test_two_classes_with_one_iri_give_no_change_when_only_their_order_differs() -> None:
    one, two = klass(BOOK, slot(ISBN)), klass(BOOK, slot("urn:b"))
    assert changes(lock(one, two), lock(two, one)) == []


def test_changes_are_sorted_so_the_draft_is_stable() -> None:
    old = lock(klass("urn:z", slot("urn:s1")), klass("urn:a", slot("urn:s2")), klass("urn:m"))
    new = lock(klass("urn:m"))
    found = changes(old, new)
    assert [c.class_uri for c in found] == sorted(c.class_uri for c in found)


# -- the draft loads once its unresolved steps are gone ----------------------------------------------

LEGAL_IRIS = {
    "plain": ("https://example.org/ns/Book", "https://example.org/ns/title"),
    "colons": ("urn:example:book:1", "urn:example:slot:a:b"),
    "parentheses": ("https://example.org/ns/Book(1)", "https://example.org/ns/title(x)"),
    "brackets": ("https://example.org/ns/Book[1]", "https://example.org/ns/title[x]"),
    "hash and query": ("https://example.org/ns#Book", "https://example.org/ns?x=1#title"),
    "percent": ("https://example.org/ns/B%20k", "https://example.org/ns/t%C3%A9"),
    "unicode": ("https://example.org/ns/B" + chr(0xE9), "https://example.org/ns/" + chr(0x4E2D)),
    "keywords inside": ("https://example.org/GRAPH/SERVICE", "https://example.org/rp_graph/_:b"),
    "a prefix lookalike": ("https://example.org/a:b", "https://example.org/rdf:type"),
    "an apostrophe": ("https://example.org/it's", "https://example.org/say'hi"),
    "an ampersand and equals": ("https://example.org/a&b=c", "https://example.org/x;y,z"),
    "a tilde and an at sign": ("https://example.org/~u@host", "https://example.org/!$*+"),
}


def dropped(class_uri: str, slot_uri: str) -> tuple[SchemaLock, SchemaLock]:
    return lock(klass(class_uri, slot(slot_uri))), lock(klass(class_uri), version="2")


def written(tmp_path: Path, old: SchemaLock, new: SchemaLock) -> Path:
    drafted = draft(old, new)
    path = tmp_path / f"{old.schema_version}__{new.schema_version}.yaml"
    path.write_text(yaml.safe_dump(drafted.model_dump(exclude_none=True)), encoding="utf-8")
    return path


@pytest.mark.parametrize(("class_uri", "slot_uri"), LEGAL_IRIS.values(), ids=LEGAL_IRIS)
def test_a_drop_draft_loads_whatever_legal_characters_the_iris_hold(
    tmp_path: Path, class_uri: str, slot_uri: str
) -> None:
    old, new = dropped(class_uri, slot_uri)
    loaded = load_migration(written(tmp_path, old, new))
    (step,) = loaded.steps or []
    assert f"<{slot_uri}>" in (step.delete_pattern or "")
    assert f"<{class_uri}>" in (step.where_pattern or "")


@pytest.mark.parametrize(
    "character",
    [" ", ">", '"', "{", "}", "|", "^", "`", chr(92), chr(10), chr(0)],
    ids=[
        "space",
        "gt",
        "quote",
        "open",
        "close",
        "bar",
        "caret",
        "tick",
        "backslash",
        "newline",
        "nul",
    ],
)
def test_a_drop_draft_for_an_iri_that_cannot_be_written_in_angle_brackets_is_refused(
    character: str,
) -> None:
    """An IRI with such a character is no IRI; a draft that held it would run a different step than
    the one meant, so ``term`` refuses it while drafting (PD-22.6)."""
    old, new = dropped(BOOK, f"urn:a{character}b ?p ?o . ?s <urn:c")
    with pytest.raises(SparqlError, match="not a valid IRI"):
        draft(old, new)


def test_a_draft_with_unresolved_steps_is_refused_and_loads_once_they_are_removed(
    tmp_path: Path,
) -> None:
    old = lock(klass(BOOK, slot(ISBN), slot("urn:gone")))
    new = lock(klass(BOOK, slot(ISBN, required=True), slot("urn:new", required=True)), version="2")
    drafted = draft(old, new)
    assert any(s.unresolved for s in drafted.steps or [])
    path = written(tmp_path, old, new)
    with pytest.raises(InvalidMigration, match="unresolved"):
        load_migration(path)
    kept = drafted.model_copy(
        update={"steps": [s for s in drafted.steps or [] if not s.unresolved]}
    )
    path.write_text(yaml.safe_dump(kept.model_dump(exclude_none=True)), encoding="utf-8")
    loaded = load_migration(path)
    assert [s.title for s in loaded.steps or []] == [
        "DROP <urn:gone> of <" + BOOK + "> (deletes data)"
    ]


def test_a_draft_with_nothing_to_write_loads_as_a_migration_without_steps(tmp_path: Path) -> None:
    old = lock(klass(BOOK, slot()))
    new = lock(klass(BOOK, slot(), slot("urn:opt")), klass(SHELF), version="2")
    assert changes(old, new) and not not_safe(changes(old, new))
    loaded = load_migration(written(tmp_path, old, new))
    assert not loaded.steps
    assert (loaded.from_version, loaded.to_version) == ("1", "2")


@pytest.mark.parametrize(
    "version",
    [
        "1.0-rc.1",
        "2024/11",
        "v 3",
        "1\n",
        chr(0xE9),
        "1: 2",
        "#1",
        "'1'",
        '"1"',
        "- 1",
        "1.10",
        "0x1F",
    ],
)
def test_a_draft_keeps_odd_versions_exactly_through_the_file(tmp_path: Path, version: str) -> None:
    old = lock(klass(BOOK, slot()), version=version)
    new = lock(klass(BOOK), version=version + "x")
    path = tmp_path / "any.yaml"
    path.write_text(yaml.safe_dump(draft(old, new).model_dump(exclude_none=True)), encoding="utf-8")
    loaded = load_migration(path)
    assert (loaded.from_version, loaded.to_version) == (version, version + "x")


def test_a_draft_names_the_schema_of_the_new_lock_and_nothing_of_the_old() -> None:
    old = lock(klass(BOOK, slot()))
    new = SchemaLock(
        schema_id="https://example.org/ns/renamed",
        schema_version="2",
        locked_classes=[klass(BOOK)],
    )
    assert draft(old, new).schema_id == "https://example.org/ns/renamed"


def test_every_destructive_or_needs_a_step_change_gets_a_step_and_a_safe_one_gets_none() -> None:
    for name, (old, new, rule) in TABLE_ROWS.items():
        steps = draft(old, new).steps or []
        wanted = sum(
            1 for c in changes(old, new) if c.rule in (LockRule.DESTRUCTIVE, LockRule.NEEDS_STEP)
        )
        assert len(steps) == wanted, f"{name}: {rule}, {len(steps)} steps for {wanted} changes"
        if rule == LockRule.SAFE:
            assert steps == [], name
