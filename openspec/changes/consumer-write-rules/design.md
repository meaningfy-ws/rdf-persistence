# Design: consumer-write-rules

> Derives from: EPIC `consumer-write-rules` (proposal.md, DEC-1 to DEC-8). Facts:
> `inputs/seed.md`; the developer's answers: `inputs/qa.md`.

## Context

- `metamodel_importmap()` (`rdf_persistence/schema/services/schema.py`) maps
  `rdf_persistence/model/<stem>` to the installed file, for `model/*.yaml` only.
- `SplitPydanticGenerator.generate_module_import` (`extensions/pydantic_split.py`) imports a class
  of a module beside the root, of the metamodel folder (from `public_package()` on a consumer's
  run), or of a module that names `python_package` (from that package, a deep import). A toolkit
  technical module lands in the last branch today.
- `run_aggregate_validators` lets `InvalidBody`, `ValidationError`, store errors and `Conflict` pass
  and wraps anything else in `RuntimeError` (500).
- `problems.install_problem_handlers` answers a mapped error with a fresh `Problem` built from its
  kind and text; `problem_response(problem)` sends `problem.model_dump(exclude_none=True)`, so a
  subclass instance would carry its extra fields.
- `Problem`'s OpenAPI component is closed (`additionalProperties: false`); `openapi.py` writes the
  problem answers of each route from `ProblemKind`s with schema `Problem` (or `InUseProblem`), and a
  `default` "Any other problem" answer with `Problem`.
- `Session.find(cls, **equals)` lists by the listings, ignores access; the reader's `_visible(iri)`
  applies the tenant check and `may_read`, and `context.removed` holds the transaction's removals.
- A stored root has one `rdf:type`, its own class (`mapper._write`).
- The TypeScript template lists every induced slot of a class and writes no `extends`.

## Decisions

### Stage 1: a consumer problem, raised by a rule (#415, #397 part 1)

- **PD-1 The importmap (DEC-1).** `metamodel_importmap()` keeps every existing key and value, and
  adds `f"{MODEL_PREFIX}/{rel}"` → the file without suffix, for each `rel` = the posix path of a
  `model/technical/**/*.yaml` file relative to `model/`, suffix dropped (for example
  `rdf_persistence/model/technical/api/rp_api_entrypoints`). `model/migrations/` holds migration
  files, not schemas: it is not mapped. A unit test asserts the old keys and values are unchanged
  (RISK-1).
- **PD-1a One schema under two import names.** Probed while planning (`SchemaView` with the new
  keys): a technical module's closure already holds some modules under several import strings
  (`rp_api_entrypoints` loads `rp_core` three times, `rp_access`, `rp_tenancy`, `rp_annotations`
  twice), on the toolkit's own run today; `all_classes()` counts each class once. A consumer that
  imports two technical modules by the new keys adds no further duplicate (a module imported by its
  new key and by a relative import was loaded once). The generators iterate `schema_map.values()`,
  so `ToolkitTypescriptGenerator.modules()` keeps the first module of each name (a dict by
  `schema.name`), a no-op for every closure without duplicates. TC-1b asserts, on the toy's
  technical target, each generated `.ts` and `.py` module file once, each interface and class once,
  and `schema_map`'s duplicate names no more than the toolkit's own closure has. Rejected:
  normalising import strings in `load_schema` (a change to every schema load, the CRITICAL path).
- **PD-2 Importing a toolkit technical class (DEC-2).** In `generate_module_import`, on a
  consumer's run (`not self.toolkit`), a module whose source file is under `METAMODEL_DIR /
  "technical"` is imported from `public_package()`, as a metamodel module is. Before rendering, the
  Python step checks the consumer's own modules: every class of a toolkit technical module that one
  of them names (as `is_a`, a mixin or a slot range) must be in `rdf_persistence.__all__`; otherwise
  `SchemaGenerationError("<consumer class> uses <toolkit class> of <module>, which rdf_persistence
  does not export")`, reported as a problem, and nothing is written. The toolkit's own run is
  unchanged (`target_module`).
- **PD-2a No shadowed field.** The same check refuses a consumer class extending a toolkit
  technical class when one of the consumer's own slots has a Python field name (its `alias`, else
  its name) equal to a field of the toolkit class that is not that same slot (for example a slot
  `kind` with `alias: type`): `SchemaGenerationError("<consumer class>.<slot> shadows <toolkit
  class>.<field>")`. Narrowing the inherited slot itself through `slot_usage` stays allowed. Reason:
  a shadowed `type` or `status` breaks assignability to `Problem` and PD-6's status check. Test:
  TC-3b. Rejected: renaming at generation (a generated name the schema does not say).
- **PD-3 Where the subclass lives.** A consumer domain or value module importing a technical module
  already fails `_module_problems` (`checks/boundary.py`); unchanged, and the docs say the subclass
  goes in a technical module (DEC-3).
- **PD-4 TypeScript (DEC-3).** No template change: the consumer interface lists every induced slot,
  `Problem`'s included, and the problem module is a served schema, so its names are imported from
  `rp_service.ts` (`_with_served`). "Extends" is met by assignability: a unit test reads the
  generator's `TsModule`s and asserts each `Problem` field (name, type, optional or not) is a field
  of `HeldKeyProblem` with the same type and a required field stays required; `make typecheck-ts`
  compiles the toy's folders.
- **PD-5 The error.** `core/domain/exceptions.py`: `class RuleRefusal(PersistenceError)` with
  `__init__(self, problem: object)`; it keeps `problem` and its text is the problem's `detail`, else
  its `title`, else its class name. The domain imports no `Problem` (layers), so the type is checked
  at the edge (PD-6). Exported from `rdf_persistence`. `run_aggregate_validators` adds it to the
  errors that pass; `run_delete_validators` does not (a delete rule raising it is a bug: 500, as any
  other exception, a no-go).
- **PD-6 The answer.** `problems.py`: `ERROR_KINDS` gains `(errors.RuleRefusal, INTERNAL_ERROR)`, the
  fallback kind, so the gap test stays green. `install_problem_handlers(app, base, locate, *,
  refusal_problems: tuple[type[Problem], ...] = ())`. In `toolkit_error`, the **first** statement
  is `if isinstance(error, RuleRefusal): return refusal_response(base, error, refusal_problems)`,
  before the internal-error logging (`problems.py:259`), so a refusal is never logged as an internal
  error with a traceback. `refusal_response`: when `type(error.problem)` is one of
  `refusal_problems` (exact class) and its `status` is 409 or 422, `problem_response(error.problem)`,
  nothing logged; otherwise the 500 internal-error problem and one `log.error("rule refusal
  answered as internal error", extra=log_extra(LogContext(step="answer-rule-refusal",
  error_type=<the problem's class name>, error_detail="unregistered class" | "status <n>")))`, no
  `exc_info`. The problem is sent as the rule built it: `detail` kept whatever the status (the
  rule's own text, as `REFUSED`). Tested by TC-6: a registered refusal leaves no `log.error` record;
  an unregistered one leaves exactly one, with no traceback.
- **PD-7 Registering the classes (DEC-4).** `install_service(..., refusal_problems:
  Sequence[type[BaseModel]] = ())` and `ServiceKit(..., refusal_problems=...)`; the kit checks each
  is a subclass of `Problem` (else `TypeError` naming it, at start-up) and keeps them as a tuple;
  `install_service` passes them to `install_problem_handlers` and to `install_openapi`.
- **PD-8 The document.** Two places, because route answers are built per route at registration
  (`route_options`, `openapi.py:280`) and `install_openapi` only adds components:
  1. **Per route.** `AggregateOpenApi.__init__(view, cls, rp_path, refusals: tuple[type[BaseModel],
     ...] = ())`; `router.py:461` passes `kit.refusal_problems`. `route_options(..., refusals=())`
     gains the parameter; `create()` and `replace()` pass `self._refusals`, and `route_options`
     then writes the 409 and the 422 answers' schema as `anyOf` of their current `$ref`
     (`Problem`, or `InUseProblem`) and a `$ref` to each refusal class. Every other caller passes
     nothing and is unchanged.
  2. **Components and the default answer.** `install_openapi`: each registered class's JSON
     schema (`cls.model_json_schema(ref_template="#/components/schemas/{model}")`, its `$defs`
     hoisted as components) becomes a component named by the class; a name already a component
     fails start-up with `ValueError` naming it. In the same `openapi()` closure, after the build,
     every operation's `default` answer `$ref` to `Problem` becomes `anyOf` of `Problem` and the
     refusal classes (one loop over `document.paths`), since a refusal reaches any route that runs
     rules (a workflow transition, for example).

  With no registered class, the document is byte-for-byte as before (golden test). The Pydantic schema of a generated class is used because a
  consumer technical target writes no components the service reads; making it write them is out of
  this appetite (rejected alternative, recorded).
- **PD-9 The toy.** `tests/fixtures/library/services/library_problems.yaml` (new, `module_kind:
  technical`, `python_package: tests.fixtures.library.services.generated`) imports
  `rdf_persistence/model/technical/api/rp_api_entrypoints` and declares `HeldKeyProblem` (`is_a:
  Problem`, slot `holder`, range `uri`, required). `services/loan_checks_response.yaml` imports
  `library_problems`, so the existing technical target generates it (no new target: the generator
  lane's cost, consumer-friction D-9). `make generate`; the toy trees and manifests are committed.
- **PD-9a The stage-1 toy rule.** `tests/toy_service.py` gains `fixed_refusal(old, new, principal,
  reader)`, a write rule for `Book` with no reader call: `isbn == "held"` raises
  `RuleRefusal(HeldKeyProblem(type=HELD, title="Key held", status=409, detail="isbn held is held",
  holder=FIXED_HOLDER))`; `isbn == "malformed"` raises the same class with `status=422`; any other
  isbn passes. `HELD` and `FIXED_HOLDER` are constant IRIs of the toy. TC-5 to TC-8 use it, so stage
  1 ships alone. `held_isbn` (worked example 1), which needs `find`, is stage 2's (task 2.4).

### Stage 2: find, typed rules, the fake reader, state names (#397 part 2, #387, #386)

- **PD-10 `find` (DEC-5).** `AggregateReader.find(self, cls: type[BaseModel], **equals: object) ->
  list[str]` on the protocol and `_Reader`: `[iri for iri in await self._session.find(cls,
  **equals) if self._visible(iri) and iri not in self._context.removed and iri not in
  self._context.collected]`, order kept. No `rely_on`, no read cache.
  - **Roots changed earlier in the transaction are left out** (`context.collected`): their stored
    values are stale (a replace of B1's isbn `v`→`w` followed by an add of B2 with `v` must not find
    B1). Leaving them out can miss a holder the transaction kept at `v`; the commit's unique key
    then refuses (`KeyConflict`), so the miss fails safe. Rejected: matching the collected triples
    against `equals` (a second, triple-level evaluator of listing filters to keep in line with the
    SPARQL one).
  - **A `None` value is refused**: `find` raises `TypeError(f"find({cls.__name__}): {slot} is None;
    a rule asks for a value, never for its absence")` before any query. `Session.find` reads `None`
    as "no value", which would make `find(Book, isbn=new.isbn)` on a book without isbn match every
    such book. The how-to warns and the worked examples guard it. Rejected: passing `None` through
    (the trap above), or answering `[]` (silent). Errors are `Session.find`'s (`ValueError`, `BadQuery`, `RuntimeError`
  without listings); `run_aggregate_validators` passes none of them, so one escaping a rule is the
  rule's bug and becomes `RuntimeError` naming the rule (500).
- **PD-11 Typed registration (DEC-6).** In `aggregate_validators.py`:
  `def aggregate_rules[M: BaseModel](cls: type[M], *rules: Callable[[BaseModel | None, M,
  Principal, AggregateReader], Awaitable[None] | None]) -> tuple[str, tuple[AggregateValidator,
  ...]]` and `delete_rules[M]` (`Callable[[M, Principal, AggregateReader], ...]`); both return
  `(cls.__name__, tuple(cast(...)))`, the one `cast` in the toolkit.
  - **`new` is typed `M`**: sound, the guard decodes the new root as its most specific root class,
    which is `cls` or derives from it.
  - **`old` is typed `BaseModel | None`**, not `M`: `_decoded_stored` (`write_guards.py:222`)
    decodes the stored root by its stored types, so a replace that moves a stored `Book` to a class
    derived from it hands the derived class's rule an `old` that is a `Book`. A rule narrows `old`
    with `isinstance`. Rejected: decoding `old` as the selected class (a stored graph without the
    derived class's required slots does not decode, so the replace would fail with a 500).
  - **A delete rule's `old` is typed `M`**: sound, a removal selects the rules by the stored root's
    own types.
  - Tests: TC-10 (mypy): a rule `(old: BaseModel | None, new: Book, …)` registers with no `cast`;
    one typed `new: Loan` registered for `Book` reports `[arg-type]`; one typed `old: Book | None`
    also reports `[arg-type]`, the documented price of a sound `old`; and the registered rule
    receives a `Book` as `new` at run time.
- **PD-12 `state_name` (DEC-6).** `collaboration/services/workflows.py`: `def
  state_name(workflow: Workflow, iri: str) -> str`: `prefix = f"{workflow.id}/"`; when `iri` starts
  with it and the rest is in `workflow.workflow_states`, return the rest; else `ValueError(f"{iri}
  is not a state of workflow {workflow.workflow_name}")`. Exported from `rdf_persistence`.
- **PD-13 The fake (DEC-7).** `testkit/fakes.py`: `class FakeAggregateReader` with
  `__init__(self, aggregates: Iterable[BaseModel] = (), *, roots: Iterable[type[BaseModel]],
  unreadable: Iterable[str] = ())`, keyed by each model's `id`; `roots` are the classes `find`
  accepts, as the real reader accepts only aggregate roots with a path.
  `calls: list[tuple[str, tuple[object, ...], dict[str, object]]]` records `(method, args, kwargs)`
  in order, refused calls included. The contract, the same for both readers (PD-14 pins each row):
  - `classes_of(iri)`: `frozenset({type(m).__name__})` for a readable seeded `m` (a stored root
    has one `rdf:type`, its own class), else empty.
  - `aggregate(iri)`: a deep copy of a readable seeded model, else None.
  - `find(cls, **equals)`: the sorted ids of the readable seeded models whose class is exactly
    `cls` (the listing selects by the root's one type, so a model of a derived class is not
    found), where each slot equals its value; on a multivalued slot a single value means "one of
    the values is it" and a list means "all its items are among them"; an IRI-ranged slot compares
    the IRI string. Refusals: `cls` not among `roots` → `ValueError`; a `None` value →
    `TypeError` (PD-10); a name that is not a field of `cls` → `BadQuery`; a value that does not
    validate against the field's item type (`pydantic.TypeAdapter`) → `BadQuery`; a `Contains`
    or a dotted keyword → `NotImplementedError` naming it (the fake's documented limit; the
    contract cases use neither).
  Exported from `rdf_persistence.testkit`.
- **PD-14 The conformance kit (DEC-7).** `testkit/reader_conformance.py`, as `store_conformance.py`,
  generic (no toy name): `@dataclass(frozen=True) class Seeded` with fields
  - `root: type[BaseModel]`, a concrete root class; `readable: str` and `unreadable: str`, two
    seeded IRIs of class `root`; `absent: str`, an IRI seeded nowhere;
  - `other: type[BaseModel]` and `other_iri: str`, a seeded aggregate of another root class;
  - `abstract_parent: type[BaseModel]`, an abstract root class with no path from which `other`
    derives (a model of a derived class is found only by its own class);
  - `not_root: type[BaseModel]`, a class that is no aggregate root;
  - `slot: str` and `value: object`, a single-valued slot of `root` that both `readable` and
    `unreadable` hold `value` on; `wrong_value: object`, a value not of `slot`'s type;
  - `iri_slot: str` and `iri_value: str`, an IRI-ranged slot `readable` holds;
  - `multi_slot: str` and `multi_values: tuple[object, ...]`, a multivalued slot `readable` holds
    at least two values on.

  Cases, each `async def <case>(reader: AggregateReader, seeded: Seeded) -> None`: classes of
  readable, unreadable, absent, `other_iri`; aggregate of the same four; find by `slot` (readable
  only); find on `root` omits `other_iri`; find on `abstract_parent` and on `not_root` raise
  `ValueError`; `wrong_value` raises `BadQuery`; `None` raises `TypeError`; find by `iri_slot`;
  find by one and by all of `multi_values`. `CASES` lists them.
  `tests/unit/testkit/test_reader_conformance.py` builds one `Seeded` from the toy library (two
  books, a magazine as `other`, `LendingItem` as `abstract_parent`, a chapter as `not_root`) and
  parametrises `CASES` × {fake, real}; the real reader is built over a `FakeStore` session with
  listings and a `may_read` that refuses `unreadable`.
- **PD-15 Docs.** The aggregate-validators how-to: the consumer problem (module, registration,
  raising), `find`, `aggregate_rules`, the fake. `architecture/api.adoc`: the refusal row of the
  error matrix and the document's `anyOf`. The testkit page: the fake and the kit. The generation
  page: importing technical modules, `Problem` as the supported extension point (DEC-2).
  `CHANGELOG.md` `[Unreleased]`: added names; *BREAKING* (DEC-8): "`AggregateReader` gains `find`;
  a hand-written reader implements it, or use `rdf_persistence.testkit.FakeAggregateReader`".

## Algorithm / approach

**Worked example 1: a rule names a key's holder** (the toy, stage 2; stage 1 uses `fixed_refusal`,
PD-9a). The toy service registers `refusal_problems=[HeldKeyProblem]` and
`aggregate_validators=dict([aggregate_rules(Book, held_isbn)])`, where

```python
async def held_isbn(old: BaseModel | None, new: Book, principal, reader) -> None:
    if new.isbn is None:
        return  # find refuses None (PD-10): absence is not a key
    holders = [iri for iri in await reader.find(Book, isbn=new.isbn) if iri != new.id]
    if holders:
        raise RuleRefusal(HeldKeyProblem(type=T, title="Key held", status=409,
                                         detail=f"isbn {new.isbn} is held", holder=holders[0]))
```

A client creates book B2 with B1's isbn: the guard decodes B2 as `Book`, `held_isbn` gets `[B1]`
from `find`, raises; `run_aggregate_validators` lets it pass; nothing is collected; the handler
finds `HeldKeyProblem` registered, status 409, sends `{"type": T, "title": "Key held", "status":
409, "detail": "isbn … is held", "holder": B1}` as `application/problem+json`. The rule runs
before the commit, so the unique key's `KeyConflict` is never reached.

**Worked example 2: a key moves within one unit of work** (PD-10, PD-11). Stored: B1 with isbn
`v`. A unit of work replaces B1 with isbn `w`, then adds B2 with isbn `v`.

1. B1's replace: the guard selects `Book`'s rules; `old` is B1 as stored (`v`), typed
   `BaseModel | None`, `new` is B1 at `w`. `held_isbn` calls `find(Book, isbn="w")`: the store has
   no `w` → `[]`; the replace is collected, so `context.collected` now holds B1.
2. B2's add: `held_isbn` calls `find(Book, isbn="v")`. `Session.find` returns `[B1]` (the store still
   says `v`), but B1 is in `context.collected`, so the reader returns `[]`; B2 is collected.
3. The commit sends both; the unique key `isbn_key` holds (B1 `w`, B2 `v`): committed.

Had step 1 replaced B1's title only (B1 stays at `v`), step 2 would still return `[]` and the rule
would pass B2; the commit then fails with `KeyConflict` (409 `key-conflict`), naming no holder: the
miss fails safe (PD-10).

## Error matrix

| Input / state | Behaviour |
|---|---|
| Consumer imports `rdf_persistence/model/technical/<theme>/<m>` | resolves to the package file (PD-1) |
| Consumer imports a path that names no file | the import error as today, naming the path |
| A consumer domain or value module imports a technical module | `MODULE_KIND` problem, as today (PD-3) |
| A consumer class extends a toolkit technical class not in `__all__` | `SchemaGenerationError` naming both; nothing written (PD-2) |
| `refusal_problems` holds a class not extending `Problem` | `TypeError` naming it at start-up (PD-7) |
| A registered class's name is already a component | `ValueError` naming it at start-up (PD-8) |
| Rule raises `RuleRefusal` with a registered class, status 409/422 | that problem, extra fields included (PD-6) |
| … with an unregistered class, a subclass of a registered one, or a non-`Problem` object | 500 internal-error, logged with the class name (PD-6) |
| … with status other than 409/422 | 500 internal-error, logged with the status (PD-6) |
| Rule raises `RuleRefusal` in a unit of work commit (in process) | the commit raises it; nothing written |
| A delete rule raises `RuleRefusal` | `RuntimeError` naming the rule (500), as today for any non-listed error |
| `find` on a session opened without listings | `RuntimeError` from `Session.find`, wrapped as a rule bug (500); the kit's sessions have listings (TC-9) |
| `find` with a filter the listing refuses | `BadQuery` inside the rule → rule bug, 500 |
| `find` while the transaction collected an add with that value | not found (store as committed); the unique key still refuses the commit |
| `find` for a root the transaction replaced earlier (its value moved away) | not returned, so no false refusal (PD-10, worked example 2) |
| `find` for a root the transaction replaced earlier but kept at the value | not returned; the commit's unique key refuses (`KeyConflict`), fails safe (PD-10) |
| `find` with a `None` value | `TypeError` naming the slot, before any query; a rule bug, 500 (PD-10) |
| `find` on an abstract parent with no path, or a class that is no root | `ValueError` (both readers; PD-13, PD-14) |
| `find` with a value not of the slot's type, or an unknown slot | `BadQuery` (both readers) |
| `find` on a multivalued slot | one value: one of the values is it; a list: all its items are among them |
| A consumer slot whose alias or name is a field of the toolkit class it extends | `SchemaGenerationError` naming both (PD-2a) |
| `find` for an aggregate removed in this transaction | not returned (PD-10) |
| `find` for an unreadable or another tenant's aggregate | not returned (PD-10) |
| `aggregate_rules(cls, rule)` where `rule` is typed for another class | mypy error (PD-11) |
| `state_name` with another workflow's IRI, or a name not among its states | `ValueError` naming IRI and workflow (PD-12) |
| The fake asked a `Contains` or dotted `find` | `NotImplementedError` naming the keyword (PD-13) |
| No `refusal_problems` | handlers and the document as before (TC-6) |

## Anti-patterns

- Building the answer from the error's text for a refusal (the generic branch): the extra fields are
  lost, which is #397.
- Making `RuleRefusal` a `Conflict`: code that retries on `Conflict` would retry a 422.
- Importing `Problem` in `core.domain`: the layer rule; the check is at the edge.
- Changing an existing importmap key, or mapping `model/migrations/`.
- A hand-written `.ts` file to prove assignability: the file guard refuses `*.ts` outside
  `generated/` (PD-4 proves it in Python).
- A `find` that relies on versions or reads the read cache.

## Test plan

| TC | Scenario | Proof | Tier / lane |
|---|---|---|---|
| TC-1 | rp-generation "the problem module" | `metamodel_importmap()` has the technical key; every key of the `model/*.yaml` set equals today's value | unit, `tests/unit/schema/` |
| TC-1b | PD-1a | the toy technical target's output: each `.ts` and `.py` module file once, each interface and class once; the closure's duplicate module names no more than `rp_api_entrypoints`'s own | generator unit |
| TC-3b | PD-2a | a `toy_copy` whose `HeldKeyProblem` gains a slot `kind` with `alias: type` fails naming `HeldKeyProblem.kind` and `Problem.type`; narrowing `status` through `slot_usage` passes | generator unit |
| TC-2 | rp-generation "a consumer problem" (#415 acceptance) | the toy's `HeldKeyProblem` Pydantic class: `issubclass(HeldKeyProblem, rdf_persistence.Problem)`; the generated module imports `Problem` from `rdf_persistence` (`assert_public_imports`) | generator unit, `make test-generator` |
| TC-3 | rp-generation "a class the package does not export" | a `toy_copy` whose `library_problems` declares a class `is_a: InUseProblem` (not in `rdf_persistence.__all__`) fails naming both classes; no file written | generator unit |
| TC-4 | PD-4 | `TsModule` of `library_problems`: every `Problem` field present with the same type and required-ness | generator unit |
| TC-5 | rp-service-api "a refusal with a consumer problem type", "a 422 refusal" (#397 acceptance 1) | toy service with `fixed_refusal` (PD-9a): isbn `held` → 409, isbn `malformed` → 422, each with `type`, `detail`, `holder`; store unchanged | unit, `tests/unit/api/test_rule_refusal.py` |
| TC-6 | "an unregistered problem class", "a status outside 409 and 422", "a class that is not a problem", no `refusal_problems` | 500 problem without the rule's fields; `caplog`: exactly one `log.error` record naming the class or status, with no `exc_info`, and none for a registered refusal (PD-6); start-up `TypeError`; the document's golden unchanged with none | unit |
| TC-7 | "the document lists the problem" | `HeldKeyProblem` a component; `anyOf` on create/replace 409 and 422 and on `default`; `make typecheck-openapi-ts` compiles the toy document; the contract test (`test_the_service_keeps_to_its_document`) passes with the toy's refusal | unit, CI "types" |
| TC-8 | in-process refusal | a unit of work commit raises `RuleRefusal`, nothing written | unit, `tests/unit/collaboration/test_aggregate_validators.py` |
| TC-9 | rp-service-api find scenarios (#397 acceptance 2) | holder found; another tenant's not; unreadable not; removed-in-transaction not; replaced-earlier not (worked example 2, both variants: committed, and `KeyConflict`); `None` → `TypeError`; through the generic API's session (listings present) | unit + feature |
| TC-10 | typed registration | a unit test runs `mypy.api.run` on three snippets (PD-11): `(old: BaseModel \| None, new: Book, …)` passes with no `cast`; `new: Loan` for `Book` and `old: Book \| None` each report `[arg-type]`; and the registered rule receives a `Book` as `new` at run time | unit |
| TC-11 | state_name | inverse; another workflow's IRI; an unknown name | unit |
| TC-12 | rp-testkit "a rule under unit test" (#386 acceptance) | a rule over a fake seeded with two books, one unreadable: sees one; `calls` lists the rule's calls | unit, `tests/unit/testkit/` |
| TC-13 | rp-testkit "the fake and the real reader agree" | `CASES` (PD-14: readability, absence, another root class, abstract parent, non-root, wrong type, `None`, IRI slot, multivalued one and all) × {fake, real} all pass | unit |
| TC-14 | gate | `make check-generated`, `make check-types`, `make check-architecture` clean | `make check-all` |

The feature file `features/consumer_write_rules.feature` holds TC-5, TC-9 and TC-12 in the
business language; it is appended to `tests/feature/` with its steps in stage 2.

## Risks

- **RISK-1 the importmap's CRITICAL blast radius** (81 dependants: generation, manifests, the kit,
  OpenAPI). Likelihood low (keys added only), impact high. Mitigation: TC-1 pins the old keys;
  stage 1's `make generate` must change nothing in the toolkit's own trees beyond the toy's new
  files and the manifests' input hashes (any other diff is reported, not fixed); the lead runs
  `make reindex` and the GitNexus impact at stage start and before the last commit.
- **RISK-2 a consumer extends a technical class that later changes.** The toolkit reorganises its
  technical modules (thematic moves happened twice). Mitigation: DEC-2 promises `Problem` only, and
  PD-2's export check makes any other extension fail at generation, not at run time.
- **RISK-3 an answer outside the published contract.** A rule raises a problem the document does
  not list. Mitigation: only registered classes are sent (PD-6), the document lists them (PD-8),
  and TC-7 runs the contract test with the toy's refusal.
- **RISK-4 `find` leaks an aggregate.** Another tenant's, or one the writer may not read.
  Mitigation: `_visible` on every IRI, TC-9 tests both scopes, TC-13 holds the fake to it.
- **RISK-5 a rule leaks through its problem.** A rule copies an unreadable holder's IRI into an
  extra field. Mitigation: `find` never returns one (RISK-4); the how-to says extra fields are the
  rule author's responsibility, like `detail`.
- **RISK-6 the consumer's reader stubs break** (DEC-8). Likelihood high for MWB2, impact low (mypy
  names the stub). Mitigation: CHANGELOG *BREAKING* with the fake as migration; the PR names the
  consumer's issue context (D-12).
- **RISK-7 the generator lane slows** (consumer-friction D-9). Mitigation: no new toy target (PD-9);
  the lead compares the toy generation time with develop's at stage 1.

## Delivery decisions

The lead's, per R-0007; the developer may overrule any of them.

- **D-1 Branch.** Stage 1 is built on `change/consumer-write-rules` (the worktree the shaping session
  made), not `change/consumer-write-rules-1` as `tasks.md` names it; stage 2 opens its own branch.
- **D-2 Stage review.** One pass of L2 and L3 together (P-0005, the developer's brief of
  2026-11-27), not the two grouped runs `tasks.md` 1.6 names; the full review (L1, L2, L3 apart,
  L4+L5 as one) runs once at the end of stage 2.
- **D-3 Tester.** The PLAN has no `## Invariants` section; the lead asks for the adversarial tester
  (`develop/agents.adoc#challenge`) right after the riskiest task. **Riskiest: 1.3**, because it adds
  the boundary that decides which rule refusals reach the client (only registered classes at
  409/422, RISK-3, RISK-5) and moves a branch ahead of the internal-error log.
- **D-4 Merge order.** Built now, rebased on `develop` after `narrowed-slot-override` (#417) and
  `typescript-toolkit-modules` (#402) merge (P-0002); generated-file conflicts by P-0003.
- **D-5 Task 1.4 stopped (the developer, 2026-11-27).** The stage-start impact on a fresh index
  rated `route_options` (`openapi.py`) CRITICAL: 14 direct callers, one per route kind, a risk the
  PLAN did not name. Asked whether to proceed, narrow, or stop, the developer chose to stop 1.4: the
  document half of PD-8 (`refusals` on `AggregateOpenApi` and `route_options`, the components and
  the `default` loop in `install_openapi`, TC-7) goes back to a shaping session. Tasks 1.1 to 1.3 go
  ahead. Consequences the lead draws, for the developer to overrule:
  - 1.3 keeps PD-7's registration (`refusal_problems` on `install_service` and `ServiceKit`, the
    `TypeError` check) and passes it to `install_problem_handlers` only, not to `install_openapi`.
  - RISK-3 stays open in stage 1: a registered refusal is answered with its extra fields, while
    `Problem`'s closed component in the published document does not list them. The PR and the
    hand-over note say so; the contract test is not run with a refusal in stage 1.
  - 1.5 drops the document's `anyOf` from the `api.adoc` row and the how-to.
- **D-6 A living scenario contradicted DEC-1 (the developer, 2026-11-27).** rp-generation "the
  schemas a consumer imports" said no technical schema can be imported; 1.1's gate failed on its
  feature scenario. The PLAN's delta only added requirements. That wording had no design reason:
  `technical-models` left the importmap globbing `model/*.yaml` (its PD-1, "unchanged") and its
  review pinned the side effect with a test (its D-13). The developer re-signed the scenario as
  MODIFIED in this change's delta: technical modules resolve by their path under `model/`,
  `model/migrations/` does not. The layer rule (a domain or value module never imports a technical
  one, PD-3) is unchanged. The feature scenario in `tests/feature/technical_models.feature` is
  reworded in task 1.1.
- **D-7 A load flake, not this change.** `tests/unit/tooling/test_lanes.py::test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make`
  failed once in 1.1's gate (`-n 16` against `-n 17`): it reads the free memory twice on a machine
  shared with sibling sessions. It passes alone; left as is, named in the PR.

## Lanes for moved or rewritten tests

None moved or rewritten. New tests: generator unit (TC-2 to TC-4) in `make test-generator`; library
unit (TC-1, TC-5 to TC-13) in the unit lanes; feature scenarios in the feature lane; TC-7's
TypeScript compile in the CI "types" job.
