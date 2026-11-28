"""The fake aggregate reader: what a rule sees, what it records and what it refuses (consumer-write-rules PD-13, TC-12)."""

from typing import Any

import pytest
from pydantic import BaseModel

from rdf_persistence import BadQuery, Contains, InvalidBody
from rdf_persistence.testkit import FakeAggregateReader
from tests.fixtures.library.domain.generated.books import Book, Chapter
from tests.toy import book_iri, dune

ISBN = "978-0"


def two_books(**kwargs: Any) -> FakeAggregateReader:
    """Two books holding the same isbn; the second is unreadable."""
    seeded = [dune(book_iri(1), chapters=0, isbn=ISBN), dune(book_iri(2), chapters=0, isbn=ISBN)]
    return FakeAggregateReader(seeded, roots=[Book], unreadable=[book_iri(2)], **kwargs)


async def no_held_isbn(old: Any, new: Any, who: Any, reader: Any) -> None:
    """A rule as a consumer writes it: refuse a key another aggregate holds."""
    holders = [iri for iri in await reader.find(Book, isbn=new.isbn) if iri != new.id]
    if holders:
        raise InvalidBody(f"isbn {new.isbn} is held by {holders[0]}")


async def test_a_rule_over_a_fake_with_two_books_one_unreadable_sees_one():  # TC-12
    reader = two_books()
    with pytest.raises(InvalidBody, match=book_iri(1)):
        await no_held_isbn(None, dune(book_iri(3), isbn=ISBN), None, reader)
    assert await reader.find(Book, isbn=ISBN) == [book_iri(1)], "the unreadable book is not found"
    assert await reader.classes_of(book_iri(2)) == frozenset(), "nor its classes"
    assert await reader.aggregate(book_iri(2)) is None, "nor itself"


async def test_calls_lists_the_calls_in_order_refused_ones_included():  # TC-12
    reader = two_books()
    await reader.classes_of(book_iri(1))
    await reader.aggregate(book_iri(1))
    await reader.find(Book, isbn=ISBN)
    with pytest.raises(TypeError):
        await reader.find(Book, isbn=None)
    assert reader.calls == [
        ("classes_of", (book_iri(1),), {}),
        ("aggregate", (book_iri(1),), {}),
        ("find", (Book,), {"isbn": ISBN}),
        ("find", (Book,), {"isbn": None}),
    ]


async def test_the_aggregate_is_a_copy_the_rule_may_change():
    reader = two_books()
    first = await reader.aggregate(book_iri(1))
    assert isinstance(first, Book)
    first.label = "changed"
    second = await reader.aggregate(book_iri(1))
    assert isinstance(second, Book), "still a book"
    assert second.label == "Dune", "the seeded model is untouched"


async def test_classes_of_a_readable_aggregate_is_its_own_class():
    assert await two_books().classes_of(book_iri(1)) == frozenset({"Book"})


@pytest.mark.parametrize(
    ("case", "cls", "equals", "error", "match"),
    [
        (
            "a class that is not among the roots",
            Chapter,
            {"number": 1},
            ValueError,
            "not an aggregate root",
        ),
        ("no keyword", Book, {}, ValueError, "needs a slot"),
        ("a None value", Book, {"isbn": None}, TypeError, "isbn"),
        ("a name that is no field", Book, {"nope": "x"}, BadQuery, "nope"),
        ("a value of the wrong type", Book, {"published": "yesterday"}, BadQuery, "published"),
        ("a Contains", Book, {"label": Contains(text="dun")}, NotImplementedError, "label"),
        ("a dotted keyword", Book, {"written_by.label": "x"}, BadQuery, "written_by.label"),
        ("an empty list", Book, {"authors": []}, ValueError, "empty list"),
    ],
)
async def test_find_refuses(
    case: str,
    cls: type[BaseModel],
    equals: dict[str, object],
    error: type[Exception],
    match: str,
):
    with pytest.raises(error, match=match):
        await two_books().find(cls, **equals)


async def test_the_limit_of_the_fake_is_named_in_the_refusal():
    with pytest.raises(NotImplementedError, match="label"):
        await two_books().find(Book, label=Contains(text="x"))


@pytest.mark.parametrize(
    ("authors", "equals", "found"),
    [
        (["Herbert", "Asimov"], {"authors": "Asimov"}, True),
        (["Herbert", "Asimov"], {"authors": ["Asimov", "Herbert"]}, True),
        (["Herbert"], {"authors": ["Asimov", "Herbert"]}, False),
        (["Herbert"], {"authors": "Asimov"}, False),
    ],
)
async def test_a_value_on_a_multivalued_slot_is_one_of_them_and_a_list_is_all_of_them(
    authors: list[str], equals: dict[str, object], found: bool
):
    book = dune(book_iri(1), chapters=0).model_copy(update={"authors": authors})
    reader = FakeAggregateReader([book], roots=[Book])
    assert (await reader.find(Book, **equals) == [book_iri(1)]) is found, str(equals)
