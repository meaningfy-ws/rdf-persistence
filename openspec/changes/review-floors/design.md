<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: the EPIC `review-floors` (`proposal.md`, DEC-1 to DEC-6).

# Design: review-floors

## Context

Seven issues hold the review findings that seven delivered changes left under the floor
(`inputs/seed.md`). The codebase analysis of 2026-11-22 (`inputs/triage.md`) checked every item
against `develop` 25e23156 and gave it one class; the re-triage of 2026-11-25 on `develop`
12d84873 found none of them fixed by the changes merged since (only line numbers moved; the
lines cited here are the new ones). The owner then folded in three test-debt issues: #272 (all
six items, 272-a to 272-f), #273 and #275 (round 2 of `inputs/qa.md`). This PLAN delivers the
**P** items, about fifty, and those nine, in three stages, and nothing else. The **B**, **Q** and
**R** items are the EPIC's no-gos and the OPEN questions of `inputs/qa.md`, answered by the owner
on 2026-11-25 as recommended; the **D** items need only a line in the issue comment (task 4.1).

The **P** items are of four kinds, and each kind has its own proof (DEC-3):

| Kind | Proof that behaviour is kept |
|---|---|
| A characterisation test (pins today's behaviour) | it passes on today's code, and fails under the planted mutation the task names (reverted, recorded in the hand-off) |
| A refactor of library or generator code | the tests that cover the code (named per task) stay green with no edit to their assertions; `make check-generated` shows no diff where the task says none |
| A test-only change (helpers, assertions, moves) | the same test ids collect and pass (minus the three dropped: PD-9's duplicate and PD-11's two tests); the scenario-map rows follow (`make refresh-map`) |
| A docs or docstring change | `make check-docs`; a cold read of the changed page by the stage pass |

Spec deltas: none of the items changes behaviour, so the PLAN needs no requirement change. It
carries two deltas of wording and of today's behaviour only: `rp-generation`'s scenario "a domain
module in a technical target" says "a target", as its feature test runs it (#189 S1), and
`rp-testkit` gains the D-7 scenario (#215 W2). Both requirements' SHALL text is unchanged.

## Goals / Non-Goals

**Goals:**

- Every **P** item of `inputs/triage.md` done, each with its proof.
- Each of the seven issues closed or narrowed to its out-of-scope items (DEC-4).

**Non-Goals:**

- Every **B**, **Q**, **R** item (the EPIC's no-gos).
- Measuring or improving performance: the two items that cut repeated work (PD-6, 192-b) are
  structure tidy-ups whose proof is the unchanged outcome, not a speed-up.

## Decisions

The EPIC's DEC-1 to DEC-6 hold; these are the PLAN's.

- **PD-1 (252-e):** `more_count` moves to `rp_collaboration_services.yaml`, beside `hidden_count`,
  not the other way: the api module already imports the collaboration one (line 24), and the
  slot's meaning (referrers not named) belongs to the naming code in `collaboration`. Its
  `slot_uri`, range, description and the class that uses it (`InUseProblem`) do not change.
  Probed on 2026-11-22 (the move made, `make generate` run, then reverted): `make generate`
  changes exactly these files besides the two YAMLs:
  `rdf_persistence/collaboration/services/generated/context.jsonld` (+3 lines: the term
  `"more_count": {"@id": "moreCount"}`), and three `rp-manifest.json` files (the input hashes:
  `api/entrypoints/generated/`, `collaboration/services/generated/`,
  `tests/fixtures/library/domain/generated/`). The api module's context keeps its `moreCount`
  term; no Python, shapes, OpenAPI or TypeScript file changes; `test_shape_snapshot.py`,
  `test_problems.py` and `test_public_surface.py` pass (136 tests). The added context term is
  **additive, with the same IRI**, and nothing loads the collaboration services context for
  `InUseProblem`: the PLAN classes it as preserving under DEC-1 and names it in OPEN-9(a).
  Accept: `git diff --stat` after task 1.8 lists those six files plus 252-h3's (below), nothing
  else.
- **PD-2 (252-f):** in `collaboration-layers`, `referenced_removals` joins the layer of
  `transitions | write_guards` and `referrer_naming` the layer of
  `discussion | reference_collections | workflows`. Reason: `referenced_removals` imports
  `referrer_naming` (so they cannot be siblings), `collaboration` imports `referrer_naming`, and
  `referrer_naming` imports only generated rows. If `make check-architecture` refuses the
  placement, the builder reports the refusing import to the lead before moving either module
  (P-0019): the contract follows the code, never the reverse in this EPIC.
- **PD-3 (252-g):** `ReferencedRemovals.in_use` computes `referrers & allowed` once and keeps
  `shown` as a `frozenset` for membership and a sorted tuple for order; `named()` takes
  `Iterable[ReferrerRow]` (its caller drops `list(...)`); `_problem` takes `schema:
  type[BaseModel]` and reads `__name__` inside. The `InUse` message text is not touched (DEC-1).
- **PD-4 (252-i):** `author_iri(n)`, `AUTHOR` and `WRITTEN_BY` join `tests/toy.py` beside
  `book_iri`. The two session test files' plain helpers (`StubRefusal`, `opened`, `author`,
  `stored`) move to a helper module `tests/unit/persistence/referrer_helpers.py` (as
  `loading_helpers.py` beside it): the two `StubRefusal` classes become one, the recording one,
  and `author(iri, *more)` is the superset of the two `author` forms. The `store` fixture, the
  same in both, moves to a new `tests/unit/persistence/conftest.py`; each `session` fixture stays
  in its file while the two differ (the first takes `refusal`). The
  integration test `tests/integration/store/test_referenced_removal.py` uses `author_iri` and the
  two IRIs from `tests/toy.py`.
- **PD-5 (235-m):** the write guard's collection check gets one private frozen dataclass,
  `_CollectionCheck(session: Session, iri: str, name: str, collection: ReferenceCollection,
  context: GuardContext, adding: bool)`: what is known when the check starts. `stored` and
  `heads` are computed during the check (`heads` only after `_check_members`), so they stay
  arguments. The caller in `prepare` (`write_guards.py:117`) builds it. New signatures:
  - `_check_collection(self, check: _CollectionCheck) -> None` (was 6 arguments; `# noqa:
    PLR0913` at line 224 goes)
  - `_check_held_member_class(self, check: _CollectionCheck) -> None`
  (all five stay `async def`, as today)
  - `_check_members(self, check: _CollectionCheck, stored: set[str]) -> Sequence[AggregateHead]`
  - `_unlike_nested(self, check: _CollectionCheck, heads: Sequence[AggregateHead], stored:
    set[str]) -> list[str]` (`# noqa` at line 430 goes)
  - `_check_no_cycle(self, check: _CollectionCheck, heads: Sequence[AggregateHead], stored:
    set[str]) -> None` (`# noqa` at line 336 goes)
  The `# noqa: PLR0913` of `prepare` (line 91) and of `__init__` (line 73) stay: it is the `WriteGuard` port's signature.
  `_exact_heads` becomes a module function `_exact_heads(own, heads)`, and `_rely_on_walked`
  calls it, so no method names its class (S-3). `_CollectionCheck` is a dataclass in `services`,
  not a model: it lives within one call and crosses no boundary (PD-24 applies to data that
  crosses one).
- **PD-6 (192-b):** `stored_file_class(view)` is computed once per caller: `is_stored_file` and
  `is_service_written` take a keyword-only `stored_file: str | None | _Unset = _UNSET`, where
  `_UNSET` is a private sentinel of `schema_structure.py` meaning "compute it" (so every other
  caller is unchanged); `None` keeps its own meaning, "this schema has no stored-file class"
  (`stored_file_class` returns it, `schema_structure.py:233-243`), and a caller that passes
  `None` is trusted. The two callers that repeat it:
  - the library: `build_router(kit)` (`router.py:486`) computes `stored_file_class(kit.view)`
    once before its loop over `kit.documents.aggregates` and passes it to
    `add_aggregate_routes(router, kit, gate, rp_path, cls, *, stored_file: str | None)` (one
    caller, `router.py:495`; not in `public-surface.json`), which passes it to
    `is_service_written(kit.view, cls, stored_file=stored_file)` at line 455;
  - the generator: `application_problems(view, classes, roots)` (`checks/application.py:69`)
    computes it once beside `others` and `owned`, and passes it through `_row_of` and
    `_application_row` (new keyword `stored_file`) to `is_stored_file(view, cls,
    stored_file=stored_file)` at line 44.
  No cache keyed on a `SchemaView` (a view can be mutated; a stale cache is a wrong answer).
- **PD-7 (192-e):** one accessor, `toolkit_roots()` in the module that defines `TOOLKIT_ROOTS`,
  is the only reader; the ten modules besides `config.py` that name it (the nine `ROOTS_USERS`
  lists and `rdf_persistence_generation/testkit/conformance.py`, the one it misses) call it. The
  tests patch the one constant (`# X1`) instead of ten, and `ROOTS_USERS` goes. A new test asserts no other module reads `TOOLKIT_ROOTS`
  (ast-grep or `grep` over the package), so the list cannot drift again.
- **PD-8 (192-f, g, h):** the one predicate is a new library function in `schema_structure.py`,
  `is_generated_with(schema: SchemaDefinition, root_package: str | None) -> bool` (`root_package
  is None or python_package_of(schema) in (None, root_package)`). `generated_schemas(view,
  folder)` keeps its signature and filters `own_schemas` with
  `is_generated_with(schema, python_package_of(view.schema))`; the generator's
  `_generated_here(self, schema)` becomes `return is_generated_with(schema, self.root_package)`
  (the generator may import the library; never the reverse). `root_package` itself is still read
  at `pydantic_split.py:589` with `annotation_text`; it becomes `python_package_of(view.schema)`
  so both sides read the annotation one way (error-matrix row if they disagree). One home
  per name: `METAMODEL_ROOT` derives from `vocabulary.METAMODEL.name`, the generator's `PYPROJECT`
  from `testkit/freshness.DEFAULT_PROJECT` (or both from one new constant if the import direction
  forbids it). `pydantic_split.py:189, 219` keep reading through `METAMODEL_DIR` (two `# X1` tests
point it at a broken copy: `test_ext_pydantic_split.py:147` and `:625`), as `METAMODEL_DIR /
METAMODEL_ROOT`, and `METAMODEL_DIR` (`:97`) becomes `vocabulary.METAMODEL.parent`, so the
literal `"rp.yaml"` and the second derivation of the folder go while the seam stays. Comparisons stay by
  name (the resolved-path comparison is **B**, out). `enum_meanings` and `TENANT_STATE_IRIS` move
  to a test helper (`tests/schema_helpers.py`, or the existing helper module of
  `tests/unit/schema/` if there is one), their three test users follow, and the `vocabulary`
  docstring says what the module holds today. Neither is in `public-surface.json`.
- **PD-9 (192-i):** the duplicate dropped is `test_theme_layout.py::test_the_pairs_of_the_guards_include_each_moved_module`;
  its twin `test_no_old_module_paths.py::test_the_old_path_of_every_moved_generated_module_is_scanned_for`
  stays (it sits with the guard it checks). Its scenario-map row goes by `make refresh-map`.
- **PD-10 (192-j2):** one helper module for the theme map, `tests/theme_map.py` (shared by the
  library's and the generator's pyramids, as `tests/scene.py` is), built from `read_targets` on
  the repository's `pyproject.toml`, never from a hand list or raw `tomllib`. The six places
  import it. A generator test importing a `tests/` helper is allowed (`tests/toy.py` precedent);
  the cross-test guard allows helper modules, not `test_*` modules.
- **PD-11 (192-m):** `test_no_module_of_schema_imports_the_files_or_tenancy_module` goes, as a
  repeat of the `themes-ordered` contract, together with what serves only it:
  `test_the_schema_sources_are_found` (the check that its walk found files), the helpers
  `imported_modules` and `schema_sources`, and the constants `SCHEMA_PACKAGE` and `UPPER_MODULES`.
  The behaviour tests of that file (`test_the_stored_file_class_is_the_class_whose_class_uri_is_rp_stored_file`,
  `test_the_tenant_state_iris_are_the_meanings_of_the_tenancy_enum`) stay. `make
  check-architecture` runs in CI (job "Architecture"), so the guarantee keeps its lane.
- **PD-12 (189-s):** the six config tests use `app.domain.generated` (or `p.domain.generated`)
  where they had `app`, `a` or `p`; their assertions do not change.
- **PD-13 (125-i1):** the wake test builds the toy service with `relay_interval_seconds` far above
  the test's wait (60 s against a 2 s wait; the setting allows up to 31536000), through the real
  seam `ToyService(toolkit=ToolkitSettings(events=...))`, so only `relay.wake()` can deliver in
  time. No patch of the relay (testing.adoc rule 3). The planted
  mutation is the deleted `self.relay.wake()` call in `kit.py:_publish`. An exception to
  `testing.adoc` rule 11 (no timing-based asserts), recorded here and in the test's docstring:
  the property under test is itself a timing ("before the interval"), and the relay's interval
  has no injectable clock; the wait is `testkit.wait_until_async` with a 2 s deadline, no sleep,
  and the margin is 30×. Task 3.1 is the second exception, for the same reason: "a start-up
  longer than `timeout` does not raise" needs a start-up that takes real time, so its lifespan
  waits 0.2 s against `timeout=0.05` (4×, and the test fails, not hangs, if it regresses).
- **PD-14 (125-i2):** the `claim_idle` redelivery test is the toolkit's own Redis test in
  `tests/integration/adapters/test_redis_events.py` (lane: `make test-containers`, local, the
  lead's gate; no CI lane runs containers): a receiver raises once, the bus is not restarted, and
  the message comes again after `claim_idle_seconds` (0.5 s). Not a conformance-kit case (no-go).
- **PD-15 (189-u):** the docs state what the code does: a consumer's technical module (its route
  shapes) goes in its own technical target, because a target of mixed kinds is refused
  (`boundary.py:283`); a request body used by the domain stays in the domain target unannotated;
  a consumer's own routes take their OpenAPI schemas from FastAPI's Pydantic models, not from
  `openapi-components.json` (which holds the toolkit's served schemas). `model.adoc:179-183`
  ("the root schema imports it") is corrected. The builder checks each sentence against a test or
  the code line it describes and lists them in the hand-off.

- **PD-16 (252-h1, h2, h3), the new texts:**
  - h3, the `in_use` slug's description (`rp_api_entrypoints.yaml:210`): "The delete would leave
    other aggregates pointing at a class that refuses it; the answer names the referrers the
    caller may read, up to a limit, and counts the rest." Expected regenerated files (the
    builder confirms with `git diff --stat`): `api/entrypoints/generated/rp_api_entrypoints.py`,
    `docs/modules/ROOT/partials/reference/problem-types.adoc`,
    `tests/fixtures/library/golden/served_typescript/rp_service.ts`,
    `tests/fixtures/library/web/src/domain/generated/rp_service.ts`, the api target's
    `rp-manifest.json`, and `tests/fixtures/library/golden/openapi/openapi.json` if it carries
    the description.
  - h1, `in_use_problem`'s first paragraph (`problems.py:174-190`; the paragraph on `locate`
    that #360 added stays as it is, after this one): "The problem of a refused
    removal (PD-11): no ``detail``, the members say who refers. ``error.referrers`` come from the
    guard's diagnosis read or from the same-commit check. A filtered error (a ``readable``
    callable judged them) names the readable referrers, up to the cap, and counts the readable
    rest in ``more_count`` and the unreadable in ``hidden_count``; only structured members carry
    them, as the text of a 409 is never sent. An unfiltered error names nobody: every referrer
    aggregate is counted in ``hidden_count`` (D-10, fail closed)."
  - h2, `Aggregates.remove` (`aggregates.py:151-162`, the sentence on `readable`): "``readable`` says which referrers the
    caller may read; it shapes the ``InUse`` of a refusal. ``None`` gives an unfiltered
    ``InUse`` that names every referrer: fit for an in-process caller, never to be shown by name
    to a caller who may not read them (see ``InUse``)."

The owner folded in #272, #273 and #275 on 2026-11-25 (`inputs/qa.md`, round 2). Their rows are
in `inputs/triage.md` (*Re-triage of 2026-11-25*); their decisions:

- **PD-17 (272-d, 272-e, 272-f), one home for the toy's test vocabulary:** `tests/toy.py`
  declares, with these values and types (the majority form today):
  `BIBO = "http://purl.org/ontology/bibo/"` (a `str`),
  `TITLE = URIRef("http://purl.org/dc/terms/title")`,
  `BOOK_CLASS = URIRef("http://purl.org/ontology/bibo/Book")` and `FAST_POLL = 0.01`; and it
  replaces the module dict `BOOK_JSON` with `book_json() -> dict`, which builds a new dict (its
  nested lists new too) on every call. `TIMEOUT = 3.0` stays in `tests/events_follow.py`, already
  the shared home its two users import it from (`tests/feature/test_events.py`,
  `tests/unit/api/test_events_route.py`); `test_open_event_stream.py:15` imports it from there.
  Each file that declares one of these names **with the same value** imports it instead; where only
  the type differs it converts at the use: `str(BOOK_CLASS)` in `tests/unit/activity_helpers.py:30`
  and `test_collaboration_workflow.py:62`, `str(TITLE)` in `test_jsonld.py:25`,
  `Namespace(BIBO)` in `test_abstract_root_reference.py:24`. Four same-named constants mean
  something else and stay as they are: `test_activity_shape.py:30` (another IRI),
  `iri_policy_helpers.py:59` (a class name), `test_generated_source_safety.py:16` (a text, not an
  IRI) and `test_event_stream.py:22` (`TIMEOUT = 2.0`). The sixteen `poll_seconds=0.01` literals
  become `poll_seconds=FAST_POLL`. The uses of `BOOK_JSON` (33 besides the imports, in `test_documents.py`,
  `test_documents_strict.py`, `test_jsonld.py`) call `book_json()`: `{**BOOK_JSON, "x": ...}`
  becomes `book_json() | {"x": ...}`, `BOOK_JSON[...]` becomes `book_json()[...]`, and a
  `deepcopy(BOOK_JSON[...])` (`test_documents.py:190`) drops the `deepcopy`. No assertion changes.
- **PD-18 (272-b):** `tests/e2e/library_app.py` moves to `tests/library_app.py` (shared across
  tiers, as `tests/toy.py` is); its four users follow (`tests/unit/api/test_library_app.py:16`,
  `tests/e2e/world.py:19`, `tests/generator/e2e/test_generated_library_served.py:35`, and
  `tests/e2e/test_library.py:101`, whose `Path(__file__).with_name("library_app.py")` becomes the
  path of `tests/library_app.py`, so the public-imports check still reads the composition root).
  `tests/generator/integration/test_getting_started_example.py:46` imports the getting-started
  example's own `library_app`, not this one, and does not change. Three texts name the old path
  and follow: `docs/modules/ROOT/pages/user-manual/index.adoc:15`, the docstring of
  `tests/generator/e2e/test_generated_library_served.py:5`, and the rule-5 example of
  `tests/unit/tooling/test_changed.py:58`, which becomes `tests/e2e/world.py` (a path under
  `tests/e2e`, so the row stays a rule-5 case; `tests/library_app.py` would fall under rule 3).
- **PD-19 (272-c), a library change the owner accepted:** `rdf_persistence/api/services/shacl.py`
  gains `load_warm_shapes(path: Path) -> Graph`: it reads the bytes, hashes them (SHA-256), parses
  through the per-digest cache, warms the shapes up once per digest and returns a graph of the
  caller's own. `_shape_triples` and `_read_shapes` move from `documents.py` into `shacl.py`
  behind it; `Documents.__init__` (`documents.py:131-133`) becomes `self.shapes =
  load_warm_shapes(folder / SHAPES_FILE)`; `warm_up_once` becomes the private `_warm_up_once`,
  as no caller is left outside the module (it is not in `tests/fixtures/public-surface.json`, nor
  is `load_warm_shapes` added to it: the function is internal to `api.services`). The digest is
  then never the caller's to get right, which is the finding. Under DEC-1 this is the one item that
  adds a function; the owner folded it in knowing so (round 2), and no outcome changes: the same
  shapes are warmed once per process, keyed by the same digest.
- **PD-20 (272-a):** a tooling test, `tests/unit/tooling/test_patch_markers.py`, walks the AST of
  every `tests/unit/**/*.py` and `tests/generator/unit/**/*.py` file and fails, naming file and
  line, for each `monkeypatch.setattr` or `monkeypatch.delattr` call whose target is toolkit code
  and whose line does not end in a `# X1` to `# X5` marker (`testing.adoc` rule 3). The target is
  toolkit code when the first argument is a string starting `rdf_persistence` or a name (or an
  attribute chain on a name) bound in that file by an import from `rdf_persistence` or
  `rdf_persistence_generation`, `as` names included. Comments come from `tokenize` (the AST has
  none); a call that spans lines passes with the marker on its first or its last line (every
  marked multi-line call today carries it on the first: `test_freshness.py:202`,
  `test_hard_check.py:1247`). Patches of toolkit **instances** (a fixture's object, such as
  `toy.documents` at `test_roundtrip.py:89`) are beyond the guard: it reads names, not types, and
  says so in its docstring. The unmarked calls it finds on the stage-3 branch get the marker of their kind,
  each kind checked against rule 3's list; a call that fits none of the five kinds is reported to
  the lead (P-0019), not marked to pass. It runs last in stage 3, after PD-7 has replaced the ten
  `TOOLKIT_ROOTS` patches with one.
- **PD-21 (#273):** `develop/testing.adoc` gains one sentence after the `# X1`-`# X5` list (line
  54): a planted mutation in a generated file (to show a test bites) needs `-p
  no:rdf_persistence_generation.testkit.freshness` on the `uv run pytest` line, because the
  freshness plugin stops the run on a hand-edited generated file; the mutation is reverted before
  anything else runs.
- **PD-22 (#275):** one double, `TenancyDouble(open_session: Callable[[], Any])` (`Any`, as
  `RecordingSession` is not a `Session`), in
  `tests/unit/api/iri_policy_helpers.py`, whose `tenant_session(self, tenant, principal, *,
  may_read=None)` yields `open_session()`. The four hand-written doubles go: `StoreTenancy(store)`
  becomes `TenancyDouble(lambda: session_on(store))` (a fresh session per call, as today);
  `RecordingTenancy` and the two local `Tenancy` classes become `TenancyDouble(lambda: session)`
  (one session, as today; `RecordingTenancy`'s users that read `.session` keep a name for it). The
  drift guard is a test beside it:
  `tests/unit/api/test_tenancy_double.py::test_the_tenancy_double_takes_what_tenant_session_takes`
  asserts the parameters of `TenancyDouble.tenant_session` (names, kinds, defaults) equal those of
  `Tenancy.tenant_session`; the next keyword `Tenancy` gains fails it, naming the parameter. Not
  `create_autospec`: it would accept the keyword but yield a mock, not the session the tests need.

## Algorithm / approach

Each stage runs the same loop per task: write the characterisation test first where the task
names one, show it bites with the planted mutation, revert the mutation; then the change; then the
task gate (`make test-changed check-quality`; `make test-fast check-quality` after a change to a
port or `domain`). Operations are edits to code, tests and docs: retrying a task is safe (it is
re-run from the branch); there is no data and no replay.

Worked examples:

- **A characterisation test (252-j1):** a session that removes author `A` (a refusing class,
  still referenced by book `B`) and adds a book whose unique key another book holds. The fake
  store answers both claims "held". Today `_refused_by_store` checks the key claims first
  (`session.py:1830`), so the commit raises `KeyConflict`, not `InUse`. The test asserts the type.
  Planted mutation: swap the two `if` blocks; the test fails with `InUse`.
- **A characterisation test (252-j2):** a commit that removes author `A` and adds a book linking
  author `C` (not removed). No heads read (`READ_HEADS`) names `A` before the commit's request
  (`_refusing_among` is not called). Planted mutation: `named = sorted(removed)` in
  `_refuse_links_to_removed` (`session.py:1720`), so `_refusing_among([A])` sends a heads read.
  (Dropping `not named or` would not bite: `Session.heads([])` sends no query, `session.py:806`.)
  If another step of this commit already reads `A`'s head, the test compares the count of heads
  reads with the same commit minus the added book instead.
- **A refactor (235-m):** `_check_members(self, session, name, collection, stored, context)`
  becomes `_check_members(self, check: _CollectionCheck, stored: set[str])` (PD-5). The covering tests
  (`test_collaboration_nesting*.py`, four files) pass unedited; the three `xfail(strict=True)`
  stay xfail (a refactor that "fixes" one of them has changed behaviour and is a defect here).
- **A docs change (214-g):** `test.adoc#event-stream` gains a short list of outcomes, each taken
  from the docstring `testkit/streams.py:176-183` or from D-7's new test: a start-up or shutdown
  of the lifespan is outside `timeout`; an app that raises before the head re-raises; one that
  raises after the head ends the read with what came; no response is a `RuntimeError`; a bad
  argument is a `ValueError`. Plus #215 S4: a test that holds several streams at once enters the
  app's lifespan itself (as `tests/unit/api/conftest.py:21` does).

### Moved or rewritten tests and their CI lane

| Test(s) | Change | CI lane still running it | What it still proves |
|---|---|---|---|
| `tests/unit/persistence/test_session_referenced_removal.py`, `..._dependents.py` | helpers to `referrer_helpers.py`, `store` to `conftest.py`, IRIs from `tests/toy.py` | "Unit tests n/8" (`make test-unit-ci`) | the same-commit and store guards, unchanged |
| `tests/integration/store/test_referenced_removal.py` | IRIs from `tests/toy.py` | none (`make test-containers`, local) | as before |
| `test_theme_layout.py::test_the_pairs_of_the_guards_include_each_moved_module` | dropped (PD-9) | its twin in "Unit tests n/8" | each moved module's old path is scanned |
| `test_schema_imports_no_upper_module.py::test_no_module_of_schema_imports_the_files_or_tenancy_module` | dropped (PD-11) | the contract `themes-ordered` in "Architecture" | `schema` imports no upper theme |
| `test_hard_check.py`, `test_python_package_rule.py`, `test_no_old_module_paths.py`, `test_theme_domain_targets.py`, `test_theme_layout.py` | assertions split, messages added; theme map from `tests/theme_map.py` | "Generator tests" (the first two), "Unit tests n/8" (the others) | the same rules |
| `tests/generator/unit/conftest.py` users of `ROOTS_USERS` | one `# X1` patch (PD-7) | "Generator tests" | the same rules on the patched roots |
| `test_hard_check.py:1246-1248` (patches `{PACKAGE_CHECK}.TOOLKIT_ROOTS` and `steps.TOOLKIT_ROOTS`) | one `# X1` patch of `config.TOOLKIT_ROOTS` (PD-7) | "Generator tests" | the toolkit-project checks on a copied model folder |
| `test_ext_pydantic_split.py:657` (fixture `beside_as_toolkit`, patches `pydantic_split.TOOLKIT_ROOTS`) | one `# X1` patch of `config.TOOLKIT_ROOTS` (PD-7) | "Generator tests" | a folder treated as the toolkit's own |
| `test_schema_imports_no_upper_module.py::test_the_schema_sources_are_found` | dropped with its subject (PD-11) | the contract `themes-ordered` in "Architecture" | — (it only checked the dropped test's walk) |
| `test_freshness.py`, `test_generate_config.py`, `test_generation_inputs.py` (six tests) | layered package names (PD-12) | "Generator tests" | the same parsing outcomes |
| `tests/feature/test_technical_models.py` (`_fails_naming_package_and_kind`) | one `Then` per assertion (189-r) | "Feature tests (BDD)" | exit code, package and kind, each in its own step |
| `test_vocabulary.py`, `test_access_loading.py`, `test_schema_imports_no_upper_module.py` users of `enum_meanings` | import from the test helper (PD-8) | "Unit tests n/8" | the enum meanings the schema declares |
| `test_open_event_stream.py:102`, `test_streams.py:154, 165` | `re.escape` (215-S5) | "Unit tests n/8" | the timeout names the URL |
| the ~30 files declaring `BIBO`, `TITLE`, `BOOK_CLASS`, `TIMEOUT`; the 37 users of `BOOK_JSON`; the six files with `poll_seconds=0.01` (PD-17) | import from `tests/toy.py` | their lanes unchanged: "Unit tests n/8", "Feature tests (BDD)", "Generator tests"; `tests/integration/**` and `tests/perf/**` none (local) | the same assertions on the same values |
| `tests/e2e/library_app.py` and its four users (PD-18) | moved to `tests/library_app.py` | "Unit tests n/8" (`test_library_app.py`); the e2e files none (local `make test-e2e`) | the composition root uses public names only |
| `tests/unit/api/iri_policy_helpers.py`, `test_iri_policy_minting.py`, `test_replace_internal_values.py` (PD-22) | one `TenancyDouble` | "Unit tests n/8" | the same minting and replace outcomes |
| `tests/unit/api/test_shacl.py` (PD-19) | unchanged; one new test of `load_warm_shapes` | "Unit tests n/8" | the warm-up and the lock-free validation |

A test the PLAN marks `slow` runs only in `make test-unit` (local) and "Generator tests"; no new
test here is slow except where the task says so.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| "Fix" an `xfail(strict=True)` while refactoring | leave it xfail; report it to the lead if it starts passing | its pass means behaviour changed (DEC-1) |
| Reword an error message while moving its code | keep the text byte for byte | messages are **B** here (DEC-1) |
| Edit a test's assertion to make a refactor pass | stop and report (P-0019) | the assertion is the proof (DEC-3) |
| Cache on a `SchemaView` | compute once per caller and pass it (PD-6) | a view can be mutated |
| Hand-edit a generated file or golden | `make generate`, `make refresh-golden`, `make refresh-served-golden` | AGENTS.md principle 2 |
| Write a characterisation test that only passes | plant the named mutation and see it fail first | an unbitten test proves nothing (DEC-3) |
| Add a conformance-kit case for `claim_idle` | the toolkit's own Redis test (PD-14) | a kit case changes what consumers' runs check |
| Write docs from memory of the design | check each sentence against the code or a test (PD-15) | the seeds found the docs already contradict the code |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A refactor changes an outcome | a covering test fails; or an `xfail(strict=True)` passes (XPASS fails the run) | revert the step; the builder reports it; the lead decides (never edit the assertion) |
| A characterisation test does not fail under its planted mutation | the builder's red run | the test is too weak: strengthen it before the change it guards |
| The `more_count` move changes a generated class or the public surface | `public-surface.json`/`model-shape.yaml` tests; `git diff` on the generated Python fields | revert PD-1; leave 252-e in #252 (OPEN-9) |
| The import contract refuses PD-2's placement | `make check-architecture` | report the refusing import to the lead (PD-2) |
| `make generate` rewrites more than PD-1 and 252-h3 expect | `git diff --stat` after `make generate` | stop; a stale generated tree on `develop` is a separate fix, reported |
| `tests/theme_map.py` from `read_targets` lists a theme the hand lists did not (or the reverse) | the six users' tests fail or change their counts | the hand list was stale: the lead decides; record it as a delivery decision |
| The PD-7 guard misses a reader (e.g. `from ... import TOOLKIT_ROOTS as R`) | the guard's own test on a planted alias | match the name in imports too |
| `make refresh-map` reports unmapped tests | exit 1 | the lead adds the rows (builders never edit `scenario-map.csv`) |
| The wake test is flaky under load (PD-13) | CI unit shard failure | the margin is 30×; if it still flakes, quarantine with an issue link (`testing.adoc`) |
| The Redis `claim_idle` test is slow or flaky | `make test-containers` | it is not in CI; the lead records the run's result in `evidence/` |
| The library's `generated_schemas` and the generator's `_generated_here` disagree on an input (they read `python_package` through different helpers, PD-8) | a `test_ext_pydantic_split.py` test fails | keep the generator's reader and report the input that differs; 192-f goes back to #192 |
| The relay's first look races the wake (a delivery within 2 s that the interval, not the wake, made) | the planted mutation leaves the test green | the test commits twice: it waits (up to 60 s, any delivery) until the first activity reaches the hub, so the relay has looked once and is in its 60 s wait; only then does it commit the second and assert it within 2 s |
| Two parallel tasks edit the same test file | merge conflict in the stage branch | the roadmap sequences them (1.1→1.2, 2.1→2.2→2.3, 3.1→3.3) |
| A docs sentence contradicts the code | the stage pass's cold read; the builder's hand-off list | fix the sentence; never the code |
| A file's `BOOK_CLASS` (or `TITLE`, `BIBO`, `TIMEOUT`) holds another value than `tests/toy.py`'s and is not on PD-17's list of four | its tests fail after the import | keep the file's own constant and add it to the hand-off; never change the value a test asserts |
| A test mutated `BOOK_JSON` and another relied on the mutation (an order dependency `book_json()` breaks) | that test fails after PD-17 | report it to the lead: the hidden coupling is a defect of the test, fixed in its own commit |
| PD-20's guard flags a call that fits no `# X` kind | the guard's list on the stage-3 branch | report it to the lead (P-0019); the lead rewrites the test through a seam or records an exception in `testing.adoc` |
| PD-20's guard misses a patch through an alias (`import rdf_persistence.x as m`; `monkeypatch.setattr(m, ...)`) | its own case on a planted alias | the import binding covers `as` names |
| `load_warm_shapes` warms twice for the same bytes, or once for different bytes (PD-19) | its Red test | the digest is of the bytes, never of the path |
| `TenancyDouble` drifts from `Tenancy.tenant_session` | `test_tenancy_double.py` fails naming the parameter | add the parameter to the double |
| An issue is closed while an item is still open | the task 4.1 comment lists each item with its class | reopen; DEC-4 |

## Risks / Trade-offs

- **RISK-1, a "preserving" change is not** (likelihood low, impact high): the tidy-ups touch the
  referrer guard and the nesting guard, both write-path code. Mitigation: characterisation tests
  first (DEC-3), the strict xfails stay as tripwires, the adversarial tester runs after task 1.6
  (the write-guard refactor; `develop/agents.adoc#challenge`).
- **RISK-2, the generated tree drifts** (likelihood medium, impact low): `make generate` may
  regenerate more than the two model edits. Mitigation: the error matrix row; `make
  check-generated` in the stage gate.
- **RISK-3, the EPIC grows into the B items** (likelihood medium, impact medium): each tidy-up sits
  beside a fix the review wanted. Mitigation: DEC-1, the anti-patterns, and the per-stage L2+L3
  pass checks the diff against `inputs/triage.md`'s **P** rows.
- **RISK-4, a consumer relies on a moved name** (likelihood low, impact low): `enum_meanings`,
  `TENANT_STATE_IRIS` and the slot's module are not in `public-surface.json`, but a consumer may
  import them. Accepted: they are not public (`rdf_persistence.__all__`), and OPEN-9 asks the
  owner.
- **RISK-5, characterisation tests pin accidental behaviour** (likelihood low, impact medium): a
  test of `KeyConflict` over `InUse` pins PD-4 of the referrer change, a decided order, not an
  accident. Each characterisation test cites the decision it pins; one with no decision behind it
  is not written.
- **RISK-6, the issues' item lists drift from the code before delivery** (likelihood medium,
  impact low): another EPIC may touch the same files. Mitigation: each stage starts by re-checking
  its rows of `inputs/triage.md` on the current `develop` (task 1.0, 2.0, 3.0).
- **RISK-7, PD-17 is the widest edit of the EPIC** (likelihood medium, impact low): about thirty
  test files in stage 1 meet stage 1's and stage 3's own edits of the same files
  (`test_session_referenced_removal_dependents.py`, `test_open_event_stream.py`,
  `test_event_stream.py`). Mitigation: PD-17 is task 1.11, the last of stage 1, after every other
  stage-1 edit of those files; stage 3 starts from `develop` with it merged.

## Open Questions

None. The owner answered OPEN-1 to OPEN-9 on 2026-11-25 by accepting every recommendation, and
round 2 folded in #272 (all six items), #273 and #275 (`inputs/qa.md`). #371 and #372 are planned
in `consumer-friction`, not here.
