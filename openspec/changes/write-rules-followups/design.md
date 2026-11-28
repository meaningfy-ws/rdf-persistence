# Design: write-rules-followups

> Derives from: EPIC `write-rules-followups` (proposal.md, DEC-1 to DEC-6); issue #455.

## Context

`consumer-write-rules` (archived 2026-11-28) left the items of #455 under its review floor. Each
item was checked against `origin/develop` 6bcad805 (`inputs/qa.md`); two were dropped (DEC-1) and
one narrowed to a docstring (DEC-2). Nothing here touches a schema, a generated artefact or a
migration. The library change sits in `collaboration/services`, `api/entrypoints` and `testkit`;
the generator change in `rdf_persistence_generation`. Layers are unchanged.

## Goals / Non-Goals

**Goals:** S1 to S7 hold (the spec deltas); the two readers refuse alike in one order; the docs and
docstrings say what the code does; the refactors leave every existing test green.

**Non-Goals:** the EPIC's no-gos.

## Decisions

- **PD-1 Refusal registration (DEC-4, T-F1).** `_checked_refusal_problems(classes: Iterable[...])`
  does `classes = tuple(classes)` first, then checks each, then returns it. `ServiceKit`'s and
  `install_service`'s parameter type becomes `Iterable[type[BaseModel]]`. `refusal_response` admits
  a problem when `type(problem) in refusal_problems`, `isinstance(status, int) and not
  isinstance(status, bool)`, and `status in _REFUSAL_STATUSES` (so an `HTTPStatus.CONFLICT`, an
  `int` subclass, still passes; `409.0` and `True` do not). The logged reason for a bad status
  changes from `f"status {status}"` to `f"status {status!r}"`, so `409.0` and `True` are named
  as given.
- **PD-2 R-S4.** `service.py`'s `refusal_problems` paragraph says "every write that runs the rules
  (the generic create, replace and every other guarded write)" in place of "the generic create and
  replace".
- **PD-3 The shared find helper (D-20, DEC-3, the fake's check order).** In
  `aggregate_validators.py`, beside `checked_find_values`:
  `def find_items(cls: type[BaseModel], equals: Mapping[str, object]) -> dict[str, list[object]]`,
  "the items asked per slot". In this order, before any query: no keyword → `ValueError(f"find
  ({cls.__name__}) needs a slot to match; a rule never reads a whole class")`; for each keyword in
  order, a dotted one → the existing `BadQuery` text, a `None`, alone or as an item of a list or
  tuple → the existing `TypeError` text, an empty list or tuple → `ValueError(f"find({cls.__name__}): {slot} is an empty list")`; then each
  value is split (`list`/`tuple` → its items, else `[value]`).
  **One order for both readers** (the spec's "same order"): (1) the helper; (2) the value check,
  strict, over the slots `cls` has, skipping an item that is a `Contains`
  (`_refuse_values_not_of_the_slot`, which now takes the helper's output) → `BadQuery`; (3) the root
  check → `ValueError("{name} is not an aggregate root with a path")`; (4) an unknown slot →
  `BadQuery`. `_Reader.find` does (1), (2), then `Session.find`, which does (3) in `served_root` and
  (4) in the listing plan. The fake does (1), (2), (3), (4), then a `Contains` →
  `NotImplementedError` (its one limit), then matches.
- **PD-4 The value check (perf, robustness).** `_adapter(cls, slot)` is `@functools.cache`
  (`TypeAdapter(_item_type(cls, slot))`), with a `ponytail:` comment naming the ceiling (one entry
  per (class, slot) asked for; classes are module-level, so it stays small). The `BadQuery` text is
  `f"{slot} of {cls.__name__} does not take {reprlib.repr(items)}: {reasons}"`, where `reasons` is
  `"; ".join(e["msg"] for e in error.errors(include_input=False))`: no part of it repeats the
  value unbounded.
- **PD-5 `Session.find`'s docstring (DEC-2).** Its `BadQuery` line reads: "a value whose text is
  not a value of its slot (each value is taken as its RDF text: `5` for a string slot is `"5"`;
  a rule's reader checks the Python type strictly)". `user-manual/files.adoc` says the same in its
  `BadQuery` bullet.
- **PD-6 The conformance kit.** Two new cases in `CASES`: `find_without_a_slot_is_refused`
  (`ValueError`, matching `"needs a slot"`) and `find_by_a_dotted_keyword_is_bad_query`
  (`**{f"{seeded.slot}.x": seeded.value}`, `BadQuery`). The three unfiltered calls get
  `**{seeded.slot: seeded.value}`: `find_on_a_root_omits_another_root` still asserts `other_iri`
  is absent; the abstract-parent and not-root cases match `"not an aggregate root"` (both readers
  raise `"{name} is not an aggregate root with a path"`), and their filter is a slot those classes
  lack, so they reach the root check (3) and cannot pass on the empty-filter refusal. A third new
  case, `find_checks_the_value_before_the_root`: `Seeded` gains two keyword arguments,
  `not_root_slot` and `not_root_wrong_value` (a slot of `not_root` and a value not of its type;
  the toy's are `number` and `"x"` on `Chapter`), and the case asserts
  `find(seeded.not_root, **{seeded.not_root_slot: seeded.not_root_wrong_value})` → `BadQuery`
  (the order (2) before (3)), unskipped. In `tests/unit/testkit/test_fake_reader.py`, the
  case "a class that is not among the roots" (`Chapter, {}`) gets `{"number": 1}` and
  `match="not an aggregate root"`; the dotted-keyword cases move from `NotImplementedError` to
  `BadQuery`.
- **PD-7 `technical_checks.py` (the move).** `rdf_persistence_generation/extensions/technical_checks.py`
  takes `refuse_unsupported_extensions`, `_refuse_shadowing`, `_named_by`, `_technical_classes`,
  `_exported_names`, `unexported_technical` (public now: `pydantic_split` uses it) and
  `is_toolkit_technical` (public: both modules use it), `_field_name`, and `is_python_name` (public:
  rendering's `_named_after_slot` uses it; `_field_name` needs it). `technical_checks` defines its
  own `METAMODEL_DIR = METAMODEL.parent` if it needs it and **imports nothing from
  `pydantic_split`**; `pydantic_split` imports from it (no cycle). No behaviour changes in the
  move; it is its own commit.
- **PD-8 The enum export check.** `refuse_unsupported_extensions` also refuses a consumer slot whose
  range (from `_named_by`) is an enum of a technical module that `rdf_persistence` does not export:
  `SchemaGenerationError(f"{cls.name} uses {name} of {module}, which rdf_persistence does not
  export")`, the class message's shape. A `_technical_enums(view)` beside `_technical_classes`
  feeds both this and `unexported_technical`. S6's test ranges a toy consumer slot to
  `ProblemSlug` (in `rp_api_entrypoints`, not exported), through the generator tests'
  `break_toy` fixture.
- **PD-9 TypeScript `modules()`.** One comment line above `first.setdefault`: "a schema name is
  unique within one import closure; two distinct schemas under one name would be merged here".
- **PD-10 Schema cache (DEC-5).** The ceiling comment cites linkml/linkml#4306 in place of "upstream
  issue to file", and names `hbreader.Pathilizer._strifier` as a private attribute it sets.
  `pyproject.toml`'s `generate` extra gains `"hbreader>=0.9.1",` with a comment ("the schema
  cache pickles its `Pathilizer`"). The lead runs `uv lock` and `uv sync`, then `make test-seed`
  again. A unit test (S7): `"_strifier" in inspect.getsource(Pathilizer.__str__)` (a fresh
  `Pathilizer` has no such attribute: only `__str__` reads it), `str(_pathilized("x")) == "x"`,
  and `_pathilized("x")` round-trips through `pickle` with `_SchemaPickler`.
- **PD-11 `ban_reading`.** `tests/scene.py` gains `async def ban_reading(scene: Scene, iri: str) ->
  None` (the `test_aggregate_validators_api` body, which also records `scene.access_etag`); the two
  module-level copies are deleted and import it. The feature test's harness holds a `Scene`: its
  method delegates to it. `test_delete_in_use`'s harness has no `Scene`: it keeps its own copy.
- **PD-12 Docs and CHANGELOG.** `user-manual/access.adoc`, the paragraph on `reader.find`: `find`
  with no slot raises `ValueError`; `user-manual/test.adoc`, the paragraph on
  `FakeAggregateReader`'s limits: the fake refuses a dotted keyword with `BadQuery`, as the real
  reader, and `Contains` is its one limit. `CHANGELOG.md` `[Unreleased]`: the two BREAKING lines
  (DEC-6) and a Fixed entry for T-F1, T-F2 and the enum check.

## Algorithm / approach

**Worked example 1, the shared helper.** `find(Book)` → `ValueError`, nothing queried, in both
readers. `find(Book, **{"holder.name": "x"}, isbn=None)` → `BadQuery` (the dotted keyword comes
first in keyword order). `find(Book, isbn=None, **{"holder.name": "x"})` → `TypeError`.
`find(Chapter, number="x")` (a non-root, a mistyped value) → `BadQuery` in both readers (the value
before the root); `find(Book, nosuch=1, authors=[])` → `ValueError` in both (the empty list in the
helper). The conformance kit holds the value-before-root order (PD-6).

**Worked example 2, a bounded `BadQuery`.** `find(Book, pages="x" * 10_000)` on an int slot →
`BadQuery("pages of Book does not take ['xxxxxxxxxxxx...xxxxxxxxxxxxx']: Input should be a valid
integer")`: about 90 characters, under S5's bound of 300, naming the slot and the class.

**Worked example 3, a registered refusal at `409.0`.** A rule raises `RuleRefusal(HeldKeyProblem.
model_construct(status=409.0, ...))` → the client gets the 500 internal-error problem; one error
record with `error_detail="status 409.0"` and the refusal as `exc_info`.

Every change is a pure function or a check before a query: nothing to retry or replay.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Let the conformance kit's refusal cases match a bare `ValueError` | match the message | the empty-filter refusal is also a `ValueError` (Rabbit-holes) |
| Make `Session.find` strict | fix its docstring | DEC-2 |
| Mix the move (PD-7) with the enum check (PD-8) in one commit | move first, then change | the move must show no behaviour change |
| Put `hbreader` in the base dependencies | the `generate` extra | only the generator imports it |
| Import anything from `pydantic_split` in `technical_checks` | move `is_python_name` and `_field_name` with the checks | an import cycle |
| Leave a fake-reader or conformance refusal case with an empty filter | give it a filter and a message match | it would pass on the empty-filter refusal |
| Test `Pathilizer("x")._strifier` | inspect `Pathilizer.__str__`'s source | the attribute exists only after hbreader sets it |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| `refusal_problems` a generator | S1 | registered in full |
| A non-problem class inside a generator | S1 | `TypeError` naming it, at start-up |
| A refusal status `409.0` or `True` | S2 | 500 internal-error, one error record naming the status |
| A refusal status `HTTPStatus.CONFLICT` (an `int` subclass, via `model_construct`) | a row of S2's parametrized test in `test_rule_refusal.py` (`409.0`, `True` → 500; `HTTPStatus.CONFLICT` → answered) | answered as built, as today |
| A `None` inside a list on an unknown slot (`find(Book, nosuch=["a", None])`) | a unit test of the helper | `TypeError`, both readers (step 1) |
| An empty list beside an unknown keyword | worked example 1 | `ValueError`, both readers |
| A non-root class with a mistyped value | conformance (PD-6) | `BadQuery`, both readers |
| A rule's `find(cls)` with no keyword | S3, conformance | `ValueError`, nothing queried, both readers; the rule is a bug: 500 |
| A rule's dotted keyword | S4, conformance | `BadQuery` in both readers, nothing queried |
| A huge mistyped value | S5 | `BadQuery`, the message bounded |
| A consumer slot ranged to an unexported technical enum | S6 | `SchemaGenerationError` naming the class, the enum and its module; nothing written |
| A linkml upgrade drops `Pathilizer._strifier` | S7 | the unit test fails in CI |
| An abstract parent or non-root asked with a filter | conformance (PD-6) | `ValueError` with its own message, both readers |

## Risks / Trade-offs

- **RISK-1** `openapi-refusal-problems` merges first and edits `kit.py` (likelihood medium, impact
  low). Mitigation: rebase before the gates; resolve `kit.py` by hand, keeping both changes; the
  rebased head is what `make check-all` runs on.
- **RISK-2** A linkml upgrade changes `hbreader` (likelihood low, impact medium: a silent wrong
  cache). Mitigation: S7 and DEC-5's declared lower bound.
- **RISK-3** A consumer rule or test relies on `find(cls)` unfiltered or on the fake's
  `NotImplementedError` (likelihood low: the consumer's checkout uses neither today; impact low).
  Mitigation: the two BREAKING lines say what to do (pass a slot; expect `BadQuery`).

## Open Questions

None.

## Lanes for moved or rewritten tests

| Test | Lane that still runs it in CI | What it still proves |
|---|---|---|
| `test_fake_reader.py` dotted case (`NotImplementedError` → `BadQuery`) | unit | the fake refuses a dotted keyword, now as the real reader |
| `reader_conformance` cases given a filter (PD-6) | unit (`tests/unit/testkit/test_reader_conformance.py`, the fake and the real reader over a `FakeStore`) | the root, abstract-parent and non-root rules, each by its own message |
| The `ban_reading` users (PD-11) | unit, feature | unchanged |
| The generator tests of `refuse_unsupported_extensions` (PD-7) | generator | unchanged, now importing `technical_checks` |

## Delivery decisions

- **D-1 The PLAN gate: 8.1, then 8.8, accepted (R-0005).** A fresh reviewer attacked and gated
  the PLAN twice (`evidence/clarity-gate.md`). Run 2's three gaps (the order case on a slot
  `Chapter` lacks, a `None` inside a list on an unknown slot, the `HTTPStatus` row's reference) are
  folded into PD-3, PD-6 and the error matrix without a third run, per the developer's rule
  R-0005. The tasks cite the Decisions bullets by PD id, not by anchor: the bullets have none.
