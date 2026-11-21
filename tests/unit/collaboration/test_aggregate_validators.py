"""Aggregate validators: registration, selection and running (aggregate-validators PD-1, PD-2, PD-3, PD-7, T-1 to T-5)."""

import functools
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError

from rdf_persistence import DatabaseGone, InvalidBody, Principal, StoreUnavailable
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateReader,
    AggregateValidator,
    AggregateValidators,
    run_aggregate_validators,
)
from rdf_persistence.schema.services.schema import load_schema
from tests.toy import ADA, TENANT, TOY_SCHEMA, shelf, shelf_iri

FOLDER = TOY_SCHEMA.parent
TOY_NS = "https://example.org/ns/library#"
SHAPES_NS = "https://example.org/ns/shapes#"
SHELF = TOY_NS + "Shelf"
LIBRARY = str(load_schema(TOY_SCHEMA).get_uri("Library", expand=True))
WHO = Principal(id=ADA)

# The toy library has no abstract parent of a root, no root derived from a root and no second root on
# another line, so these shapes live in a schema of their own (no change to the toy schema).
SHAPES = """
id: https://example.org/ns/shapes
name: shapes
prefixes:
  ex: https://example.org/ns/shapes#
default_prefix: ex
classes:
  AggregateRoot:
    mixin: true
  Item:
    abstract: true
  Shelf:
    is_a: Item
    mixins: [AggregateRoot]
  SpecialShelf:
    is_a: Shelf
  Book:
    is_a: Item
    mixins: [AggregateRoot]
"""


@pytest.fixture
def shapes(tmp_path: Path) -> tuple[SchemaView, Path]:
    (tmp_path / "shapes.yaml").write_text(SHAPES)
    return SchemaView(str(tmp_path / "shapes.yaml")), tmp_path


def toy(mapping: dict[str, Sequence[AggregateValidator]]) -> AggregateValidators:
    return AggregateValidators(load_schema(TOY_SCHEMA), mapping, FOLDER)


def accepts(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    return None


@pytest.mark.parametrize(
    ("key", "reason"),
    [
        ("Nope", "not a class"),
        ("Described", "a mixin"),
        ("TenantAccess", "a toolkit class"),
        ("Chapter", "no root derives from it"),
    ],
)  # T-1
def test_a_key_that_is_not_an_application_root_is_refused_with_its_reason(key: str, reason: str):
    with pytest.raises(ValueError, match=f"{key}.*{reason}"):
        toy({key: [accepts]})


def test_a_non_callable_rule_is_a_type_error_naming_its_key():
    with pytest.raises(TypeError, match="Shelf"):
        toy({"Shelf": ["not callable"]})  # type: ignore[list-item]


def test_the_tenant_root_and_a_root_are_accepted_keys():  # T-2
    validators = toy({"Shelf": [accepts], "Library": [accepts]})
    assert validators.select(shelf_iri(1), [SHELF]) is not None, "Shelf selects its rule"
    assert validators.select(TENANT, [LIBRARY]) is not None, "the tenant root selects its rule"


def test_an_abstract_parent_of_a_root_is_an_accepted_key(shapes: tuple[SchemaView, Path]):  # T-2
    view, folder = shapes
    validators = AggregateValidators(view, {"Item": [accepts]}, folder)
    selected = validators.select("urn:s", [SHAPES_NS + "Shelf"])
    assert selected is not None, "a Shelf is an Item, so the rule of Item applies"
    assert selected[0] == "Shelf", "the model class is the root's own"


def test_an_empty_mapping_selects_nothing():
    assert toy({}).select(shelf_iri(1), [SHELF]) is None, "no rules, no selection"


def test_a_class_with_no_rule_selects_nothing():
    assert toy({"Library": [accepts]}).select(shelf_iri(1), [SHELF]) is None


def test_a_type_that_is_not_a_root_selects_nothing():
    assert toy({"Shelf": [accepts]}).select(shelf_iri(1), [TOY_NS + "Chapter"]) is None


# Selection and running (PD-3, PD-7: T-3, T-4, T-5)


def named(label: str, calls: list[str]) -> AggregateValidator:
    def rule(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        calls.append(label)

    return rule


class NoReader:
    async def classes_of(self, iri: str) -> frozenset[str]:
        return frozenset()


READER: AggregateReader = NoReader()


def refuses_with_invalid_body(old: Any, new: Any, who: Any, reader: Any) -> None:
    raise InvalidBody("refused")


async def refuses_async(old: Any, new: Any, who: Any, reader: Any) -> None:
    raise InvalidBody("refused late")


def refuses_with_validation_error(old: Any, new: Any, who: Any, reader: Any) -> None:
    class Strict(BaseModel):
        count: int

    Strict(count="not a number")  # type: ignore[arg-type]


def has_a_bug(old: Any, new: Any, who: Any, reader: Any) -> None:
    raise KeyError("missing")


def returns_a_value(old: Any, new: Any, who: Any, reader: Any) -> Any:
    return True


async def returns_a_value_async(old: Any, new: Any, who: Any, reader: Any) -> Any:
    return 1


async def raises_after_an_await(old: Any, new: Any, who: Any, reader: Any) -> None:
    await reader.classes_of("urn:x")
    raise ValueError("late bug")


def _partial_rule(extra: str, old: Any, new: Any, who: Any, reader: Any) -> None:
    raise KeyError(extra)


def _selected_rules(validators: AggregateValidators, types: list[str]):
    selected = validators.select("urn:s", types)
    assert selected is not None, "a rule applies"
    return selected[1]


async def test_rules_run_from_the_most_general_key_to_the_class_in_list_order(
    shapes: tuple[SchemaView, Path],
):  # T-3
    view, folder = shapes
    calls: list[str] = []
    validators = AggregateValidators(
        view,
        {
            "Shelf": [named("shelf-1", calls), named("shelf-2", calls)],
            "Item": [named("item", calls)],
        },
        folder,
    )
    rules = _selected_rules(validators, [SHAPES_NS + "Shelf"])
    await run_aggregate_validators(rules, None, shelf("urn:s"), WHO, READER)
    assert calls == ["item", "shelf-1", "shelf-2"], "parent first, then the class, each in order"


async def test_the_first_refusal_stops_the_rest(shapes: tuple[SchemaView, Path]):  # T-3
    view, folder = shapes
    calls: list[str] = []
    validators = AggregateValidators(
        view, {"Item": [refuses_with_invalid_body], "Shelf": [named("shelf", calls)]}, folder
    )
    rules = _selected_rules(validators, [SHAPES_NS + "Shelf"])
    with pytest.raises(InvalidBody):
        await run_aggregate_validators(rules, None, shelf("urn:s"), WHO, READER)
    assert calls == [], "the rule after the refusal never ran"


@pytest.mark.parametrize(
    ("rule", "raised", "message"),
    [
        (refuses_with_invalid_body, InvalidBody, "refused"),
        (refuses_async, InvalidBody, "refused late"),
        (refuses_with_validation_error, ValidationError, "count"),
        (has_a_bug, RuntimeError, "has_a_bug.*KeyError.*missing"),
        (functools.partial(_partial_rule, "x"), RuntimeError, "partial"),
        (returns_a_value, TypeError, "True"),
        (returns_a_value_async, TypeError, "1"),
        (raises_after_an_await, RuntimeError, "raises_after_an_await.*ValueError.*late bug"),
    ],
    ids=lambda case: getattr(case, "__name__", None) if callable(case) else None,
)
async def test_a_rule_is_run_as_the_contract_says(
    rule: AggregateValidator, raised: type[Exception], message: str
):  # T-4
    with pytest.raises(raised, match=message):
        await run_aggregate_validators([rule], None, shelf(shelf_iri(1)), WHO, READER)


async def test_a_rule_that_is_a_bug_is_chained_to_its_error():  # T-4
    with pytest.raises(RuntimeError) as caught:
        await run_aggregate_validators([has_a_bug], None, shelf(shelf_iri(1)), WHO, READER)
    assert isinstance(caught.value.__cause__, KeyError), "the original error is the cause"


@pytest.mark.parametrize("error", [StoreUnavailable("down"), DatabaseGone("gone")])
async def test_a_store_error_from_the_reader_passes_unwrapped(error: Exception):  # T-4
    async def reads(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        raise error

    with pytest.raises(type(error)):
        await run_aggregate_validators([reads], None, shelf(shelf_iri(1)), WHO, READER)


async def test_rules_see_copies_and_what_they_do_to_them_is_never_kept():  # T-4
    seen: dict[str, Any] = {}

    def vandal(old: Any, new: Any, who: Any, reader: Any) -> None:
        new.label = "changed"
        seen["old"] = old

    mine = shelf(shelf_iri(1))
    await run_aggregate_validators([vandal], None, mine, WHO, READER)
    assert mine.label == "Shelf", "the caller's model is untouched"
    assert seen["old"] is None, "old is None on a create"


def test_a_root_typed_with_a_class_and_its_subclass_takes_the_rules_of_the_subclass(
    shapes: tuple[SchemaView, Path],
):  # T-5
    view, folder = shapes
    calls: list[str] = []
    validators = AggregateValidators(
        view, {"Shelf": [named("shelf", calls)], "SpecialShelf": [named("special", calls)]}, folder
    )
    for types in (["Shelf", "SpecialShelf"], ["SpecialShelf", "Shelf"]):
        selected = validators.select("urn:s", [SHAPES_NS + t for t in types])
        assert selected is not None
        class_name, rules = selected
        assert class_name == "SpecialShelf", "the most specific type is the model class"
        assert len(rules) == 2, "its ancestors' rules and its own"


def test_a_root_typed_on_two_lines_is_refused_naming_both_types(
    shapes: tuple[SchemaView, Path],
):  # T-5
    view, folder = shapes
    validators = AggregateValidators(view, {"Shelf": [accepts]}, folder)
    with pytest.raises(InvalidBody, match=r"urn:s.*two lines.*Book.*Shelf"):
        validators.select("urn:s", [SHAPES_NS + "Shelf", SHAPES_NS + "Book"])


def test_a_root_typed_on_two_lines_with_no_rule_on_either_is_not_refused(
    shapes: tuple[SchemaView, Path],
):  # T-5
    view, folder = shapes
    validators = AggregateValidators(view, {}, folder)
    assert validators.select("urn:s", [SHAPES_NS + "Shelf", SHAPES_NS + "Book"]) is None
