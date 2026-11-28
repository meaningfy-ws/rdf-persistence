# EPIC: write-rules-followups

## Appetite

SMALL. One stage, one PR. The follow-ups of `consumer-write-rules` (issue #455), left under that
change's review floor (its D-20, D-21, D-23). Golden-thread parents: `rp-service-api` "A consumer
rule refuses a write with its own problem" and "A consumer rule finds the aggregates that hold a
value", `rp-testkit` "A rule is unit-tested with the testkit's reader", `rp-generation` "A consumer
class extends a toolkit technical class the package exports".

## Why

`consumer-write-rules` shipped a rule's own refusal problem, `AggregateReader.find` and the fake
reader. Its reviews left small defects and tidy-ups under the floor: a generator of refusal
problems registers nothing, `409.0` passes as a status, the two readers still disagree on a dotted
keyword, a rule can page through a whole class on each write, and the generator's schema cache
leans on an undeclared library. No consumer uses `find` or `refusal_problems` yet, so this is the
cheapest moment to tighten them.

## Solution outline

- **Refusal registration.** `refusal_problems` is materialised before it is checked; a refusal's
  status counts only as an `int` 409 or 422.
- **`find` in the rule readers.** One shared helper refuses, in one order, an empty filter, a dotted
  keyword and a `None`, for both the real reader and the fake; the value check caches its
  `TypeAdapter` per (class, slot) and bounds the value it quotes. The conformance kit holds the two
  new refusals.
- **Docstrings that say what the code does.** `Session.find`'s `BadQuery` (a value whose text does
  not parse), `install_service`'s refusal wording (every write that runs the rules).
- **Generator.** The consumer-schema checks move out of `pydantic_split.py` into
  `extensions/technical_checks.py`, and the export check covers technical enums. The TypeScript
  `modules()` states its uniqueness assumption.
- **Schema cache.** Its ceiling comment cites linkml/linkml#4306 and names `hbreader` and
  `Pathilizer._strifier`; `hbreader` is declared; a test fails if `_strifier` goes.
- **Tests.** `ban_reading` lives once, in `tests/scene.py`.

## Key decisions

- **DEC-1**: In scope: every item of #455 and the brief except `_item_type`'s unwrap depth and the
  schema cache's thread lock. *Reason:* `_item_type` already handles what the generator emits
  (`list[X | None]`, wider unions); generation is single-threaded. *Rejected:* building both "for
  later".
- **DEC-2**: `Session.find`'s `BadQuery` is fixed in its docstring, not by a strict check.
  *Reason:* `reference_collections` passes stored membership-rule values as text for every slot; a
  strict `Session.find` would break rules on non-string slots. The rule readers stay strict (D-16,
  D-21 F-2). *Rejected:* a strict `Session.find`.
- **DEC-3**: A rule reader's `find(cls)` with no keyword raises `ValueError`, before any query, in
  both readers; `Session.find` still allows it. *Reason:* an unfiltered find pages through the class
  on every write; a rule bug, answered as a 500 like an empty list. *Rejected:* allowing it and
  documenting the cost.
- **DEC-4**: A refusal is answered as built only when its status is an `int` that is not a `bool`,
  and is 409 or 422; `409.0` and `True` get the 500 and the one error record (D-22). *Rejected:* accepting an
  equal float.
- **DEC-5**: `hbreader>=0.9.1` is declared in the `generate` extra, beside `linkml`; the locked
  version stays 0.9.1. *Rejected:* naming it in the comment only.
- **DEC-6**: BREAKING in the CHANGELOG: DEC-3, and the fake's `BadQuery` for a dotted keyword
  (it raised `NotImplementedError`). *Reason:* a consumer rule or test that relied on either
  changes.

## Rabbit-holes

- The conformance kit's three unfiltered calls would pass for the wrong reason once DEC-3 lands
  (an empty filter is also a `ValueError`): each gets a filter and a message match.
- `pydantic_split.py`'s other functions stay where they are; only the consumer-schema checks move.

## No-gos

- Removing the schema cache: it waits on linkml/linkml#4306.
- A lock or depth counter for concurrent generation (DEC-1).
- `_item_type` changes (DEC-1).
- A strict `Session.find` (DEC-2).
- `Contains` in the fake reader (its limit stays `NotImplementedError`).
- The OpenAPI listing of refusal problems: that is `openapi-refusal-problems`.

---

## What Changes

- `ServiceKit` takes `refusal_problems` as any iterable of classes, a generator included.
- A refusal whose status is not an `int` 409 or 422 is the 500 internal-error problem.
- **BREAKING** `AggregateReader.find(cls)` with no keyword raises `ValueError` in the real reader
  and in `FakeAggregateReader`.
- **BREAKING** `FakeAggregateReader.find` raises `BadQuery` for a dotted keyword, as the real reader.
- **BREAKING** (found in delivery, `design.md` D-8) `reader_conformance.Seeded` takes
  `not_root_slot` and `not_root_wrong_value`, and `CASES` gains three cases.
- Both readers refuse in one order (no slot, dotted keyword, `None`, empty list, mistyped value,
  then a class that is no root and an unknown slot), a `None` inside a list included.
- A `BadQuery` from the rule readers quotes a bounded value.
- Generation fails, naming it, when a consumer slot is ranged to a technical enum the package does
  not export.
- `hbreader` becomes a declared dependency of the `generate` extra.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-service-api`: the refusal's status check (DEC-4); `find` with no keyword (DEC-3).
- `rp-testkit`: the fake refuses a dotted keyword as the real reader does.
- `rp-generation`: the export check covers technical enums.

## Impact

`rdf_persistence/api/entrypoints/{kit,problems,service}.py`,
`rdf_persistence/collaboration/services/aggregate_validators.py`,
`rdf_persistence/persistence/services/session.py` (docstring),
`rdf_persistence/testkit/{fakes,reader_conformance}.py`,
`rdf_persistence_generation/extensions/{pydantic_split,typescript}.py`,
`rdf_persistence_generation/technical_checks.py` (at the package root, not in `extensions/`: D-5),
`rdf_persistence_generation/schema_cache.py`, `pyproject.toml`, `uv.lock`, the tests (and
`tests/scene.py`), `CHANGELOG.md`, `user-manual/{access,files,test}.adoc`,
`architecture/api.adoc`. No schema, no migration; the generated manifests changed only in the
hashes of their generator inputs.

**Delivered** in one PR (stage 1), every item of the shape built; nothing promised was dropped.
