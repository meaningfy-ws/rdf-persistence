<!-- PLAN (design half) of test-debt-paydown. PLAN = this file + tasks.md.
     Re-planned 2026-11-21 on develop 030f580f (thematic layout). Facts with file:line:
     inputs/refresh-a.md (PD-1 to PD-7, PD-9, PD-10, PD-15, #215), inputs/refresh-b.md (PD-8, PD-11
     moves, test_tenant_move, the guard), inputs/refresh-c.md (PD-11 rest, PD-12, rules).
     inputs/facts.md (be129a0) keeps the reasoning; its paths are void. -->

# Design: test-debt-paydown

## Context

The test-suite grooming (archived `2026-11-16-test-suite-grooming`) left a *Debt* list and
"under the floor" review findings, and the mutation run left survivors no test kills. The first
PLAN (gated 2026-11-17 on `be129a0`) went stale when the thematic restructure moved the package
into `rdf_persistence/<theme>/{domain,services,adapters,entrypoints}` and the tests into
`tests/unit/<theme>/` and `tests/generator/`. This PLAN keeps the first PLAN's decisions and ids,
rebased on today's code, plus the owner's answers of 2026-11-20 and 2026-11-21 (`inputs/handover.md`,
`inputs/qa.md`).

Constraints: the layering and `make` gates of `AGENTS.md`; `develop/testing.adoc`; nothing
generated is edited by hand; no new test library.

## Goals / Non-Goals

**Goals**
- G-1: every monkeypatch of toolkit code (`rdf_persistence*`; PD-17's scope) in `tests/unit/` and
  `tests/generator/unit/` is either replaced by a real seam (PD-1, PD-17) or belongs to one of the
  five exception classes recorded in `testing.adoc` (PD-17).
- G-2: no test waits on wall-clock time for an absence, except the testkit's own timeout test
  (`test_open_event_stream.py:96-101`, it tests the timeout) (PD-3 done by #213, PD-4).
- G-3: no test file imports a test module, and a test guards it (PD-8).
- G-4: every behaviour-changing survivor of `make mutation` is killed or recorded as equivalent
  with its reason (PD-12); `make mutation` shows no unexplained survivor.
- G-5: the `rp-messages` spec says what the code does about an empty commit (DEC-1).
- G-6: `ToyService()`'s median construction time drops by at least 25 % (PD-7).
- G-7: the root of `tests/unit/` holds no test file: tooling tests are in `tests/unit/tooling/`,
  package tests in `tests/unit/package/` (PD-11).

**Non-Goals**
- Widening `make mutation`'s selection (`setup.cfg [mutmut]`) (PD-13).
- Rewriting adversarial files; adding a test library; changing a public behaviour (PD-5 removes a
  branch without changing an outcome; PD-7 skips a repeated warm-up whose effect is process-wide).
- #215's W2, W5, S4, S5 (they stay on #215).

## Decisions

- **PD-1 Monkeypatches with a real seam** (refresh-a PD-1). Replace:
  - `tests/unit/api/test_events_route.py` TC-37a (`:354-377`) and TC-38 (`:426-444`): `async with
    kit.relay.paused():` (PD-2), in stage 2;
  - `tests/unit/api/test_service_kit.py` TC-82 (`:686-704`): drop the `MessageBus.publish` spy; keep
    `kit.bus is None`, the write's success and "the commit is recorded";
  - `tests/unit/tenancy/test_migrate_dataset.py` NOTHING (`:223-232`) / DROP_STAMPS (`:235-242`):
    `Inert(Dataset)` / `Unstamping(Dataset)` beside `Failing` (`:244-251`), overriding `update`
    (the runner calls `dataset.update(prepare_update(...))`, `migration_runner.py:162`);
  - same file, SparqlError (`:263-275`): build the `Chain` tuple by hand (`migrations.py:105`;
    `chain_of` cannot carry it, `load_chain` refuses a bad request at `:88-90`) with one
    `Migration(schema_id="https://ex.org/a b")` and a stamp under that IRI (so `stamp_problems`,
    `migrations.py:330`, passes); assert `SparqlError` and that `"migration_request"`
    (`migrations.py:232-242`) is a frame name in `excinfo.traceback` (the attack ran it: it raises
    "not a valid IRI for SPARQL"). If that does not reach it, the patch stays in class X3 (PD-17)
    and the builder reports it;
  - `tests/unit/tenancy/test_migrate_dataset_adversarial.py` (`:188-212`): `CountingDataset(Dataset)`
    (it replaces a patch of rdflib's `Dataset.contexts`, replaced all the same); the `dataset(...)`
    helper (`test_migrate_dataset.py:47-49`, in `tests/migration_helpers.py` after 1.2) gains
    `kind: type[Dataset] = Dataset`; `many_graphs` (`:178-185`) passes `CountingDataset`; plus
    `assert small > 0`;
  - `tests/generator/unit/test_generation_inputs.py` (`:199-209`, `:212-224`): call
    `generate(read_targets(...), base, (step,), check=False)` (`pipeline.py:217`);
  - `tests/generator/unit/test_freshness.py` linkml version (`:182-188`): edit the copied manifest
    through `GenerationManifest`; sha256 (`:424-440`): rewrite the recorded hash of
    `rp_api_entrypoints.yaml` in the copied manifest through `GenerationManifest` (the file itself
    is the toolkit's and is not copied).
  Kept, in PD-17's classes: `tests/unit/api/test_receive.py` KeyError (`:357-368`) and LookupError
  (`:371-382`) (X3), `test_freshness.py` no-extra (`:191-207`) (X5).
- **PD-2 `Relay.paused()`** (`rdf_persistence/events/services/relay.py`, `_lock` `:107`,
  `run_once` `:126-131`): an `asynccontextmanager` holding `_lock`; a wake-up during the block runs
  one round after it. The lock is not reentrant: `run_once()` inside the block hangs, which the
  docstring says. TC-38 follows and takes inside the block. Spec: `rp-events` ADDED requirement;
  three unit tests in `tests/unit/events/test_relay.py` (held, resumed, released on exception).
- **PD-3 Absence waits:** done by #213 (`open_event_stream`, sentinels in
  `test_events_route.py:197-207`, `:380-398`, `:466-493`). Nothing to do.
- **PD-4 Keep-alive and d18:** the grant-removed test (`test_events_route.py:236-243`) mounts
  `mount(service, "/idle", sse=short_times(keep_alive_seconds=0.001))` (0 is refused, `ge=0.001`);
  d18 (`tests/unit/events/test_relay.py:307-321`) uses
  `events=EventSettings(publish_timeout_seconds=0.01)` (0.001 would be flaky under xdist:
  `InMemoryEventBus.publish` awaits `_deliver`, `fakes.py:430`); `HangingBus` (`:294-304`) keeps its
  other-tenant branch non-suspending, with a comment saying why. No production change.
- **PD-5 Store status branch** (`rdf_persistence/persistence/adapters/sparql_protocol.py`
  `_raise_for_status` `:100-125`): remove the `>= INTERNAL_SERVER_ERROR` branch (`:105-106`); the
  final `not is_success` (`:124-125`) raises the same class and text. The comment at
  `tests/unit/persistence/test_fuseki_store.py:190-191` is updated.
- **PD-6 Auth** (`rdf_persistence/api/entrypoints/auth.py:38-41`): keep both halves; add two tests
  in `tests/unit/api/test_service_kit.py` beside `:104-116`: a valid token sent as `Basic <jwt>` is
  a 401, and `"Bearer "` with a verifier stub that accepts any string is a 401. The stub is wired
  with `installed(FastAPI(), toy, verifier=stub)` (`test_service_kit.py:278`; `ToyService` takes no
  verifier). The empty-token half stays because `TokenVerifier` is a public port and a consumer's
  verifier is not held to the conformance matrix.
- **PD-7 `ToyService()` cost** (refresh-a PD-7; owner 2026-11-21 "warm once per shapes"): in
  `rdf_persistence/api/services/documents.py` (`:106-109`), (a) `Documents.__init__` reads the bytes
  of `folder / SHAPES_FILE` each time and computes `digest = sha256(data).hexdigest()`; an
  `lru_cache(maxsize=8)` `_shape_triples(digest: str, data: bytes) -> tuple` parses `data` on a miss
  with `Graph().parse(data=data, format=TURTLE)` (the `text/turtle` media type of `core.domain.media`; the packaging test forbids rdflib's short names) and returns its triples; each `Documents` builds
  its own `Graph` and adds them with `graph.addN((s, p, o, graph) for s, p, o in triples)` (rdflib
  7.6's `addN` drops quads of another context); (b) `warm_up` runs once per digest per process: a
  module-level `set` of warmed digests, checked first without the lock (a set lookup); on a miss,
  `sparql_parsing.SPARQL_PARSER_LOCK` (an `RLock`, `sparql_parsing.py:26`) is taken, the set
  re-checked, `warm_up` run and the digest added (the warm-up's effect is process-wide,
  `api/services/shacl.py` docstring). The revised
  `tests/unit/api/test_shacl.py::test_documents_warm_up_when_built_and_validate_without_the_lock`
  builds from a `tmp_path` copy of `GENERATED` whose shapes file gets a unique trailing comment
  (other test modules build `Documents(VIEW, GENERATED)` at import, `test_iri_policy_checks.py:70`,
  so `GENERATED`'s digest is already warm): the first build warms (`lock.taken >= 1`), a second
  build of the same copy takes no lock, a second unique copy warms again, and checking a body takes
  no lock. Acceptance:
  `inputs/probes/probe_parts.py` (imports updated to the theme paths) gives a `ToyService()` median
  of 7, before and after on one checkout and machine, at least 25 % lower (baseline ≈ 242 ms).
- **PD-8 Cross-test imports** (refresh-b §1; 113 statements, 43 source modules: the 108 of
  `inputs/probes/cross_imports.out` plus `tests/unit/sparql_threads.py:36` and four module-object
  imports). Rule: constants and builders go to a helper beside their users; fixtures to that
  folder's `conftest.py`; a helper used across tiers to `tests/`; across themes of one tier to that
  tier's root (`tests/unit/`, as `builders.py`). One home per source module (✱ = another tier or
  theme imports it):

  | Source test module | Home |
  |---|---|
  | `unit/tenancy/test_tenant_sweep` ✱ | `tests/tenancy_world.py` (new); fixture `world` → `tests/unit/tenancy/conftest.py` (new) |
  | `unit/tenancy/test_tenant_dump` ✱, `test_pending_mark` ✱ | `tests/dump_helpers.py` (new); fixtures `stamped`, `aged`, `chains` → `tests/unit/tenancy/conftest.py`; `PLUMBING`, `three_commits` → `tests/unit/tenancy/tenancy_helpers.py` |
  | `unit/tenancy/test_session_activity` ✱, `unit/persistence/test_session_activity_adversarial` ✱, `test_session_unique_keys` ✱, `unit/provenance/test_activity_shape` ✱ | `tests/unit/activity_helpers.py` (new) |
  | `unit/events/test_relay` ✱ | `tests/relay_helpers.py` (new); fixture `world` → `tests/unit/events/conftest.py` (new) |
  | `unit/api/test_events_route` ✱ | `tests/events_follow.py` (new): `listening`, `mount`, `replace`, `reshape_grants`, `with_carol`, `another_book`, `events_of`, `opening`, `drained` (#213), with `short_times`, `KEEP_ALIVE`, `WEEK` that `mount` needs (`test_events_route.py:89-106`) |
  | `unit/api/test_service_kit` ✱ | `tests/toy_service.py` (`made`, `installed`, `A_UUID`) |
  | `unit/api/test_documents` ✱ | `tests/toy.py` (`BOOK`, `BOOK_JSON`, `encoded`) |
  | `unit/api/test_router` | `tests/unit/api/scene.py` (`everyone_has_a_role`, made public) |
  | `unit/api/test_iri_policy_checks` | `tests/unit/api/iri_policy_helpers.py` (new) |
  | `unit/core/test_sparql_parsing` ✱ | `tests/unit/builders.py` (`RecordingLock`) |
  | `unit/tenancy/test_migration_runner` ✱, `test_migrate_dataset` ✱ | `tests/migration_helpers.py` (the existing `tests/unit/tenancy/migration_helpers.py` moves there); fixtures `lib_chain`, `three`, `toolkit_chain` → `tests/unit/tenancy/conftest.py` |
  | `unit/tenancy/test_tenancy`, `test_tenancy_stores` | `tests/unit/tenancy/tenancy_helpers.py` (new) |
  | `unit/migrations/test_migration_chain`, `test_migration_files` | `tests/unit/migrations/migration_steps.py` (new) |
  | `unit/persistence/test_loading` | `tests/unit/persistence/loading_helpers.py` (new) |
  | `unit/messaging/test_messagebus`, `test_messagebus_wiring` | `tests/unit/messaging/messagebus_helpers.py` (new) |
  | `unit/collaboration/test_collaboration_*` (7 modules), `test_write_guards` | `tests/unit/collaboration/collaboration_data.py`; the fixtures of `test_collaboration_workflow` → `tests/unit/collaboration/conftest.py`; `poetry(slot, value)` ✱ (`test_collaboration_collections.py:60`) → `tests/toy.py`; same-named, different helpers take their module's prefix (`cascade_poetry` from `cascade:65`, `cascade_put` from `:75`, `collections_put` from `collections:68`; `as_ada` once if identical, else prefixed the same way) |
  | `unit/package/test_theme_layout` ✱ (moved by 1.1) | `tests/unit/layout_table.py` (new, its `ROOT` at `parents[2]`); the patches of `TURNED_ON` (`test_theme_layout.py:632, :641, :669, :674`, and `test_no_old_module_paths.py` was `:252`) target `tests.unit.layout_table.TURNED_ON` |
  | `unit/package/test_technical_split` ✱ (moved by 1.1) | `tests/unit/import_contracts.py` |
  | `unit/testkit/test_shape_snapshot` ✱ | `tests/metamodel.py` (new) |
  | `generator/unit/test_generate_cli`, `test_freshness`, `test_freshness_plugin` | `tests/generator/unit/golden.py` |
  | `generator/unit/test_lock` | `tests/generator/unit/lock_helpers.py` (new) |
  | `generator/unit/test_hard_check`, `test_boundary_check` | `tests/generator/unit/checks.py` (new; `hard_check_problems`, `boundary_problems`) |
  | `generator/e2e/test_generated_library_served` | `tests/generator/e2e/generated_toy.py` (new) |
  | `integration/store/test_session` | `tests/integration/store/sessions.py` |
  | `e2e/test_library` | `tests/e2e/world.py` |

  Then a guard, `tests/unit/tooling/test_no_cross_test_imports.py`: an `ast` scan of every
  `tests/**/*.py` (helpers and conftests too), anchored on `Path(__file__).parents[3]`, failing on
  five forms: `from tests.….test_x import …`, `from .test_x import …`, `from tests.… import test_x`,
  `from . import test_x`, `import tests.….test_x`; its own test plants all five in a `tmp_path` tree
  (shape of `test_library_tests_stay_apart.py:148-207`; relative-import resolution from
  `inputs/probes/cross_imports.py`).
- **PD-9 P-20 rows** (refresh-a PD-9): `tests/unit/access/test_token_verifier.py` `INVALID_TOKENS`
  (`:112-141`) 28 → 17 per `inputs/facts.md` item 4's table (no `sub-dot`/`empty-sub` case:
  `test_jwks.py:415-421` covers `UNUSABLE_SUBJECTS`); `tests/unit/testkit/test_fake_identity.py`
  (`:55-58`) keeps `"ANN@example.org"` only. Each drop is confirmed by a hand mutation of its
  `rdf_persistence/access/adapters/jwks.py` branch that a kept case catches (in the commit body).
  The two new `_bound_key` branches (`:158`, `:162`) are out of scope.
- **PD-10 P-31 unit half** (refresh-a PD-10): `tests/unit/api/test_documents.py`'s parametrised
  `documents` fixture (`:84-85`) becomes `each_policy_documents`, taken only by `:232` (outside
  node refused) and `:359` (round trip); the other 38 tests take `default_documents`. Tests that
  take only `book_class` become single-policy too; the two kept tests carry the policy coverage.
  `tests/unit/persistence/test_listing_query.py` hostile filter (`:212-220`) and hostile contains
  (`:222-234`): `@pytest.mark.parametrize("policy", [POLICIES[0]], indirect=True, ids=["default"])`
  (a bound literal does not depend on the policy).
- **PD-11 Under-the-floor items** (refresh-b §2-3, refresh-c §1; owner: "keep the moves"):
  - moves: the 13 tooling tests of `tests/unit/` to `tests/unit/tooling/`, the 17 package tests and
    `sparql_threads.py` to `tests/unit/package/` (lists: refresh-b §2), each with `__init__.py`;
    `parents[2]` → `parents[3]` in the 21 files refresh-b lists; `Makefile:55, :121`;
    `testing.adoc:27`; `tests/changed.py`: rule 11 (`:94-95`) selects `tests/unit/package/`,
    `root_unit_tests()` (`:73-75`) and the `root_tests` parameter it feeds (`:78`, `:99`, `:124`)
    go, the root-file branch (`:84-86`) stays for a future root file (its scenario is kept in the
    delta), rule 2 (`:105-106`) names
    `tests/unit/tooling/test_check_docs.py`; `tests/unit/tooling/test_changed.py` follows
    (`:24, :32, :33, :41, :206-211, :238-244`); `rp-developer-checks` MODIFIED delta (this change's
    `specs/`). `test_private_transaction_pieces.py` stays in `tests/unit/collaboration/` (its theme
    reruns it; the first PLAN's move predates themes). Order: `git mv` and commit first, then
    `make refresh-map` (it follows renames), then `make test-durations`;
  - `tests/unit/tenancy/test_tenant_move.py` stays where it is (`setup.cfg:29` stays valid); its
    `schema.services` imports (`vocabulary`, `load_schema`, `iri_types`) and `tests.toy`
    (`SETTINGS`, `TOY_SCHEMA`) become literal `URIRef`s, literal `frozenset`s for `Iris(settings,
    roots, owned)` and a local `ServiceSettings(...)`; then a new `.importlinter` contract
    `tenant-move-test-imports-only-its-module` (forbidden: `rdf_persistence.schema`,
    `rdf_persistence.*.adapters`, `rdf_persistence.*.entrypoints`, `rdf_persistence.testkit`,
    `tests.toy`, `tests.toy_service`; text in refresh-b §3);
  - one class-comment form, `# Class:` / `# Classes:`, named in `testing.adoc` rule 6
    (`:56-57`); the 52 other forms rewritten (refresh-c §1 table);
  - the 73 stage/task hits (56 docstring lines, 15 comments, 2 assert messages in
    `tests/feature/test_observability.py:208, :240`) replaced by the requirement or PD they serve,
    or reworded without the words "stage 1/2" where they name a fixture (`uml_library_stage2.py:5`,
    `test_uml_generate.py:5`), so the grep is empty;
  - a marker-completeness test in `tests/unit/tooling/test_markers.py` (every `tests/**/test_*.py`
    has a row in `_MARKERS_BY_DIR`, `tests/conftest.py:86-104`); the Hypothesis profile test
    (`:142-157`) also run with `-n 2`;
  - a `utc_now()` awareness test in `tests/unit/persistence/test_utc_now.py` (new;
    `persistence/services/session.py:385`);
  - `tests/unit/api/listing_shelf.py` bodies through the models with `Genre` members, persona
    constants (`ADA`, `RITA`, `OMAR`) in `tests/toy_service.py`, used by `listing_shelf.py` and
    `tests/unit/api/scene.py`;
  - conftest constants: `GENERATED` (`tests/unit/conftest.py:19`) → `tests/toy.py`; `TOY`,
    `ROOT_SCHEMA`, `Breaker` (`tests/generator/unit/conftest.py:11-14`) →
    `tests/generator/unit/golden.py`; `TEST_DATA_DIR` and `load_text_file`
    (`tests/conftest.py:40, :169-181`) deleted.
- **PD-12 Mutation survivors** (refresh-c §2; owner: "re-run at stage start"). The selection is
  `setup.cfg [mutmut]` as it stands: the `domain` of every theme, `iris/services/iris.py`,
  `tenancy/services/tenant_move.py`, run with `tests/unit/{core,files,iris}` and
  `tests/unit/tenancy/test_tenant_move.py`. Task 3.1 re-runs `make mutation` and writes
  `inputs/survivors-before.md` (headed with the commit and the selection); the group recipes of
  `inputs/facts.md` item 10 and refresh-c §2 are hints where a mutant still exists (A, D, D' are
  gone). A killing test sits inside the selected test folders (a killer elsewhere does not count:
  Q's moves into `tests/unit/iris/`). Split by test file, disjoint:
  - 3.2: every `tests/unit/core/test_*.py` (`test_exceptions.py`, `test_sparql.py`,
    `test_sparql_parsing.py`, and the tests of `base.py` and `media.py` such as `test_rp_model.py`),
    `tests/unit/files/test_blob_keys.py`, `tests/unit/tenancy/test_tenant_move.py`,
    `tests/unit/iris/test_layout.py` (C, R, S, T, and the new `layout.py`, `sparql_parsing.py`,
    `MessageLimitExceeded.command` survivors);
  - 3.3: every other `tests/unit/iris/test_*.py` (E, G, H, H', I, J, K, L, M, N, O, P, Q; L'
    timeboxed to 15 minutes, then recorded equivalent if no legal policy kills it).
  Recorded as equivalent, each with its one-line reason, in `tests/audit/equivalent-mutants.md`:
  B, F, N root-only, L' if so, and every kind-`message` mutant under one DEC-3 heading. DEC-3's
  "rule 9" is a stale citation (`testing.adoc` rule 9 is about Gherkin); its reason stands: an
  error message's wording is not behaviour a caller relies on.
- **PD-13 No wider mutation:** the selection is not widened; it is not needed for any goal.
- **PD-14 Merge** (DEC-2, owner 2026-11-21 "one PR at the end", over P-0013's per-stage PRs for
  this change): one branch `change/test-debt-paydown-build` off `develop`, one PR after stage 3,
  rebased on `develop` before it opens (P-0002), merged only on a green PR CI (P-0013's "never on
  red or missing checks" holds).
- **PD-15 Conformance poll** (`rdf_persistence/testkit/event_bus_conformance.py`): `run_case(case,
  pair, *, poll_seconds=POLL_SECONDS)` (`:106-113`, a keyword added with a default) sets a module
  `ContextVar` `_POLL_SECONDS` for the duration of the case; `Inbox.has` (`:38-54`) reads it and
  passes it to `wait_until_async`. `Case` (`:57`) and `Inbox()` keep their signatures, so no public
  type changes and the cases in `CASES` are untouched. Test
  `tests/unit/testkit/test_event_bus_conformance_poll.py`: a `DelayedPair` over the in-memory pair
  delivers 0.1 s after `publish`; a delivery case passes in < 1 s with `poll_seconds=0.02`; a second
  test runs `run_case(case, pair)` unchanged. `DelayedPair` implements the whole `BusPair`
  (its `failing()` delegates to the wrapped pair); a bare `Inbox()` outside `run_case`
  (`test_redis_events.py:44`) reads the default `POLL_SECONDS`. `tests/integration/adapters/test_redis_events.py`
  (`:47-49`) passes `poll_seconds=0.05`. Spec: `rp-testkit` delta.
- **PD-16 #215 S1-S3** (owner 2026-11-20 "take S1-S3"), in `tests/unit/api/test_events_route.py`
  and `tests/unit/api/test_open_event_stream.py`:
  - S1, TC-37 (`:336-351`): commit a second visible sentinel and ask `events=4`; assert the four
    ids are distinct and in commit order (replay, then live, none twice);
  - S2, TC-37b (`:380-398`): resume from the id of the visible commit made before the hidden
    replace, so the replay itself holds the hidden activity; assert it is not sent;
  - S3: the default-route test (`:197-207`) asserts the sentinel's generation entity is
    `settled.book_iri`; `test_one_event_is_returned_with_the_activity_iri_as_its_id`
    (`test_open_event_stream.py:54-79`) checks the event's data against the book.
  The PR body says "Closes #215 S1-S3"; #215 stays open for W2, W5, S4, S5.
- **PD-17 Monkeypatch triage** (owner 2026-11-21 "widen: triage all 20 here"; refresh-a PD-1
  list; scope: `monkeypatch.setattr` and `monkeypatch.delattr` of toolkit code, and
  `monkeypatch.setitem`/`delitem` of `sys.modules`). Replaced:
  - `tests/unit/collaboration/test_collaboration_collections_adversarial.py:659` (`Mapper.max_roots`
    property): the `collaboration` fixture's `build` (`tests/unit/collaboration/conftest.py:34`,
    `mapper=toy_mapper()`) gains `mapper=`, and the three tests use `toy_mapper_limited(LIMIT)`
    (`tests/toy.py:85`);
  - `tests/unit/api/test_service_kit.py:451` (`service.kit.max_restore_bytes`): the
    `max_restore_bytes` setting through `installed(app, toy, settings=…)` (`:278`).
  Every other patch is kept in one of five classes, written
  in `testing.adoc` under rule 3 (`:44`), one sentence each:
  - **X1, a configuration constant of the generator or the kit pointed at a copy:**
    `test_generation_inputs.py:272`, `test_components_served.py:64, :74, :86`,
    `test_ext_typescript.py:172, :225`, `test_hard_check.py:1241-1242`,
    `test_ext_pydantic_split.py:158, :630, :657`, `tests/generator/unit/conftest.py:81`,
    `tests/unit/package/test_technical_split.py` (`openapi.served_folders`, was `:248`);
  - **X2, an order or a hand-off no public result shows, observed by a pass-through spy or an
    instrumented lock:** `test_shacl.py:27, :58`, `test_sparql_parsing.py:42, :55`,
    `test_router_hardening.py:140-141`, `test_toolkit_wiring_adversarial.py:60, :83`;
  - **X3, a fault or defect no port can produce, injected to prove a guard catches it:**
    `test_receive.py:363, :377`, `test_roundtrip.py:65`, `test_migration_files.py:252`,
    `test_fakes.py:240`, `tests/unit/events/test_relay.py:404, :429, :523, :556, :601`, and the
    SparqlError patch if PD-1's route fails;
  - **X4, a random draw pinned:** `test_iris_application_adversarial.py:249`;
  - **X5, an absent optional dependency:** `test_freshness.py:194-201`, `test_generate_cli.py:82-88`
    (the `sys.modules` items and the `generation.steps` `delattr` of the missing-extra set-up).
  Bare file names above are under `tests/unit/<theme>/` or `tests/generator/unit/` (refresh-a PD-1
  gives each full path). Each kept line gets a trailing `# X1` to `# X5` comment (not the `# Class:`
  form of PD-11), so `grep -rn "monkeypatch.setattr" tests/unit tests/generator/unit` lists only
  lines carrying one, or targets outside `rdf_persistence*`
  (rdflib, `sqlite3`, `subprocess`: refresh-a PD-1).

## Algorithm / approach

Three stages on one branch, one PR at the end (PD-14). The lead re-indexes GitNexus at each
stage's start. Builders work in worktrees the lead creates under `.worktrees/<task>` (P-0015), one
task each, only where tasks run in parallel (`agents.adoc:90-91`); the lead cherry-picks. Each
stage ends with `make check-all` and `make test-containers` on its head, one L2+L3 review pass
(P-0005), the fixes, and both gates again.

- **Stage 1 (tests only):** PD-11's moves first and alone (1.1), then PD-8 (1.2): both touch many
  files. Then 1.3 (PD-1 except the `paused()` users, PD-17), 1.4 (PD-4, PD-16) and 1.5 (PD-9,
  PD-10) in parallel; their files are disjoint, and `tests/audit/scenario-map.csv` is the lead's:
  after each parallel group the lead adds the new tests' rows and runs `make refresh-map` (it exits
  1 while a test is unmapped). Then 1.6 (PD-11's rest) alone: it shares
  `testing.adoc`, `test_documents.py` and `listing_shelf.py` with them.
- **Stage 2 (production + its tests):** PD-2 and its two users, PD-5, PD-6, PD-7, PD-15 in
  parallel; then DEC-1's spec check.
- **Stage 3 (mutation):** PD-12, then the final review, the rebase, the PR (PD-14), acceptance,
  archive.

Worked example (PD-16 S2): today TC-37b resumes from `a2`, the hidden replace itself, so the
replay is empty of hidden work. After: commit a visible replace `a1`, then the hidden replace
`a2`, then a visible sentinel `a3`; resume from `a1`; take one event; assert it is `a3`.

Worked example (PD-7): before, two `ToyService()` in one process each run `warm_up` (≈ 139 ms).
After, the first warms digest `d` and adds it to the warmed set; the second finds `d` and skips
it; `Documents` over a rewritten shapes file has digest `d'` and warms again.

Worked example (PD-12, group J): `assert not Iris(settings).part_needs_type()` with the default
policy, and `assert Iris(settings_with(part_template="{root}/parts/{type}/{id}")).part_needs_type()`,
in `tests/unit/iris/`.

### Anti-patterns
- Replacing a monkeypatch with a new fake class of toolkit code (PD-1 and PD-17 use real seams or
  a recorded class).
- A sentinel event that could arrive before the hidden one (commit it after).
- Moving a test into a lane CI does not run (every move here stays in the unit lane; refresh-b §2:
  no lane glob names a root file).
- A killing test outside the mutation's selected test folders (it kills nothing there).
- A "killing" test that asserts message text (DEC-3).
- Mass rewrites with `sed -i`, heredocs or scripts; edits go through Edit, Serena or `ast-grep`.

## Error matrix

| Failure | Detected by | Handling |
|---|---|---|
| A moved test is no longer collected, or its map row is lost | `make refresh-map` exit 1 or 2, "Removed rows" > 0; the count in `make test-fast` | commit the `git mv` first, then refresh (it follows renames) |
| A moved file still resolves the repo root with `parents[2]` | its own test fails (paths under `tests/`) | 1.1 changes the 21 files refresh-b lists |
| A root-package change selects no test in `make test-changed` | `tests/unit/tooling/test_changed.py` | rule 11 selects `tests/unit/package/` |
| CI shards unbalanced after the moves | the PR's CI times | `make test-durations` after 1.1 |
| A cross-import guard false positive | the guard's own test with a helper and a test module | the guard names the module; rename the helper |
| `Relay.paused()` never released, or `run_once()` inside it | pytest-timeout 120 s | the test fails naming itself; the docstring warns |
| A sentinel committed before the subscriber listens | `open_event_stream` times out | `await listening(hub, n)` before the sentinel |
| Shapes cache returns stale triples after a rewrite | 2.4's test: two same-size rewrites in `tmp_path` | the key is the content digest |
| Warm-up skipped for shapes never warmed | 2.4's revised `test_shacl` test: other shapes warm again | the set is keyed by digest |
| Two threads warm the same digest at once | the set is read and written under `SPARQL_PARSER_LOCK` | a second caller finds the digest |
| A kept P-20 case no longer guards a dropped one's branch | PD-9's hand mutation | keep the dropped case |
| A kept monkeypatch with no class | 1.3's grep acceptance | classify or replace |
| A survivor's "killing" test does not kill it | 3.4's re-run of `make mutation` | fix the test; nothing left unexplained |
| `develop` moved under the branch | the rebase before the PR (PD-14) | generated files: take develop's, run `make generate` |

## Risks / Trade-offs

- **RISK-1** (medium, low): PD-8 and PD-11 touch ~80 files; a missed path breaks collection.
  Mitigation: one source module per step, `make test-fast` after each, the guard last.
- **RISK-2** (low, medium): the `Dataset` subclasses (PD-1) are not walked by rdflib's SPARQL
  engine the way the patch was. Mitigation: `assert small > 0`.
- **RISK-3** (low, medium): a consumer's `TokenVerifier` accepts an empty token. Mitigation: PD-6
  keeps the guard and tests it.
- **RISK-4** (medium, low): fewer survivors die than the recipes say. Mitigation: a corrected test
  or an equivalence line each; G-4 is "explained", not "zero".
- **RISK-5** (medium, medium): one PR after three stages on a fast-moving `develop` (this PLAN was
  re-planned once for that reason). Mitigation: rebase on `develop` at each stage's end, full gates
  after each rebase; generated conflicts as in the error matrix.
- **RISK-6** (low, medium): the warmed-digest set hides a parse action a later validation needs.
  Mitigation: `shacl.py`'s docstring scope (fixed shapes, `sh:targetClass` only) is unchanged; the
  set only skips a repeat of the same shapes.

## Open Questions

None open. Answered: OQ-1 CI wait (2026-11-17, "keep CI wait"); the 2026-11-20 and 2026-11-21
rounds (`inputs/qa.md`).

**DEC-5 (gate accepted below 9):** the re-plan's gate run 1 scored 8.9/10; its ten gaps and the
attack's 21 findings (4 blockers) are folded in, and the gate is not re-run, by the owner's
standing rule R-0005 ("accept the score as good enough: fold the small gaps in and do not re-run
the gate to reach 9").

## Delivery decisions

By the lead, 2026-11-21, under the owner's "work as a team leader with subagents in parallel".

- **D-1 Order:** 2.2, 2.3, 2.4, 2.5 and the first half of 2.1 ran in parallel with stage 1, each
  in its own worktree, since they touch no file 1.1 or 1.2 moves; their commits were picked onto
  the build branch. Stages 1 and 2 share one L2+L3 pass (P-0005) and one gate run; PD-14's one PR
  is unchanged.
- **D-2 PD-9:** `no-exp` stays (18 cases, not 17): no other test fails when the claims stop
  requiring `exp`, and the no-drop-without-a-survivor rule outranks the count.
- **D-3 PD-4:** the keep-alive test's call phase stays at about 0.12 s (target 0.1 s): the wait is
  ~7 ms, the rest is the test's two grant PUTs, which belong in the call phase.
- **D-4 PD-17:** the two pass-through spies on `tenancy.tenants` in `test_relay.py` are X2, not X3
  as the list said; `test_environment.py` and `test_testkit_lazy_import.py`'s `sys.modules`
  patches are X5. The kit's restore limit is set through `ToyService(max_restore_bytes=)`, since
  `installed()` returns the app.
- **D-5 Stage-1 review (L2+L3), accepted findings, one fixer:**
  - W1: the three `paused()` tests pass with a no-op `paused()` over the non-suspending fakes; the
    held test starts `run_once()` as a task inside the block and asserts it is not done after a few
    loop turns (with a control without `paused()`), then that it publishes after.
  - S1: TC-82's docstring says "publishes nothing" follows from `kit.bus is None`.
  - S2: `DelayedPair.failing()` makes the next publish raise at once, as the wrapped pair's does.
  - S3: the PD-15 tests say in a comment why they time real waits (the scenario is about time).
  - S4: the warm-once set and its lock move to `api/services/shacl.py` as `warm_up_once(shapes,
    digest)`; `documents.py` calls it.
  - S6: `tests/unit/api/scene.py` and `tests/unit/import_contracts.py` move to `tests/`, since
    another tier imports them (PD-8's rule over its table); `collaboration_data.py` predates the
    change and stays.
  - S7: the `sys.modules` line in `test_testkit_lazy_import.py` carries its trailing `# X5`.
  - S8: `paused()` gets one sentence in `user-manual/test.adoc`; the ticks are the lead's.
  Rejected: S4's cache-key note (hashing the bytes is cheap and keeps the cache correct), S5 (the
  contract is refresh-b §3's text and forbids what the mutation selection needs). W2 is the lead's
  (`evidence/gates-stage1.md`).
- **D-6 Stage 3:**
  - `make mutation` did not start on `develop`'s head: mutmut copies only `rdf_persistence`, and
    `tests/conftest.py` loads a plugin from `rdf_persistence_generation`; mutmut runs two pytest
    sessions in one process, and the span fixture's second provider was ignored. `also_copy` gains
    the generator and the fixture adds its exporter to a provider already set; `only_mutate` and the
    test selection are unchanged (PD-13 holds).
  - Before: 1091 mutants, 84 survived, 23 with no test (`inputs/survivors-before.md`). After: 33
    (32 at 3.4, one more after D-7), each in `tests/audit/equivalent-mutants.md` (3 that no legal
    input tells apart, 30 under DEC-3).
  - DEC-3 is read as "wording": a test may assert what a message must name, where a caller or a
    docstring relies on it (`MessageLimitExceeded` names its limit and ends `by <command>`; an iri
    refusal names the offending iri, which the problem detail carries).
  - L' is killed by a legal policy (a graph template that reads as another tenant's aggregate), so it
    is not equivalent.
- **D-7 Final review (L1, L2, L3, L4+L5), accepted findings, one fixer:**
  - L1 S-1: `exp-as-a-numeric-string` comes back to `INVALID_TOKENS` (19 cases): it alone fails when
    `exp` loses `strict`, which sits in generated code that `make mutation` leaves out.
  - L2 S1 = L3 S1: the two `draw_id` patches in `test_iris_application_adversarial.py` carry `# X4`.
  - L2 S3: the application-apart test asserts that the refusal names the probe IRI, not its sentence;
    `_require_application_apart__mutmut_3` joins the DEC-3 list (`_2` stays killed: another test
    asserts the IRI that follows `templates:`).
  - L2 N2: the relay's raising-block test commits after the block, as the `rp-events` scenario says.
  - L2 N3: the stage-3 asserts get messages; the `prepare_query` test asserts the prefix resolved.
  - L2 N4: an `rp-iri-policy` delta says a graph IRI is refused when it reads as an aggregate or
    loaded graph *of that tenant*, which the code does and a stage-3 test pins.
  - L1 N-1 = L4+L5 #2 (docstring part): `warm_up_once` says its digest must be that of the bytes the
    shapes were parsed from; L4+L5 #1: `_shape_triples` says it is keyed by the digest and the bytes.
  - L4+L5 #3: `tests/changed.py` names the docs-check test path as a constant; L2 N5:
    `slow-markers.md` names `tests/unit/package/test_packaging.py`.
  - The lead's: L2 S2 (the gates and `make mutation` at the final head in `evidence/`), L2 N1 (five
    stage-3 map rows to "Policies are checked when settings are made").
  Deferred to the handover (outside the PLAN or older than it): L3 N1 (a tooling guard for the X
  marks), L3 N2 (`tests/e2e/library_app.py` used by a unit test), L4+L5 #2's `load_warm_shapes`,
  #4 (`BOOK_JSON` as a builder), #5 (one fast-poll constant), #6 (the toy vocabulary in one home).
