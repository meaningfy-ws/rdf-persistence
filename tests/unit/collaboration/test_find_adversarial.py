"""Adversarial probes of a rule's ``find`` (write-rules-followups PD-3 to PD-6, DEC-1, DEC-3): both readers, the helper, the cache, the bounded message and the conformance kit."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

import pytest
from pydantic import BaseModel, Field

from rdf_persistence import BadQuery, Principal, generated_models
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateReader,
    AggregateValidators,
    _adapter,
    checked_find_values,
    find_items,
    refuse_values_not_of_the_slot,
)
from rdf_persistence.persistence.services.generated.rp_persistence_services import Contains
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import GuardContext, open_session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeAggregateReader, FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from rdf_persistence.testkit.reader_conformance import CASES, Case, Seeded
from tests.fixtures.library.domain.generated.books import (
    Book,
    Chapter,
    Genre,
    LendingItem,
    Magazine,
)
from tests.toy import ADA, MODULES, TENANT, TOY_SCHEMA, book_iri, dune, shelf_iri, toy_mapper

T = TypeVar("T")

# The fixtures of tests/unit/testkit/test_reader_conformance.py, repeated: a test module imports no other.
UNREADABLE = book_iri(2)
MAGAZINE = f"{TENANT}/magazines/{UUID(int=1)}"
PUBLISHED = date(2020, 1, 1)
AUTHORS = ("Herbert", "Asimov")

SEEDED = Seeded(
    root=Book,
    readable=book_iri(1),
    unreadable=UNREADABLE,
    absent=book_iri(9),
    other=Magazine,
    other_iri=MAGAZINE,
    abstract_parent=LendingItem,
    not_root=Chapter,
    not_root_slot="number",
    not_root_wrong_value="x",
    slot="published",
    value=PUBLISHED,
    wrong_value="yesterday",
    text_slot="isbn",
    not_text=5,
    iri_slot="shelf",
    iri_value=shelf_iri(1),
    multi_slot="authors",
    multi_values=AUTHORS,
)


def models() -> list[Book | Magazine]:
    readable = dune(book_iri(1), chapters=0).model_copy(
        update={"published": PUBLISHED, "shelf": shelf_iri(1), "authors": list(AUTHORS)}
    )
    unreadable = dune(UNREADABLE, chapters=0).model_copy(
        update={"published": PUBLISHED, "authors": ["Herbert"]}
    )
    return [readable, unreadable, Magazine(id=MAGAZINE, label="Wired")]


@asynccontextmanager
async def fake_reader() -> AsyncIterator[AggregateReader]:
    yield FakeAggregateReader(models(), roots=[Book, Magazine], unreadable=[UNREADABLE])


@asynccontextmanager
async def real_reader() -> AsyncIterator[AggregateReader]:
    """The real reader over a ``FakeStore`` session with listings, whose ``may_read`` refuses ``unreadable``."""
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    view = load_schema(TOY_SCHEMA)
    async with open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=Principal(id=ADA),
        listings=Listings(view),
        may_read=lambda iri: iri != UNREADABLE,
    ) as session:
        for model in models():
            await session.add_graph(model.id, toy_mapper().to_triples(model))
        loaded = generated_models(*MODULES)
        yield AggregateValidators(view, {}, Path(TOY_SCHEMA).parent).reader(
            session,
            GuardContext(collected={}, rely_on=lambda *_: None, removed=frozenset()),
            lambda name, iri, graph, tracked: toy_mapper().from_graph(
                loaded.named(name), iri, graph, tracked
            ),
        )


READERS: dict[str, Callable[[], AbstractAsyncContextManager[AggregateReader]]] = {
    "fake": fake_reader,
    "real": real_reader,
}


class Tagged(BaseModel):
    """Slots of the shapes ``_item_type`` meets."""

    genres: list[Genre] = []
    maybe_genres: Optional[list[Genre]] = None  # noqa: UP045 - typing.Union is the shape under test
    maybe_count: int | None = None
    numbers: list[int] | None = None
    either: int | str | None = None
    dates: Optional[list[date]] = None  # noqa: UP045
    aliased: str | None = Field(default=None, alias="alias_name")


class Box(BaseModel, Generic[T]):  # noqa: UP046 - the old generic syntax is the shape under test
    item: list[T] = []


class Twin(BaseModel):
    item: list[str] = []


class OtherTwin(BaseModel):
    item: list[int] = []


# --- the order of refusals, both readers -------------------------------------------------------------

ORDER = [
    ("no keyword", Book, {}, ValueError, "needs a slot"),
    ("no keyword, a non-root", Chapter, {}, ValueError, "needs a slot"),
    ("dotted before a None", Book, {"holder.name": "x", "isbn": None}, BadQuery, "slot path"),
    ("a None before dotted", Book, {"isbn": None, "holder.name": "x"}, TypeError, "is None"),
    ("dotted, value None", Book, {"a.b": None}, BadQuery, "slot path"),
    ("mistyped value, non-root", Chapter, {"number": "x"}, BadQuery, "number of Chapter"),
    ("bool for an int slot, non-root", Chapter, {"number": True}, BadQuery, "number of Chapter"),
    ("float for an int slot", Chapter, {"number": 1.0}, BadQuery, "number of Chapter"),
    ("numeric string for an int slot", Chapter, {"number": "5"}, BadQuery, "number of Chapter"),
    (
        "empty list beside an unknown slot",
        Book,
        {"nosuch": 1, "authors": []},
        ValueError,
        "empty list",
    ),
    ("empty tuple", Book, {"authors": ()}, ValueError, "empty list"),
    ("None in a list, unknown slot", Book, {"nosuch": ["a", None]}, TypeError, "nosuch is None"),
    ("None in a tuple", Book, {"authors": ("a", None)}, TypeError, "authors is None"),
    ("unknown slot", Book, {"nosuch": 1}, BadQuery, "not a slot|nosuch"),
    ("empty keyword name", Book, {"": 1}, BadQuery, ""),
    (
        "mistyped value before an unknown slot",
        Book,
        {"published": "yesterday", "nosuch": 1},
        BadQuery,
        "published of Book",
    ),
    (
        "an unknown slot before a mistyped one",
        Book,
        {"nosuch": 1, "published": "yesterday"},
        BadQuery,
        "published of Book",
    ),
    ("a string for an enum slot", Book, {"genre": "fiction"}, BadQuery, "genre of Book"),
    ("a number in a list of strings", Book, {"authors": ["a", 5]}, BadQuery, "authors of Book"),
    ("a tuple inside a list", Book, {"authors": [("a", "b")]}, BadQuery, "authors of Book"),
    ("a set is one item", Book, {"authors": {"a"}}, BadQuery, "authors of Book"),
    ("a generator is one item", Book, {"authors": (a for a in "ab")}, BadQuery, "authors of Book"),
    (
        "a datetime for a date slot",
        Book,
        {"published": datetime(2020, 1, 1, tzinfo=UTC)},
        BadQuery,
        "published of Book",
    ),
    (
        "a mistyped item beside a Contains",
        Book,
        {"authors": [Contains(text="a"), 5]},
        BadQuery,
        "authors of Book",
    ),
    ("a Contains for a date slot is left alone", Book, {"published": date(2020, 1, 1)}, None, ""),
    ("an enum member", Book, {"genre": Genre.FICTION}, None, ""),
    ("a list of enum members", Book, {"genre": [Genre.FICTION]}, None, ""),
    ("an empty string", Book, {"isbn": ""}, None, ""),
    ("a tuple of values", Book, {"authors": ("Herbert", "Asimov")}, None, ""),
    ("a list of values", Book, {"authors": ["Herbert", "Asimov"]}, None, ""),
]


async def outcome(reader: AggregateReader, cls: type[BaseModel], equals: dict[str, Any]) -> object:
    try:
        return await reader.find(cls, **equals)
    except Exception as error:  # noqa: BLE001 - the outcome is what is compared
        return type(error)


@pytest.mark.parametrize("kind", READERS)
@pytest.mark.parametrize(
    ("name", "cls", "equals", "expected", "pattern"), ORDER, ids=[row[0] for row in ORDER]
)
async def test_each_refusal_of_the_order_holds_in_both_readers(
    kind: str,
    name: str,
    cls: type[BaseModel],
    equals: dict[str, Any],
    expected: type[Exception] | None,
    pattern: str,
):
    """probe of PD-3: the order of refusals; a row without an exception is a positive case."""
    async with READERS[kind]() as reader:
        if expected is None:
            found = await reader.find(cls, **equals)
            assert isinstance(found, list), f"{name}: answers a list of ids on {kind}"
            return
        with pytest.raises(expected, match=pattern or None) as caught:
            await reader.find(cls, **equals)
        assert type(caught.value) is expected or isinstance(caught.value, expected), (
            f"{name} on {kind}"
        )


async def test_the_two_readers_agree_on_every_row_of_the_order():
    """probe of PD-3: one order for both readers, positive and negative rows alike."""
    disagreements: list[str] = []
    for name, cls, equals, _, _ in ORDER:
        async with READERS["fake"]() as fake, READERS["real"]() as real:
            seen = (await outcome(fake, cls, equals), await outcome(real, cls, equals))
        if seen[0] != seen[1]:
            disagreements.append(f"{name}: fake {seen[0]!r}, real {seen[1]!r}")
    assert not disagreements, f"the readers disagree: {disagreements}"


async def test_the_fake_does_not_answer_the_unreadable_for_a_found_value():
    """probe of PD-6: the fake and the real reader hold back the same unreadable aggregate."""
    async with READERS["fake"]() as fake, READERS["real"]() as real:
        for reader in (fake, real):
            found = await reader.find(SEEDED.root, **{SEEDED.slot: SEEDED.value})
            assert UNREADABLE not in found, f"{type(reader).__name__} leaks the unreadable"
            assert models()[0].id in found, f"{type(reader).__name__} finds the readable"


async def test_the_fake_refuses_a_contains_with_not_implemented_after_every_other_check():
    """probe of PD-3: a mistyped item and an unknown slot are refused before the fake's one limit."""
    reader = FakeAggregateReader(models(), roots=[SEEDED.root])
    with pytest.raises(NotImplementedError):
        await reader.find(Book, authors=Contains(text="a"))
    with pytest.raises(BadQuery):
        await reader.find(Book, nosuch=Contains(text="a"))  # unknown slot comes before the limit
    with pytest.raises(ValueError, match="empty list"):
        await reader.find(Book, authors=Contains(text="a"), genre=[])


# --- the helper ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "items"),
    [
        ("ab", ["ab"]),
        (["a", "b"], ["a", "b"]),
        (("a", "b"), ["a", "b"]),
        ({"a"}, [{"a"}]),
        (b"ab", [b"ab"]),
        ([["a"]], [["a"]]),
    ],
    ids=["str", "list", "tuple", "set", "bytes", "nested"],
)
def test_find_items_splits_only_a_list_or_a_tuple(value: object, items: list[object]):
    """probe of PD-3: only a list or tuple is split; a str, set or bytes is one item."""
    assert find_items(Book, {"authors": value}) == {"authors": items}, "split rule"


def test_find_items_does_not_consume_a_generator():
    """probe of PD-3: a generator is one item and is not iterated."""
    generator = (a for a in "ab")
    asked = find_items(Book, {"authors": generator})
    assert asked["authors"] == [generator], "one item"
    assert list(generator) == ["a", "b"], "left unconsumed"


def test_find_items_answers_a_copy_of_the_list():
    """probe of PD-3: mutating the answer does not change the caller's list."""
    given = ["a", "b"]
    asked = find_items(Book, {"authors": given})
    asked["authors"].append("c")
    assert given == ["a", "b"], "the caller's list is untouched"


def test_find_items_keeps_the_keyword_order():
    """probe of PD-3: the keyword order is the order of checks and of the answer."""
    assert list(find_items(Book, {"b": 1, "a": 2, "c": 3})) == ["b", "a", "c"], "order kept"


def test_find_items_refuses_none_deep_in_a_list_only_at_the_first_level():
    """probe of PD-3: a None nested in an item list is the value check's, not the helper's."""
    assert find_items(Book, {"authors": [["a", None]]}) == {"authors": [["a", None]]}, (
        "not the helper's"
    )
    with pytest.raises(BadQuery):
        refuse_values_not_of_the_slot(Book, find_items(Book, {"authors": [["a", None]]}))


def test_find_items_refuses_a_dotted_slot_even_with_a_list_value():
    """probe of PD-3: a dotted keyword is refused whatever its value."""
    for value in ([], [None], (), "x"):
        with pytest.raises(BadQuery, match="slot path"):
            find_items(Book, {"a.b": value})


def test_find_items_refuses_none_before_an_empty_list_of_the_same_value_order():
    """probe of PD-3: keyword order decides between a None and an empty list."""
    with pytest.raises(TypeError):
        find_items(Book, {"a": None, "b": []})
    with pytest.raises(ValueError, match="empty list"):
        find_items(Book, {"b": [], "a": None})


# --- the value check and the cache --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slot", "value", "accepted"),
    [
        ("genres", Genre.FICTION, True),
        ("genres", "fiction", False),
        ("maybe_genres", Genre.POETRY, True),
        ("maybe_genres", "poetry", False),
        ("maybe_count", 5, True),
        ("maybe_count", True, False),
        ("maybe_count", "5", False),
        ("maybe_count", 5.0, False),
        ("numbers", 5, True),
        ("numbers", False, False),
        ("dates", date(2020, 1, 1), True),
        ("dates", datetime(2020, 1, 1, tzinfo=UTC), False),
        ("dates", "2020-01-01", False),
        ("either", 5, True),
        ("either", "a", True),
        ("either", 5.5, False),
    ],
)
def test_the_value_check_is_strict_for_every_shape_of_slot(
    slot: str, value: object, accepted: bool
):
    """probe of DEC-1 and PD-4: the item type of each slot shape, strictly."""
    if accepted:
        assert checked_find_values(Tagged, slot, [value]) == [value], f"{slot} takes {value!r}"
    else:
        with pytest.raises(BadQuery, match=f"{slot} of Tagged"):
            checked_find_values(Tagged, slot, [value])


def test_the_slot_of_an_alias_is_checked_by_its_field_name_and_the_alias_is_left_alone():
    """probe of PD-3: ``model_fields`` is keyed by field name, so an alias is an unknown slot."""
    assert checked_find_values(Tagged, "aliased", ["a"]) == ["a"], "the field name is checked"
    with pytest.raises(BadQuery):
        checked_find_values(Tagged, "aliased", [5])
    refuse_values_not_of_the_slot(
        Tagged, {"alias_name": [5]}
    )  # left to the caller: no refusal here


def test_the_cache_answers_the_same_adapter_for_the_same_class_and_slot():
    """probe of PD-4: one adapter per (class, slot)."""
    assert _adapter(Tagged, "genres") is _adapter(Tagged, "genres"), "cached"
    assert _adapter(Tagged, "genres") is not _adapter(Tagged, "numbers"), "per slot"


def test_the_cache_tells_two_classes_with_the_same_slot_apart():
    """probe of PD-4: the key is the class, not its name or its slot."""
    assert checked_find_values(Twin, "item", ["a"]) == ["a"], "str twin"
    assert checked_find_values(OtherTwin, "item", [1]) == [1], "int twin"
    with pytest.raises(BadQuery):
        checked_find_values(OtherTwin, "item", ["a"])
    with pytest.raises(BadQuery):
        checked_find_values(Twin, "item", [1])


def test_the_cache_tells_two_parametrisations_of_a_generic_model_apart():
    """probe of PD-4: ``Box[int]`` and ``Box[str]`` are two classes."""
    assert checked_find_values(Box[int], "item", [1]) == [1], "int box"
    assert checked_find_values(Box[str], "item", ["a"]) == ["a"], "str box"
    with pytest.raises(BadQuery):
        checked_find_values(Box[int], "item", ["a"])
    with pytest.raises(BadQuery):
        checked_find_values(Box[str], "item", [1])


def test_the_cache_tells_two_classes_of_one_name_apart():
    """probe of PD-4: a class rebuilt at run time with the same name is its own key."""
    first = type("Same", (BaseModel,), {"__annotations__": {"v": list[int]}})
    second = type("Same", (BaseModel,), {"__annotations__": {"v": list[str]}})
    assert checked_find_values(first, "v", [1]) == [1], "first takes int"
    assert checked_find_values(second, "v", ["a"]) == ["a"], "second takes str"
    with pytest.raises(BadQuery):
        checked_find_values(second, "v", [1])


def test_an_unknown_slot_is_not_cached_as_an_answer():
    """probe of PD-4: the unknown slot raises every time (the cache stores no failure as a success)."""
    for _ in range(2):
        with pytest.raises(KeyError):
            checked_find_values(Tagged, "nosuch", ["a"])


def test_an_empty_item_list_is_accepted_and_answers_nothing():
    """probe of PD-4: no item, no validation."""
    assert checked_find_values(Tagged, "genres", []) == [], "empty"


# --- the bounded message ------------------------------------------------------------------------------


def recursive() -> list[object]:
    loop: list[object] = []
    loop.append(loop)
    return loop


class Huge:
    def __repr__(self) -> str:
        return "H" * 100_000


@pytest.mark.parametrize(
    ("name", "items"),
    [
        ("a long string", ["x" * 100_000]),
        ("many items", ["x"] * 10_000),
        ("a long list as one item", [["x" * 1000] * 1000]),
        ("a recursive list", [recursive()]),
        ("a deep nest", [[[[[[[[["x" * 5000]]]]]]]]]),
        ("a huge repr", [Huge()]),
        ("a long bytes", [b"x" * 100_000]),
        ("a long dict", [{str(i): "x" * 100 for i in range(10_000)}]),
        ("a set", [set(range(10_000))]),
    ],
)
def test_a_mistyped_value_gives_a_bounded_message_whatever_it_is(name: str, items: list[object]):
    """probe of PD-4: the message never repeats a value in full, and naming it never fails."""
    with pytest.raises(BadQuery) as caught:
        checked_find_values(Chapter, "number", items)
    assert len(str(caught.value)) < 400, f"{name}: bounded"
    assert "number of Chapter" in str(caught.value), f"{name}: names the slot and the class"


def test_a_bad_query_message_names_each_reason_once_for_the_one_failing_item():
    """probe of PD-4: a failing item gives a reason, not the pydantic dump with a URL."""
    with pytest.raises(BadQuery) as caught:
        checked_find_values(Chapter, "number", ["x"])
    assert "pydantic.dev" not in str(caught.value), "no documentation URL"
    assert "validation error" not in str(caught.value), "no pydantic header"


@pytest.mark.parametrize("kind", READERS)
async def test_a_huge_value_is_bounded_in_both_readers_for_a_non_root_too(kind: str):
    """probe of PD-4: the bound holds through ``find`` of both readers."""
    async with READERS[kind]() as reader:
        with pytest.raises(BadQuery) as caught:
            await reader.find(Chapter, number="x" * 100_000)
    assert len(str(caught.value)) < 300, "bounded"


# --- the conformance kit holds a bad reader to account -------------------------------------------------

ROOTS = [SEEDED.root, SEEDED.other]


class Mutant(FakeAggregateReader):
    """A fake with one wrong behaviour; ``wrong`` answers its refusal or ``None`` to defer to the fake."""

    wrong: Callable[[type[BaseModel], dict[str, Any]], BaseException | list[str] | None]

    def __init__(
        self, wrong: Callable[[type[BaseModel], dict[str, Any]], BaseException | list[str] | None]
    ):
        super().__init__(models(), roots=ROOTS, unreadable=[UNREADABLE])
        self.wrong = wrong

    async def find(self, cls: type[BaseModel], **equals: Any) -> list[str]:
        answer = self.wrong(cls, equals)
        if isinstance(answer, BaseException):
            raise answer
        if answer is not None:
            return answer
        return await super().find(cls, **equals)


def root_first(cls: type[BaseModel], equals: dict[str, Any]) -> BaseException | None:
    if cls not in ROOTS and equals:
        return ValueError(f"{cls.__name__} is not an aggregate root with a path")
    return None


def bare_value_error(cls: type[BaseModel], equals: dict[str, Any]) -> BaseException | None:
    if cls not in ROOTS:
        return ValueError(f"find({cls.__name__}) needs a slot to match")
    return None


def dotted_accepted(cls: type[BaseModel], equals: dict[str, Any]) -> list[str] | None:
    return [] if any("." in slot for slot in equals) else None


def no_keyword_accepted(cls: type[BaseModel], equals: dict[str, Any]) -> list[str] | None:
    return [m.id for m in models()] if not equals else None


def leaks_the_other_root(cls: type[BaseModel], equals: dict[str, Any]) -> list[str] | None:
    return [SEEDED.other_iri] if cls is SEEDED.root else None


MUTANTS = [
    ("root before value", root_first, "find_checks_the_value_before_the_root"),
    (
        "a root error that is the wrong message",
        bare_value_error,
        "find_on_a_class_that_is_no_root_is_refused",
    ),
    ("the same, for an abstract parent", bare_value_error, "find_on_an_abstract_parent_is_refused"),
    ("a dotted keyword accepted", dotted_accepted, "find_by_a_dotted_keyword_is_bad_query"),
    ("no keyword accepted", no_keyword_accepted, "find_without_a_slot_is_refused"),
    ("another root leaked", leaks_the_other_root, "find_on_a_root_omits_another_root"),
]


@pytest.mark.parametrize(("name", "wrong", "case_name"), MUTANTS, ids=[m[0] for m in MUTANTS])
async def test_the_kit_catches_a_reader_with_one_wrong_behaviour(
    name: str, wrong: Callable[..., Any], case_name: str
):
    """probe of PD-6: each new case fails on a reader that breaks exactly its rule."""
    case: Case = next(c for c in CASES if c.__name__ == case_name)
    with pytest.raises(
        (Exception, pytest.fail.Exception)
    ):  # any failure of the case, an unexpected error too
        await case(Mutant(wrong), SEEDED)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_kit_passes_a_mutant_that_defers_to_the_fake(case: Case):
    """probe of PD-6: the mutant harness itself is honest (a mutant with no fault passes every case)."""
    await case(Mutant(lambda cls, equals: None), SEEDED)
