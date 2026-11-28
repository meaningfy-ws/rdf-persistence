"""The ``AggregateReader`` conformance suite: one set of cases, run against the fake and the real reader.

Each case takes a reader and a ``Seeded`` describing what both were seeded with. A divergence
between the fake and the real reader is a bug in the fake. The caller seeds each reader the same
way, with ``unreadable`` refused to the writer, then runs every case of ``CASES``.
"""

from collections.abc import Awaitable, Callable

import pytest
from pydantic import BaseModel

from rdf_persistence.collaboration.services.aggregate_validators import AggregateReader
from rdf_persistence.core.domain.exceptions import BadQuery


class Seeded:
    """What the reader under test was seeded with, as the cases read it; read-only after building.

    A plain class, not a dataclass: it holds classes and values, no model, and the model guard
    forbids a hand-written dataclass in the testkit. All arguments are keywords.

    - ``root``: a concrete root class; ``readable`` and ``unreadable`` are two seeded IRIs of it,
      the writer may not read the second; ``absent`` is an IRI seeded nowhere.
    - ``other`` and ``other_iri``: a seeded aggregate of another root class.
    - ``abstract_parent``: an abstract root class with no path, which ``other`` derives from.
    - ``not_root``: a class that is no aggregate root.
    - ``slot`` and ``value``: a single-valued slot of ``root`` that ``readable`` and ``unreadable``
      both hold at ``value``; ``wrong_value`` is not of the slot's type.
    - ``text_slot`` and ``not_text``: a text slot of ``root`` and a value that is not text (a number).
    - ``iri_slot`` and ``iri_value``: an IRI-ranged slot ``readable`` holds.
    - ``multi_slot`` and ``multi_values``: a multivalued slot ``readable`` holds at least two
      values on.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        root: type[BaseModel],
        readable: str,
        unreadable: str,
        absent: str,
        other: type[BaseModel],
        other_iri: str,
        abstract_parent: type[BaseModel],
        not_root: type[BaseModel],
        slot: str,
        value: object,
        wrong_value: object,
        text_slot: str,
        not_text: object,
        iri_slot: str,
        iri_value: str,
        multi_slot: str,
        multi_values: tuple[object, ...],
    ) -> None:
        self.root = root
        self.readable = readable
        self.unreadable = unreadable
        self.absent = absent
        self.other = other
        self.other_iri = other_iri
        self.abstract_parent = abstract_parent
        self.not_root = not_root
        self.slot = slot
        self.value = value
        self.wrong_value = wrong_value
        self.text_slot = text_slot
        self.not_text = not_text
        self.iri_slot = iri_slot
        self.iri_value = iri_value
        self.multi_slot = multi_slot
        self.multi_values = multi_values


Case = Callable[[AggregateReader, Seeded], Awaitable[None]]


async def classes_of_readable_is_its_class(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.classes_of(seeded.readable) == {seeded.root.__name__}


async def classes_of_unreadable_is_empty(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.classes_of(seeded.unreadable) == frozenset()


async def classes_of_absent_is_empty(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.classes_of(seeded.absent) == frozenset()


async def classes_of_another_root_is_its_class(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.classes_of(seeded.other_iri) == {seeded.other.__name__}


async def aggregate_of_readable_is_its_model(reader: AggregateReader, seeded: Seeded) -> None:
    model = await reader.aggregate(seeded.readable)
    assert type(model) is seeded.root, "the model of its class"
    assert getattr(model, "id") == seeded.readable, "the model at the IRI"  # noqa: B009


async def aggregate_of_unreadable_is_none(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.aggregate(seeded.unreadable) is None


async def aggregate_of_absent_is_none(reader: AggregateReader, seeded: Seeded) -> None:
    assert await reader.aggregate(seeded.absent) is None


async def aggregate_of_another_root_is_its_model(reader: AggregateReader, seeded: Seeded) -> None:
    assert type(await reader.aggregate(seeded.other_iri)) is seeded.other


async def find_by_a_slot_returns_only_the_readable(reader: AggregateReader, seeded: Seeded) -> None:
    found = await reader.find(seeded.root, **{seeded.slot: seeded.value})
    assert found == [seeded.readable], "the unreadable holder is left out"


async def find_on_a_root_omits_another_root(reader: AggregateReader, seeded: Seeded) -> None:
    assert seeded.other_iri not in await reader.find(seeded.root), "another class is not found"


async def find_on_an_abstract_parent_is_refused(reader: AggregateReader, seeded: Seeded) -> None:
    with pytest.raises(ValueError):
        await reader.find(seeded.abstract_parent)


async def find_on_a_class_that_is_no_root_is_refused(
    reader: AggregateReader, seeded: Seeded
) -> None:
    with pytest.raises(ValueError):
        await reader.find(seeded.not_root)


async def find_by_a_value_of_the_wrong_type_is_bad_query(
    reader: AggregateReader, seeded: Seeded
) -> None:
    with pytest.raises(BadQuery):
        await reader.find(seeded.root, **{seeded.slot: seeded.wrong_value})


async def find_a_text_slot_by_a_number_is_bad_query(
    reader: AggregateReader, seeded: Seeded
) -> None:
    """Found T2-F1: the real reader answered, where the fake refused (a number is no text)."""
    with pytest.raises(BadQuery):
        await reader.find(seeded.root, **{seeded.text_slot: seeded.not_text})


async def find_by_none_is_refused(reader: AggregateReader, seeded: Seeded) -> None:
    with pytest.raises(TypeError, match=seeded.slot):
        await reader.find(seeded.root, **{seeded.slot: None})


async def find_by_an_iri_slot_compares_the_iri(reader: AggregateReader, seeded: Seeded) -> None:
    found = await reader.find(seeded.root, **{seeded.iri_slot: seeded.iri_value})
    assert found == [seeded.readable]


async def find_by_one_of_many_values_matches(reader: AggregateReader, seeded: Seeded) -> None:
    found = await reader.find(seeded.root, **{seeded.multi_slot: seeded.multi_values[-1]})
    assert found == [seeded.readable]


async def find_by_all_of_many_values_matches(reader: AggregateReader, seeded: Seeded) -> None:
    found = await reader.find(seeded.root, **{seeded.multi_slot: list(seeded.multi_values)})
    assert found == [seeded.readable]


CASES: tuple[Case, ...] = (
    classes_of_readable_is_its_class,
    classes_of_unreadable_is_empty,
    classes_of_absent_is_empty,
    classes_of_another_root_is_its_class,
    aggregate_of_readable_is_its_model,
    aggregate_of_unreadable_is_none,
    aggregate_of_absent_is_none,
    aggregate_of_another_root_is_its_model,
    find_by_a_slot_returns_only_the_readable,
    find_on_a_root_omits_another_root,
    find_on_an_abstract_parent_is_refused,
    find_on_a_class_that_is_no_root_is_refused,
    find_by_a_value_of_the_wrong_type_is_bad_query,
    find_a_text_slot_by_a_number_is_bad_query,
    find_by_none_is_refused,
    find_by_an_iri_slot_compares_the_iri,
    find_by_one_of_many_values_matches,
    find_by_all_of_many_values_matches,
)
