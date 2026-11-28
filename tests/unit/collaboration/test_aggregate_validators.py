"""Aggregate validators: registration, selection and running (aggregate-validators PD-1, PD-2, PD-3, PD-7, T-1 to T-5)."""

import functools
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError
from rdflib import RDF, URIRef

from rdf_persistence import (
    AccessRules,
    Conflict,
    DatabaseGone,
    InvalidBody,
    KeyConflict,
    Principal,
    RuleRefusal,
    StoreUnavailable,
    generated_models,
    load_role_definitions,
)
from rdf_persistence.collaboration.services import write_guards
from rdf_persistence.collaboration.services.aggregate_validators import (
    AggregateReader,
    AggregateValidator,
    AggregateValidators,
    run_aggregate_validators,
)
from rdf_persistence.collaboration.services.workflows import Workflows, load_workflow, state_iri
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.session import GuardContext, Session, open_session
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import aggregate_keys
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books import Book
from tests.toy import (
    ADA,
    MODULES,
    REVIEW_WORKFLOW,
    ROLES,
    TENANT,
    TOY_SCHEMA,
    author_iri,
    book_iri,
    dune,
    shelf,
    shelf_iri,
    toy_mapper,
)
from tests.unit.collaboration.collaboration_data import save

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

    async def aggregate(self, iri: str) -> BaseModel | None:
        return None

    async def find(self, cls: type[BaseModel], **equals: object) -> list[str]:
        return []


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


def refuses_with_a_problem(old: Any, new: Any, who: Any, reader: Any) -> None:
    raise RuleRefusal(Marker("held"))


class Marker:
    def __init__(self, detail: str) -> None:
        self.detail = detail


@pytest.mark.parametrize(
    ("rule", "raised"),
    [(refuses_with_a_problem, RuleRefusal), (has_a_bug, RuntimeError)],
    ids=lambda case: getattr(case, "__name__", None) if callable(case) else None,
)
async def test_a_rule_refusal_passes_as_it_is_and_any_other_error_is_wrapped(
    rule: AggregateValidator, raised: type[Exception]
):  # PD-5
    with pytest.raises(raised) as caught:
        await run_aggregate_validators([rule], None, shelf(shelf_iri(1)), WHO, READER)
    assert type(caught.value) is raised, "RuleRefusal is not wrapped in RuntimeError"


async def test_a_rule_refusal_carries_its_problem_and_its_detail_as_text():  # PD-5
    marker = Marker("isbn x is held")
    assert RuleRefusal(marker).problem is marker, "the problem is kept"
    assert str(RuleRefusal(marker)) == "isbn x is held", "the text is the problem's detail"


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


def test_the_model_class_is_the_most_specific_root_type_whatever_the_rules(
    shapes: tuple[SchemaView, Path],
):  # PD-6, the stored root
    view, folder = shapes
    validators = AggregateValidators(view, {}, folder)
    assert (
        validators.model_class([SHAPES_NS + "Shelf", SHAPES_NS + "SpecialShelf"]) == "SpecialShelf"
    )
    assert validators.model_class([SHAPES_NS + "Shelf", SHAPES_NS + "Book"]) is None, "two lines"
    assert validators.model_class([SHAPES_NS + "Item"]) is None, "not a root"


# The reader (PD-5: T-6, T-7)


@asynccontextmanager
async def reading_session(
    store: FakeStore | None = None, *, may_read: Callable[[str], bool] | None = None
) -> AsyncIterator[Session]:
    """A session on a store, opened with the caller's read check (``fake_session`` does not take one)."""
    store = store or FakeStore()
    if FAKE_DATABASE not in await store.list_datasets():
        await store.create_dataset(FAKE_DATABASE)
    async with open_session(
        store, database=FAKE_DATABASE, tenant_iri=TENANT, principal=WHO, may_read=may_read
    ) as session:
        yield session


def context(
    collected: dict[str, list] | None = None, removed: frozenset[str] = frozenset()
) -> GuardContext:
    held = {iri: tuple(triples) for iri, triples in (collected or {}).items()}
    return GuardContext(collected=held, rely_on=lambda *_: None, removed=removed)


def reader_of(
    session: Session,
    collected: dict[str, list] | None = None,
    removed: frozenset[str] = frozenset(),
) -> AggregateReader:
    models = generated_models(*MODULES)
    return toy({}).reader(
        session,
        context(collected, removed),
        lambda name, iri, graph, tracked: toy_mapper().from_graph(
            models.named(name), iri, graph, tracked
        ),
    )


async def store_both(session: Session) -> None:
    for model in (shelf(shelf_iri(1)), dune(book_iri(1))):
        await session.add_graph(str(model.id), toy_mapper().to_triples(model))


def counting_queries(store: FakeStore) -> list[str]:
    """Every query the store answers from now on."""
    seen: list[str] = []
    original = store.query

    async def spy(dataset: str, text: str):
        seen.append(text)
        return await original(dataset, text)

    store.query = spy  # type: ignore[method-assign]
    return seen


async def test_a_stored_aggregate_answers_with_its_own_class_not_its_ancestors():  # T-6
    async with reading_session() as session:
        await store_both(session)
        reader = reader_of(session)
        assert await reader.classes_of(shelf_iri(1)) == {"Shelf"}, "a shelf is a Shelf only"
        assert await reader.classes_of(book_iri(1)) == {"Book"}, "a book is a Book only"


async def test_an_aggregate_the_store_does_not_hold_answers_empty():  # T-6
    async with reading_session() as session:
        assert await reader_of(session).classes_of(shelf_iri(7)) == frozenset()


async def test_a_writer_who_may_not_read_the_aggregate_gets_the_same_empty_answer_as_for_none():  # T-6
    async with reading_session(may_read=lambda iri: False) as session:
        await store_both(session)
        assert await reader_of(session).classes_of(shelf_iri(1)) == frozenset(), "hidden is absent"


async def test_the_read_check_is_asked_about_the_iri_and_a_yes_lets_the_class_through():  # T-6
    asked: list[str] = []

    def may_read(iri: str) -> bool:
        asked.append(iri)
        return iri == shelf_iri(1)

    async with reading_session(may_read=may_read) as session:
        await store_both(session)
        reader = reader_of(session)
        assert await reader.classes_of(shelf_iri(1)) == {"Shelf"}, "readable"
        assert await reader.classes_of(book_iri(1)) == frozenset(), "not readable"
    assert asked == [shelf_iri(1), book_iri(1)], "the check is asked once per IRI"


@pytest.mark.parametrize("iri", ["a literal", "https://elsewhere.org/x", "not an iri at all"])
async def test_what_is_not_an_aggregate_iri_answers_empty_without_a_query(iri: str):  # T-6
    store = FakeStore()
    async with reading_session(store) as session:
        seen = counting_queries(store)
        assert await reader_of(session).classes_of(iri) == frozenset()
        assert seen == [], "no query for a non-aggregate"


async def test_an_aggregate_collected_earlier_in_the_transaction_answers_with_its_root_types():  # T-6
    triples = toy_mapper().to_triples(shelf(shelf_iri(3)))
    store = FakeStore()
    async with reading_session(store) as session:
        seen = counting_queries(store)
        reader = reader_of(session, {shelf_iri(3): triples})
        assert await reader.classes_of(shelf_iri(3)) == {"Shelf"}
        assert seen == [], "the collected change answers, not the store"


async def test_a_type_the_view_does_not_know_is_dropped_from_the_answer():  # T-6
    other = URIRef("https://example.org/ns/library#NoSuchClass")
    triples = [
        *toy_mapper().to_triples(shelf(shelf_iri(3))),
        (URIRef(shelf_iri(3)), RDF.type, other),
    ]
    async with reading_session() as session:
        reader = reader_of(session, {shelf_iri(3): triples})
        assert await reader.classes_of(shelf_iri(3)) == {"Shelf"}, "NoSuchClass is not in the view"


async def test_an_aggregate_of_a_class_that_is_not_a_root_answers_with_its_class_name():  # T-6
    chapter = URIRef("http://purl.org/ontology/bibo/Chapter")
    triples = [(URIRef(shelf_iri(3)), RDF.type, chapter)]
    async with reading_session() as session:
        reader = reader_of(session, {shelf_iri(3): triples})
        assert await reader.classes_of(shelf_iri(3)) == {"Chapter"}, "any class of the view"


@pytest.mark.parametrize("error", [StoreUnavailable("down"), DatabaseGone("gone")])
async def test_a_store_error_met_by_the_reader_passes_unwrapped(error: Exception):  # T-7
    store = FakeStore()
    async with reading_session(store) as session:

        async def failing(dataset: str, text: str):
            raise error

        store.query = failing  # type: ignore[method-assign]
        with pytest.raises(type(error)) as raised:
            await reader_of(session).classes_of(shelf_iri(1))
        assert raised.value is error, "not wrapped"


# In the guard (PD-6, PD-8, PD-9: T-8 to T-11)

REVIEW = load_workflow(REVIEW_WORKFLOW)
DRAFT = state_iri(REVIEW, "draft")


def guarded(
    mapping: dict[str, Sequence[AggregateValidator]] | None, *, workflows: bool = False
) -> WriteGuards:
    view = load_schema(TOY_SCHEMA)
    rules = AccessRules(load_role_definitions(ROLES))
    kept = Workflows([REVIEW], view, rules) if workflows else None
    return WriteGuards(
        toy_mapper(),
        generated_models(*MODULES),
        Listings(view),
        kept,
        validators=None if mapping is None else toy(mapping),
    )


def no_bad_label(old: Any, new: Any, who: Any, reader: Any) -> None:
    if new.label == "bad":
        raise InvalidBody("no bad labels")


def relabelled(iri: str, label: str):
    return shelf(iri).model_copy(update={"label": label})


async def stored_shelf(session: Session, iri: str = shelf_iri(1)) -> str:
    """Store a shelf by the toolkit's own path, whatever the guard says; its version."""
    await save(session, shelf(iri))
    return (await session.get_graph(iri))[2]


async def test_a_refused_add_leaves_no_graph():
    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Shelf": [no_bad_label]})
    ) as session:
        with pytest.raises(InvalidBody, match="no bad labels"):
            await session.add_graph(
                shelf_iri(1), toy_mapper().to_triples(relabelled(shelf_iri(1), "bad"))
            )
        assert await session.heads([shelf_iri(1)]) == [], "nothing was written"


async def test_a_refused_replace_leaves_the_stored_version():
    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Shelf": [no_bad_label]})
    ) as session:
        version = await stored_shelf(session)
        triples = toy_mapper().to_triples(relabelled(shelf_iri(1), "bad"))
        with pytest.raises(InvalidBody, match="no bad labels"):
            await session.replace_graph(shelf_iri(1), triples, version)
        assert (await session.get_graph(shelf_iri(1)))[2] == version, "the stored version stands"


async def test_a_refused_unit_of_work_commit_raises_invalid_body_and_writes_nothing():
    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Shelf": [no_bad_label]})
    ) as session:
        with pytest.raises(InvalidBody, match="no bad labels"):
            await save(session, shelf(shelf_iri(2)), relabelled(shelf_iri(1), "bad"))
        assert await session.heads([shelf_iri(1), shelf_iri(2)]) == [], "one refusal, no write"


def refuses_the_label(old: Any, new: Any, who: Any, reader: Any) -> None:
    if new.label == "bad":
        raise RuleRefusal(Marker("no bad labels"))


async def test_a_refused_unit_of_work_commit_raises_rule_refusal_and_writes_nothing():  # TC-8
    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Shelf": [refuses_the_label]})
    ) as session:
        with pytest.raises(RuleRefusal, match="no bad labels") as caught:
            await save(session, shelf(shelf_iri(2)), relabelled(shelf_iri(1), "bad"))
        assert isinstance(caught.value.problem, Marker), "the problem the rule built"
        assert await session.heads([shelf_iri(1), shelf_iri(2)]) == [], "one refusal, no write"


async def test_a_rule_sees_old_none_on_an_add_and_the_stored_aggregate_on_a_replace():
    seen: list[tuple[Any, Any]] = []

    def watch(old: Any, new: Any, who: Any, reader: Any) -> None:
        seen.append((old, new))

    async with fake_session(tenant_iri=TENANT, guards=guarded({"Shelf": [watch]})) as session:
        version = await stored_shelf(session)
        assert seen[0][0] is None, "an add has no old"
        await session.replace_graph(
            shelf_iri(1), toy_mapper().to_triples(relabelled(shelf_iri(1), "next")), version
        )
    old, new = seen[1]
    assert (old.label, new.label) == ("Shelf", "next"), "old is what is stored, new what is written"
    assert old.created is not None, "old carries tracking"
    assert new.created is None, "new does not"


async def test_a_rule_gets_the_principal_of_the_session_and_a_reader():
    seen: list[Any] = []

    def watch(old: Any, new: Any, who: Any, reader: Any) -> None:
        seen.extend([who, reader])

    async with fake_session(
        tenant_iri=TENANT, principal=WHO, guards=guarded({"Shelf": [watch]})
    ) as session:
        await stored_shelf(session)
    assert seen[0] == WHO, "the writer"
    assert hasattr(seen[1], "classes_of"), "the reader"


async def test_a_rule_reads_the_class_of_a_member_through_its_reader():
    classes: list[frozenset[str]] = []

    async def members(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        classes.extend([await reader.classes_of(i) for i in new.has_part or []])

    async with fake_session(tenant_iri=TENANT, guards=guarded({"Shelf": [members]})) as session:
        await save(session, dune(book_iri(1)))
        await save(session, shelf(shelf_iri(1)).model_copy(update={"has_part": [book_iri(1)]}))
    assert classes == [frozenset({"Book"})]


async def shelf_class_seen_by_a_book_rule(*, shelf_first: bool) -> list[frozenset[str]]:
    """Commit a book and the shelf it stands on in one unit of work; what the book's rule saw of the shelf.

    The shelf is the book's ``shelf`` reference: a collection guard would refuse a shelf naming a
    member that is not stored yet, a plain reference is not checked.
    """
    seen: list[frozenset[str]] = []

    async def looks_at_the_shelf(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        seen.append(await reader.classes_of(new.shelf))

    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Book": [looks_at_the_shelf]})
    ) as session:
        book = dune(book_iri(1), shelf=shelf_iri(1))
        objects = (shelf(shelf_iri(1)), book) if shelf_first else (book, shelf(shelf_iri(1)))
        await save(session, *objects)
    return seen


async def test_a_root_added_later_in_the_same_unit_of_work_is_empty_to_the_rule():  # T-6
    assert await shelf_class_seen_by_a_book_rule(shelf_first=False) == [frozenset()], (
        "the shelf is collected after the book: not there yet"
    )


async def test_a_root_added_earlier_in_the_same_unit_of_work_has_its_class_for_the_rule():  # T-6
    assert await shelf_class_seen_by_a_book_rule(shelf_first=True) == [frozenset({"Shelf"})], (
        "the shelf is collected before the book"
    )


async def test_an_empty_mapping_does_not_even_read_the_root_types(
    monkeypatch: pytest.MonkeyPatch,
):  # G-4
    real = write_guards.root_types
    calls: list[str] = []

    def spy(iri: str, *rest: Any) -> Any:
        calls.append(iri)
        return real(iri, *rest)

    monkeypatch.setattr(write_guards, "root_types", spy)  # X2
    async with fake_session(tenant_iri=TENANT, guards=guarded({})) as session:
        await stored_shelf(session)
    assert calls == [], "the root types were computed with no rule at all"


async def test_a_class_without_a_rule_is_not_decoded_or_read():  # T-8
    calls: list[str] = []
    for mapping in (None, {}, {"Library": [no_bad_label]}):
        async with fake_session(tenant_iri=TENANT, guards=guarded(mapping)) as session:
            version = await stored_shelf(session)
            for name in ("get_graph", "heads"):
                original = getattr(session, name)

                async def spy(*args: Any, _name: str = name, _original: Any = original):
                    calls.append(_name)
                    return await _original(*args)

                setattr(session, name, spy)
            triples = toy_mapper().to_triples(relabelled(shelf_iri(1), "next"))
            await session.replace_graph(shelf_iri(1), triples, version)
        calls.append("|")
    runs = "".join(calls).split("|")
    assert runs[0] == runs[1] == runs[2], (
        "the same reads with no rule, none for this class, or none at all"
    )


async def test_a_rule_on_a_class_under_a_workflow_sees_the_state_the_guard_kept():  # T-9
    seen: list[Any] = []

    def watch(old: Any, new: Any, who: Any, reader: Any) -> None:
        seen.append(new.workflow_status)

    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Book": [watch]}, workflows=True)
    ) as session:
        await save(session, dune(book_iri(1)))
        version = (await session.get_graph(book_iri(1)))[2]
        await session.replace_graph(
            book_iri(1), toy_mapper().to_triples(dune(book_iri(1), chapters=1)), version
        )
    assert seen == [DRAFT, DRAFT], "the initial state on the add, the kept state on the replace"


async def test_a_stored_aggregate_that_no_longer_decodes_is_a_runtime_error_naming_it():  # T-10
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as plain:
        # stored raw, as legacy data: a shelf with no label, which the generated class refuses
        triples = [(URIRef(shelf_iri(1)), RDF.type, URIRef(SHELF))]
        version = await plain.add_graph(shelf_iri(1), triples)
    async with fake_session(
        store, tenant_iri=TENANT, guards=guarded({"Shelf": [accepts]})
    ) as session:
        with pytest.raises(RuntimeError, match=f"stored {shelf_iri(1)} does not decode"):
            await session.replace_graph(
                shelf_iri(1), toy_mapper().to_triples(shelf(shelf_iri(1))), version
            )


async def test_a_new_body_that_does_not_decode_is_an_invalid_body():
    async with fake_session(tenant_iri=TENANT, guards=guarded({"Shelf": [accepts]})) as session:
        with pytest.raises(InvalidBody, match=shelf_iri(1)):
            await session.add_graph(shelf_iri(1), [(URIRef(shelf_iri(1)), RDF.type, URIRef(SHELF))])


async def test_a_stale_replace_a_rule_refuses_is_invalid_body_and_one_it_accepts_is_a_conflict():  # T-11
    async with fake_session(
        tenant_iri=TENANT, guards=guarded({"Shelf": [no_bad_label]})
    ) as session:
        await stored_shelf(session)
        refused = toy_mapper().to_triples(relabelled(shelf_iri(1), "bad"))
        with pytest.raises(InvalidBody, match="no bad labels"):
            await session.replace_graph(shelf_iri(1), refused, "stale")
        accepted = toy_mapper().to_triples(relabelled(shelf_iri(1), "fine"))
        with pytest.raises(Conflict):
            await session.replace_graph(shelf_iri(1), accepted, "stale")


# The reader hands over an aggregate (aggregate-guards D-1 to D-4: T1, T2, T4 to T7b)

FORBIDDEN = "forbidden"
AUTHOR = TOY_NS + "Author"


@asynccontextmanager
async def guarded_session(
    mapping: dict[str, Sequence[AggregateValidator]],
    *,
    store: FakeStore | None = None,
    may_read: Callable[[str], bool] | None = None,
    finding: bool = False,
) -> AsyncIterator[Session]:
    """A session with the rules ``mapping`` and the caller's read check (``fake_session`` takes none).

    ``finding`` opens it with listings and the toy's keys, as the kit does: ``find`` works, a key clash refuses."""
    store = store or FakeStore()
    if FAKE_DATABASE not in await store.list_datasets():
        await store.create_dataset(FAKE_DATABASE)
    view = load_schema(TOY_SCHEMA)
    async with open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=WHO,
        guards=guarded(mapping),
        may_read=may_read,
        listings=Listings(view) if finding else None,
        keys=aggregate_keys(view) if finding else (),
    ) as session:
        yield session


def reading_the_shelf(seen: list[Any]) -> AggregateValidator:
    """A rule on books that keeps what the reader hands over of the shelf the book names."""

    async def rule(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        seen.append(await reader.aggregate(new.shelf) if new.shelf else None)

    return rule


async def no_forbidden_shelf(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    shelf_read = await reader.aggregate(new.shelf)
    if shelf_read is not None and shelf_read.label == FORBIDDEN:
        raise InvalidBody("the shelf is forbidden")


async def add_book_on(session: Session, shelf_at: str, number: int = 1) -> None:
    await session.add_graph(
        book_iri(number), toy_mapper().to_triples(dune(book_iri(number), shelf=shelf_at))
    )


@pytest.mark.parametrize(
    ("label", "refused"), [(FORBIDDEN, True), ("fine", False)]
)  # T1: one table, the refusal and the pass
async def test_a_rule_reads_the_aggregate_a_reference_names_and_refuses_on_what_it_says(
    label: str, refused: bool
):
    async with guarded_session({"Book": [no_forbidden_shelf]}) as session:
        await save(session, relabelled(shelf_iri(1), label))
        if refused:
            with pytest.raises(InvalidBody, match="the shelf is forbidden"):
                await add_book_on(session, shelf_iri(1))
        else:
            await add_book_on(session, shelf_iri(1))
        assert bool(await session.heads([book_iri(1)])) is not refused, "written only if accepted"


async def test_the_reader_hands_over_the_stored_aggregate_as_its_model_with_tracking():  # T1
    seen: list[Any] = []
    async with guarded_session({"Book": [reading_the_shelf(seen)]}) as session:
        await save(session, shelf(shelf_iri(1)))
        await add_book_on(session, shelf_iri(1))
    assert (seen[0].label, seen[0].created is not None) == ("Shelf", True), "decoded, tracked"


@pytest.mark.parametrize(
    "case", ["not readable", "missing", "not an aggregate iri"]
)  # T2, E1, E2, E3: three ways to be absent, one answer
async def test_an_aggregate_the_writer_may_not_read_or_that_is_not_there_is_none(case: str):
    seen: list[Any] = []
    target = {"not readable": shelf_iri(1), "missing": shelf_iri(9)}.get(
        case, "https://elsewhere.org/x"
    )
    async with guarded_session(
        {"Book": [reading_the_shelf(seen)]}, may_read=lambda iri: case != "not readable"
    ) as session:
        await save(session, shelf(shelf_iri(1)))
        await add_book_on(session, target)
    assert seen == [None], f"{case}: absent to the rule"


async def test_an_aggregate_added_earlier_in_the_unit_is_read_as_collected_with_no_guard():  # T4
    seen: list[Any] = []
    reads: list[str] = []
    async with guarded_session({"Book": [reading_the_shelf(seen)]}) as session:
        original = session.get_graph

        async def spy(iri: str):
            reads.append(iri)
            return await original(iri)

        session.get_graph = spy  # type: ignore[method-assign]  # X5: a counting spy on the read
        async with session.transaction() as t:
            await t.add_graph(shelf_iri(1), toy_mapper().to_triples(shelf(shelf_iri(1))))
            await t.add_graph(
                book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=shelf_iri(1)))
            )
    assert reads == [], "a collected aggregate is not read from the store, so not relied on"  # TC-5
    assert (seen[0].label, seen[0].created) == ("Shelf", None), "as written: no tracking"


async def test_an_aggregate_removed_earlier_in_the_unit_is_none_and_has_no_classes():  # T5
    seen: list[Any] = []
    classes: list[frozenset[str]] = []

    async def both(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        seen.append(await reader.aggregate(new.shelf))
        classes.append(await reader.classes_of(new.shelf))

    async with guarded_session({"Book": [both]}) as session:
        version = await stored_shelf(session, shelf_iri(1))
        async with session.transaction() as t:
            await t.remove(shelf_iri(1), version)
            await t.add_graph(
                book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=shelf_iri(1)))
            )
    assert (seen, classes) == ([None], [frozenset()]), "the two reads agree: removed is absent"


async def test_a_book_read_then_changed_before_the_commit_fails_the_commit_naming_it():  # T6
    store = FakeStore()
    async with (
        guarded_session({"Book": [reading_the_shelf([])]}, store=store) as session,
        fake_session(store, tenant_iri=TENANT) as other,
    ):
        await save(session, shelf(shelf_iri(1)))
        with pytest.raises(Conflict) as caught:
            async with session.transaction() as t:
                await t.add_graph(
                    book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=shelf_iri(1)))
                )
                version = (await other.get_graph(shelf_iri(1)))[2]
                await other.replace_graph(
                    shelf_iri(1),
                    toy_mapper().to_triples(relabelled(shelf_iri(1), "changed")),
                    version,
                )
        assert shelf_iri(1) in caught.value.iris, "the conflict names the aggregate read"
        assert await session.heads([book_iri(1)]) == [], "nothing was written"


async def test_a_read_that_clashes_with_a_guard_of_the_transaction_is_a_conflict_not_a_500():  # T6b
    async def reads_when_asked(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        if new.label == "reads":
            await reader.aggregate(shelf_iri(2))

    store = FakeStore()
    async with (
        guarded_session({"Shelf": [reads_when_asked]}, store=store) as session,
        fake_session(store, tenant_iri=TENANT) as other,
    ):
        await save(session, shelf(shelf_iri(2)))
        with pytest.raises(Conflict) as caught:
            async with session.transaction() as t:
                # the nesting guard relies on the member at the version it has now
                await t.add_graph(
                    shelf_iri(1),
                    toy_mapper().to_triples(
                        shelf(shelf_iri(1), nests=True).model_copy(
                            update={"has_part": [shelf_iri(2)]}
                        )
                    ),
                )
                version = (await other.get_graph(shelf_iri(2)))[2]
                await other.replace_graph(
                    shelf_iri(2),
                    toy_mapper().to_triples(relabelled(shelf_iri(2), "changed")),
                    version,
                )
                await t.add_graph(
                    shelf_iri(3),
                    toy_mapper().to_triples(relabelled(shelf_iri(3), "reads")),
                )
        assert shelf_iri(2) in caught.value.iris, "a 409 naming the member, not a RuntimeError"


async def test_two_rules_reading_one_aggregate_read_the_store_once():  # T7
    async def second(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        await reader.aggregate(new.shelf)

    async with guarded_session({"Book": [reading_the_shelf([]), second]}) as session:
        await save(session, shelf(shelf_iri(1)))
        reads: list[str] = []
        original = session.get_graph

        async def spy(iri: str):
            reads.append(iri)
            return await original(iri)

        session.get_graph = spy  # type: ignore[method-assign]  # X5: a counting spy on the read
        await add_book_on(session, shelf_iri(1))
    assert reads == [shelf_iri(1)], "the second read is the first one's copy"


async def test_what_a_rule_does_to_the_aggregate_it_read_is_not_seen_by_the_next_read():  # E9
    seen: list[str] = []

    async def vandal(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        (await reader.aggregate(new.shelf)).label = "vandalised"

    async def witness(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        seen.append((await reader.aggregate(new.shelf)).label)

    async with guarded_session({"Book": [vandal, witness]}) as session:
        await save(session, shelf(shelf_iri(1)))
        await add_book_on(session, shelf_iri(1))
    assert seen == ["Shelf"], "each read is a copy"


async def test_collected_triples_that_do_not_decode_are_a_runtime_error():  # T7b, E4
    author = author_iri(1)
    async with (
        guarded_session({"Book": [reading_the_shelf([])]}) as session,
        session.transaction() as t,
    ):
        await t.add_graph(author, [(URIRef(author), RDF.type, URIRef(AUTHOR))])
        with pytest.raises(RuntimeError, match=f"{author} does not decode"):
            await t.add_graph(book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=author)))


async def test_a_stored_aggregate_that_does_not_decode_is_a_runtime_error():  # E4
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as plain:
        await plain.add_graph(shelf_iri(1), [(URIRef(shelf_iri(1)), RDF.type, URIRef(SHELF))])
    async with guarded_session({"Book": [reading_the_shelf([])]}, store=store) as session:
        with pytest.raises(RuntimeError, match=f"{shelf_iri(1)} does not decode"):
            await add_book_on(session, shelf_iri(1))


# The gaps the floor left out (aggregate-guards-test-gaps: TC-1 to TC-4)


async def test_a_read_after_the_unit_replaced_the_aggregate_gives_the_replaced_value():  # TC-1
    labels: list[str] = []

    async def reads_label(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
        labels.append((await reader.aggregate(new.shelf)).label)

    async with guarded_session({"Book": [reads_label]}) as session:
        version = await stored_shelf(session, shelf_iri(1))
        async with session.transaction() as t:
            await t.add_graph(
                book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=shelf_iri(1)))
            )
            await t.replace_graph(
                shelf_iri(1), toy_mapper().to_triples(relabelled(shelf_iri(1), "next")), version
            )
            await t.add_graph(
                book_iri(2), toy_mapper().to_triples(dune(book_iri(2), shelf=shelf_iri(1)))
            )
    assert labels == ["Shelf", "next"], "the second rule reads the replacement, not the cached read"


async def test_an_aggregate_removed_in_a_unit_cannot_be_added_back_in_it():  # TC-2, DEC-3
    async with guarded_session({}) as session:
        version = await stored_shelf(session, shelf_iri(1))
        with pytest.raises(ValueError, match="already has a change"):
            async with session.transaction() as t:
                await t.remove(shelf_iri(1), version)
                await t.add_graph(
                    shelf_iri(1), toy_mapper().to_triples(relabelled(shelf_iri(1), "again"))
                )


async def test_an_aggregate_whose_types_name_no_single_root_class_is_none():  # TC-3, E5
    chapter = URIRef("http://purl.org/ontology/bibo/Chapter")
    triples = [(URIRef(shelf_iri(3)), RDF.type, chapter)]
    async with reading_session() as session:
        reader = reader_of(session, {shelf_iri(3): triples})
        assert await reader.aggregate(shelf_iri(3)) is None, "Chapter is no root class"


async def test_an_aggregate_read_then_removed_by_the_unit_leaves_both_changes_in_the_commit():  # TC-4, E8
    seen: list[Any] = []
    async with guarded_session({"Book": [reading_the_shelf(seen)]}) as session:
        version = await stored_shelf(session, shelf_iri(1))
        async with session.transaction() as t:
            await t.add_graph(
                book_iri(1), toy_mapper().to_triples(dune(book_iri(1), shelf=shelf_iri(1)))
            )
            await t.remove(shelf_iri(1), version)
        assert seen[0].label == "Shelf", "the rule judged the aggregate as it was"
        assert len(await session.heads([book_iri(1)])) == 1, "the add is committed"


# The reader finds the holder of a value (consumer-write-rules PD-10; TC-9)

OTHER_TENANT = "https://example.org/libraries/0badc0de"
ISBN = "978-0-441"


def isbn_book_iri(n: int, tenant: str = TENANT) -> str:
    return f"{tenant}/books/{UUID(int=n)}"


@asynccontextmanager
async def finding_session(
    store: FakeStore,
    *,
    tenant: str = TENANT,
    may_read: Callable[[str], bool] | None = None,
) -> AsyncIterator[Session]:
    """A session with listings, as the kit opens one, so that ``find`` works."""
    if FAKE_DATABASE not in await store.list_datasets():
        await store.create_dataset(FAKE_DATABASE)
    async with open_session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=tenant,
        principal=WHO,
        listings=Listings(load_schema(TOY_SCHEMA)),
        may_read=may_read,
    ) as session:
        yield session


async def add_isbn_book(session: Session, n: int, isbn: str, tenant: str = TENANT) -> str:
    iri = isbn_book_iri(n, tenant)
    await session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=0, isbn=isbn)))
    return iri


async def held_isbn_rule(old: Any, new: Any, who: Any, reader: AggregateReader) -> None:
    if new.isbn is None:
        return
    holders = [iri for iri in await reader.find(Book, isbn=new.isbn) if iri != new.id]
    if holders:
        raise InvalidBody(f"isbn {new.isbn} is held by {holders[0]}")


@pytest.mark.parametrize(
    ("scope", "found"),
    [
        ("held", True),
        ("another tenant", False),
        ("unreadable", False),
        ("removed in the transaction", False),
        ("replaced earlier in the transaction", False),
    ],
)
async def test_find_returns_the_holder_only_inside_what_the_writer_may_read_in_the_tenant(
    scope: str, found: bool
):  # TC-9
    tenant = OTHER_TENANT if scope == "another tenant" else TENANT
    store = FakeStore()
    async with finding_session(store, tenant=tenant) as owner:
        holder = await add_isbn_book(owner, 1, ISBN, tenant)
    collected = {holder: toy_mapper().to_triples(dune(holder, chapters=0, isbn=ISBN))}
    async with finding_session(store, may_read=lambda iri: scope != "unreadable") as session:
        reader = reader_of(
            session,
            collected if scope.startswith("replaced") else None,
            frozenset({holder}) if scope.startswith("removed") else frozenset(),
        )
        assert (await reader.find(Book, isbn=ISBN) == [holder]) is found, scope


async def test_find_keeps_the_order_of_the_store_and_leaves_out_what_does_not_match():  # TC-9
    async with finding_session(FakeStore()) as session:
        for n in (3, 1, 2):
            await add_isbn_book(session, n, ISBN)
        await add_isbn_book(session, 4, "other")
        found = await reader_of(session).find(Book, isbn=ISBN)
    assert found == [isbn_book_iri(n) for n in (1, 2, 3)], (
        "the session's IRI order, only the holders"
    )


async def test_find_for_none_is_a_type_error_naming_the_slot_before_any_query():  # TC-9
    store = FakeStore()
    async with finding_session(store) as session:
        seen = counting_queries(store)
        with pytest.raises(TypeError, match=r"find\(Book\): isbn is None"):
            await reader_of(session).find(Book, isbn=None)
        assert seen == [], "refused before the store was asked"


async def test_a_rule_that_finds_a_holder_refuses_a_second_book_with_its_key():  # TC-9
    async with guarded_session({"Book": [held_isbn_rule]}, finding=True) as session:
        await add_isbn_book(session, 1, ISBN)
        with pytest.raises(InvalidBody, match=f"held by {isbn_book_iri(1)}"):
            await add_isbn_book(session, 2, ISBN)
        await add_isbn_book(session, 3, "free")
        assert len(await session.heads([isbn_book_iri(n) for n in (1, 2, 3)])) == 2, "1 and 3"


@pytest.mark.parametrize("keeps_the_key", [False, True])
async def test_a_key_that_moves_within_one_unit_is_not_held_by_the_root_that_left_it(
    keeps_the_key: bool,
):  # TC-9, worked example 2: both variants
    first, second = isbn_book_iri(1), isbn_book_iri(2)
    async with guarded_session({"Book": [held_isbn_rule]}, finding=True) as session:
        await add_isbn_book(session, 1, "v")
        version = (await session.get_graph(first))[2]
        replacement = dune(first, chapters=0, isbn="v" if keeps_the_key else "w")
        if keeps_the_key:
            replacement = replacement.model_copy(update={"label": "Dune, again"})

        async def unit() -> None:
            async with session.transaction() as t:
                await t.replace_graph(first, toy_mapper().to_triples(replacement), version)
                await t.add_graph(
                    second, toy_mapper().to_triples(dune(second, chapters=0, isbn="v"))
                )

        if keeps_the_key:
            with pytest.raises(KeyConflict):
                await unit()  # the rule misses the holder; the commit's unique key refuses
            assert await session.heads([second]) == [], "nothing was written"
        else:
            await unit()
            assert len(await session.heads([first, second])) == 2, "both committed"
        assert await session.heads([shelf_iri(1)]) == [], "the removal is committed"
